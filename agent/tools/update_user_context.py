"""Tool #15 — update_user_context.

Persists a piece of context the user just told the agent: a lifestyle,
event, preference, or constraint. Insert-only. Never updates or expires
prior contexts — the agent reconciles conflicts in its prompt, not by
silently rewriting history.
"""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from agent.db.client import get_database


ContextType = Literal["lifestyle", "event", "preference", "constraint"]


class UpdateUserContextInput(BaseModel):
    user_id: str = Field(min_length=1)
    text: str = Field(min_length=3, max_length=400)
    type: ContextType
    active_from: date | None = None  # defaults to today() inside the function
    active_until: date | None = None  # None = ongoing

    @model_validator(mode="after")
    def _active_range_valid(self) -> "UpdateUserContextInput":
        if (
            self.active_from is not None
            and self.active_until is not None
            and self.active_until < self.active_from
        ):
            raise ValueError("active_until must be on or after active_from")
        return self


class UpdateUserContextResult(BaseModel):
    context_id: str
    user_id: str
    type: ContextType
    text: str
    active_from: date
    active_until: date | None
    created_at: datetime


def _at_midnight(d: date) -> datetime:
    """Match the rest of the codebase: dates persist as naive midnight datetimes."""
    return datetime(d.year, d.month, d.day)


async def update_user_context(
    params: UpdateUserContextInput,
    *,
    collection=None,
) -> UpdateUserContextResult:
    """Save something the user just told the agent about themselves.

    Use this when the user states a lifestyle ("I'm bulking"), event
    ("exam week"), preference ("never round up"), or constraint ("can't
    spend after the 25th"). One call = one new context doc. Do NOT call
    this to "correct" a prior context — write a new one with the right
    date range and let the prompt reconcile.

    active_from defaults to today() when omitted. active_until=None means
    ongoing. Both bounds are inclusive.
    """
    if collection is None:
        collection = get_database().user_context

    af = params.active_from or date.today()
    au = params.active_until
    created_at = datetime.now(UTC)

    doc = {
        "user_id": params.user_id,
        "text": params.text,
        "type": params.type,
        "active_from": _at_midnight(af),
        "active_until": _at_midnight(au) if au is not None else None,
        "created_at": created_at,
    }

    result = await collection.insert_one(doc)
    return UpdateUserContextResult(
        context_id=str(result.inserted_id),
        user_id=params.user_id,
        type=params.type,
        text=params.text,
        active_from=af,
        active_until=au,
        created_at=created_at,
    )
