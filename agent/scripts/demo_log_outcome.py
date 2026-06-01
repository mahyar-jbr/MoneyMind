"""Demo proof script for BACKLOG #18 — log_outcome against Atlas.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_log_outcome

Writes ONE outcome for a synthetic intervention_id under
u_demo_log_outcome_18, reads it back via find_one, asserts the full
shape contract (esp. server-computed delta_pct + intervention_id as
ObjectId + measured_at recent UTC), then cleans up.
"""

import asyncio
from datetime import UTC, datetime

from bson import ObjectId

from agent.db.client import close_mongo, get_database
from agent.tools.log_outcome import LogOutcomeInput, log_outcome


USER_ID = "u_demo_log_outcome_18"


async def main() -> None:
    db = get_database()
    coll = db.outcomes

    # Clean slate.
    await coll.delete_many({"user_id": USER_ID})

    # Synthetic intervention_id — the tool doesn't verify existence by design.
    intervention_id = str(ObjectId())

    print(f"\n=== LOG: 1 outcome under {USER_ID} ===")
    print(f"  synthetic intervention_id: {intervention_id}")
    result = await log_outcome(
        LogOutcomeInput(
            user_id=USER_ID,
            intervention_id=intervention_id,
            window_days=14,
            metric="weekly_food_spend",
            before=180.0,
            after=118.5,
            agent_judgment="successful",
        )
    )
    print(f"  outcome_id:    {result.outcome_id}")
    print(f"  metric:        {result.metric}")
    print(f"  before/after:  ${result.before} → ${result.after}")
    print(f"  delta_pct:     {result.delta_pct}% (server-computed)")
    print(f"  judgment:      {result.agent_judgment}")
    print(f"  measured_at:   {result.measured_at.isoformat()}")

    # Read back + verify the full contract.
    print("\n=== VERIFY: find_one ===")
    doc = await coll.find_one({"_id": ObjectId(result.outcome_id)})
    assert doc is not None, "outcome should be findable by id"

    assert doc["delta_pct"] == -34.17, (
        f"delta_pct must be -34.17, got {doc['delta_pct']}"
    )
    assert isinstance(doc["intervention_id"], ObjectId), (
        "intervention_id must be persisted as ObjectId, not string"
    )
    assert str(doc["intervention_id"]) == intervention_id
    assert doc["user_id"] == USER_ID
    assert doc["metric"] == "weekly_food_spend"
    assert doc["before"] == 180.0
    assert doc["after"] == 118.5
    assert doc["window_days"] == 14
    assert doc["agent_judgment"] == "successful"

    now = datetime.now(UTC)
    measured_at = doc["measured_at"]
    # Mongo strips tz on store; the in-process result still has it.
    if measured_at.tzinfo is None:
        measured_at = measured_at.replace(tzinfo=UTC)
    age_seconds = (now - measured_at).total_seconds()
    assert age_seconds < 10, f"measured_at should be recent (was {age_seconds:.1f}s old)"

    print(f"  intervention_id type: {type(doc['intervention_id']).__name__}")
    print(f"  delta_pct:            {doc['delta_pct']}% ✓")
    print(f"  measured_at age:      {age_seconds:.2f}s")
    print("\n  ALL ASSERTIONS PASSED")

    # Cleanup.
    print(f"\n=== CLEANUP: removing {USER_ID} outcome ===")
    deleted = await coll.delete_many({"user_id": USER_ID})
    print(f"deleted {deleted.deleted_count} outcome(s)")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
