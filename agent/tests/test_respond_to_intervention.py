"""Unit tests for respond_to_intervention. All helpers via agent.tests._fakes (#14a)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import get_database_tripwire, make_mongomock_collection
from agent.tools import respond_to_intervention as respond_to_intervention_module
from agent.tools.respond_to_intervention import (
    RespondToInterventionInput,
    RespondToInterventionResult,
    respond_to_intervention,
)


@pytest.fixture
async def interventions_coll():
    return make_mongomock_collection(collection_name="interventions")


async def _seed_pending(coll, **overrides) -> str:
    """Insert one PENDING intervention, return its intervention_id string."""
    defaults = {
        "_id": ObjectId(),
        "user_id": "u_482",
        "proposed_at": datetime.now(UTC) - timedelta(minutes=10),
        "triggered_by": {"tool": "get_spend_anomaly", "input": {}},
        "type": "reminder",
        "params": {"day": "sunday", "what": "meal prep"},
        "user_response": None,
        "responded_at": None,
        "related_memory": None,
        "status": "pending",
    }
    defaults.update(overrides)
    await coll.insert_one(defaults)
    return str(defaults["_id"])


# ─── happy path: each response value ────────────────────────────────


async def test_accepted_flips_status_to_responded(interventions_coll):
    iv_id = await _seed_pending(interventions_coll)
    result = await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482", intervention_id=iv_id, user_response="accepted"
        ),
        collection=interventions_coll,
    )
    assert isinstance(result, RespondToInterventionResult)
    assert result.previous_status == "pending"
    assert result.new_status == "responded"
    assert result.user_response == "accepted"
    assert result.params_changed is False

    doc = await interventions_coll.find_one({"_id": ObjectId(iv_id)})
    assert doc["status"] == "responded"
    assert doc["user_response"] == "accepted"
    assert doc["responded_at"] is not None


async def test_declined_flips_status_to_responded(interventions_coll):
    iv_id = await _seed_pending(interventions_coll)
    result = await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482", intervention_id=iv_id, user_response="declined"
        ),
        collection=interventions_coll,
    )
    assert result.new_status == "responded"
    doc = await interventions_coll.find_one({"_id": ObjectId(iv_id)})
    assert doc["status"] == "responded"
    assert doc["user_response"] == "declined"


async def test_modified_status_and_params_applied(interventions_coll):
    iv_id = await _seed_pending(interventions_coll)
    new_params = {"day": "saturday", "what": "meal prep + groceries"}
    result = await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482",
            intervention_id=iv_id,
            user_response="modified",
            modified_params=new_params,
        ),
        collection=interventions_coll,
    )
    assert result.new_status == "responded"
    assert result.params_changed is True
    doc = await interventions_coll.find_one({"_id": ObjectId(iv_id)})
    assert doc["params"] == new_params


async def test_ignored_status_is_ignored_not_responded(interventions_coll):
    iv_id = await _seed_pending(interventions_coll)
    result = await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482", intervention_id=iv_id, user_response="ignored"
        ),
        collection=interventions_coll,
    )
    assert result.new_status == "ignored"
    doc = await interventions_coll.find_one({"_id": ObjectId(iv_id)})
    assert doc["status"] == "ignored"
    assert doc["user_response"] == "ignored"


# ─── params guard rules ─────────────────────────────────────────────


def test_modified_response_requires_params():
    with pytest.raises(ValidationError, match="modified_params"):
        RespondToInterventionInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            user_response="modified",
        )


def test_modified_response_rejects_empty_params():
    with pytest.raises(ValidationError, match="modified_params"):
        RespondToInterventionInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            user_response="modified",
            modified_params={},
        )


def test_params_rejected_when_response_not_modified():
    with pytest.raises(ValidationError, match="only allowed when user_response='modified'"):
        RespondToInterventionInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            user_response="accepted",
            modified_params={"day": "sunday"},
        )


async def test_modified_params_applied_only_when_modified(interventions_coll):
    """Accepted responses must NOT silently overwrite params even if a buggy
    caller passes something — Pydantic catches that at construction
    (covered by test_params_rejected_when_response_not_modified), but
    verify the DB shape doesn't change for accepted either."""
    iv_id = await _seed_pending(interventions_coll)
    original_params = {"day": "sunday", "what": "meal prep"}
    result = await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482", intervention_id=iv_id, user_response="accepted"
        ),
        collection=interventions_coll,
    )
    assert result.params_changed is False
    doc = await interventions_coll.find_one({"_id": ObjectId(iv_id)})
    assert doc["params"] == original_params


# ─── responded_at server-stamped ────────────────────────────────────


