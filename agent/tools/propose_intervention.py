"""Tool #17 — propose_intervention.

Writes a PENDING intervention doc to atlas.interventions. The frontend
approval UI (#22) renders it; a separate `respond_to_intervention` tool
(future ticket) will flip the response/status when the user answers.

Write-only. Single insert_one. Does NOT update related_memory.use_count
or any other doc — those updates fire on the response, not the proposal.

Persisted shape matches docs/data-model.md § interventions with two
additions:
  - user_response, responded_at: null at write time (the snippet shows
    the answered form).
  - status: "pending" at write time (new field; lets readers filter
    without a `{user_response: null}` query).
"""

from datetime import UTC, datetime
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel, Field

from agent.db.client import get_database


InterventionType = Literal["cap", "reminder", "swap_suggestion", "reflection"]


class ProposeInterventionTrigger(BaseModel):
    tool: str = Field(min_length=1, max_length=80)
    input: dict = Field(default_factory=dict)


class ProposeInterventionInput(BaseModel):
    user_id: str = Field(min_length=1)
    type: InterventionType
    params: dict = Field(default_factory=dict)
    triggered_by: ProposeInterventionTrigger
    related_memory_id: str | None = None


class ProposeInterventionResult(BaseModel):
    intervention_id: str
    user_id: str
    type: InterventionType
    proposed_at: datetime
    status: Literal["pending"]


async def propose_intervention(
    params: ProposeInterventionInput,
    *,
    collection=None,
) -> ProposeInterventionResult:
    """Propose an intervention the user can accept, decline, or modify.

    Use this when you want to act on a pattern you've just observed:
    cap (limit spending in a category), reminder (Sunday meal-prep nudge),
    swap_suggestion (DoorDash → groceries), or reflection (a prompt the
    user can answer in chat). Always carry `triggered_by` so the next
    reader knows why this fired. If the proposal is anchored in a
    recalled memory, set `related_memory_id`.

    Do NOT call write_memory in the same turn as a proposal. The memory
    write should fire on the RESPONSE, not on this proposal. This tool
    writes pending interventions; a follow-up tool handles responses.
    """
    if collection is None:
        collection = get_database().interventions

    # Validate related_memory_id BEFORE any DB call.
    related_memory_oid: ObjectId | None = None
    if params.related_memory_id is not None:
        try:
            related_memory_oid = ObjectId(params.related_memory_id)
        except (InvalidId, TypeError) as exc:
            raise ValueError(
                f"related_memory_id is not a valid ObjectId: {params.related_memory_id!r}"
            ) from exc

    proposed_at = datetime.now(UTC)
    doc = {
        "user_id": params.user_id,
        "proposed_at": proposed_at,
        "triggered_by": {
            "tool": params.triggered_by.tool,
            "input": dict(params.triggered_by.input),
        },
        "type": params.type,
        "params": dict(params.params),
        "user_response": None,
        "responded_at": None,
        "related_memory": related_memory_oid,
        "status": "pending",
    }

    result = await collection.insert_one(doc)
    return ProposeInterventionResult(
        intervention_id=str(result.inserted_id),
        user_id=params.user_id,
        type=params.type,
        proposed_at=proposed_at,
        status="pending",
    )
