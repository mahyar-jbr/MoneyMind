import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


FetchSummary = Callable[[str, str], Awaitable[str]]


def _week_bounds(now: datetime) -> tuple[datetime, datetime]:
    now_utc = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
    monday = now_utc.date() - timedelta(days=now_utc.date().weekday())
    week_start = datetime(monday.year, monday.month, monday.day, tzinfo=UTC)
    return week_start, week_start + timedelta(days=7)


async def fetch_agent_weekly_summary(user_id: str, agent_url: str) -> str:
    prompt = (
        "Create my weekly MoneyMind inbox summary. Use summarize_week, "
        "then reply with only the final summary paragraph."
    )
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{agent_url.rstrip('/')}/chat",
            headers={"X-MoneyMind-User-Id": user_id},
            json={"message": prompt},
        ) as response:
            response.raise_for_status()
            chunks = [chunk async for chunk in response.aiter_text()]

    summary = "".join(chunks).strip()
    if not summary:
        raise RuntimeError("agent returned an empty weekly summary")
    return summary


async def post_weekly_summary(
    db: Any,
    *,
    user_id: str,
    now: datetime | None = None,
    agent_url: str | None = None,
    fetch_summary: FetchSummary | None = None,
) -> dict:
    now = now or datetime.now(UTC)
    week_start, week_end_exclusive = _week_bounds(now)
    week_key = week_start.date().isoformat()

    existing = await db.inbox_messages.find_one(
        {
            "user_id": user_id,
            "type": "weekly_summary",
            "metadata.week_start": week_key,
        }
    )
    if existing:
        return {
            "created": False,
            "message_id": str(existing["_id"]),
            "week_start": week_key,
        }

    fetcher = fetch_summary or fetch_agent_weekly_summary
    summary = await fetcher(
        user_id,
        agent_url or os.getenv("AGENT_URL", "http://localhost:8001"),
    )

    doc = {
        "user_id": user_id,
        "type": "weekly_summary",
        "title": "Weekly MoneyMind summary",
        "body": summary,
        "created_at": now,
        "metadata": {
            "week_start": week_key,
            "week_end_exclusive": week_end_exclusive.date().isoformat(),
            "source": "user_triggered_weekly_summary",
        },
    }
    result = await db.inbox_messages.insert_one(doc)
    return {
        "created": True,
        "message_id": str(result.inserted_id),
        "week_start": week_key,
    }
