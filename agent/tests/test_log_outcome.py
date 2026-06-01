"""Unit tests for log_outcome. All helpers via agent.tests._fakes (#14a)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import get_database_tripwire, make_mongomock_collection
from agent.tools import log_outcome as log_outcome_module
from agent.tools.log_outcome import (
    LogOutcomeInput,
    LogOutcomeResult,
    log_outcome,
)


@pytest.fixture
async def outcomes_coll():
    return make_mongomock_collection(collection_name="outcomes")


def _input(**overrides):
    defaults = {
        "user_id": "u_482",
        "intervention_id": str(ObjectId()),
        "window_days": 14,
        "metric": "weekly_food_spend",
        "before": 180.0,
        "after": 118.5,
        "agent_judgment": "successful",
    }
    defaults.update(overrides)
    return LogOutcomeInput(**defaults)


# ─── AC: persisted doc shape ────────────────────────────────────────


async def test_inserts_document_with_correct_shape(outcomes_coll):
    result = await log_outcome(_input(), collection=outcomes_coll)
    assert isinstance(result, LogOutcomeResult)
    doc = await outcomes_coll.find_one({"_id": ObjectId(result.outcome_id)})
    assert doc is not None
    expected_keys = {
        "_id", "intervention_id", "user_id", "measured_at", "window_days",
        "metric", "before", "after", "delta_pct", "agent_judgment",
    }
    assert set(doc.keys()) == expected_keys


# ─── AC: delta_pct computed server-side, not accepted as input ──────


def test_delta_pct_computed_server_side():
    """The input model must not accept delta_pct — it's derived."""
    assert "delta_pct" not in LogOutcomeInput.model_fields


# ─── AC: delta_pct formula (3 cases per ticket) ─────────────────────


async def test_delta_pct_negative_change(outcomes_coll):
    """before=180, after=118.50 → -34.17%"""
    result = await log_outcome(
        _input(before=180.0, after=118.5), collection=outcomes_coll
    )
    assert result.delta_pct == -34.17
    doc = await outcomes_coll.find_one({"_id": ObjectId(result.outcome_id)})
    assert doc["delta_pct"] == -34.17


async def test_delta_pct_positive_change(outcomes_coll):
    """before=50, after=80 → +60.0%"""
    result = await log_outcome(
        _input(before=50.0, after=80.0), collection=outcomes_coll
    )
    assert result.delta_pct == 60.0


async def test_delta_pct_uses_abs_before_for_sign(outcomes_coll):
    """before=-100, after=-50 → +50.0 (direction-of-change, not raw ratio)"""
    result = await log_outcome(
        _input(before=-100.0, after=-50.0), collection=outcomes_coll
    )
    assert result.delta_pct == 50.0


# ─── AC: before=0 → delta_pct=0.0 (no division error) ───────────────


async def test_delta_pct_zero_when_before_is_zero(outcomes_coll):
    result = await log_outcome(
        _input(before=0.0, after=42.0), collection=outcomes_coll
    )
    assert result.delta_pct == 0.0


# ─── AC: measured_at server-stamped UTC ─────────────────────────────


async def test_measured_at_is_server_stamped(outcomes_coll):
    r1 = await log_outcome(_input(), collection=outcomes_coll)
    await asyncio.sleep(0.01)
    r2 = await log_outcome(_input(), collection=outcomes_coll)
    assert r1.measured_at < r2.measured_at
    assert r1.measured_at.tzinfo is not None  # UTC-aware


async def test_measured_at_is_recent(outcomes_coll):
    before = datetime.now(UTC)
    result = await log_outcome(_input(), collection=outcomes_coll)
    after = datetime.now(UTC)
    assert before - timedelta(seconds=1) <= result.measured_at <= after + timedelta(seconds=1)


# ─── AC: intervention_id persisted as ObjectId, not string ──────────


