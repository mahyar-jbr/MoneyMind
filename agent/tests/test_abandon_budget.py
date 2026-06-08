"""Hermetic tests for V6 abandon_budget — status-flip pattern, three call paths."""

from datetime import UTC, datetime
from typing import Any

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import make_mongomock_collection
from agent.tools.abandon_budget import (
    AbandonBudgetInput,
    abandon_budget,
)


def _seed_budget(
    *,
    user_id: str = "u_482",
    category: str = "food",
    limit: float = 500,
    status: str = "active",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "user_id": user_id,
        "category": category,
        "limit": limit,
        "period": "month",
        "status": status,
        "created_at": now,
        "updated_at": now,
    }


@pytest.fixture
async def collection():
    coll = make_mongomock_collection(collection_name="budgets")
    await coll.insert_many([
        _seed_budget(category="food", limit=500),
        _seed_budget(category="shopping", limit=300),
        _seed_budget(category="transport", limit=200),
        _seed_budget(category="coffee", limit=80, status="abandoned"),  # already abandoned
        _seed_budget(user_id="u_other", category="food", limit=999),     # someone else's
    ])
    return coll


# ─── Path B: exact category match (the hot path Gemini should prefer) ─


async def test_category_path_exact_match_flips_status(collection):
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", category="food"),
        collection=collection,
    )
    assert r.abandoned is True
    assert r.needs_confirmation is False
    assert r.category == "food"
    assert r.limit == 500.0
    doc = await collection.find_one({"_id": ObjectId(r.budget_id)})
    assert doc["status"] == "abandoned"
    assert "abandoned_at" in doc


async def test_category_path_normalizes_input(collection):
    """User says 'Food' or 'food.delivery' — both flip the 'food' budget."""
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", category="Food.Delivery"),
        collection=collection,
    )
    assert r.abandoned is True
    assert r.category == "food"


async def test_category_path_no_match_returns_active_categories(collection):
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", category="bitcoin"),
        collection=collection,
    )
    assert r.abandoned is False
    assert r.needs_confirmation is False
    assert set(r.active_categories) == {"food", "shopping", "transport"}


# ─── Path A: fuzzy query (when the user phrases loosely) ───────────


async def test_query_path_single_match_flips(collection):
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", query="forget the food cap"),
        collection=collection,
    )
    assert r.abandoned is True
    assert r.category == "food"


async def test_query_path_multiple_matches_returns_needs_confirmation(collection):
    await collection.insert_one(_seed_budget(category="food fast", limit=200))
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", query="food"),
        collection=collection,
    )
    assert r.abandoned is False
    assert r.needs_confirmation is True
    assert len(r.candidates) == 2
    cats = {c.category for c in r.candidates}
    assert cats == {"food", "food fast"}


async def test_query_path_all_stopwords_falls_through_to_no_match(collection):
    """'forget the cap' is all stopwords — should not accidentally match any."""
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", query="forget the cap"),
        collection=collection,
    )
    assert r.abandoned is False
    assert r.needs_confirmation is False
    assert set(r.active_categories) == {"food", "shopping", "transport"}


async def test_query_path_no_match_returns_active_categories(collection):
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", query="forget my bitcoin cap"),
        collection=collection,
    )
    assert r.abandoned is False
    assert r.needs_confirmation is False
    assert "food" in r.active_categories


# ─── Path C: budget_id direct flip (confirmation follow-up) ────────


async def test_budget_id_path_skips_search_and_flips_directly(collection):
    shopping = await collection.find_one({"user_id": "u_482", "category": "shopping"})
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", budget_id=str(shopping["_id"])),
        collection=collection,
    )
    assert r.abandoned is True
    assert r.category == "shopping"
    assert r.limit == 300.0


async def test_budget_id_path_idempotent_on_already_abandoned(collection):
    food = await collection.find_one({"user_id": "u_482", "category": "food"})
    first = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", budget_id=str(food["_id"])),
        collection=collection,
    )
    assert first.abandoned is True
    second = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", budget_id=str(food["_id"])),
        collection=collection,
    )
    assert second.abandoned is False


async def test_budget_id_path_invalid_objectid_raises(collection):
    with pytest.raises(ValueError, match="invalid budget_id"):
        await abandon_budget(
            AbandonBudgetInput(user_id="u_482", budget_id="not-an-objectid"),
            collection=collection,
        )


# ─── Mutually-exclusive params ─────────────────────────────────────


async def test_no_path_raises(collection):
    with pytest.raises(ValueError, match="must pass one"):
        await abandon_budget(
            AbandonBudgetInput(user_id="u_482"), collection=collection
        )


async def test_two_paths_at_once_raises(collection):
    with pytest.raises(ValueError, match="only ONE"):
        await abandon_budget(
            AbandonBudgetInput(user_id="u_482", query="food", category="food"),
            collection=collection,
        )


# ─── User isolation tripwires ──────────────────────────────────────


async def test_user_isolation_category_path(collection):
    """u_482 abandoning 'food' must NEVER flip u_other's food cap."""
    await abandon_budget(
        AbandonBudgetInput(user_id="u_482", category="food"),
        collection=collection,
    )
    other = await collection.find_one({"user_id": "u_other", "category": "food"})
    assert other["status"] == "active"


async def test_user_isolation_budget_id_path(collection):
    """u_482 cannot abandon u_other's budget even with its goal_id directly."""
    other = await collection.find_one({"user_id": "u_other", "category": "food"})
    r = await abandon_budget(
        AbandonBudgetInput(user_id="u_482", budget_id=str(other["_id"])),
        collection=collection,
    )
    assert r.abandoned is False
    doc = await collection.find_one({"_id": other["_id"]})
    assert doc["status"] == "active"


# ─── Validation ────────────────────────────────────────────────────


def test_empty_user_id_rejected():
    with pytest.raises(ValidationError):
        AbandonBudgetInput(user_id="", category="food")
