"""Voyage AI embeddings — thin async wrapper.

Calls Voyage's HTTP API directly (no SDK) to keep the dep surface tiny.
Uses `voyage-3` (1024-dim) to match the Atlas vector index. Marks query
intent via `input_type="query"`; document writers should use "document".
"""

import asyncio
import os
from typing import Literal

import httpx


VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3"
EXPECTED_DIM = 1024
MAX_TEXT_LEN = 500
RETRY_BACKOFF_S = 1.0  # tests monkeypatch this to 0 to keep the suite fast


async def _embed(
    text: str,
    *,
    input_type: Literal["query", "document"],
    client: httpx.AsyncClient | None = None,
) -> list[float]:
    if not text:
        raise ValueError("text must be non-empty")
    if len(text) > MAX_TEXT_LEN:
        raise ValueError(f"text exceeds {MAX_TEXT_LEN} chars")

    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise RuntimeError("VOYAGE_API_KEY is not set")

    payload = {"model": VOYAGE_MODEL, "input": text, "input_type": input_type}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)

    try:
        # Single retry on 429/5xx with 1s backoff.
        for attempt in (1, 2):
            response = await client.post(VOYAGE_URL, headers=headers, json=payload)
            if response.status_code == 200:
                break
            if attempt == 1 and (response.status_code == 429 or response.status_code >= 500):
                await asyncio.sleep(RETRY_BACKOFF_S)
                continue
            response.raise_for_status()
        response.raise_for_status()
        data = response.json()
        embedding = data["data"][0]["embedding"]
    finally:
        if owns_client:
            await client.aclose()

    if len(embedding) != EXPECTED_DIM:
        raise ValueError(
            f"Voyage returned dim={len(embedding)}; expected {EXPECTED_DIM}"
        )
    return embedding


async def embed_query(text: str, *, client: httpx.AsyncClient | None = None) -> list[float]:
    """Embed a SEARCH QUERY (input_type=query) into a 1024-dim vector."""
    return await _embed(text, input_type="query", client=client)


async def embed_document(text: str, *, client: httpx.AsyncClient | None = None) -> list[float]:
    """Embed a DOCUMENT (input_type=document) into a 1024-dim vector.

    Used by the memory-write path (#14) and by the #13 demo script since
    Atlas auto-embed is NOT configured on this cluster — writers must
    populate the `embedding` field themselves.
    """
    return await _embed(text, input_type="document", client=client)
