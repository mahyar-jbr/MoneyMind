from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth.clerk import AuthenticatedUser, current_user
from app.db.client import get_database


router = APIRouter(prefix="/inbox", tags=["inbox"])


def _serialize_message(doc: dict[str, Any]) -> dict[str, Any]:
    message = dict(doc)
    message["id"] = str(message.pop("_id"))
    value = message.get("created_at")
    if isinstance(value, datetime):
        message["created_at"] = value.isoformat()
    return message


@router.get("")
async def list_inbox_messages(
    user: AuthenticatedUser = Depends(current_user),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    cursor = (
        get_database()
        .inbox_messages.find({"user_id": user.user_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    messages = []
    async for doc in cursor:
        messages.append(_serialize_message(doc))
    return {"user_id": user.user_id, "messages": messages}
