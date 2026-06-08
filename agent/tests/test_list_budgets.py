"""Hermetic tests for V6 list_budgets."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from agent.tests._fakes import make_mongomock_collection
from agent.tools.list_budgets import (
    ListBudgetsInput,
    list_budgets,
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
        _seed_budget(category="coffee", limit=80, status="abandoned"),
        _seed_budget(user_id="u_other", category="food", limit=999),
    ])
    return coll


# ─── Default behavior ──────────────────────────────────────────────


async def test_returns_only_active_by_default(collection):
    r = await list_budgets(ListBudgetsInput(user_id="u_482"), collection=collection)
    assert r.count == 3
    assert {b.category for b in r.budgets} == {"food", "shopping", "transport"}
    assert all(b.status == "active" for b in r.budgets)


async def test_sort_alphabetical_for_stable_ui(collection):
    r = await list_budgets(ListBudgetsInput(user_id="u_482"), collection=collection)
    categories = [b.category for b in r.budgets]
    assert categories == sorted(categories)


# ─── Status filter ─────────────────────────────────────────────────


async def test_status_all_includes_abandoned(collection):
    r = await list_budgets(
        ListBudgetsInput(user_id="u_482", status="all"), collection=collection
    )
    assert r.count == 4
    statuses = {b.status for b in r.budgets}
    assert statuses == {"active", "abandoned"}


async def test_status_abandoned_filter(collection):
    r = await list_budgets(
        ListBudgetsInput(user_id="u_482", status="abandoned"), collection=collection
    )
    assert r.count == 1
    assert r.budgets[0].category == "coffee"


# ─── User isolation tripwire ────────────────────────────────────────


async def test_never_surfaces_another_users_budgets(collection):
    r = await list_budgets(
        ListBudgetsInput(user_id="u_482", status="all"), collection=collection
    )
    # u_other's food=$999 must not appear.
    food_budgets = [b for b in r.budgets if b.category == "food"]
    assert len(food_budgets) == 1
    assert food_budgets[0].limit == 500.0  # u_482's, not u_other's $999


async def test_unknown_user_returns_empty(collection):
    r = await list_budgets(
        ListBudgetsInput(user_id="u_nobody"), collection=collection
    )
    assert r.count == 0
    assert r.budgets == []


# ─── Validation ─────────────────────────────────────────────────────


def test_empty_user_id_rejected():
    with pytest.raises(ValidationError):
        ListBudgetsInput(user_id="")


def test_invalid_status_rejected():
    with pytest.raises(ValidationError):
        ListBudgetsInput(user_id="u_482", status="paused")  # type: ignore[arg-type]
