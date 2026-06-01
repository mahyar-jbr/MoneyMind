"""Demo proof for BACKLOG #11a — agent graph wired with all 5 Sprint 2 tools.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_graph

3-turn end-to-end demo against real Atlas + real Gemini:

  Turn 1: "How am I doing on food this week?" — graph fires tools,
          replies with real numbers.
  Turn 2: "I'm bulking this month, expect more food spend." — graph
          calls update_user_context; verify a doc lands in Atlas under
          u_demo_graph_11a with type=lifestyle.
  Turn 3: "How am I doing on food this week?" — same question; the
          system message now includes the just-written active context.
          The reply should acknowledge the bulking context.

Cleanup at the end removes the seeded context + any memories the agent
wrote during the run.

Note: synthetic.csv must already be ingested under u_482 (the canonical
demo user). This script reuses that ingest under the demo user_id
u_demo_graph_11a by copying the transactions in.
"""

import asyncio
from datetime import UTC, datetime

from agent.db.client import close_mongo, get_database
from agent.graphs.main import arun_chat


USER_ID = "u_demo_graph_11a"


async def _seed_transactions_from_u_482() -> int:
    """Copy u_482's transactions to USER_ID so the demo user has data."""
    db = get_database()
    src = db.transactions
    cnt = await src.count_documents({"user_id": "u_482"})
    if cnt == 0:
        raise RuntimeError("u_482 has no transactions — run ingest first")
    # Re-seed idempotently
    await src.delete_many({"user_id": USER_ID})
    copied = 0
    async for doc in src.find({"user_id": "u_482"}):
        new_doc = {k: v for k, v in doc.items() if k != "_id"}
        new_doc["user_id"] = USER_ID
        await src.insert_one(new_doc)
        copied += 1
    return copied


async def _cleanup() -> dict:
    db = get_database()
    res = {}
    res["transactions"] = (await db.transactions.delete_many({"user_id": USER_ID})).deleted_count
    res["user_context"] = (await db.user_context.delete_many({"user_id": USER_ID})).deleted_count
    res["memories"] = (await db.memories.delete_many({"user_id": USER_ID})).deleted_count
    return res


async def _turn(label: str, message: str) -> str:
    print(f"\n=== {label}: {message!r} ===")
    reply = await arun_chat(USER_ID, message)
    print(f"REPLY: {reply}")
    return reply


async def main() -> None:
    print("=== SEED: copying u_482 transactions to demo user ===")
    n = await _seed_transactions_from_u_482()
    print(f"copied {n} transactions to {USER_ID}")

    # Turn 1 — graph should call tools and cite real numbers
    await _turn("TURN 1 (pre-context)", "How am I doing on food this week?")

    # Turn 2 — graph should write a user_context doc
    await _turn("TURN 2 (state context)", "I'm bulking this month, expect more food spend.")

    # Verify the context landed
    db = get_database()
    ctx_count = await db.user_context.count_documents({"user_id": USER_ID, "type": "lifestyle"})
    print(f"\n>>> user_context lifestyle docs written by agent: {ctx_count}")
    sample = await db.user_context.find_one({"user_id": USER_ID, "type": "lifestyle"})
    if sample:
        print(f">>> agent stored: {sample.get('text')!r}")
        print(f">>> active_from={sample.get('active_from')}  active_until={sample.get('active_until')}")

    # Turn 3 — same as Turn 1, but now the system message should include
    # the active context block
    await _turn("TURN 3 (post-context)", "How am I doing on food this week?")

    # Cleanup
    print("\n=== CLEANUP ===")
    counts = await _cleanup()
    print(f"deleted: {counts}")

    await close_mongo()
    print(f"\nDone at {datetime.now(UTC).isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
