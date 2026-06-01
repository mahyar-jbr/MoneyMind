"""Demo proof script for BACKLOG #16 — check_goal_pace against Atlas.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_goal_pace

Seeds ONE goal doc for u_demo_goal_pace_16, walks four as_of values to
land four verdicts on the same goal (not_started → behind → past_due
→ complete), prints the full result + note each time, then cleans up.
"""

import asyncio
from datetime import date, datetime

from bson import ObjectId

from agent.db.client import close_mongo, get_database
from agent.tools.check_goal_pace import CheckGoalPaceInput, check_goal_pace


USER_ID = "u_demo_goal_pace_16"


async def _run(label: str, goal_id: str, as_of: date) -> None:
    print(f"\n--- {label} (as_of={as_of.isoformat()}) ---")
    r = await check_goal_pace(
        CheckGoalPaceInput(user_id=USER_ID, goal_id=goal_id, as_of=as_of)
    )
    print(f"  verdict:         {r.verdict}")
    print(f"  current/target:  ${r.current_amount:.0f} / ${r.target_amount:.0f}")
    print(f"  expected at now: ${r.expected_amount:.0f}")
    print(f"  delta:           {r.delta_amount:+.0f} ({r.delta_pct:+.1f}%)")
    print(f"  note:            {r.note}")


async def main() -> None:
    db = get_database()
    coll = db.goals

    # Clean slate.
    await coll.delete_many({"user_id": USER_ID})

    # Seed ONE goal.
    goal_doc = {
        "_id": ObjectId(),
        "user_id": USER_ID,
        "title": "Emergency Fund",
        "target_amount": 8000.0,
        "current_amount": 2400.0,
        "target_date": datetime(2026, 12, 31),
        "pace_check": "weekly",
        "status": "active",
        "created_at": datetime(2026, 1, 1),
    }
    await coll.insert_one(goal_doc)
    goal_id = str(goal_doc["_id"])
    print(f"\n=== SEED: 1 goal under {USER_ID} ===")
    print(f"  goal_id:        {goal_id}")
    print(f"  title:          {goal_doc['title']}")
    print(f"  target_amount:  ${goal_doc['target_amount']:.0f}")
    print(f"  current_amount: ${goal_doc['current_amount']:.0f}")
    print(f"  target_date:    {goal_doc['target_date'].date()}")
    print(f"  status:         {goal_doc['status']}")

    # Walk four verdicts.
    await _run("TURN 1: not_started", goal_id, date(2026, 1, 1))
    await _run("TURN 2: behind", goal_id, date(2026, 6, 1))
    await _run("TURN 3: past_due", goal_id, date(2027, 1, 15))

    # Mutate the goal directly (NOT via the tool — the tool is read-only)
    # to simulate "user finished saving and marked it done."
    await coll.update_one(
        {"_id": goal_doc["_id"]},
        {"$set": {"current_amount": 8000.0, "status": "complete"}},
    )
    await _run("TURN 4: complete (after direct status flip)", goal_id, date(2027, 1, 15))

    # Cleanup.
    print(f"\n=== CLEANUP: removing {USER_ID} goal ===")
    deleted = await coll.delete_many({"user_id": USER_ID})
    print(f"deleted {deleted.deleted_count} goal(s)")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
