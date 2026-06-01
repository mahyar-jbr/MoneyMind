"""Unit tests for check_goal_pace. All helpers via agent.tests._fakes (#14a)."""

from datetime import date, datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import get_database_tripwire, make_mongomock_collection
from agent.tools import check_goal_pace as check_goal_pace_module
from agent.tools.check_goal_pace import (
    CheckGoalPaceInput,
    CheckGoalPaceResult,
    check_goal_pace,
)


@pytest.fixture
async def goals_coll():
    return make_mongomock_collection(collection_name="goals")


async def _seed(coll, **overrides):
    """Insert one goal doc, return its goal_id string."""
    defaults = {
        "_id": ObjectId(),
        "user_id": "u_482",
        "title": "Emergency Fund",
        "target_amount": 8000.0,
        "current_amount": 2400.0,
        "target_date": datetime(2026, 12, 31),
        "pace_check": "weekly",
        "status": "active",
        "created_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    await coll.insert_one(defaults)
    return str(defaults["_id"])


# ─── round-trip ─────────────────────────────────────────────────────


async def test_persisted_fields_round_trip(goals_coll):
    goal_id = await _seed(goals_coll)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 6, 1)),
        collection=goals_coll,
    )
    assert isinstance(result, CheckGoalPaceResult)
    assert result.user_id == "u_482"
    assert result.goal_id == goal_id
    assert result.title == "Emergency Fund"
    assert result.target_amount == 8000.0
    assert result.current_amount == 2400.0
    assert result.target_date == date(2026, 12, 31)
    assert result.as_of == date(2026, 6, 1)
    assert isinstance(result.note, str) and result.note  # always non-empty


# ─── verdicts ───────────────────────────────────────────────────────


async def test_verdict_ahead(goals_coll):
    # 41.6% elapsed × $8000 = ~$3,328 expected. Set current way above that.
    goal_id = await _seed(goals_coll, current_amount=5000.0)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 6, 1)),
        collection=goals_coll,
    )
    assert result.verdict == "ahead"
    assert result.delta_pct > 5.0
    assert "ahead of pace" in result.note


async def test_verdict_on_track_in_tolerance_band(goals_coll):
    # Expected ~$3,328 at 2026-06-01; current $3,400 → +2.2% (inside ±5%).
    goal_id = await _seed(goals_coll, current_amount=3400.0)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 6, 1)),
        collection=goals_coll,
    )
    assert result.verdict == "on_track"
    assert abs(result.delta_pct) < 5.0


async def test_verdict_behind(goals_coll):
    goal_id = await _seed(goals_coll, current_amount=2400.0)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 6, 1)),
        collection=goals_coll,
    )
    assert result.verdict == "behind"
    assert result.delta_pct < -5.0
    assert "behind pace" in result.note


async def test_verdict_complete_status(goals_coll):
    goal_id = await _seed(goals_coll, status="complete", current_amount=8000.0)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 6, 1)),
        collection=goals_coll,
    )
    assert result.verdict == "complete"
    assert "complete" in result.note
    assert "8000" in result.note


async def test_verdict_abandoned_status(goals_coll):
    goal_id = await _seed(goals_coll, status="abandoned")
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 6, 1)),
        collection=goals_coll,
    )
    assert result.verdict == "abandoned"
    assert result.note == "Emergency Fund: abandoned."


async def test_verdict_paused_returns_paused_but_computes_delta(goals_coll):
    goal_id = await _seed(goals_coll, status="paused", current_amount=2400.0)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 6, 1)),
        collection=goals_coll,
    )
    assert result.verdict == "paused"
    # delta is still computed for informational reply
    assert result.expected_amount > 0
    assert result.delta_pct != 0  # would be ~-28% behind
    assert "paused" in result.note
    assert "vs. pace" in result.note


async def test_verdict_past_due(goals_coll):
    # Past target_date with current still below target.
    goal_id = await _seed(goals_coll, current_amount=2400.0)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2027, 1, 15)),
        collection=goals_coll,
    )
    assert result.verdict == "past_due"
    assert "past due" in result.note
    assert "5600" in result.note  # 8000 - 2400 = 5600 short


async def test_verdict_not_started_when_as_of_equals_created_at(goals_coll):
    goal_id = await _seed(goals_coll)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 1, 1)),
        collection=goals_coll,
    )
    assert result.verdict == "not_started"
    assert "just started" in result.note


# ─── divide-by-zero guard ───────────────────────────────────────────


async def test_delta_pct_zero_when_expected_is_zero(goals_coll):
    # When elapsed_days == 0, frac == 0, expected_amount == 0 → delta_pct = 0.
    goal_id = await _seed(goals_coll, current_amount=0.0)
    result = await check_goal_pace(
        CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 1, 1)),
        collection=goals_coll,
    )
    assert result.expected_amount == 0.0
    assert result.delta_pct == 0.0
    assert result.verdict == "not_started"


# ─── user isolation ─────────────────────────────────────────────────


async def test_user_isolation(goals_coll):
    """A goal with matching _id but different user_id must not be returned."""
    shared_id = ObjectId()
    await goals_coll.insert_one({
        "_id": shared_id, "user_id": "u_other", "title": "Their goal",
        "target_amount": 8000.0, "current_amount": 0.0,
        "target_date": datetime(2026, 12, 31), "pace_check": "weekly",
        "status": "active", "created_at": datetime(2026, 1, 1),
    })
    with pytest.raises(LookupError):
        await check_goal_pace(
            CheckGoalPaceInput(user_id="u_482", goal_id=str(shared_id)),
            collection=goals_coll,
        )


# ─── error paths ────────────────────────────────────────────────────


async def test_invalid_objectid_raises_value_error_before_db(goals_coll, monkeypatch):
    """Invalid ObjectId must raise ValueError BEFORE any DB call."""
    # Tripwire find_one — if the tool gets there with an invalid id, we want to know.
    called = []
    orig_find_one = goals_coll.find_one

    async def _watching_find_one(*a, **kw):
        called.append((a, kw))
        return await orig_find_one(*a, **kw)

    monkeypatch.setattr(goals_coll, "find_one", _watching_find_one)
    with pytest.raises(ValueError, match="not a valid ObjectId"):
        await check_goal_pace(
            CheckGoalPaceInput(user_id="u_482", goal_id="not-an-objectid"),
            collection=goals_coll,
        )
    assert called == [], "DB was queried with an invalid ObjectId"


async def test_missing_goal_raises_lookup_error(goals_coll):
    missing_id = str(ObjectId())
    with pytest.raises(LookupError, match="not found"):
        await check_goal_pace(
            CheckGoalPaceInput(user_id="u_482", goal_id=missing_id),
            collection=goals_coll,
        )


# ─── validation ─────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        CheckGoalPaceInput(user_id="", goal_id=str(ObjectId()))


def test_validation_empty_goal_id():
    with pytest.raises(ValidationError):
        CheckGoalPaceInput(user_id="u_482", goal_id="")


# ─── tripwire (#14 pattern) ─────────────────────────────────────────


async def test_no_modification_of_other_collections(goals_coll, monkeypatch):
    """Any silent fallback to the global db handle must fail loud."""
    goal_id = await _seed(goals_coll)
    with get_database_tripwire(monkeypatch, check_goal_pace_module):
        await check_goal_pace(
            CheckGoalPaceInput(user_id="u_482", goal_id=goal_id, as_of=date(2026, 6, 1)),
            collection=goals_coll,
        )
    # Doc count unchanged: tool is read-only.
    assert await goals_coll.count_documents({}) == 1
