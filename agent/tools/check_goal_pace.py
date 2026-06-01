"""Tool #16 — check_goal_pace.

Read-only pace check for a single goal: linear projection from created_at
to target_date, compare against current_amount, return a verdict + note
the agent can paraphrase.

The goal doc's `current_amount` is the source of truth. This tool does
NOT recompute it from transactions; that's #16a if we ever need it.
"""

from datetime import date, datetime
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel, Field

from agent.db.client import get_database


GoalStatus = Literal["active", "paused", "complete", "abandoned"]
Verdict = Literal[
    "ahead", "on_track", "behind", "complete", "not_started", "past_due",
    "paused", "abandoned",
]
TOLERANCE_PCT = 5.0


class CheckGoalPaceInput(BaseModel):
    user_id: str = Field(min_length=1)
    goal_id: str = Field(min_length=1)
    as_of: date | None = None


class CheckGoalPaceResult(BaseModel):
    user_id: str
    goal_id: str
    title: str
    status: GoalStatus
    target_amount: float
    current_amount: float
    target_date: date
    as_of: date
    expected_amount: float
    delta_amount: float
    delta_pct: float
    verdict: Verdict
    note: str


def _format_note(
    verdict: Verdict,
    *,
    title: str,
    target_amount: float,
    current_amount: float,
    expected_amount: float,
    delta_pct: float,
    target_date: date,
) -> str:
    short = title
    if verdict == "complete":
        return f"{short}: complete — target {target_amount:.0f} reached."
    if verdict == "abandoned":
        return f"{short}: abandoned."
    if verdict == "paused":
        return f"{short}: paused (was {delta_pct:+.0f}% vs. pace)."
    if verdict == "past_due":
        gap = target_amount - current_amount
        return (
            f"{short}: past due — {gap:.0f} short of {target_amount:.0f} target "
            f"by {target_date.isoformat()}."
        )
    if verdict == "not_started":
        return f"{short}: just started; pace check not meaningful yet."
    if verdict == "ahead":
        return (
            f"{short}: {delta_pct:+.0f}% ahead of pace "
            f"(have ${current_amount:.0f}, expected ${expected_amount:.0f})."
        )
    if verdict == "behind":
        return (
            f"{short}: {delta_pct:+.0f}% behind pace "
            f"(have ${current_amount:.0f}, expected ${expected_amount:.0f})."
        )
    # on_track
    return (
        f"{short}: on track ({delta_pct:+.0f}%, have ${current_amount:.0f} "
        f"of ${target_amount:.0f}, by {target_date.isoformat()})."
    )


async def check_goal_pace(
    params: CheckGoalPaceInput,
    *,
    collection=None,
) -> CheckGoalPaceResult:
    """Return a pace verdict for a single goal.

    Use this when the user asks about a specific goal ("how am I doing on
    my emergency fund?"), when you're about to propose an intervention
    that depends on goal progress, or as part of a weekly summary. The
    `note` field is a one-line summary you can paraphrase.

    Does NOT update the goal. The goal's `current_amount` is the source
    of truth — pace is computed against that, not recomputed from
    transactions.
    """
    if collection is None:
        collection = get_database().goals

    try:
        oid = ObjectId(params.goal_id)
    except (InvalidId, TypeError) as exc:
        raise ValueError(f"goal_id is not a valid ObjectId: {params.goal_id!r}") from exc

    doc = await collection.find_one({"_id": oid, "user_id": params.user_id})
    if doc is None:
        raise LookupError(
            f"goal {params.goal_id} not found for user {params.user_id}"
        )

    as_of = params.as_of or date.today()

    # Coerce stored dates (naive datetimes at midnight) back to date.
    created_at_dt = doc["created_at"]
    if isinstance(created_at_dt, datetime):
        created_at_date = created_at_dt.date()
    else:
        created_at_date = created_at_dt
    target_date_dt = doc["target_date"]
    if isinstance(target_date_dt, datetime):
        target_date_ = target_date_dt.date()
    else:
        target_date_ = target_date_dt

    target_amount = float(doc["target_amount"])
    current_amount = float(doc["current_amount"])
    status: GoalStatus = doc["status"]
    title = doc["title"]

    total_days = (target_date_ - created_at_date).days
    elapsed_days = (as_of - created_at_date).days
    if total_days <= 0:
        # Edge: target on/before creation. Treat as immediate.
        expected_amount = target_amount
    else:
        frac = max(0.0, min(1.0, elapsed_days / total_days))
        expected_amount = target_amount * frac

    delta_amount = current_amount - expected_amount
    delta_pct = (delta_amount / expected_amount * 100) if expected_amount > 0 else 0.0

    # Verdict (order matters — first match wins).
    verdict: Verdict
    if status == "complete":
        verdict = "complete"
    elif status == "abandoned":
        verdict = "abandoned"
    elif status == "paused":
        verdict = "paused"
    elif as_of > target_date_ and current_amount < target_amount:
        verdict = "past_due"
    elif elapsed_days <= 0:
        verdict = "not_started"
    elif delta_pct >= TOLERANCE_PCT:
        verdict = "ahead"
    elif delta_pct <= -TOLERANCE_PCT:
        verdict = "behind"
    else:
        verdict = "on_track"

    note = _format_note(
        verdict,
        title=title,
        target_amount=target_amount,
        current_amount=current_amount,
        expected_amount=expected_amount,
        delta_pct=delta_pct,
        target_date=target_date_,
    )

    return CheckGoalPaceResult(
        user_id=params.user_id,
        goal_id=params.goal_id,
        title=title,
        status=status,
        target_amount=target_amount,
        current_amount=current_amount,
        target_date=target_date_,
        as_of=as_of,
        expected_amount=round(expected_amount, 2),
        delta_amount=round(delta_amount, 2),
        delta_pct=round(delta_pct, 2),
        verdict=verdict,
        note=note,
    )