async def test_responded_at_server_stamped(interventions_coll):
    iv1 = await _seed_pending(interventions_coll)
    iv2 = await _seed_pending(interventions_coll)
    r1 = await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482", intervention_id=iv1, user_response="accepted"
        ),
        collection=interventions_coll,
    )
    await asyncio.sleep(0.01)
    r2 = await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482", intervention_id=iv2, user_response="declined"
        ),
        collection=interventions_coll,
    )
    assert r1.responded_at < r2.responded_at
    assert r1.responded_at.tzinfo is not None


# ─── error paths ────────────────────────────────────────────────────


async def test_invalid_intervention_id_raises_before_db(
    interventions_coll, monkeypatch
):
    """Tripwire: monkeypatch find_one_and_update, assert never called."""
    called = []
    orig = interventions_coll.find_one_and_update

    async def _watching(*a, **kw):
        called.append((a, kw))
        return await orig(*a, **kw)

    monkeypatch.setattr(interventions_coll, "find_one_and_update", _watching)
    with pytest.raises(ValueError, match="not a valid ObjectId"):
        await respond_to_intervention(
            RespondToInterventionInput(
                user_id="u_482",
                intervention_id="not-an-objectid",
                user_response="accepted",
            ),
            collection=interventions_coll,
        )
    assert called == []


async def test_already_responded_returns_status_error(interventions_coll):
    """Second response to the same intervention raises LookupError with the
    'already in status X' message."""
    iv_id = await _seed_pending(interventions_coll)
    await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482", intervention_id=iv_id, user_response="accepted"
        ),
        collection=interventions_coll,
    )
    with pytest.raises(LookupError, match="already in status 'responded'"):
        await respond_to_intervention(
            RespondToInterventionInput(
                user_id="u_482", intervention_id=iv_id, user_response="declined"
            ),
            collection=interventions_coll,
        )


async def test_missing_intervention_raises_lookup_error(interventions_coll):
    missing_id = str(ObjectId())
    with pytest.raises(LookupError, match="not found"):
        await respond_to_intervention(
            RespondToInterventionInput(
                user_id="u_482", intervention_id=missing_id, user_response="accepted"
            ),
            collection=interventions_coll,
        )


async def test_user_isolation_on_update(interventions_coll):
    """An intervention owned by u_other must NOT be reachable by u_482."""
    iv_id = await _seed_pending(interventions_coll, user_id="u_other")
    with pytest.raises(LookupError, match="not found"):
        await respond_to_intervention(
            RespondToInterventionInput(
                user_id="u_482", intervention_id=iv_id, user_response="accepted"
            ),
            collection=interventions_coll,
        )
    # And the doc is unchanged.
    doc = await interventions_coll.find_one({"_id": ObjectId(iv_id)})
    assert doc["status"] == "pending"
    assert doc["user_response"] is None


# ─── validation ─────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        RespondToInterventionInput(
            user_id="", intervention_id=str(ObjectId()), user_response="accepted"
        )


def test_validation_empty_intervention_id():
    with pytest.raises(ValidationError):
        RespondToInterventionInput(
            user_id="u_482", intervention_id="", user_response="accepted"
        )


def test_validation_invalid_response_value():
    with pytest.raises(ValidationError):
        RespondToInterventionInput(
            user_id="u_482",
            intervention_id=str(ObjectId()),
            user_response="invalid",
        )


# ─── single DB call on success ──────────────────────────────────────


async def test_single_db_call_on_success(interventions_coll, monkeypatch):
    """Happy path uses ONE find_one_and_update + zero find_one (find_one
    is the error-classification path only)."""
    iv_id = await _seed_pending(interventions_coll)

    fou_calls = []
    fo_calls = []
    orig_fou = interventions_coll.find_one_and_update
    orig_fo = interventions_coll.find_one

    async def _watch_fou(*a, **kw):
        fou_calls.append((a, kw))
        return await orig_fou(*a, **kw)

    async def _watch_fo(*a, **kw):
        fo_calls.append((a, kw))
        return await orig_fo(*a, **kw)

    monkeypatch.setattr(interventions_coll, "find_one_and_update", _watch_fou)
    monkeypatch.setattr(interventions_coll, "find_one", _watch_fo)

    await respond_to_intervention(
        RespondToInterventionInput(
            user_id="u_482", intervention_id=iv_id, user_response="accepted"
        ),
        collection=interventions_coll,
    )

    assert len(fou_calls) == 1, "expected exactly one find_one_and_update call"
    assert len(fo_calls) == 0, "expected zero find_one calls on happy path"


# ─── tripwire (#14 pattern) ─────────────────────────────────────────


async def test_no_modification_of_other_collections(interventions_coll, monkeypatch):
    iv_id = await _seed_pending(interventions_coll)
    with get_database_tripwire(monkeypatch, respond_to_intervention_module):
        await respond_to_intervention(
            RespondToInterventionInput(
                user_id="u_482", intervention_id=iv_id, user_response="accepted"
            ),
            collection=interventions_coll,
        )
    # Doc count unchanged: only an UPDATE, never an insert.
    assert await interventions_coll.count_documents({}) == 1
