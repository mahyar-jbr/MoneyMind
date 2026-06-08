"""Hermetic tests for V1 list_goals."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from agent.tests._fakes import make_mongomock_collection
from agent.tools.list_goals import (
    ListGoalsInput,
    list_goals,
)


def _seed_goal(
    *,
    user_id: str = "u_482",
    title: str = "Emergency fund",
    status: str = "active",
    target_amount: float = 10000,
    current_amount: float = 2400,
    target_date: datetime | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "title": title,
        "target_amount": target_amount,
        "current_amount": current_amount,
        "target_date": target_date or datetime(2026, 12, 31),
        "pace_check": "weekly",
        "status": status,
        "created_at": created_at or datetime.now(UTC),
    }


@pytest.fixture
async def collection():
    coll = make_mongomock_collection(collection_name="goals")
    base = datetime(2026, 6, 1, tzinfo=UTC)
    # 3 active goals (newest first by created_at), 1 paused, 1 complete,
    # plus another user's goal we must never surface.
    await coll.insert_many([
        _seed_goal(title="Japan trip", created_at=base + timedelta(days=3)),
        _seed_goal(title="Emergency fund", created_at=base + timedelta(days=2)),
        _seed_goal(title="New laptop", created_at=base + timedelta(days=1)),
        _seed_goal(title="Old gym goal", status="paused", created_at=base),
        _seed_goal(title="Last year's savings", status="complete", created_at=base - timedelta(days=30)),
        _seed_goal(user_id="u_other", title="someone else's goal"),
    ])
    return coll


# ─── Default behavior: active only, newest first ────────────────────


async def test_returns_only_active_by_default(collection):
    r = await list_goals(ListGoalsInput(user_id="u_482"), collection=collection)
    assert r.count == 3
    assert {g.title for g in r.goals} == {"Japan trip", "Emergency fund", "New laptop"}
    assert all(g.status == "active" for g in r.goals)


async def test_default_sort_newest_first(collection):
    r = await list_goals(ListGoalsInput(user_id="u_482"), collection=collection)
    titles = [g.title for g in r.goals]
    assert titles == ["Japan trip", "Emergency fund", "New laptop"]


# ─── status filter variants ─────────────────────────────────────────


async def test_status_all_includes_paused_and_complete(collection):
    r = await list_goals(
        ListGoalsInput(user_id="u_482", status="all"), collection=collection
    )
    assert r.count == 5  # 3 active + 1 paused + 1 complete
    statuses = {g.status for g in r.goals}
    assert statuses == {"active", "paused", "complete"}


async def test_status_paused_filter(collection):
    r = await list_goals(
        ListGoalsInput(user_id="u_482", status="paused"), collection=collection
    )
    assert r.count == 1
    assert r.goals[0].title == "Old gym goal"


async def test_status_complete_filter(collection):
    r = await list_goals(
        ListGoalsInput(user_id="u_482", status="complete"), collection=collection
    )
    assert r.count == 1
    assert r.goals[0].title == "Last year's savings"


# ─── User isolation tripwire ────────────────────────────────────────


async def test_never_surfaces_another_users_goals(collection):
    """Critical: u_482 must never see u_other's goal even with status='all'."""
    r = await list_goals(
        ListGoalsInput(user_id="u_482", status="all"), collection=collection
    )
    titles = {g.title for g in r.goals}
    assert "someone else's goal" not in titles


async def test_unknown_user_returns_empty(collection):
    r = await list_goals(
        ListGoalsInput(user_id="u_nobody"), collection=collection
    )
    assert r.count == 0
    assert r.goals == []


# ─── Result mapping ─────────────────────────────────────────────────


async def test_target_date_coerced_to_date_object(collection):
    r = await list_goals(ListGoalsInput(user_id="u_482"), collection=collection)
    from datetime import date

    assert all(isinstance(g.target_date, date) for g in r.goals)


async def test_goal_id_is_stringified_objectid(collection):
    r = await list_goals(ListGoalsInput(user_id="u_482"), collection=collection)
    from bson import ObjectId

    for g in r.goals:
        # 24-char hex strings — round-trips through ObjectId
        assert isinstance(g.goal_id, str)
        ObjectId(g.goal_id)  # raises if not parseable


# ─── Validation ─────────────────────────────────────────────────────


def test_empty_user_id_rejected():
    with pytest.raises(ValidationError):
        ListGoalsInput(user_id="")


def test_invalid_status_rejected():
    with pytest.raises(ValidationError):
        ListGoalsInput(user_id="u_482", status="archived")  # type: ignore[arg-type]


def test_limit_bounds_enforced():
    with pytest.raises(ValidationError):
        ListGoalsInput(user_id="u_482", limit=0)
    with pytest.raises(ValidationError):
        ListGoalsInput(user_id="u_482", limit=101)
