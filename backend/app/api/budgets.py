"""V6 — Budgets API.

Single Clerk-authed GET route the dashboard reads to render the
BudgetProgress widget. Agent writes via set_budget /abandon_budget tools
(agent/tools/set_budget.py + abandon_budget.py); no backend POST —
budget mutations flow through the agent only, matching V1 (goals).
"""

from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, Query

from app.auth.clerk import AuthenticatedUser, current_user
from app.db.client import get_database


router = APIRouter(prefix="/budgets", tags=["budgets"])


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


def _serialize_budget(doc: dict[str, Any]) -> dict[str, Any]:
    budget = {key: _serialize_value(value) for key, value in doc.items()}
    budget["id"] = budget.pop("_id")
    return budget


@router.get("")
async def list_budgets(
    user: AuthenticatedUser = Depends(current_user),
    status: str = Query("active", pattern="^(active|abandoned|all)$"),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List the authenticated user's per-category spending caps.

    Default status="active" hides abandoned budgets (the dashboard
    BudgetProgress widget consumes this default). Sort: category
    ascending for a stable UI order across reloads.
    """
    query: dict = {"user_id": user.user_id}
    if status != "all":
        query["status"] = status

    cursor = (
        get_database()
        .budgets.find(query)
        .sort("category", 1)
        .limit(limit)
    )
    budgets = []
    async for doc in cursor:
        budgets.append(_serialize_budget(doc))
    return {"user_id": user.user_id, "budgets": budgets}
