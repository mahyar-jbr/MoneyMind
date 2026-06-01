"""Tool #20 — summarize_week.

Weekly spending digest: structured fields for LLM reasoning + a plain-text
paragraph ready for the cron's inbox post. The cron (#21) calls this once
per active user per week.

Read-only. Does NOT call other tools — composition lives in the agent
layer. This tool reads from TWO collections (transactions, goals) and
delegates the spend aggregation to an injected callable so the test path
can skip Mongo's $dateTrunc operator.
"""

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from agent.aggregations.weekly import weekly_spend_by_category
from agent.db.client import get_database


TOLERANCE_PCT = 5.0  # same band as #16's pace tolerance


# ─── Schemas ────────────────────────────────────────────────────────


class SummarizeWeekInput(BaseModel):
    user_id: str = Field(min_length=1)
    as_of: date | None = None
    week_offset: int = Field(default=0, ge=-12, le=0)
    include_goals: bool = True


class CategorySpend(BaseModel):
    category: str
    spend: float
    pct_of_total: float


class GoalSnapshot(BaseModel):
    goal_id: str
    title: str
    pct_complete: float
    note: str


class SummarizeWeekResult(BaseModel):
    user_id: str
    week_start: date
    week_end: date
    total_spend: float
    transaction_count: int
    top_categories: list[CategorySpend]
    goals: list[GoalSnapshot]
    paragraph: str


# ─── Helpers ────────────────────────────────────────────────────────


def _pretty(category: str) -> str:
    return category.replace(".", " ").title()


def _at_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def _week_bounds(as_of: date, week_offset: int) -> tuple[date, date]:
    monday = as_of - timedelta(days=as_of.weekday())
    monday += timedelta(weeks=week_offset)
    return monday, monday + timedelta(days=6)


def _goal_note(
    *,
    status: str,
    pct_complete: float,
    target_date: date,
    target_amount: float,
    current_amount: float,
    created_at: date,
    as_of: date,
) -> str:
    """Inline pace note. Does NOT call check_goal_pace (no tool nesting)."""
    if status == "complete" or pct_complete >= 100.0:
        return "Goal reached."
    if as_of > target_date:
        gap = target_amount - current_amount
        return f"Past due (${gap:.0f} short)."
    total_days = (target_date - created_at).days
    elapsed_days = (as_of - created_at).days
    if total_days <= 0 or elapsed_days <= 0:
        return "On track."
    expected_pct = elapsed_days / total_days * 100
    delta = pct_complete - expected_pct
    if delta >= TOLERANCE_PCT:
        return f"Ahead by {delta:.0f}pp."
    if delta <= -TOLERANCE_PCT:
        return f"Behind by {-delta:.0f}pp."
    return "On track."


def _snapshot_goal(doc: dict, *, as_of: date) -> GoalSnapshot:
    target_amount = float(doc.get("target_amount", 0))
    current_amount = float(doc.get("current_amount", 0))
    pct = (
        round(min(100.0, current_amount / target_amount * 100), 1)
        if target_amount > 0
        else 0.0
    )
    td = doc.get("target_date")
    ca = doc.get("created_at")
    target_date_d = td.date() if isinstance(td, datetime) else td
    created_at_d = ca.date() if isinstance(ca, datetime) else ca
    note = _goal_note(
        status=doc.get("status", "active"),
        pct_complete=pct,
        target_date=target_date_d,
        target_amount=target_amount,
        current_amount=current_amount,
        created_at=created_at_d,
        as_of=as_of,
    )
    return GoalSnapshot(
        goal_id=str(doc["_id"]),
        title=doc.get("title", ""),
        pct_complete=pct,
        note=note,
    )


