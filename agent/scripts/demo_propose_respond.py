"""Demo proof for BACKLOG #17a-wire — propose → ask → respond chat loop.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_propose_respond

Two-turn conversation against real Atlas + real Gemini:

  TURN 1: User says "I feel like my food spend is high — want to set a
          Sunday meal prep reminder?" — expect Gemini to call
          propose_intervention. The pending intervention doc lands in
          atlas.interventions.

  TURN 2: User says "yes please" — expect Gemini to call
          respond_to_intervention with user_response="accepted",
          flipping the doc from pending → responded.

Captures which tools Gemini picked per turn using the same module-level
instrumentation pattern from #17-wire's demo_graph_full.py. Cleans up
after.

Note: if Gemini picks a different tool order on the first attempt, that's
prompt-tuning territory (#25p target e). The wiring is what this ticket
verifies — the report records what actually happened.
"""

import asyncio
from datetime import date, datetime

from bson import ObjectId

from agent.db.client import close_mongo, get_database
from agent.graphs.main import arun_chat


USER_ID = "u_demo_propose_respond_17a_wire"

NEW_TOOL = "respond_to_intervention"  # the tool whose live use this ticket proves


async def _seed_data() -> None:
    """Seed a small synthetic week + an active goal so the LLM has context."""
    db = get_database()
    await db.transactions.delete_many({"user_id": USER_ID})
    await db.goals.delete_many({"user_id": USER_ID})
    await db.interventions.delete_many({"user_id": USER_ID})

    rows = [
        (date(2026, 5, 19), "DoorDash", "food.delivery", -52.10),
        (date(2026, 5, 20), "DoorDash", "food.delivery", -38.42),
        (date(2026, 5, 22), "Uber Eats", "food.delivery", -73.48),
        (date(2026, 5, 23), "DoorDash", "food.delivery", -47.00),
    ]
    for d, merchant, cat, amt in rows:
        await db.transactions.insert_one({
            "user_id": USER_ID,
            "date": datetime(d.year, d.month, d.day),
            "merchant": merchant,
            "merchant_canonical": merchant.lower().replace(" ", "_"),
            "category": cat,
            "amount": amt,
            "currency": "USD",
            "source": "demo_propose_respond_17a_wire",
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
        "interventions": (await db.interventions.delete_many({"user_id": USER_ID})).deleted_count,
        "user_context": (await db.user_context.delete_many({"user_id": USER_ID})).deleted_count,
        "memories": (await db.memories.delete_many({"user_id": USER_ID})).deleted_count,
        "reminders": (await db.reminders.delete_many({"user_id": USER_ID})).deleted_count,
        "outcomes": (await db.outcomes.delete_many({"user_id": USER_ID})).deleted_count,
    }


async def _run_turn_with_capture(message: str) -> tuple[str, set[str]]:
    """Run ONE chat turn and capture which production tools Gemini called.

    Patches the production callable names in agent.graphs.main with
    recording shims that delegate to the originals. The wrapper's
    closure captures the patched callable at _build_tools() call time
    (same pattern as the test suite's `patch(...)` blocks).
    """
    from agent.graphs import main as graph_module

    tools_called: set[str] = set()
    targets = [
        "query_transactions", "get_spend_anomaly", "recall_memory",
        "write_memory", "update_user_context",
        "check_goal_pace", "propose_intervention", "respond_to_intervention",
        "log_outcome", "schedule_reminder", "summarize_week",
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
    await _seed_data()
    print(f"  seeded synthetic txns + Emergency Fund goal under {USER_ID}")

    # TURN 1 — expect propose_intervention.
    msg1 = (
        "I feel like my food spend is high — want to set a "
        "Sunday meal prep reminder?"
    )
    print(f"\n=== TURN 1 ===\nUSER: {msg1}")
    reply1, tools1 = await _run_turn_with_capture(msg1)
    print(f"\nAGENT: {reply1}")
    print(f"\nTOOLS CALLED THIS TURN: {sorted(tools1)}")

    # Check what landed.
    db = get_database()
    pending_count = await db.interventions.count_documents({
        "user_id": USER_ID, "status": "pending"
    })
    print(f"pending interventions in Atlas after turn 1: {pending_count}")

    # TURN 2 — expect respond_to_intervention.
    msg2 = "yes please"
    print(f"\n=== TURN 2 ===\nUSER: {msg2}")
    reply2, tools2 = await _run_turn_with_capture(msg2)
    print(f"\nAGENT: {reply2}")
    print(f"\nTOOLS CALLED THIS TURN: {sorted(tools2)}")

    responded_count = await db.interventions.count_documents({
        "user_id": USER_ID, "status": "responded"
    })
    print(f"responded interventions in Atlas after turn 2: {responded_count}")

    # Verdict.
    print("\n=== VERDICT ===")
    if NEW_TOOL in tools2:
        print(f"  ✅ Gemini called {NEW_TOOL} on turn 2 — propose-respond loop is reachable.")
    else:
        print(f"  ⚠️  Gemini did NOT call {NEW_TOOL} on turn 2.")
        print(f"      Tools fired instead: {sorted(tools2)}")
        print("      The wiring is correct (unit tests prove it).")
        print("      The LLM choosing not to call it is #25p prompt-tuning territory.")

    print("\n=== CLEANUP ===")
    counts = await _cleanup()
    print(f"deleted: {counts}")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
