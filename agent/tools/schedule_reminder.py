"""Tool #19 — schedule_reminder.

Writes one reminder doc to the NEW atlas.reminders collection. Used for
one-off pings the user explicitly asked for, OR for agent-self-scheduled
follow-ups (different from interventions: no approval flow, no outcome).

DELIBERATE EXCEPTION TO CONVENTION 5: `fires_at` persists as a UTC-aware
datetime, NOT a naive midnight datetime. Every other date field in this
codebase represents a calendar day; `fires_at` represents an instant in
time the cron compares to "now" every tick. Naive datetimes plus a
cron running across timezones is exactly the kind of bug that ships to
production.

Write-only. Single insert_one. status="pending" on every write; the cron
(#21) flips it to "fired" and a future cancel_reminder tool flips it to
"cancelled".
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel, Field, model_validator

from agent.db.client import get_database


ReminderSource = Literal["user", "agent"]
PAST_GRACE_SECONDS = 5


class ScheduleReminderInput(BaseModel):
    user_id: str = Field(min_length=1)
    fires_at: datetime
    text: str = Field(min_length=3, max_length=200)
    source: ReminderSource
    related_intervention_id: str | None = None

    @model_validator(mode="after")
    def _normalize_and_validate_fires_at(self) -> "ScheduleReminderInput":
        """Coerce naive fires_at to UTC; reject past instants.

        Naive datetimes from the LLM are treated as UTC (the only sensible
        interpretation given the cron contract). A fires_at more than
        PAST_GRACE_SECONDS in the past at validation time is a bug — the
        LLM either resolved the wrong instant or did the wrong arithmetic.
        """
        if self.fires_at.tzinfo is None:
            self.fires_at = self.fires_at.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if self.fires_at < now - timedelta(seconds=PAST_GRACE_SECONDS):
            raise ValueError(
                f"fires_at is in the past ({self.fires_at.isoformat()} < "
                f"now {now.isoformat()})"
            )
        return self


class ScheduleReminderResult(BaseModel):
    reminder_id: str
    user_id: str
    fires_at: datetime
    text: str
    source: ReminderSource
    status: Literal["pending"]
    created_at: datetime


async def schedule_reminder(
    params: ScheduleReminderInput,
    *,
    collection=None,
) -> ScheduleReminderResult:
    """Schedule a one-off reminder to fire at a specific UTC instant.

    Use this when the user explicitly asks for a ping ("remind me to
    cancel the gym trial in 7 days") OR when you want to self-schedule
    a follow-up that isn't an intervention. For pattern-detected nudges
    with Accept/Decline + measurable outcomes, use propose_intervention
    instead.

    Pass fires_at as an absolute UTC datetime — resolve any "in N days"
    or "on the 25th" phrasing to a real instant at call time. The tool
    coerces naive datetimes to UTC and rejects past instants.
    """
    if collection is None:
        collection = get_database().reminders

    related_intervention_oid: ObjectId | None = None
    if params.related_intervention_id is not None:
        try:
            related_intervention_oid = ObjectId(params.related_intervention_id)
        except (InvalidId, TypeError) as exc:
            raise ValueError(
                f"related_intervention_id is not a valid ObjectId: "
                f"{params.related_intervention_id!r}"
            ) from exc

    created_at = datetime.now(UTC)
    doc = {
        "user_id": params.user_id,
        "fires_at": params.fires_at,
        "text": params.text,
        "source": params.source,
        "related_intervention_id": related_intervention_oid,
        "status": "pending",
        "created_at": created_at,
        "fired_at": None,
    }

    result = await collection.insert_one(doc)
    return ScheduleReminderResult(
        reminder_id=str(result.inserted_id),
        user_id=params.user_id,
        fires_at=params.fires_at,
        text=params.text,
        source=params.source,
        status="pending",
        created_at=created_at,
    )