def _format_paragraph(
    *,
    week_start: date,
    total_spend: float,
    transaction_count: int,
    top_categories: list[CategorySpend],
    goals: list[GoalSnapshot],
) -> str:
    week_label = f"Week of {week_start.strftime('%a, %b %-d')}"

    # Goals tail clause.
    if not goals:
        goals_line = ""
    elif len(goals) == 1:
        g = goals[0]
        # Drop the trailing period from the note and lowercase first word.
        clause = g.note.rstrip(".")
        if clause:
            clause = clause[0].lower() + clause[1:]
        goals_line = f" You're {g.pct_complete:.0f}% to {g.title} — {clause}."
    else:
        needs_attention = sum(
            1 for g in goals if g.note.startswith(("Behind", "Past due"))
        )
        goals_line = (
            f" {len(goals)} active goals tracking; "
            f"{needs_attention} need attention."
        )

    # Empty week.
    if total_spend == 0:
        if not goals:
            return f"{week_label}: no spending recorded. Quiet week."
        return f"{week_label}: no spending recorded.{goals_line}"

    # Top-3 in the paragraph (top-5 in the structured result).
    top3 = top_categories[:3]
    cat_parts = ", ".join(f"{_pretty(c.category)} ${c.spend:.0f}" for c in top3)
    biggest = f" Biggest categories: {cat_parts}." if cat_parts else ""
    return (
        f"{week_label}: you spent ${total_spend:.0f} across "
        f"{transaction_count} transactions.{biggest}{goals_line}"
    )


# ─── Tool ───────────────────────────────────────────────────────────


async def summarize_week(
    params: SummarizeWeekInput,
    *,
    collection=None,
    goals_collection=None,
    aggregator: Callable[..., Awaitable[list[dict]]] | None = None,
) -> SummarizeWeekResult:
    """Produce a weekly spending digest as structured data + a plain paragraph.

    Use this for any "how am I doing?" / "what did I spend this week?" /
    weekly-summary question. The cron (#21) posts the `paragraph` field
    verbatim to the user's inbox; the structured fields let the LLM
    reason on top.

    Do NOT use this to compute anomaly z-scores (use get_spend_anomaly)
    or to enumerate individual transactions (use query_transactions).
    """
    db: Any = None
    if collection is None or goals_collection is None or aggregator is None:
        db = get_database()
    if collection is None:
        collection = db.transactions
    if goals_collection is None:
        goals_collection = db.goals
    if aggregator is None:
        async def _real_aggregator(
            user_id: str,
            date_from: datetime,
            date_to_exclusive: datetime,
        ) -> list[dict]:
            return await weekly_spend_by_category(
                db,
                user_id=user_id,
                date_from=date_from,
                date_to_exclusive=date_to_exclusive,
                category=None,
            )
        aggregator = _real_aggregator

    as_of = params.as_of or date.today()
    week_start, week_end = _week_bounds(as_of, params.week_offset)
    range_from = _at_midnight(week_start)
    range_to_exclusive = _at_midnight(week_end + timedelta(days=1))

    # Spend aggregation.
    buckets = await aggregator(params.user_id, range_from, range_to_exclusive)
    if buckets:
        bucket = buckets[0]
        total_spend = float(bucket.get("total_spend", 0.0))
        by_category = dict(bucket.get("by_category", {}))
    else:
        total_spend = 0.0
        by_category = {}

    ranked = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
    top_categories = [
        CategorySpend(
            category=cat,
            spend=round(float(spend), 2),
            pct_of_total=round(float(spend) / total_spend * 100, 1)
            if total_spend > 0
            else 0.0,
        )
        for cat, spend in ranked[:5]
    ]

    # Outflow transaction count (separate small query — aggregation doesn't carry it).
    transaction_count = await collection.count_documents(
        {
            "user_id": params.user_id,
            "amount": {"$lt": 0},
            "date": {"$gte": range_from, "$lt": range_to_exclusive},
        }
    )

    # Goal snapshots.
    goals: list[GoalSnapshot] = []
    if params.include_goals:
        async for doc in goals_collection.find(
            {"user_id": params.user_id, "status": "active"}
        ):
            goals.append(_snapshot_goal(doc, as_of=as_of))

    paragraph = _format_paragraph(
        week_start=week_start,
        total_spend=total_spend,
        transaction_count=transaction_count,
        top_categories=top_categories,
        goals=goals,
    )

    return SummarizeWeekResult(
        user_id=params.user_id,
        week_start=week_start,
        week_end=week_end,
        total_spend=round(total_spend, 2),
        transaction_count=transaction_count,
        top_categories=top_categories,
        goals=goals,
        paragraph=paragraph,
    )
