import httpx
import pytest

from agent.embeddings import voyage


@pytest.fixture(autouse=True)
def voyage_key(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "fake-key-for-tests")
    monkeypatch.setattr(voyage, "RETRY_BACKOFF_S", 0)  # don't actually sleep in tests


def _ok_response(dim=1024):
    return httpx.Response(200, json={"data": [{"embedding": [0.0] * dim}]})


def _make_client(responses):
    """Build a httpx.AsyncClient whose transport replays the given responses in order."""
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        if not queue:
            raise AssertionError("more requests than expected")
        return queue.pop(0)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_embed_query_returns_1024_floats():
    async with _make_client([_ok_response()]) as client:
        result = await voyage.embed_query("hello", client=client)
    assert len(result) == 1024
    assert all(isinstance(x, float) for x in result)


async def test_embed_query_empty_text_raises():
    with pytest.raises(ValueError):
        await voyage.embed_query("")


async def test_embed_query_too_long_raises():
    with pytest.raises(ValueError):
        await voyage.embed_query("x" * 501)


async def test_embed_query_wrong_dim_raises():
    async with _make_client([_ok_response(dim=512)]) as client:
        with pytest.raises(ValueError, match="dim=512"):
            await voyage.embed_query("hello", client=client)


async def test_embed_query_retries_once_on_429():
    responses = [httpx.Response(429, text="rate limited"), _ok_response()]
    async with _make_client(responses) as client:
        result = await voyage.embed_query("hello", client=client)
    assert len(result) == 1024


async def test_embed_query_retries_once_on_5xx():
    responses = [httpx.Response(503, text="upstream"), _ok_response()]
    async with _make_client(responses) as client:
        result = await voyage.embed_query("hello", client=client)
    assert len(result) == 1024


async def test_embed_query_raises_after_second_failure():
    responses = [httpx.Response(429), httpx.Response(429)]
    async with _make_client(responses) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await voyage.embed_query("hello", client=client)


async def test_embed_query_does_not_retry_on_4xx_other_than_429():
    responses = [httpx.Response(401, text="unauth")]
    async with _make_client(responses) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await voyage.embed_query("hello", client=client)


async def test_no_voyage_key_raises(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="VOYAGE_API_KEY"):
        await voyage.embed_query("hello")


async def test_embed_document_uses_document_input_type():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        seen["payload"] = _json.loads(request.content)
        return _ok_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await voyage.embed_document("doc text", client=client)
    assert seen["payload"]["input_type"] == "document"


async def test_embed_query_sends_query_input_type():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        seen["payload"] = _json.loads(request.content)
        return _ok_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await voyage.embed_query("q text", client=client)
    assert seen["payload"]["input_type"] == "query"
    assert seen["payload"]["model"] == "voyage-3"
