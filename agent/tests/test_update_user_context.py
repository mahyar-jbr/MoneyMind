"""Unit tests for update_user_context. All helpers via agent.tests._fakes (#14a)."""

import asyncio
from datetime import date, datetime, timedelta

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import get_database_tripwire, make_mongomock_collection
from agent.tools import update_user_context as update_user_context_module
from agent.tools.update_user_context import (
    UpdateUserContextInput,
    UpdateUserContextResult,
    update_user_context,
)


@pytest.fixture
async def user_context_coll():
    return make_mongomock_collection(collection_name="user_context")


def _input(**overrides):
    defaults = {
        "user_id": "u_482",
        "text": "I'm bulking this month — food spend will be high",
        "type": "lifestyle",
        "active_from": date(2026, 5, 1),
        "active_until": date(2026, 5, 31),
    }
    defaults.update(overrides)
    return UpdateUserContextInput(**defaults)


# ─── AC: persisted doc shape ────────────────────────────────────────


async def test_inserts_document_with_correct_shape(user_context_coll):
    result = await update_user_context(_input(), collection=user_context_coll)
    assert isinstance(result, UpdateUserContextResult)

    doc = await user_context_coll.find_one({"_id": ObjectId(result.context_id)})
    assert doc is not None
    assert set(doc.keys()) == {
        "_id",
        "user_id",
        "text",
        "type",
        "active_from",
        "active_until",
        "created_at",
    }
    assert doc["user_id"] == "u_482"
    assert doc["text"].startswith("I'm bulking")
    assert doc["type"] == "lifestyle"
    assert doc["active_from"] == datetime(2026, 5, 1)
    assert doc["active_until"] == datetime(2026, 5, 31)
    assert isinstance(doc["created_at"], datetime)


# ─── AC: active_from defaults to today() ────────────────────────────


async def test_active_from_defaults_to_today(user_context_coll):
    result = await update_user_context(
        _input(active_from=None, active_until=None),
        collection=user_context_coll,
    )
    assert result.active_from == date.today()
    doc = await user_context_coll.find_one({"_id": ObjectId(result.context_id)})
    today_midnight = datetime(date.today().year, date.today().month, date.today().day)
    assert doc["active_from"] == today_midnight


# ─── AC: active_until=None persists as None ─────────────────────────


async def test_active_until_none_persists_as_none(user_context_coll):
    result = await update_user_context(
        _input(active_until=None), collection=user_context_coll
    )
    doc = await user_context_coll.find_one({"_id": ObjectId(result.context_id)})
    assert doc["active_until"] is None


# ─── AC: date conversion ────────────────────────────────────────────


async def test_dates_persisted_as_naive_midnight_datetimes(user_context_coll):
    result = await update_user_context(_input(), collection=user_context_coll)
    doc = await user_context_coll.find_one({"_id": ObjectId(result.context_id)})
    assert isinstance(doc["active_from"], datetime)
    assert doc["active_from"].tzinfo is None  # naive
    assert doc["active_from"].time() == datetime.min.time()  # midnight
    assert isinstance(doc["active_until"], datetime)
    assert doc["active_until"].tzinfo is None
    assert doc["active_until"].time() == datetime.min.time()


# ─── AC: created_at server-stamped ──────────────────────────────────


async def test_created_at_is_server_stamped(user_context_coll):
    r1 = await update_user_context(_input(text="first ctx"), collection=user_context_coll)
    await asyncio.sleep(0.01)
    r2 = await update_user_context(_input(text="second ctx"), collection=user_context_coll)
    assert r1.created_at < r2.created_at
    assert r1.created_at.tzinfo is not None  # UTC-aware


# ─── AC: each call inserts a new doc (no update/supersede) ──────────


async def test_each_call_inserts_new_document(user_context_coll):
    r1 = await update_user_context(
        _input(text="bulking through May", active_until=date(2026, 5, 31)),
        collection=user_context_coll,
    )
    r2 = await update_user_context(
        _input(text="cutting through June", active_until=date(2026, 6, 30)),
        collection=user_context_coll,
    )
    assert r1.context_id != r2.context_id
    count = await user_context_coll.count_documents({"user_id": "u_482"})
    assert count == 2
    # First doc was NOT modified — text still "bulking through May"
    first_doc = await user_context_coll.find_one({"_id": ObjectId(r1.context_id)})
    assert first_doc["text"] == "bulking through May"


# ─── AC: user isolation persisted ───────────────────────────────────


async def test_user_id_persisted(user_context_coll):
    await update_user_context(_input(user_id="u_alpha"), collection=user_context_coll)
    await update_user_context(_input(user_id="u_beta"), collection=user_context_coll)
    assert await user_context_coll.count_documents({"user_id": "u_alpha"}) == 1
    assert await user_context_coll.count_documents({"user_id": "u_beta"}) == 1


# ─── AC: past-dated active_from is allowed ──────────────────────────


async def test_past_active_from_allowed(user_context_coll):
    past = date.today() - timedelta(days=365)
    result = await update_user_context(
        _input(active_from=past, active_until=None),
        collection=user_context_coll,
    )
    assert result.active_from == past


# ─── AC: tripwire — no fallback to global db handle ─────────────────


async def test_no_modification_of_other_collections(user_context_coll, monkeypatch):
    """If the tool ever falls back to get_database(), the test fails loud."""
    with get_database_tripwire(monkeypatch, update_user_context_module):
        await update_user_context(_input(), collection=user_context_coll)
    assert await user_context_coll.count_documents({}) == 1


# ─── Validation ─────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        UpdateUserContextInput(user_id="", text="something valid", type="event")


def test_validation_text_too_short():
    with pytest.raises(ValidationError):
        UpdateUserContextInput(user_id="u_482", text="ab", type="event")


def test_validation_text_too_long():
    with pytest.raises(ValidationError):
        UpdateUserContextInput(user_id="u_482", text="x" * 401, type="event")


def test_validation_invalid_type():
    with pytest.raises(ValidationError):
        UpdateUserContextInput(
            user_id="u_482", text="something valid", type="invalid"
        )


def test_validation_active_until_before_active_from():
    with pytest.raises(ValidationError):
        UpdateUserContextInput(
            user_id="u_482",
            text="something valid",
            type="event",
            active_from=date(2026, 5, 31),
            active_until=date(2026, 5, 1),
        )


def test_validation_active_until_equal_to_active_from_ok():
    """Equal dates are valid — context active on a single day."""
    inp = UpdateUserContextInput(
        user_id="u_482",
        text="something valid",
        type="event",
        active_from=date(2026, 5, 15),
        active_until=date(2026, 5, 15),
    )
    assert inp.active_from == inp.active_until


