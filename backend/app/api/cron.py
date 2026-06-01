import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth.clerk import AuthenticatedUser, current_user
from app.cron.reminders import fire_due_reminders
from app.cron.weekly_summary import post_weekly_summary
from app.db.client import get_database


router = APIRouter(prefix="/cron", tags=["cron"])


@router.post("/weekly-summary")
async def run_weekly_summary_cron(
    user: AuthenticatedUser = Depends(current_user),
) -> dict:
    try:
        return await post_weekly_summary(
            get_database(),
            user_id=user.user_id,
            user_token=user.token,
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Agent weekly summary failed: {exc}",
        ) from exc


@router.post("/reminders")
async def run_reminder_cron(
    user: AuthenticatedUser = Depends(current_user),
) -> dict:
    return await fire_due_reminders(get_database(), user_id=user.user_id)
