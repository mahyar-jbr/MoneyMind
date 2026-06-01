"""Tool #12 — get_spend_anomaly.

Detects when a user's spend in a category over the last `window_days` is
unusually high compared to their recent weekly baseline. Returns a structured
verdict (z-score, mean, std, is_anomaly, optional human-grade note) so the
agent can speak about it concretely.

Baseline construction:
  - The baseline window is `baseline_weeks` calendar weeks ending the day
    before the current window starts.
  - Each week's category spend is summed. Weeks with no rows in that category
    are treated as 0.0 (not skipped) — otherwise the mean is misleading.
  - Population std (divisor = N), not sample std.

Anomaly rule:
  is_anomaly = (z_score >= 2.0) AND (current_spend > baseline_mean)
  The AND guard avoids divide-by-zero on perfectly steady spend AND
  prevents the tool from firing on downside surprises (a quiet week is not
  something the agent should escalate).
"""

import math
from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field

from agent.db.client import get_database


class GetSpendAnomalyInput(BaseModel):
    user_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    window_days: int = Field(default=7, ge=1, le=90)
    baseline_weeks: int = Field(default=8, ge=2, le=52)
    as_of: date | None = None  # anchor; caller provides for determinism


class GetSpendAnomalyResult(BaseModel):
    user_id: str
    category: str
    window_days: int
    window_start: date
    window_end: date
    current_spend: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    is_anomaly: bool
    baseline_weeks_used: int
    note: str | None = None


def _pretty(category: str) -> str:
    return category.replace(".", " ").title()


def _make_note(category: str, current_spend: float, baseline_mean: float, weeks_used: int) -> str:
    pretty = _pretty(category)
    if baseline_mean <= 0:
        return f"{pretty} spend appeared this week (no prior history)."
    ratio = current_spend / baseline_mean
    return f"{pretty} is {ratio:.1f}x your {weeks_used}-week average (${baseline_mean:.0f})."


async def get_spend_anomaly(
    params: GetSpendAnomalyInput,
    *,
    collection=None,
) -> GetSpendAnomalyResult:
    """Detect whether {category} spend in the last {window_days} is unusually high.

    Use this when the user asks if their spending is "weird," "high," or
    "out of pattern," or when you (the agent) want to proactively check a
    category before responding. Compares the current window total to a
    rolling baseline of recent calendar weeks. Returns z-score + flag.

    Do NOT use this for raw row lookup (use query_transactions) or for the
    weekly summary paragraph (use summarize_week).
    """
    if collection is None:
        collection = get_database().transactions

    # Resolve windows (inclusive both ends, by date)
    as_of = params.as_of or date.today()
    window_end = as_of
    window_start = window_end - timedelta(days=params.window_days - 1)
    baseline_end_inclusive = window_start - timedelta(days=1)
    baseline_start = baseline_end_inclusive - timedelta(weeks=params.baseline_weeks) + timedelta(days=1)

    # Convert to datetime bounds for Mongo. Stored docs are naive datetimes
    # at midnight (verified in #11), so naive bounds compare correctly.
    def at_midnight(d: date) -> datetime:
        return datetime(d.year, d.month, d.day)

    # --- current_spend: single scalar query, outflow-only ---
    cur_pipeline_match = {
        "user_id": params.user_id,
        "category": params.category,
        "amount": {"$lt": 0},
        "date": {
            "$gte": at_midnight(window_start),
            "$lt": at_midnight(window_end + timedelta(days=1)),  # end-of-day inclusive
        },
    }
    current_spend = 0.0
    async for doc in collection.find(cur_pipeline_match, {"_id": 0, "amount": 1}):
        current_spend += -doc["amount"]  # outflow stored negative; report positive

    # --- baseline: fetch all rows in the baseline range, bucket in Python ---
    # Why not weekly_spend_by_category? mongomock-motor doesn't implement
    # $dateTrunc, and the test suite needs to be hermetic. Python bucketing
    # produces deterministic numbers. Flagged for PM in the dev report.
    #
    # Bucketing strategy: exactly `baseline_weeks` consecutive 7-day buckets
    # ending the day BEFORE window_start. Buckets are anchored to baseline_start
    # (not ISO Mondays) — this guarantees the divisor is `baseline_weeks` and
    # prevents calendar drift from inflating it.
    baseline_rows = collection.find(
        {
            "user_id": params.user_id,
            "category": params.category,
            "amount": {"$lt": 0},
            "date": {
                "$gte": at_midnight(baseline_start),
                "$lt": at_midnight(window_start),  # exclusive — window_start belongs to current
            },
        },
        {"_id": 0, "date": 1, "amount": 1},
    )

    # Bucket i covers [baseline_start + 7i, baseline_start + 7(i+1))
    series = [0.0] * params.baseline_weeks
    async for doc in baseline_rows:
        d = doc["date"]
        if isinstance(d, datetime):
            d = d.date()
        bucket_idx = (d - baseline_start).days // 7
        if 0 <= bucket_idx < params.baseline_weeks:
            series[bucket_idx] += -doc["amount"]

    n = len(series)
    baseline_mean = sum(series) / n if n else 0.0
    baseline_std = (
        math.sqrt(sum((x - baseline_mean) ** 2 for x in series) / n) if n else 0.0
    )
    baseline_weeks_used = sum(1 for x in series if x > 0)

    if baseline_std > 0:
        z_score = (current_spend - baseline_mean) / baseline_std
    else:
        z_score = 0.0

    is_anomaly = z_score >= 2.0 and current_spend > baseline_mean

    note: str | None = None
    if is_anomaly:
        note = _make_note(params.category, current_spend, baseline_mean, baseline_weeks_used)
    elif baseline_mean == 0 and current_spend > 0:
        # No prior history but spend happened — informational, not "anomaly".
        note = _make_note(params.category, current_spend, 0, baseline_weeks_used)

    return GetSpendAnomalyResult(
        user_id=params.user_id,
        category=params.category,
        window_days=params.window_days,
        window_start=window_start,
        window_end=window_end,
        current_spend=round(current_spend, 2),
        baseline_mean=round(baseline_mean, 2),
        baseline_std=round(baseline_std, 2),
        z_score=round(z_score, 2),
        is_anomaly=is_anomaly,
        baseline_weeks_used=baseline_weeks_used,
        note=note,
    )
