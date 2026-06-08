"""Tool — write_goal (V1).

Insert a new user-stated savings target into the `goals` collection.
Write-only: a single `insert_one`. Status defaults to "active"; the
agent never sets paused/complete/abandoned at creation time (those
transitions live in update_goal_status, deferred post-hackathon).

Persisted shape matches docs/data-model.md § goals. created_at is
stamped server-side; the agent cannot control it.
"""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent.db.client import get_database


# Same enum + same wording as agent/tools/check_goal_pace.py:21 so the two
# tools stay aligned. Only "active" is used at write time; the others
# describe later state transitions.
GoalStatus = Literal["active", "paused", "complete", "abandoned"]

# Mirrors goals.pace_check field in docs/data-model.md:42. Single allowed
# value today; kept as Literal so a future "monthly" pace doesn't silently
# slip through.
PaceCheck = Literal["weekly"]


class WriteGoalInput(BaseModel):
    user_id: str = Field(min_length=1)
    title: str = Field(
        min_length=1,
        max_length=120,
        description=(
            "Short, user-facing name. Examples: 'Emergency fund', "
            "'Japan trip', 'New laptop'. Used as the display label on the "
            "dashboard goals widget."
        ),
    )
    target_amount: float = Field(
        gt=0,
        description="Total amount the user wants to save, in their currency. Must be > 0.",
    )
    target_date: date = Field(
        description=(
            "When the user wants to hit the target. Pace verdicts compare "
            "elapsed time against this date."
        ),
    )
    current_amount: float = Field(
        default=0.0,
        ge=0,
        description="How much is already saved toward the goal. Defaults to 0 for brand-new goals.",
    )


class WriteGoalResult(BaseModel):
    goal_id: str
    user_id: str
    title: str
    target_amount: float
    target_date: date
    current_amount: float
    status: GoalStatus
    created_at: datetime


def _at_midnight(d: date) -> datetime:
    """Same date→datetime convention as write_memory + update_user_context."""
    return datetime(d.year, d.month, d.day)


async def write_goal(
    params: WriteGoalInput,
    *,
    collection=None,
) -> WriteGoalResult:
    """Persist a new savings goal the user just stated.

    Use this when the user says they want to save for something — "I want
    to save $5000 for a trip to Japan by December", "I'm trying to build
    a $10k emergency fund by end of year", "Help me save $2000 for a new
    laptop in 6 months". Resolve relative dates ("by December", "in 6
    months") to a concrete date BEFORE calling. Returns the goal_id so
    you can pass it to check_goal_pace in the same turn or a later one.
    """
    if collection is None:
        collection = get_database().goals

    created_at = datetime.now(UTC)
    doc = {
        "user_id": params.user_id,
        "title": params.title,
        "target_amount": float(params.target_amount),
        "current_amount": float(params.current_amount),
        "target_date": _at_midnight(params.target_date),
        "pace_check": "weekly",
        "status": "active",
        "created_at": created_at,
    }

    result = await collection.insert_one(doc)

    return WriteGoalResult(
        goal_id=str(result.inserted_id),
        user_id=params.user_id,
        title=params.title,
        target_amount=float(params.target_amount),
        target_date=params.target_date,
        current_amount=float(params.current_amount),
        status="active",
        created_at=created_at,
    )
