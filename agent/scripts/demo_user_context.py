"""Demo proof script for BACKLOG #15 — update_user_context against Atlas.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_user_context

Writes one ongoing context + one bounded context for u_demo_context_15,
then runs the "active on date" predicate directly against Atlas to prove
both surface on the dates they should. Cleans up at the end.

The "active on date" predicate IS the contract the graph node will use
when injecting active context into the agent's prompt (not a tool — happens
inline in the graph). Demoing it here proves the write side ships docs in
the right shape for that reader.
"""

import asyncio
from datetime import date, datetime

from agent.db.client import close_mongo, get_database
from agent.tools.update_user_context import (
    UpdateUserContextInput,
    update_user_context,
)


USER_ID = "u_demo_context_15"


def _at_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


async def _active_on(coll, on_date: date) -> list[dict]:
    target = _at_midnight(on_date)
    cursor = coll.find(
        {
            "user_id": USER_ID,
            "active_from": {"$lte": target},
            "$or": [
                {"active_until": None},
                {"active_until": {"$gte": target}},
            ],
        }
    )
    return [doc async for doc in cursor]


async def main() -> None:
    coll = get_database().user_context

    # Clean slate.
    await coll.delete_many({"user_id": USER_ID})

    # 1. Two writes.
    print(f"\n=== WRITES: 2 contexts under {USER_ID} ===")
    ongoing = await update_user_context(
        UpdateUserContextInput(
            user_id=USER_ID,
            type="lifestyle",
            text="I'm bulking — food spend will be high all summer",
            active_from=date(2026, 6, 1),
            active_until=None,
        )
    )
    print(f"  ongoing  : id={ongoing.context_id}  created_at={ongoing.created_at.isoformat()}")
    print(f"             active_from={ongoing.active_from}  active_until={ongoing.active_until}")

    bounded = await update_user_context(
        UpdateUserContextInput(
            user_id=USER_ID,
            type="event",
            text="exam week, expect more DoorDash",
            active_from=date(2026, 2, 12),
            active_until=date(2026, 2, 19),
        )
    )
    print(f"  bounded  : id={bounded.context_id}  created_at={bounded.created_at.isoformat()}")
    print(f"             active_from={bounded.active_from}  active_until={bounded.active_until}")

    # 2. Active-on-date readbacks.
    #    Today (2026-06-01) → ongoing fires (active_from=2026-06-01, no end).
    #    Feb 15 2026         → bounded fires only (ongoing's active_from is in the future).
    print("\n=== ACTIVE ON 2026-06-01 (today) ===")
    today_active = await _active_on(coll, date(2026, 6, 1))
    print(f"  {len(today_active)} context(s) active:")
    for d in today_active:
        print(f"   - type={d['type']}  text={d['text']!r}")
    assert any(d["type"] == "lifestyle" for d in today_active), "ongoing 'bulking' must surface"
    assert not any(d["type"] == "event" for d in today_active), "exam-week is in the past"

    print("\n=== ACTIVE ON 2026-02-15 (mid-exam-week) ===")
    feb_active = await _active_on(coll, date(2026, 2, 15))
    print(f"  {len(feb_active)} context(s) active:")
    for d in feb_active:
        print(f"   - type={d['type']}  text={d['text']!r}")
    assert any(d["type"] == "event" for d in feb_active), "exam-week must surface on Feb 15"
    # Ongoing 'bulking' starts 2026-06-01 — should NOT appear on Feb 15
    assert not any(d["type"] == "lifestyle" for d in feb_active), (
        "ongoing bulking is future-dated relative to Feb 15"
    )

    # 3. Cleanup.
    print(f"\n=== CLEANUP: removing {USER_ID} contexts ===")
    deleted = await coll.delete_many({"user_id": USER_ID})
    print(f"deleted {deleted.deleted_count} contexts")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