async def test_intervention_id_persisted_as_objectid(outcomes_coll):
    intervention_id = str(ObjectId())
    result = await log_outcome(
        _input(intervention_id=intervention_id), collection=outcomes_coll
    )
    doc = await outcomes_coll.find_one({"_id": ObjectId(result.outcome_id)})
    assert isinstance(doc["intervention_id"], ObjectId)
    assert str(doc["intervention_id"]) == intervention_id


# ─── AC: invalid intervention_id raises BEFORE DB hit ───────────────


async def test_invalid_intervention_id_raises_before_db(outcomes_coll, monkeypatch):
    """Tripwire pattern: monkeypatch insert_one, assert never called."""
    called = []
    orig_insert_one = outcomes_coll.insert_one

    async def _watching_insert(*a, **kw):
        called.append((a, kw))
        return await orig_insert_one(*a, **kw)

    monkeypatch.setattr(outcomes_coll, "insert_one", _watching_insert)
    with pytest.raises(ValueError, match="not a valid ObjectId"):
        await log_outcome(
            _input(intervention_id="not-an-objectid"), collection=outcomes_coll
        )
    assert called == [], "DB insert was attempted with an invalid intervention_id"


# ─── AC: all 4 judgments accepted ───────────────────────────────────


async def test_all_four_judgments_accepted(outcomes_coll):
    for j in ("successful", "partial", "failed", "inconclusive"):
        result = await log_outcome(
            _input(agent_judgment=j), collection=outcomes_coll
        )
        doc = await outcomes_coll.find_one({"_id": ObjectId(result.outcome_id)})
        assert doc["agent_judgment"] == j


# ─── AC: user isolation ─────────────────────────────────────────────


async def test_user_id_persisted(outcomes_coll):
    await log_outcome(_input(user_id="u_alpha"), collection=outcomes_coll)
    await log_outcome(_input(user_id="u_beta"), collection=outcomes_coll)
    assert await outcomes_coll.count_documents({"user_id": "u_alpha"}) == 1
    assert await outcomes_coll.count_documents({"user_id": "u_beta"}) == 1


# ─── Validation ─────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        LogOutcomeInput(
            user_id="",
            intervention_id=str(ObjectId()),
            window_days=14,
            metric="m",
            before=0,
            after=0,
            agent_judgment="successful",
        )


def test_validation_empty_intervention_id():
    with pytest.raises(ValidationError):
        LogOutcomeInput(
            user_id="u_482",
            intervention_id="",
            window_days=14,
            metric="m",
            before=0,
            after=0,
            agent_judgment="successful",
        )


def test_validation_empty_metric():
    with pytest.raises(ValidationError):
        LogOutcomeInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            window_days=14,
            metric="",
            before=0,
            after=0,
            agent_judgment="successful",
        )


def test_validation_metric_too_long():
    with pytest.raises(ValidationError):
        LogOutcomeInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            window_days=14,
            metric="x" * 81,
            before=0,
            after=0,
            agent_judgment="successful",
        )


def test_validation_window_days_zero():
    with pytest.raises(ValidationError):
        LogOutcomeInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            window_days=0,
            metric="m",
            before=0,
            after=0,
            agent_judgment="successful",
        )


def test_validation_window_days_too_large():
    with pytest.raises(ValidationError):
        LogOutcomeInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            window_days=366,
            metric="m",
            before=0,
            after=0,
            agent_judgment="successful",
        )


def test_validation_invalid_judgment():
    with pytest.raises(ValidationError):
        LogOutcomeInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            window_days=14,
            metric="m",
            before=0,
            after=0,
            agent_judgment="invalid",
        )


# ─── Tripwire (#14 pattern) ─────────────────────────────────────────


async def test_no_modification_of_other_collections(outcomes_coll, monkeypatch):
    """Any silent fallback to the global db handle must fail loud."""
    with get_database_tripwire(monkeypatch, log_outcome_module):
        await log_outcome(_input(), collection=outcomes_coll)
    assert await outcomes_coll.count_documents({}) == 1
