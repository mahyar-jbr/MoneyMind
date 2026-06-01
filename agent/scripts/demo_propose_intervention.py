"""Demo proof script for BACKLOG #17 — propose_intervention against Atlas.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_propose_intervention

Writes ONE pending intervention for u_demo_propose_17, find_one's it back
to verify the full pending-shape contract (null user_response,
null responded_at, status="pending", correct triggered_by + params),
prints the doc, then cleans up.
"""

import asyncio
from datetime import UTC, datetime

from bson import ObjectId

from agent.db.client import close_mongo, get_database
from agent.tools.propose_intervention import (
    ProposeInterventionInput,
    ProposeInterventionTrigger,
    propose_intervention,
)


USER_ID = "u_demo_propose_17"


async def main() -> None:
    db = get_database()
    coll = db.interventions

    # Clean slate.
    await coll.delete_many({"user_id": USER_ID})

    # Propose one intervention.
    print(f"\n=== PROPOSE: 1 reminder under {USER_ID} ===")
    params = ProposeInterventionInput(
        user_id=USER_ID,
        type="reminder",
        params={"day": "sunday", "what": "meal prep"},
        triggered_by=ProposeInterventionTrigger(
            tool="get_spend_anomaly",
            input={"category": "food.delivery", "window_days": 7},
        ),
        related_memory_id=None,
    )
    result = await propose_intervention(params)
    print(f"  intervention_id: {result.intervention_id}")
    print(f"  type:            {result.type}")
    print(f"  status:          {result.status}")
    print(f"  proposed_at:     {result.proposed_at.isoformat()}")

    # Read back and verify the full pending-shape contract.
    print("\n=== VERIFY: find_one ===")
    doc = await coll.find_one({"_id": ObjectId(result.intervention_id)})
    assert doc is not None, "intervention should be findable by id"

    assert doc["user_response"] is None, "user_response must be null at propose time"
    assert doc["responded_at"] is None, "responded_at must be null at propose time"
    assert doc["status"] == "pending", "status must be 'pending' at propose time"
    assert doc["type"] == "reminder"
    assert doc["params"] == {"day": "sunday", "what": "meal prep"}
    assert doc["triggered_by"] == {
        "tool": "get_spend_anomaly",
        "input": {"category": "food.delivery", "window_days": 7},
    }
    assert doc["related_memory"] is None

    now = datetime.now(UTC)
    proposed_at = doc["proposed_at"]
    # Mongo strips tz on store; the in-process result still has it.
    if proposed_at.tzinfo is None:
        proposed_at = proposed_at.replace(tzinfo=UTC)
    age_seconds = (now - proposed_at).total_seconds()
    assert age_seconds < 10, f"proposed_at should be recent (was {age_seconds:.1f}s old)"

    print(f"  user_response:   {doc['user_response']}")
    print(f"  responded_at:    {doc['responded_at']}")
    print(f"  status:          {doc['status']!r}")
    print(f"  type:            {doc['type']!r}")
    print(f"  params:          {doc['params']}")
    print(f"  triggered_by:    {doc['triggered_by']}")
    print(f"  related_memory:  {doc['related_memory']}")
    print(f"  proposed_at age: {age_seconds:.2f}s")
    print("\n  ALL ASSERTIONS PASSED")

    # Cleanup.
    print(f"\n=== CLEANUP: removing {USER_ID} intervention ===")
    deleted = await coll.delete_many({"user_id": USER_ID})
    print(f"deleted {deleted.deleted_count} intervention(s)")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
