"""Unit tests for propose_intervention. All helpers via agent.tests._fakes (#14a)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import get_database_tripwire, make_mongomock_collection
from agent.tools import propose_intervention as propose_intervention_module
from agent.tools.propose_intervention import (
    ProposeInterventionInput,
    ProposeInterventionResult,
    ProposeInterventionTrigger,
    propose_intervention,
)


@pytest.fixture
async def interventions_coll():
    return make_mongomock_collection(collection_name="interventions")


def _input(**overrides):
    defaults = {
        "user_id": "u_482",
        "type": "reminder",
        "params": {"day": "sunday", "what": "meal prep"},
        "triggered_by": ProposeInterventionTrigger(
            tool="get_spend_anomaly",
            input={"category": "food.delivery", "window_days": 7},
        ),
        "related_memory_id": None,
    }
    defaults.update(overrides)
    return ProposeInterventionInput(**defaults)


# ─── AC: doc shape ──────────────────────────────────────────────────


async def test_inserts_document_with_correct_shape(interventions_coll):
    result = await propose_intervention(_input(), collection=interventions_coll)
    assert isinstance(result, ProposeInterventionResult)

    doc = await interventions_coll.find_one({"_id": ObjectId(result.intervention_id)})
    assert doc is not None
    expected_keys = {
        "_id", "user_id", "proposed_at", "triggered_by", "type", "params",
        "user_response", "responded_at", "related_memory", "status",
    }
    assert set(doc.keys()) == expected_keys


# ─── AC: proposed_at is server-stamped UTC ──────────────────────────


async def test_proposed_at_is_server_stamped(interventions_coll):
    r1 = await propose_intervention(_input(), collection=interventions_coll)
    await asyncio.sleep(0.01)
    r2 = await propose_intervention(_input(), collection=interventions_coll)
    assert r1.proposed_at < r2.proposed_at
    assert r1.proposed_at.tzinfo is not None  # UTC-aware


# ─── AC: user_response + responded_at null on insert ────────────────


async def test_user_response_and_responded_at_are_null(interventions_coll):
    result = await propose_intervention(_input(), collection=interventions_coll)
    doc = await interventions_coll.find_one({"_id": ObjectId(result.intervention_id)})
    assert doc["user_response"] is None
    assert doc["responded_at"] is None


# ─── AC: status is "pending" on insert ──────────────────────────────


async def test_status_is_pending_on_insert(interventions_coll):
    result = await propose_intervention(_input(), collection=interventions_coll)
    assert result.status == "pending"
    doc = await interventions_coll.find_one({"_id": ObjectId(result.intervention_id)})
    assert doc["status"] == "pending"


# ─── AC: all 4 types accepted ───────────────────────────────────────


async def test_all_four_types_accepted(interventions_coll):
    for t in ("cap", "reminder", "swap_suggestion", "reflection"):
        result = await propose_intervention(
            _input(type=t), collection=interventions_coll
        )
        doc = await interventions_coll.find_one({"_id": ObjectId(result.intervention_id)})
        assert doc["type"] == t


# ─── AC: triggered_by persisted ─────────────────────────────────────


async def test_triggered_by_persisted(interventions_coll):
    trigger = ProposeInterventionTrigger(
        tool="get_spend_anomaly",
        input={"category": "food.delivery", "window_days": 7},
    )
    result = await propose_intervention(
        _input(triggered_by=trigger), collection=interventions_coll
    )
    doc = await interventions_coll.find_one({"_id": ObjectId(result.intervention_id)})
    assert doc["triggered_by"]["tool"] == "get_spend_anomaly"
    assert doc["triggered_by"]["input"] == {
        "category": "food.delivery",
        "window_days": 7,
    }


# ─── AC: related_memory handling ────────────────────────────────────


async def test_related_memory_none_persists_as_none(interventions_coll):
    result = await propose_intervention(
        _input(related_memory_id=None), collection=interventions_coll
    )
    doc = await interventions_coll.find_one({"_id": ObjectId(result.intervention_id)})
    assert doc["related_memory"] is None


async def test_related_memory_persisted_as_objectid(interventions_coll):
    memory_id = ObjectId()
    result = await propose_intervention(
        _input(related_memory_id=str(memory_id)),
        collection=interventions_coll,
    )
    doc = await interventions_coll.find_one({"_id": ObjectId(result.intervention_id)})
    assert isinstance(doc["related_memory"], ObjectId)
    assert doc["related_memory"] == memory_id


# ─── AC: invalid related_memory raises BEFORE DB ────────────────────


async def test_invalid_related_memory_raises_value_error_before_db(
    interventions_coll, monkeypatch
):
    """Invalid related_memory_id must raise ValueError BEFORE any insert hits Mongo."""
    called = []
    orig_insert_one = interventions_coll.insert_one

    async def _watching_insert(*a, **kw):
        called.append((a, kw))
        return await orig_insert_one(*a, **kw)

    monkeypatch.setattr(interventions_coll, "insert_one", _watching_insert)
    with pytest.raises(ValueError, match="not a valid ObjectId"):
        await propose_intervention(
            _input(related_memory_id="not-an-objectid"),
            collection=interventions_coll,
        )
    assert called == [], "DB insert was attempted with an invalid related_memory_id"


# ─── AC: user isolation ─────────────────────────────────────────────


async def test_user_id_persisted(interventions_coll):
    await propose_intervention(_input(user_id="u_alpha"), collection=interventions_coll)
    await propose_intervention(_input(user_id="u_beta"), collection=interventions_coll)
    assert await interventions_coll.count_documents({"user_id": "u_alpha"}) == 1
    assert await interventions_coll.count_documents({"user_id": "u_beta"}) == 1


# ─── AC: params passes through verbatim ─────────────────────────────


async def test_params_pass_through(interventions_coll):
    """v1 stores whatever the agent sends — no per-type validation."""
    weird_params = {
        "nested": {"a": 1, "b": [2, 3]},
        "amount_usd": 100,
        "weird_key": True,
    }
    result = await propose_intervention(
        _input(params=weird_params), collection=interventions_coll
    )
    doc = await interventions_coll.find_one({"_id": ObjectId(result.intervention_id)})
    assert doc["params"] == weird_params


# ─── AC: result.proposed_at is recent ───────────────────────────────


async def test_proposed_at_is_recent(interventions_coll):
    before = datetime.now(UTC)
    result = await propose_intervention(_input(), collection=interventions_coll)
    after = datetime.now(UTC)
    assert before - timedelta(seconds=1) <= result.proposed_at <= after + timedelta(seconds=1)


# ─── Validation ─────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        ProposeInterventionInput(
            user_id="",
            type="reminder",
            triggered_by=ProposeInterventionTrigger(tool="t"),
        )


def test_validation_invalid_type():
    with pytest.raises(ValidationError):
        ProposeInterventionInput(
            user_id="u_482",
            type="invalid",
            triggered_by=ProposeInterventionTrigger(tool="t"),
        )


def test_validation_empty_trigger_tool():
    with pytest.raises(ValidationError):
        ProposeInterventionInput(
            user_id="u_482",
            type="reminder",
            triggered_by=ProposeInterventionTrigger(tool=""),
        )


def test_validation_missing_triggered_by():
    with pytest.raises(ValidationError):
        ProposeInterventionInput(user_id="u_482", type="reminder")


# ─── Tripwire (#14 pattern) ─────────────────────────────────────────


async def test_no_modification_of_other_collections(interventions_coll, monkeypatch):
    """Any silent fallback to the global db handle must fail loud."""
    with get_database_tripwire(monkeypatch, propose_intervention_module):
        await propose_intervention(_input(), collection=interventions_coll)
    assert await interventions_coll.count_documents({}) == 1
