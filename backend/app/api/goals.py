"""V1 — Goals API.

Single Clerk-authed GET route the frontend dashboard reads to render the
SavingsGoals widget. The agent writes to atlas.goals via the write_goal
tool (agent/tools/write_goal.py); this route is the read path. No
backend POST — goal creation flows through the agent only, so the user
must state the goal in chat to materialize it.
"""

from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, Query

from app.auth.clerk import AuthenticatedUser, current_user
from app.db.client import get_database


router = APIRouter(prefix="/goals", tags=["goals"])


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


def _serialize_goal(doc: dict[str, Any]) -> dict[str, Any]:
    goal = {key: _serialize_value(value) for key, value in doc.items()}
    goal["id"] = goal.pop("_id")
    return goal


@router.get("")
async def list_goals(
    user: AuthenticatedUser = Depends(current_user),
    status: str = Query("active", pattern="^(active|paused|complete|abandoned|all)$"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List the authenticated user's goals, newest first.

    Default status=active suppresses paused / complete / abandoned. Pass
    status=all to include everything (used by a "show me everything" UI
    affordance, not by the default dashboard render).
    """
    query: dict = {"user_id": user.user_id}
    if status != "all":
        query["status"] = status

    cursor = (
        get_database()
        .goals.find(query)
        .sort("created_at", -1)
        .limit(limit)
    )
    goals = []
    async for doc in cursor:
        goals.append(_serialize_goal(doc))
    return {"user_id": user.user_id, "goals": goals}
