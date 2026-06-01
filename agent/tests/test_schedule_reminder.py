"""Unit tests for schedule_reminder. All helpers via agent.tests._fakes (#14a)."""

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import get_database_tripwire, make_mongomock_collection
from agent.tools import schedule_reminder as schedule_reminder_module
from agent.tools.schedule_reminder import (
    ScheduleReminderInput,
    ScheduleReminderResult,
    schedule_reminder,
)


@pytest.fixture
async def reminders_coll():
    return make_mongomock_collection(collection_name="reminders")


def _future(seconds: int = 3600) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _input(**overrides):
    defaults = {
        "user_id": "u_482",
        "fires_at": _future(7 * 86400),
        "text": "cancel the gym trial",
        "source": "user",
        "related_intervention_id": None,
    }
    defaults.update(overrides)
    return ScheduleReminderInput(**defaults)


# ─── AC: persisted doc shape ────────────────────────────────────────


async def test_inserts_document_with_correct_shape(reminders_coll):
    result = await schedule_reminder(_input(), collection=reminders_coll)
    assert isinstance(result, ScheduleReminderResult)

    doc = await reminders_coll.find_one({"_id": ObjectId(result.reminder_id)})
    assert doc is not None
    expected_keys = {
        "_id", "user_id", "fires_at", "text", "source",
        "related_intervention_id", "status", "created_at", "fired_at",
    }
    assert set(doc.keys()) == expected_keys


# ─── AC: fires_at persists as UTC-aware ─────────────────────────────


async def test_fires_at_persisted_as_utc_instant(reminders_coll):
    """Mongo (both Atlas and mongomock) strips tzinfo on store but preserves
    the UTC instant. The CONTRACT is: input is UTC-aware → result is
    UTC-aware → stored doc reads back as a naive datetime equal to the
    same UTC wall-clock. This is the same behavior real Atlas exhibits
    when tz_aware is unset on the client."""
    target = datetime.now(UTC) + timedelta(days=1)
    result = await schedule_reminder(
        _input(fires_at=target), collection=reminders_coll
    )
    # In-process result: UTC-aware.
    assert result.fires_at.tzinfo == UTC
    # Persisted: tz-stripped, same wall-clock instant.
    doc = await reminders_coll.find_one({"_id": ObjectId(result.reminder_id)})
    assert isinstance(doc["fires_at"], datetime)
    # Compare by stripping tz + microseconds — Mongo stores to ms precision.
    assert doc["fires_at"].replace(tzinfo=None, microsecond=0) == target.replace(
        tzinfo=None, microsecond=0
    )


# ─── AC: naive coerced to UTC ───────────────────────────────────────


async def test_naive_fires_at_coerced_to_utc(reminders_coll):
    naive = (datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None)
    result = await schedule_reminder(
        _input(fires_at=naive), collection=reminders_coll
    )
    # Result must be tz-aware after coercion.
    assert result.fires_at.tzinfo == UTC


# ─── AC: past fires_at raises BEFORE DB call ────────────────────────


async def test_past_fires_at_raises_before_db(reminders_coll, monkeypatch):
    """Tripwire: monkeypatch insert_one, assert never called when fires_at past."""
    called = []
    orig_insert_one = reminders_coll.insert_one

    async def _watching_insert(*a, **kw):
        called.append((a, kw))
        return await orig_insert_one(*a, **kw)

    monkeypatch.setattr(reminders_coll, "insert_one", _watching_insert)
    past = datetime.now(UTC) - timedelta(minutes=10)
    with pytest.raises(ValidationError, match="in the past"):
        ScheduleReminderInput(
            user_id="u_482",
            fires_at=past,
            text="too late",
            source="user",
        )
    assert called == [], "DB insert was attempted with a past fires_at"


# ─── AC: status/fired_at/created_at on insert ───────────────────────


