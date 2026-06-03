from datetime import datetime
from pathlib import Path
import sys
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.clerk import AuthenticatedUser, current_user
from app.db.client import get_database


router = APIRouter(prefix="/interventions", tags=["interventions"])


class InterventionResponseRequest(BaseModel):
    user_response: str
    modified_params: dict[str, Any] | None = None


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize_value(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_serialize_value(inner) for inner in value]
    return value


def _serialize_intervention(doc: dict[str, Any]) -> dict[str, Any]:
    intervention = {key: _serialize_value(value) for key, value in doc.items()}
    intervention["id"] = intervention.pop("_id")
    return intervention


def _ensure_repo_root_on_path() -> None:
    root = Path(__file__).resolve().parents[3]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.append(root_str)


async def call_respond_to_intervention(
    *,
    user_id: str,
    intervention_id: str,
    user_response: str,
    modified_params: dict[str, Any] | None,
) -> Any:
    _ensure_repo_root_on_path()
    from agent.tools.respond_to_intervention import (  # noqa: PLC0415
        RespondToInterventionInput,
        respond_to_intervention,
    )

    return await respond_to_intervention(
        RespondToInterventionInput(
            user_id=user_id,
            intervention_id=intervention_id,
            user_response=user_response,
            modified_params=modified_params,
        )
    )


@router.get("/pending")
async def list_pending_interventions(
    user: AuthenticatedUser = Depends(current_user),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    cursor = (
        get_database()
        .interventions.find({"user_id": user.user_id, "status": "pending"})
        .sort("proposed_at", -1)
        .limit(limit)
    )
    interventions = []
    async for doc in cursor:
        interventions.append(_serialize_intervention(doc))
    return {"user_id": user.user_id, "interventions": interventions}


@router.post("/{intervention_id}/respond")
async def respond_to_pending_intervention(
    intervention_id: str,
    request: InterventionResponseRequest,
    user: AuthenticatedUser = Depends(current_user),
) -> dict:
    try:
        result = await call_respond_to_intervention(
            user_id=user.user_id,
            intervention_id=intervention_id,
            user_response=request.user_response,
            modified_params=request.modified_params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        detail = str(exc)
        status_code = 409 if "already in status" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return result.model_dump(mode="json")
