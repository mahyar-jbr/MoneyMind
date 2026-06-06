"""Hermetic tests for agent.mcp_integration.client.

The conftest autouse fixture stubs `agent.graphs.main.get_mcp_tools`,
not the underlying `agent.mcp_integration.client.get_mcp_tools` — so
these tests hit the real client code with a mocked MultiServerMCPClient.
They verify:

  * Singleton caches (second call doesn't re-spawn).
  * Missing MONGODB_URI raises RuntimeError BEFORE any subprocess.
  * Spawn failure returns [] and logs (graceful fallback contract).
  * read-only flag is in the server config (R1 security guarantee).
  * tool_name_prefix=True is set (MCP `aggregate` → `mongo_aggregate`).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import BaseTool

from agent.mcp_integration import client as mcp_client_module
from agent.mcp_integration.client import SERVER_NAME, _server_config, get_mcp_tools


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Clear the module-level cache between cases."""
    mcp_client_module._reset_for_tests()
    yield
    mcp_client_module._reset_for_tests()


@pytest.fixture
def _mongodb_uri(monkeypatch):
    """Provide a fake MONGODB_URI so _server_config doesn't raise."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://fake-test-uri/moneymind")


def _fake_tool(name: str) -> BaseTool:
    """Build a minimal BaseTool the client could plausibly return."""
    from langchain_core.tools import StructuredTool

    async def _noop() -> str:
        return "ok"

    return StructuredTool.from_function(
        coroutine=_noop,
        name=name,
        description=f"fake mcp tool {name}",
    )


# ─── happy path: MCP responds, tools come back ───────────────────────────


async def test_get_mcp_tools_returns_tools_from_client(_mongodb_uri):
    fake_tools = [_fake_tool("mongo_aggregate"), _fake_tool("mongo_collection-schema")]

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=fake_tools)

    with patch(
        "langchain_mcp_adapters.client.MultiServerMCPClient",
        return_value=mock_client,
    ) as _ctor:
        tools = await get_mcp_tools()

    assert tools == fake_tools
    # tool_name_prefix=True is the R1 contract for avoiding name collisions
    # with native tools.
    _, kwargs = _ctor.call_args
    assert kwargs.get("tool_name_prefix") is True


# ─── singleton: second call doesn't re-spawn ─────────────────────────────


async def test_singleton_caches_between_calls(_mongodb_uri):
    fake_tools = [_fake_tool("mongo_find")]
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=fake_tools)

    with patch(
        "langchain_mcp_adapters.client.MultiServerMCPClient",
        return_value=mock_client,
    ) as ctor:
        first = await get_mcp_tools()
        second = await get_mcp_tools()

    assert first is second  # same list object — cached
    assert ctor.call_count == 1
    assert mock_client.get_tools.call_count == 1


# ─── safety: MONGODB_URI missing → RuntimeError BEFORE subprocess ────────


async def test_missing_mongodb_uri_raises_before_spawn(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)

    # If we ever reached the constructor, this would be the marker.
    sentinel = MagicMock()
    with patch(
        "langchain_mcp_adapters.client.MultiServerMCPClient",
        sentinel,
    ):
        tools = await get_mcp_tools()

    # Resilience: missing URI is a config error, but the contract is "agent
    # still boots with native tools", so we get [], not an exception.
    assert tools == []
    sentinel.assert_not_called()
    assert isinstance(mcp_client_module._init_error, RuntimeError)
    assert "MONGODB_URI" in str(mcp_client_module._init_error)


# ─── resilience: subprocess fails → [] returned, agent still boots ────────


async def test_spawn_failure_returns_empty(_mongodb_uri, caplog):
    def _boom(*args, **kwargs):
        raise OSError("npx not found")

    with patch(
        "langchain_mcp_adapters.client.MultiServerMCPClient",
        _boom,
    ):
        tools = await get_mcp_tools()

    assert tools == []
    assert mcp_client_module._init_error is not None
    assert isinstance(mcp_client_module._init_error, OSError)


# ─── R1 security: --read-only flag is in the server config ───────────────


def test_server_config_includes_read_only_flag(_mongodb_uri):
    cfg = _server_config()
    args = cfg[SERVER_NAME]["args"]
    assert "--read-only" in args, (
        "R1 security contract: MongoDB MCP subprocess must spawn with "
        "--read-only. A judge typing 'drop the transactions collection' "
        "must be structurally unable to do it."
    )


def test_server_config_passes_connection_string(_mongodb_uri):
    cfg = _server_config()
    args = cfg[SERVER_NAME]["args"]
    assert "--connectionString" in args
    idx = args.index("--connectionString")
    assert args[idx + 1] == "mongodb://fake-test-uri/moneymind"


def test_server_config_uses_npx(_mongodb_uri):
    cfg = _server_config()
    assert cfg[SERVER_NAME]["command"] == "npx"
    # Use the published @latest tag so we don't pin to a broken version.
    assert "mongodb-mcp-server@latest" in cfg[SERVER_NAME]["args"]


def test_server_config_transport_defaults_to_stdio(_mongodb_uri, monkeypatch):
    monkeypatch.delenv("MONGODB_MCP_TRANSPORT", raising=False)
    cfg = _server_config()
    assert cfg[SERVER_NAME]["transport"] == "stdio"


def test_server_config_transport_overridable(_mongodb_uri, monkeypatch):
    monkeypatch.setenv("MONGODB_MCP_TRANSPORT", "sse")
    cfg = _server_config()
    assert cfg[SERVER_NAME]["transport"] == "sse"


# ─── server name is the prefix string MCP will use ───────────────────────


def test_server_name_is_mongo():
    # tool_name_prefix=True + server_name="mongo" gives mongo_aggregate etc.
    assert SERVER_NAME == "mongo"
