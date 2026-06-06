"""Shared pytest fixtures for the agent test suite.

Established 2026-06-05 (R1 MCP integration). Before R1 the suite had no
shared fixtures — each tool test fixture-injected its own collection.
This file exists for cross-cutting setup that every test should get
without remembering to import it.
"""

import pytest

from agent.mcp_integration import client as mcp_client_module


@pytest.fixture(autouse=True)
def _stub_mcp_tools(monkeypatch):
    """Force `get_mcp_tools()` to return `[]` in every test.

    The MCP integration spawns a Node subprocess (`npx mongodb-mcp-server`)
    on first call. We don't want hermetic tests to (a) actually shell out,
    (b) hit Atlas through the real MCP server, or (c) introduce non-
    determinism based on whether npx happens to be on PATH. Tests that
    explicitly target the MCP path (test_mcp_client.py) monkeypatch this
    fixture out individually.

    The fixture also clears the module-level singleton between tests, so
    one test's mock can't leak state into another's.
    """

    async def _empty_mcp_tools():
        return []

    monkeypatch.setattr(
        "agent.graphs.main.get_mcp_tools",
        _empty_mcp_tools,
        raising=True,
    )
    mcp_client_module._reset_for_tests()
    yield
    mcp_client_module._reset_for_tests()
