from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.aggregations.weekly import weekly_spend_by_category
from app.db.client import get_database


router = APIRouter(prefix="/agg", tags=["aggregations"])


def parse_date_param(value: str | None, field_name: str, *, upper_bound: bool = False) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be YYYY-MM-DD") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)

    if upper_bound and len(value) == 10:
        parsed += timedelta(days=1)
    return parsed


@router.get("/weekly")
async def get_weekly_spend(
    user_id: str = Query(...),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    category: str | None = None,
) -> dict:
    weeks = await weekly_spend_by_category(
        get_database(),
        user_id=user_id,
        date_from=parse_date_param(date_from, "from"),
        date_to_exclusive=parse_date_param(date_to, "to", upper_bound=True),
        category=category,
    )
    return {"user_id": user_id, "weeks": weeks}
