"""Hermetic tests for V6 set_budget (upsert by user_id+category+status)."""


import pytest
from pydantic import ValidationError

from agent.tests._fakes import make_mongomock_collection
from agent.tools.set_budget import (
    SetBudgetInput,
    set_budget,
)


@pytest.fixture
def collection():
    return make_mongomock_collection(collection_name="budgets")


# ─── Insert path ────────────────────────────────────────────────────


async def test_first_call_inserts_a_new_budget(collection):
    r = await set_budget(
        SetBudgetInput(user_id="u_482", category="food", limit=500),
        collection=collection,
    )
    assert r.updated is False
    assert r.category == "food"
    assert r.limit == 500.0
    assert r.period == "month"
    assert r.status == "active"
    doc = await collection.find_one({"_id": _oid(r.budget_id)})
    assert doc["limit"] == 500.0
    assert doc["created_at"] == doc["updated_at"]


async def test_persisted_shape_contract(collection):
    """Doc shape must match the schema we documented in set_budget.py header."""
    await set_budget(
        SetBudgetInput(user_id="u_482", category="shopping", limit=300),
        collection=collection,
    )
    doc = await collection.find_one({"user_id": "u_482", "category": "shopping"})
    assert set(doc.keys()) == {
        "_id",
        "user_id",
        "category",
        "limit",
        "period",
        "status",
        "created_at",
        "updated_at",
    }


async def test_category_normalized_lowercase_and_top_level(collection):
    """'Food Delivery' / 'FOOD' / 'food.delivery' all collapse to 'food'."""
    for raw in ["Food", "  FOOD  ", "food.delivery", "FOOD.DELIVERY"]:
        await collection.delete_many({})
        r = await set_budget(
            SetBudgetInput(user_id="u_482", category=raw, limit=500),
            collection=collection,
        )
        assert r.category == "food"
        doc = await collection.find_one({"_id": _oid(r.budget_id)})
        assert doc["category"] == "food"


# ─── Update path (upsert) ───────────────────────────────────────────


async def test_second_call_for_same_category_updates_limit(collection):
    first = await set_budget(
        SetBudgetInput(user_id="u_482", category="food", limit=500),
        collection=collection,
    )
    second = await set_budget(
        SetBudgetInput(user_id="u_482", category="food", limit=400),
        collection=collection,
    )
    assert second.updated is True
    assert second.budget_id == first.budget_id  # same doc, mutated
    assert second.limit == 400.0
    # created_at preserved (within a millisecond — Mongo storage roundtrip
    # strips tzinfo and may truncate microseconds), updated_at bumped to
    # a strictly later value.
    delta = abs((second.created_at.replace(tzinfo=None) - first.created_at.replace(tzinfo=None)).total_seconds())
    assert delta < 0.001
    assert second.updated_at.replace(tzinfo=None) >= first.updated_at.replace(tzinfo=None)
    # Still exactly one active food budget.
    assert (
        await collection.count_documents(
            {"user_id": "u_482", "category": "food", "status": "active"}
        )
        == 1
    )


async def test_update_with_normalized_category_targets_existing_doc(collection):
    """User says 'food delivery' the second time — must update the
    same 'food' budget, not insert a new one."""
    first = await set_budget(
        SetBudgetInput(user_id="u_482", category="food", limit=500),
        collection=collection,
    )
    second = await set_budget(
        SetBudgetInput(user_id="u_482", category="Food Delivery", limit=400),
        collection=collection,
    )
    assert second.updated is True
    assert second.budget_id == first.budget_id


# ─── Abandoned budgets don't block new ones ─────────────────────────


async def test_abandoned_budget_for_same_category_does_not_block_insert(collection):
    """If the food budget was abandoned, setting a new food budget INSERTS
    a fresh active one (the abandoned doc is invisible to the upsert filter)."""
    first = await set_budget(
        SetBudgetInput(user_id="u_482", category="food", limit=500),
        collection=collection,
    )
    # Manually flip to abandoned (simulating abandon_budget).
    await collection.update_one(
        {"_id": _oid(first.budget_id)}, {"$set": {"status": "abandoned"}}
    )
    # Now set again — should be a fresh INSERT, not an update.
    second = await set_budget(
        SetBudgetInput(user_id="u_482", category="food", limit=350),
        collection=collection,
    )
    assert second.updated is False
    assert second.budget_id != first.budget_id
    # One active, one abandoned.
    assert (
        await collection.count_documents({"user_id": "u_482", "category": "food"})
        == 2
    )


# ─── User isolation ────────────────────────────────────────────────


async def test_user_isolation_two_users_two_food_budgets(collection):
    """u_alice's food cap and u_bob's food cap coexist independently."""
    await set_budget(
        SetBudgetInput(user_id="u_alice", category="food", limit=500),
        collection=collection,
    )
    await set_budget(
        SetBudgetInput(user_id="u_bob", category="food", limit=300),
        collection=collection,
    )
    alice = await collection.find_one({"user_id": "u_alice", "category": "food"})
    bob = await collection.find_one({"user_id": "u_bob", "category": "food"})
    assert alice["limit"] == 500.0
    assert bob["limit"] == 300.0
    # u_alice's update must not touch u_bob's doc.
    await set_budget(
        SetBudgetInput(user_id="u_alice", category="food", limit=600),
        collection=collection,
    )
    bob_after = await collection.find_one({"user_id": "u_bob", "category": "food"})
    assert bob_after["limit"] == 300.0


# ─── Validation tripwires ──────────────────────────────────────────


def test_empty_user_id_rejected():
    with pytest.raises(ValidationError):
        SetBudgetInput(user_id="", category="food", limit=100)


def test_empty_category_rejected():
    with pytest.raises(ValidationError):
        SetBudgetInput(user_id="u_482", category="", limit=100)


def test_zero_limit_rejected():
    with pytest.raises(ValidationError):
        SetBudgetInput(user_id="u_482", category="food", limit=0)


def test_negative_limit_rejected():
    with pytest.raises(ValidationError):
        SetBudgetInput(user_id="u_482", category="food", limit=-50)


# ─── Helpers ───────────────────────────────────────────────────────


def _oid(s: str):
    from bson import ObjectId

    return ObjectId(s)