async def test_status_pending_fired_at_null_created_at_recent(reminders_coll):
    before = datetime.now(UTC)
    result = await schedule_reminder(_input(), collection=reminders_coll)
    after = datetime.now(UTC)

    assert result.status == "pending"
    assert result.created_at.tzinfo is not None
    assert before - timedelta(seconds=1) <= result.created_at <= after + timedelta(seconds=1)

    doc = await reminders_coll.find_one({"_id": ObjectId(result.reminder_id)})
    assert doc["status"] == "pending"
    assert doc["fired_at"] is None


# ─── AC: both source values ─────────────────────────────────────────


async def test_both_source_values_accepted(reminders_coll):
    for src in ("user", "agent"):
        result = await schedule_reminder(_input(source=src), collection=reminders_coll)
        doc = await reminders_coll.find_one({"_id": ObjectId(result.reminder_id)})
        assert doc["source"] == src


# ─── AC: related_intervention_id paths ──────────────────────────────


async def test_related_intervention_none_persists_as_none(reminders_coll):
    result = await schedule_reminder(
        _input(related_intervention_id=None), collection=reminders_coll
    )
    doc = await reminders_coll.find_one({"_id": ObjectId(result.reminder_id)})
    assert doc["related_intervention_id"] is None


async def test_related_intervention_persisted_as_objectid(reminders_coll):
    intervention_id = ObjectId()
    result = await schedule_reminder(
        _input(related_intervention_id=str(intervention_id)),
        collection=reminders_coll,
    )
    doc = await reminders_coll.find_one({"_id": ObjectId(result.reminder_id)})
    assert isinstance(doc["related_intervention_id"], ObjectId)
    assert doc["related_intervention_id"] == intervention_id


async def test_invalid_related_intervention_raises_before_db(
    reminders_coll, monkeypatch
):
    """Invalid ObjectId → ValueError BEFORE the DB insert hits."""
    called = []
    orig_insert_one = reminders_coll.insert_one

    async def _watching_insert(*a, **kw):
        called.append((a, kw))
        return await orig_insert_one(*a, **kw)

    monkeypatch.setattr(reminders_coll, "insert_one", _watching_insert)
    with pytest.raises(ValueError, match="not a valid ObjectId"):
        await schedule_reminder(
            _input(related_intervention_id="not-an-objectid"),
            collection=reminders_coll,
        )
    assert called == [], "DB insert was attempted with an invalid related_intervention_id"


# ─── AC: user isolation ─────────────────────────────────────────────


async def test_user_id_persisted(reminders_coll):
    await schedule_reminder(_input(user_id="u_alpha"), collection=reminders_coll)
    await schedule_reminder(_input(user_id="u_beta"), collection=reminders_coll)
    assert await reminders_coll.count_documents({"user_id": "u_alpha"}) == 1
    assert await reminders_coll.count_documents({"user_id": "u_beta"}) == 1


# ─── Validation ─────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        ScheduleReminderInput(
            user_id="", fires_at=_future(), text="something valid", source="user"
        )


def test_validation_text_too_short():
    with pytest.raises(ValidationError):
        ScheduleReminderInput(
            user_id="u_482", fires_at=_future(), text="ab", source="user"
        )


def test_validation_text_too_long():
    with pytest.raises(ValidationError):
        ScheduleReminderInput(
            user_id="u_482", fires_at=_future(), text="x" * 201, source="user"
        )


def test_validation_invalid_source():
    with pytest.raises(ValidationError):
        ScheduleReminderInput(
            user_id="u_482", fires_at=_future(), text="something valid", source="invalid"
        )


def test_validation_past_fires_at_raises_validation_error():
    """Belt-and-suspenders: past fires_at at construction → ValidationError."""
    with pytest.raises(ValidationError, match="in the past"):
        ScheduleReminderInput(
            user_id="u_482",
            fires_at=datetime.now(UTC) - timedelta(hours=1),
            text="too late",
            source="user",
        )


# ─── Tripwire (#14 pattern) ─────────────────────────────────────────


async def test_no_modification_of_other_collections(reminders_coll, monkeypatch):
    """Any silent fallback to the global db handle must fail loud."""
    with get_database_tripwire(monkeypatch, schedule_reminder_module):
        await schedule_reminder(_input(), collection=reminders_coll)
    assert await reminders_coll.count_documents({}) == 1
