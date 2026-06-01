"""Active-user-context fetcher + formatter for the graph's system message.

Per docs/data-model.md § user_context and decisions.md (#15-close):
a context is "active on date D" iff
    active_from <= D AND (active_until IS NULL OR active_until >= D)
both bounds inclusive. The graph injects active context into the system
message on every turn so the LLM sees it BEFORE deciding whether to call
get_spend_anomaly or fire any other interpretation.

Read-only. No writes. No side effects.
"""

from datetime import date, datetime

from agent.db.client import get_database


def _at_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


async def fetch_active_context(
    user_id: str,
    *,
    as_of: date | None = None,
    collection=None,
) -> list[dict]:
    """Return user_context docs active on `as_of` (defaults to today)."""
    if collection is None:
        collection = get_database().user_context
    target = _at_midnight(as_of or date.today())
    cursor = collection.find(
        {
            "user_id": user_id,
            "active_from": {"$lte": target},
            "$or": [
                {"active_until": None},
                {"active_until": {"$gte": target}},
            ],
        }
    )
    return [doc async for doc in cursor]


def format_active_context(docs: list[dict]) -> str:
    """Format active context docs as a prompt-ready string.

    Returns "" when there are no active contexts so the system-message
    builder can simply not prepend anything.
    """
    if not docs:
        return ""

    lines = ["Active context for the user:"]
    for d in docs:
        type_ = d.get("type", "context")
        text = d.get("text", "").strip()
        active_from = d.get("active_from")
        active_until = d.get("active_until")
        if isinstance(active_from, datetime):
            active_from = active_from.date()
        if isinstance(active_until, datetime):
            active_until = active_until.date()
        range_part = (
            f"(since {active_from.isoformat()}, ongoing)"
            if active_until is None
            else f"(until {active_until.isoformat()})"
        )
        lines.append(f"- {type_}: {text} {range_part}")
    return "\n".join(lines)
