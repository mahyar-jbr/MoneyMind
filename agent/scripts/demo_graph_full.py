"""Demo proof for BACKLOG #17-wire — newly wired tools reachable in a chat turn.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_graph_full

Reuses the #20 seed (synthetic transactions + Emergency Fund goal under
a demo user), runs ONE chat turn against the real graph + real Gemini,
and captures which tool calls Gemini chose to make. Success = the LLM
picks at least one of the newly-wired tools (summarize_week,
check_goal_pace, propose_intervention, log_outcome, schedule_reminder).

Cleans up after.
"""

import asyncio
from datetime import date, datetime

from bson import ObjectId

from agent.db.client import close_mongo, get_database
from agent.graphs.main import arun_chat


USER_ID = "u_demo_wire_17"

NEW_TOOLS = {
    "check_goal_pace",
    "propose_intervention",
    "log_outcome",
    "schedule_reminder",
    "summarize_week",
}


async def _seed() -> None:
    db = get_database()
    # Wipe prior runs.
    await db.transactions.delete_many({"user_id": USER_ID})
    await db.goals.delete_many({"user_id": USER_ID})

    rows = [
        (date(2026, 5, 19), "DoorDash", "food.delivery", -52.10),
        (date(2026, 5, 20), "DoorDash", "food.delivery", -38.42),
        (date(2026, 5, 22), "Uber Eats", "food.delivery", -73.48),
        (date(2026, 5, 23), "DoorDash", "food.delivery", -47.00),
        (date(2026, 5, 18), "Presto", "transport.transit", -12.00),
        (date(2026, 5, 21), "Presto", "transport.transit", -12.00),
        (date(2026, 5, 21), "Amazon", "shopping.amazon", -73.00),
        (date(2026, 5, 22), "Balzac's", "food.coffee", -32.00),
        (date(2026, 5, 20), "Direct Deposit", "income.salary", 2400.00),
    ]
    for d, merchant, cat, amt in rows:
        await db.transactions.insert_one({
            "user_id": USER_ID,
            "date": datetime(d.year, d.month, d.day),
            "merchant": merchant,
            "merchant_canonical": merchant.lower().replace(" ", "_").replace("'", ""),
            "category": cat,
            "amount": amt,
            "currency": "USD",
            "source": "demo_wire_17",
        })

    await db.goals.insert_one({
        "_id": ObjectId(),
        "user_id": USER_ID,
        "title": "Emergency Fund",
        "target_amount": 8000.0,
        "current_amount": 2400.0,
        "target_date": datetime(2026, 12, 31),
        "pace_check": "weekly",
        "status": "active",
        "created_at": datetime(2026, 1, 1),
    })


async def _cleanup() -> dict:
    db = get_database()
    return {
        "transactions": (await db.transactions.delete_many({"user_id": USER_ID})).deleted_count,
        "goals": (await db.goals.delete_many({"user_id": USER_ID})).deleted_count,
        "user_context": (await db.user_context.delete_many({"user_id": USER_ID})).deleted_count,
        "memories": (await db.memories.delete_many({"user_id": USER_ID})).deleted_count,
        "interventions": (await db.interventions.delete_many({"user_id": USER_ID})).deleted_count,
        "outcomes": (await db.outcomes.delete_many({"user_id": USER_ID})).deleted_count,
        "reminders": (await db.reminders.delete_many({"user_id": USER_ID})).deleted_count,
    }


async def _run_with_tool_capture(message: str) -> tuple[str, set[str]]:
    """Run a single chat turn and capture which production tools fired.

    Wraps the underlying tool callables in `agent.graphs.main`'s namespace
    (the same names the wrapper imports + the unit tests patch). This
    avoids touching StructuredTool's signature, which would break the
    InjectedState injection.
    """
    from agent.graphs import main as graph_module

    tools_called: set[str] = set()

    # The 10 tool callable names live in graph_module's namespace because
    # they're imported at module top. We swap each one for a recording
    # passthrough — the wrapper still calls them through the same name.
    targets = [
        "query_transactions", "get_spend_anomaly", "recall_memory",
        "write_memory", "update_user_context",
        "check_goal_pace", "propose_intervention", "log_outcome",
        "schedule_reminder", "summarize_week",
    ]
    originals = {name: getattr(graph_module, name) for name in targets}

    def _make_recording(name, orig):
        async def _recording(*args, **kwargs):
            tools_called.add(name)
            return await orig(*args, **kwargs)

        return _recording

    for name, orig in originals.items():
        setattr(graph_module, name, _make_recording(name, orig))

    try:
        reply = await arun_chat(USER_ID, message)
    finally:
        for name, orig in originals.items():
            setattr(graph_module, name, orig)

    return reply, tools_called


async def main() -> None:
    print("=== SEED ===")
    await _seed()
    print(f"  seeded synthetic txns + Emergency Fund goal under {USER_ID}")

    print("\n=== CHAT TURN ===")
    message = "How am I doing on food spending this week?"
    print(f"USER: {message}")

    reply, tools_called = await _run_with_tool_capture(message)
    print(f"\nAGENT: {reply}")

    print(f"\nTOOLS CALLED THIS TURN: {sorted(tools_called)}")
    newly_wired_used = tools_called & NEW_TOOLS
    print(f"NEWLY-WIRED TOOLS USED:  {sorted(newly_wired_used)}")

    print("\n=== CLEANUP ===")
    counts = await _cleanup()
    print(f"deleted: {counts}")

    await close_mongo()

    # Final verdict.
    if not tools_called:
        print("\n⚠️  Gemini didn't call any tool this turn — prompt-tuning territory (#25p).")
        print("    The wiring is still correct (tests prove it); the LLM just chose to reply directly.")
    elif newly_wired_used:
        print("\n✅ A newly-wired tool fired in a real chat turn.")
    else:
        print("\n⚠️  Gemini only used originally-wired tools this turn.")
        print(f"    (Used: {sorted(tools_called)})")
        print("    The wiring is correct; refining the prompt to nudge toward summarize_week")
        print("    on 'how am I doing this week' is #25p territory.")


if __name__ == "__main__":
    asyncio.run(main())
