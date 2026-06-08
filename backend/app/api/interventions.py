import logging
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.clerk import AuthenticatedUser, current_user
from app.db.client import get_database


logger = logging.getLogger(__name__)


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


async def call_set_budget(
    *,
    user_id: str,
    category: str,
    limit: float,
) -> Any:
    """Materialize a cap intervention as a real budget in atlas.budgets.

    Called from respond_to_pending_intervention when the user accepts
    a `type="cap"` intervention. Without this, the V6 slide-8 narrative
    breaks: the intervention gets marked responded, but the dashboard's
    BudgetProgress widget never shows the cap because no budget row
    was inserted. Pre-this-fix the agent's system prompt told it to
    chain set_budget after respond_to_intervention, but the intervention
    card response path bypasses the agent entirely (frontend → REST
    proxy → backend → agent tool, no LLM turn). So the chain has to
    happen at the backend layer.
    """
    _ensure_repo_root_on_path()
    from agent.tools.set_budget import (  # noqa: PLC0415
        SetBudgetInput,
        set_budget,
    )

    return await set_budget(
        SetBudgetInput(
            user_id=user_id,
            category=category,
            limit=limit,
        )
    )


def _extract_cap_params(
    intervention_params: dict[str, Any],
    modified_params: dict[str, Any] | None,
) -> tuple[str | None, float | None]:
    """Resolve the (category, limit) to materialize for a cap intervention.

    Prefers modified_params (user tweaked the cap before accepting) over
    the original intervention.params. Coerces limit to float because
    intervention params can be persisted as strings via the agent's
    structured-output schema.

    Returns (None, None) if either field is missing or unparseable —
    the caller should silently skip set_budget rather than blow up the
    intervention response.
    """
    source: dict[str, Any] = dict(intervention_params or {})
    if modified_params:
        source.update(modified_params)

    category = source.get("category")
    if not isinstance(category, str) or not category.strip():
        return None, None

    raw_limit = source.get("limit")
    if raw_limit is None:
        return category, None
    try:
        limit = float(raw_limit)
    except (TypeError, ValueError):
        return category, None
    if limit <= 0:
        return category, None
    return category, limit


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

    response_payload = result.model_dump(mode="json")

    # V6 cap-intervention auto-materialize: when the user accepts a
    # `type="cap"` intervention, the intervention card path (REST,
    # no agent turn) means set_budget would never fire. Do it here so
    # the BudgetProgress widget reflects the accepted cap immediately.
    # Best-effort — never blow up the intervention response if the
    # cap params are malformed.
    if request.user_response == "accepted":
        try:
            doc = await get_database().interventions.find_one(
                {
                    "_id": ObjectId(intervention_id),
                    "user_id": user.user_id,
                },
                {"type": 1, "params": 1},
            )
        except Exception:  # noqa: BLE001
            doc = None
        if doc and doc.get("type") == "cap":
            category, limit = _extract_cap_params(
                doc.get("params") or {}, request.modified_params
            )
            if category and limit is not None:
                try:
                    budget_result = await call_set_budget(
                        user_id=user.user_id,
                        category=category,
                        limit=limit,
                    )
                    response_payload["budget"] = budget_result.model_dump(
                        mode="json"
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "set_budget after cap accept failed for "
                        "intervention=%s user=%s category=%s: %s",
                        intervention_id,
                        user.user_id,
                        category,
                        exc,
                    )

    return response_payload
