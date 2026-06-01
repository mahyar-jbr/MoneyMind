"""Tool #18 — log_outcome.

Writes one outcome doc to atlas.outcomes — the "did the intervention
work?" record that closes the learning loop. Write-only. delta_pct is
computed server-side from before/after; the agent doesn't get to fudge it.

Does NOT update the corresponding intervention doc. The intervention
collection is the proposal/response surface; outcomes is the measurement
surface; they're joined by intervention_id, not by mutating each other.
"""

from datetime import UTC, datetime
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel, Field

from agent.db.client import get_database


AgentJudgment = Literal["successful", "partial", "failed", "inconclusive"]


class LogOutcomeInput(BaseModel):
    user_id: str = Field(min_length=1)
    intervention_id: str = Field(min_length=1)
    window_days: int = Field(ge=1, le=365)
    metric: str = Field(min_length=1, max_length=80)
    before: float
    after: float
    agent_judgment: AgentJudgment


class LogOutcomeResult(BaseModel):
    outcome_id: str
    user_id: str
    intervention_id: str
    metric: str
    window_days: int
    before: float
    after: float
    delta_pct: float
    agent_judgment: AgentJudgment
    measured_at: datetime


def _compute_delta_pct(before: float, after: float) -> float:
    """(after - before) / abs(before) * 100, rounded to 2dp.

    Uses abs(before) so the sign of delta_pct reflects direction-of-change
    regardless of the sign of `before`. Returns 0.0 when before == 0
    (undefined ratio; the agent's prompt interprets the situation).
    """
    if before == 0:
        return 0.0
    return round((after - before) / abs(before) * 100, 2)


async def log_outcome(
    params: LogOutcomeInput,
    *,
    collection=None,
) -> LogOutcomeResult:
    """Log the measured outcome of a past intervention.

    Use this after observing N days of behavior post-intervention,
    comparing a metric before/after the proposal, and judging the result.
    delta_pct is COMPUTED — pass before/after, the tool persists the math.

    Do NOT call this twice for the same intervention. Do NOT use this to
    update the intervention doc itself (use respond_to_intervention for
    user response, log_outcome only for the measurement).
    """
    if collection is None:
        collection = get_database().outcomes

    # Validate intervention_id BEFORE any DB call.
    try:
        intervention_oid = ObjectId(params.intervention_id)
    except (InvalidId, TypeError) as exc:
        raise ValueError(
            f"intervention_id is not a valid ObjectId: {params.intervention_id!r}"
        ) from exc

    delta_pct = _compute_delta_pct(params.before, params.after)
    measured_at = datetime.now(UTC)
    doc = {
        "intervention_id": intervention_oid,
        "user_id": params.user_id,
        "measured_at": measured_at,
        "window_days": params.window_days,
        "metric": params.metric,
        "before": params.before,
        "after": params.after,
        "delta_pct": delta_pct,
        "agent_judgment": params.agent_judgment,
    }

    result = await collection.insert_one(doc)
    return LogOutcomeResult(
        outcome_id=str(result.inserted_id),
        user_id=params.user_id,
        intervention_id=params.intervention_id,
        metric=params.metric,
        window_days=params.window_days,
        before=params.before,
        after=params.after,
        delta_pct=delta_pct,
        agent_judgment=params.agent_judgment,
        measured_at=measured_at,
    )
