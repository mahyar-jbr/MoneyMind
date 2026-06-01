"""Demo proof for BACKLOG #19 — schedule_reminder against Atlas.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_schedule_reminder

Writes two reminders (one user-sourced, one agent-sourced) and runs the
canonical 'pending reminders due by T' predicate that the #21 cron will
use. Asserts both reminders surface with T = now+10d, only the 3-day one
with T = now+5d. Cleans up.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from agent.db.client import close_mongo, get_database
from agent.tools.schedule_reminder import (
    ScheduleReminderInput,
    schedule_reminder,
)


USER_ID = "u_demo_schedule_19"


async def _pending_due_by(coll, threshold: datetime) -> list[dict]:
    """The canonical 'pending reminders due by T' predicate (#21 will use it)."""
    cursor = coll.find(
        {
            "user_id": USER_ID,
            "status": "pending",
            "fires_at": {"$lte": threshold},
        }
    ).sort("fires_at", 1)
    return [doc async for doc in cursor]


async def main() -> None:
    db = get_database()
    coll = db.reminders

    # Clean slate.
    await coll.delete_many({"user_id": USER_ID})

    now = datetime.now(UTC)

    # 1. User-sourced, fires in 7 days.
    user_reminder = await schedule_reminder(
        ScheduleReminderInput(
            user_id=USER_ID,
            fires_at=now + timedelta(days=7),
            text="cancel the gym trial",
            source="user",
        )
    )
    # 2. Agent-sourced, fires in 3 days.
    agent_reminder = await schedule_reminder(
        ScheduleReminderInput(
            user_id=USER_ID,
            fires_at=now + timedelta(days=3),
            text="check in on the bulking goal",
            source="agent",
        )
    )

    print(f"\n=== WROTE: 2 reminders under {USER_ID} ===")
    print(f"  user-sourced  : id={user_reminder.reminder_id}")
    print(f"                  fires_at={user_reminder.fires_at.isoformat()}")
    print(f"  agent-sourced : id={agent_reminder.reminder_id}")
    print(f"                  fires_at={agent_reminder.fires_at.isoformat()}")

    # 3. Cron-style predicate with T = now+10d → BOTH, sorted by fires_at ASC.
    print("\n=== QUERY: pending reminders due by now+10d ===")
    docs = await _pending_due_by(coll, now + timedelta(days=10))
    print(f"  found {len(docs)} reminder(s)")
    for d in docs:
        print(f"   - fires_at={d['fires_at'].isoformat()}  source={d['source']!r}  text={d['text']!r}")
    assert len(docs) == 2, f"expected 2 reminders, got {len(docs)}"
    # 3-day (agent) should sort BEFORE 7-day (user)
    assert str(docs[0]["_id"]) == agent_reminder.reminder_id, "agent reminder must come first (sooner fires_at)"
    assert str(docs[1]["_id"]) == user_reminder.reminder_id

    # 4. Predicate with T = now+5d → only the 3-day one.
    print("\n=== QUERY: pending reminders due by now+5d ===")
    docs = await _pending_due_by(coll, now + timedelta(days=5))
    print(f"  found {len(docs)} reminder(s)")
    for d in docs:
        print(f"   - fires_at={d['fires_at'].isoformat()}  source={d['source']!r}  text={d['text']!r}")
    assert len(docs) == 1, f"expected 1 reminder, got {len(docs)}"
    assert str(docs[0]["_id"]) == agent_reminder.reminder_id

    print("\n  ALL PREDICATE ASSERTIONS PASSED")

    # Cleanup.
    print(f"\n=== CLEANUP: removing {USER_ID} reminders ===")
    deleted = await coll.delete_many({"user_id": USER_ID})
    print(f"deleted {deleted.deleted_count} reminder(s)")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
