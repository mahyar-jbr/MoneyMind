"""Tool — list_goals (V1).

Read the user's goals so the agent can discover `goal_id`s to feed into
check_goal_pace. Read-only: a single `find`. Default sort: created_at
descending so the newest goal is first; status filter defaults to
"active" only (paused/complete/abandoned suppressed unless the user
explicitly asks "show me all my goals including the abandoned ones").

This is the closure of the V1 gap: before this tool existed,
check_goal_pace had no way to obtain a goal_id and the goal beat was
invisible from chat. Pair with write_goal to round-trip the slide-7
flow end-to-end.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent.db.client import get_database


GoalStatus = Literal["active", "paused", "complete", "abandoned"]


class ListGoalsInput(BaseModel):
    user_id: str = Field(min_length=1)
    # By default show only active goals; the agent passes a value here
    # only when the user explicitly asks ("show me everything", "what
    # about the goals I gave up on").
    status: GoalStatus | Literal["all"] = Field(
        default="active",
        description=(
            "Filter by goal status. Default 'active' — surfaces only goals "
            "the user is still working on. Pass 'all' to include paused / "
            "complete / abandoned. Other enum values filter to that exact "
            "status only."
        ),
    )
    limit: int = Field(default=20, ge=1, le=100)


class GoalSummary(BaseModel):
    goal_id: str
    title: str
    target_amount: float
    current_amount: float
    target_date: date
    status: GoalStatus
    created_at: datetime


class ListGoalsResult(BaseModel):
    user_id: str
    count: int
    goals: list[GoalSummary]


def _to_summary(doc: dict) -> GoalSummary:
    td = doc.get("target_date")
    if isinstance(td, datetime):
        td = td.date()
    return GoalSummary(
        goal_id=str(doc["_id"]),
        title=doc.get("title", ""),
        target_amount=float(doc.get("target_amount", 0)),
        current_amount=float(doc.get("current_amount", 0)),
        target_date=td,
        status=doc.get("status", "active"),
        created_at=doc["created_at"],
    )


async def list_goals(
    params: ListGoalsInput,
    *,
    collection=None,
) -> ListGoalsResult:
    """List the user's savings goals so you can decide which to act on.

    Call this BEFORE check_goal_pace when the user asks "how am I doing
    on my goals?" / "what are my goals?" / "am I on track?". Returns
    goal_ids you can then pass to check_goal_pace for per-goal pace
    verdicts. Defaults to active goals only — pass status='all' if the
    user explicitly asks about paused / completed / abandoned goals.
    """
    if collection is None:
        collection = get_database().goals

    query: dict = {"user_id": params.user_id}
    if params.status != "all":
        query["status"] = params.status

    cursor = collection.find(query).sort("created_at", -1).limit(params.limit)
    goals: list[GoalSummary] = []
    async for doc in cursor:
        goals.append(_to_summary(doc))

    return ListGoalsResult(
        user_id=params.user_id,
        count=len(goals),
        goals=goals,
    )
