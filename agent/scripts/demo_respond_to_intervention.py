"""Demo proof for BACKLOG #17a — respond_to_intervention against Atlas.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_respond_to_intervention

Full lifecycle in one run:
  1. Write a PENDING intervention via #17's propose_intervention.
  2. Respond with "accepted" via #17a — assert status flips, params unchanged.
  3. Try to respond again — assert LookupError("already in status 'responded'").
  4. Cleanup.
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
from agent.tools.respond_to_intervention import (
    RespondToInterventionInput,
    respond_to_intervention,
)


USER_ID = "u_demo_respond_17a"
ORIGINAL_PARAMS = {"day": "sunday", "what": "meal prep"}


async def main() -> None:
    db = get_database()
    coll = db.interventions

    # Clean slate.
    await coll.delete_many({"user_id": USER_ID})

    # 1. Propose (PENDING).
    print(f"\n=== STEP 1: propose pending intervention under {USER_ID} ===")
    proposal = await propose_intervention(
        ProposeInterventionInput(
            user_id=USER_ID,
            type="reminder",
            params=ORIGINAL_PARAMS,
            triggered_by=ProposeInterventionTrigger(
                tool="get_spend_anomaly",
                input={"category": "food.delivery", "window_days": 7},
            ),
        )
    )
    iv_id = proposal.intervention_id
    print(f"  intervention_id: {iv_id}")
    print(f"  status:          {proposal.status}")

    # 2. Respond accepted.
    print("\n=== STEP 2: respond 'accepted' ===")
    response = await respond_to_intervention(
        RespondToInterventionInput(
            user_id=USER_ID,
            intervention_id=iv_id,
            user_response="accepted",
        )
    )
    print(f"  previous_status: {response.previous_status}")
    print(f"  new_status:      {response.new_status}")
    print(f"  user_response:   {response.user_response}")
    print(f"  responded_at:    {response.responded_at.isoformat()}")
    print(f"  params_changed:  {response.params_changed}")

    # Verify the persisted doc.
    doc = await coll.find_one({"_id": ObjectId(iv_id)})
    assert doc is not None
    assert doc["status"] == "responded", f"status was {doc['status']}"
    assert doc["user_response"] == "accepted"
    assert doc["responded_at"] is not None
    assert doc["params"] == ORIGINAL_PARAMS, "params must NOT change on accepted"

    # Recency check.
    now = datetime.now(UTC)
    responded_at = doc["responded_at"]
    if responded_at.tzinfo is None:
        responded_at = responded_at.replace(tzinfo=UTC)
    age_seconds = (now - responded_at).total_seconds()
    assert age_seconds < 10, f"responded_at should be recent (was {age_seconds:.1f}s old)"
    print(f"  ✓ persisted doc verified — responded_at age {age_seconds:.2f}s")

    # 3. Idempotency check.
    print("\n=== STEP 3: try to respond again — expect LookupError ===")
    try:
        await respond_to_intervention(
            RespondToInterventionInput(
                user_id=USER_ID,
                intervention_id=iv_id,
                user_response="declined",
            )
        )
    except LookupError as e:
        print(f"  ✓ raised LookupError as expected: {e}")
        assert "already in status 'responded'" in str(e)
    else:
        raise AssertionError("expected LookupError on double-response")

    # 4. Cleanup.
    print(f"\n=== STEP 4: cleanup {USER_ID} ===")
    deleted = await coll.delete_many({"user_id": USER_ID})
    print(f"  deleted {deleted.deleted_count} intervention(s)")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
