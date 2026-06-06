"""MongoDB MCP server integration for the agent (R1, hackathon-track eligibility).

The official MongoDB MCP Server runs as a Node subprocess
(`npx mongodb-mcp-server@latest`) and speaks the Model Context Protocol over
stdio. `langchain-mcp-adapters` wraps each MCP-provided tool as a LangChain
`StructuredTool` that drops straight into `create_react_agent(tools=[...])`.

Read-only is non-negotiable: the subprocess is started with `--readOnly`
(camelCase — the kebab-case form fails at startup), which prevents every
Atlas write operation at the server level (a judge
typing 'drop transactions' cannot do it).

Resilience contract: if the MCP subprocess fails to spawn (Node missing,
npx fails, npm registry unreachable, etc.), `get_mcp_tools()` MUST return
an empty list rather than raise. The 11 native tools then carry the
agent. The MCP failure is logged loudly so it shows up in Railway logs.
"""

import logging
import os
from typing import Any

from langchain_core.tools import BaseTool


logger = logging.getLogger(__name__)

# Server registration name. MCP tools get prefixed with this string when
# `tool_name_prefix=True` is passed to MultiServerMCPClient — so MCP's
# `aggregate` becomes `mongo_aggregate`, `collection-schema` becomes
# `mongo_collection-schema`, etc. The prefix prevents collisions with the
# 11 native tools.
SERVER_NAME = "mongo"

# Module-level cache. First successful call to `get_mcp_tools` populates
# both `_tools` and `_client`; subsequent calls return the cached list
# without re-spawning the Node subprocess.
_client: Any = None  # MultiServerMCPClient | None — kept Any to avoid
                     # eager import of langchain_mcp_adapters at module load.
_tools: list[BaseTool] | None = None
_init_error: Exception | None = None  # last spawn failure, surfaced for tests


def _server_config() -> dict[str, Any]:
    """Build the stdio subprocess config the MCP client will spawn.

    Hardcodes the read-only flag — see module docstring.
    """
    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set; cannot start MongoDB MCP server")
    return {
        SERVER_NAME: {
            "command": "npx",
            "args": [
                "-y",
                "mongodb-mcp-server@latest",
                "--readOnly",
                "--connectionString",
                mongodb_uri,
            ],
            "transport": os.environ.get("MONGODB_MCP_TRANSPORT", "stdio"),
        }
    }


async def get_mcp_tools() -> list[BaseTool]:
    """Return the MCP-exposed tools, lazy-spawned on first call.

    Singleton: the subprocess + client are spawned exactly once per process.
    Returns `[]` (NOT raises) on any spawn failure so the agent still boots
    with the 11 native tools. Failure is logged at WARNING.

    Env override: `MONGODB_MCP_DISABLE=1` skips the spawn entirely and
    returns []. Use this when you need to rule out MCP as a hang source.
    """
    global _client, _tools, _init_error
    if _tools is not None:
        return _tools

    if os.environ.get("MONGODB_MCP_DISABLE"):
        _tools = []
        logger.info("MongoDB MCP disabled by MONGODB_MCP_DISABLE; using native tools only.")
        return _tools

    try:
        # Lazy import — keeps process-boot fast when MCP isn't actually used.
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient(
            _server_config(),
            tool_name_prefix=True,
        )
        tools = await client.get_tools(server_name=SERVER_NAME)
    except Exception as exc:  # noqa: BLE001
        # Resilience contract: never crash the agent on MCP failure.
        _init_error = exc
        _tools = []
        logger.warning(
            "MongoDB MCP server unavailable (%s: %s); agent will run with "
            "native tools only.",
            type(exc).__name__,
            exc,
        )
        return _tools

    _client = client
    _tools = list(tools)
    logger.info(
        "MongoDB MCP server up; loaded %d tools: %s",
        len(_tools),
        sorted(t.name for t in _tools),
    )
    return _tools


def _reset_for_tests() -> None:
    """Test-only helper to clear the singleton between cases."""
    global _client, _tools, _init_error
    _client = None
    _tools = None
    _init_error = None
