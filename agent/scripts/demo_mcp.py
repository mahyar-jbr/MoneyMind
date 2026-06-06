"""Live integration script for R1 — verify the real MongoDB MCP server end-to-end.

Spawns the real Node subprocess (`npx mongodb-mcp-server@latest`), connects
via MCP stdio, lists the tools the server exposes, and calls one of them
against the live Atlas cluster to prove the round-trip works.

Used to manually verify the MCP integration in production after a Railway
deploy. Not part of pytest.

Run from agent/ (so .env at the project root is reachable):

    PYTHONPATH=.. uv run python -m agent.scripts.demo_mcp

Requires:
  - Node 20.19+ on PATH (apt installs this in the production container).
  - MONGODB_URI set in the environment (.env loaded automatically by serve).
  - Network access to the npm registry (first run downloads
    mongodb-mcp-server; subsequent runs use the npx cache).
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from agent.mcp_integration.client import SERVER_NAME, get_mcp_tools


# Load .env from the repo root so MONGODB_URI is available.
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


async def main() -> int:
    if not os.environ.get("MONGODB_URI"):
        print("MONGODB_URI is not set — abort", flush=True)
        return 2

    print("Spawning npx mongodb-mcp-server@latest (read-only)...", flush=True)
    tools = await get_mcp_tools()

    if not tools:
        print(
            "\n!! MCP server did not yield any tools. Common causes:\n"
            "   - Node 20+ not on PATH (apt-get install nodejs)\n"
            "   - npm registry unreachable from this machine\n"
            "   - --read-only or --connectionString rejected by the server\n"
            "   Check the agent process logs for the WARNING line from\n"
            "   agent.mcp_integration.client.\n",
            flush=True,
        )
        return 1

    print(f"\nLoaded {len(tools)} MCP tools (prefix: {SERVER_NAME}_):", flush=True)
    for t in sorted(tools, key=lambda x: x.name):
        print(f"  - {t.name}", flush=True)

    # Try to call one read-only tool we expect to be there. The exact tool
    # surface depends on the mongodb-mcp-server version; collection-schema /
    # list-databases / list-collections are all common choices. Fall back
    # through the list until one works.
    candidates = [
        ("mongo_list-databases", {}),
        ("mongo_list-collections", {"database": os.environ.get("MONGODB_DB", "moneymind")}),
        ("mongo_collection-schema", {
            "database": os.environ.get("MONGODB_DB", "moneymind"),
            "collection": "transactions",
        }),
    ]

    by_name = {t.name: t for t in tools}
    for tool_name, args in candidates:
        if tool_name not in by_name:
            continue
        print(f"\nCalling {tool_name} with {args}...", flush=True)
        try:
            result = await by_name[tool_name].ainvoke(args)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {type(exc).__name__}: {exc}", flush=True)
            continue
        # Result is usually a string (JSON or plain text). Pretty-print if JSON.
        printable = result
        if isinstance(result, str):
            try:
                printable = json.dumps(json.loads(result), indent=2)
            except (ValueError, TypeError):
                pass
        print(f"\n--- Result from {tool_name} ---\n{printable}", flush=True)
        return 0

    print("\nNo candidate tool succeeded; check server version / config.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
