from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from app.aggregations.weekly import weekly_spend_by_category
from app.db.client import get_database


router = APIRouter(prefix="/agg", tags=["aggregations"])


def parse_date_param(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be YYYY-MM-DD") from exc


@router.get("/weekly")
async def get_weekly_spend(
    user_id: str = Query("u_482"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    category: str | None = None,
) -> dict:
    weeks = await weekly_spend_by_category(
        get_database(),
        user_id=user_id,
        date_from=parse_date_param(date_from, "from"),
        date_to=parse_date_param(date_to, "to"),
        category=category,
    )
    return {"user_id": user_id, "weeks": weeks}

