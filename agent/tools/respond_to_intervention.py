"""Tool #17a — respond_to_intervention.

The R+U half of the intervention lifecycle. #17 wrote PENDING; this
tool flips status pending → responded (or ignored) and persists the
user's choice.

Update-only. Single find_one_and_update on the happy path; one extra
find_one only on the error path to classify the failure cleanly.
Does NOT bump related_memory.use_count (#13a). Does NOT write a memory
(separate agent decision).
"""

from datetime import UTC, datetime
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel, Field, model_validator
from pymongo import ReturnDocument

from agent.db.client import get_database


UserResponse = Literal["accepted", "declined", "modified", "ignored"]
NewStatus = Literal["responded", "ignored"]


class RespondToInterventionInput(BaseModel):
    user_id: str = Field(min_length=1)
    intervention_id: str = Field(min_length=1)
    user_response: UserResponse
    modified_params: dict | None = None

    @model_validator(mode="after")
    def _modified_params_only_when_modified(self) -> "RespondToInterventionInput":
        if self.user_response == "modified":
            if not self.modified_params:
                raise ValueError(
                    "user_response='modified' requires non-empty modified_params"
                )
        elif self.modified_params is not None:
            raise ValueError(
                f"modified_params is only allowed when user_response='modified', "
                f"not '{self.user_response}'"
            )
        return self


class RespondToInterventionResult(BaseModel):
    intervention_id: str
    user_id: str
    previous_status: Literal["pending"]
    new_status: NewStatus
    user_response: UserResponse
    responded_at: datetime
    params_changed: bool


async def respond_to_intervention(
    params: RespondToInterventionInput,
    *,
    collection=None,
) -> RespondToInterventionResult:
    """Record the user's response to a pending intervention.

    Use this after the user replies to a proposal in chat. Flips the
    intervention from PENDING to RESPONDED (or IGNORED). For modified
    responses, the agent resolves the user's tweak into a new params
    dict and passes it via modified_params; the doc's params field
    is updated to reflect the new shape.

    Idempotent: an already-responded intervention raises LookupError
    rather than silently re-flipping or double-recording.
    """
    if collection is None:
        collection = get_database().interventions

    try:
        oid = ObjectId(params.intervention_id)
    except (InvalidId, TypeError) as exc:
        raise ValueError(
            f"intervention_id is not a valid ObjectId: {params.intervention_id!r}"
        ) from exc

    new_status: NewStatus = (
        "ignored" if params.user_response == "ignored" else "responded"
    )
    responded_at = datetime.now(UTC)
    update_set: dict = {
        "user_response": params.user_response,
        "responded_at": responded_at,
        "status": new_status,
    }
    if params.user_response == "modified":
        update_set["params"] = dict(params.modified_params or {})

    updated = await collection.find_one_and_update(
        {"_id": oid, "user_id": params.user_id, "status": "pending"},
        {"$set": update_set},
        return_document=ReturnDocument.AFTER,
    )

    if updated is None:
        # Classify the failure with ONE extra round-trip (error path only).
        existing = await collection.find_one(
            {"_id": oid, "user_id": params.user_id}
        )
        if existing is not None:
            raise LookupError(
                f"intervention {params.intervention_id} is already in status "
                f"{existing.get('status')!r}"
            )
        raise LookupError(
            f"intervention {params.intervention_id} not found for user "
            f"{params.user_id}"
        )

    return RespondToInterventionResult(
        intervention_id=params.intervention_id,
        user_id=params.user_id,
        previous_status="pending",
        new_status=new_status,
        user_response=params.user_response,
        responded_at=responded_at,
        params_changed=(params.user_response == "modified"),
    )
