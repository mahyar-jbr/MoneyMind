"""Hermetic tests for V1 write_goal.

Uses mongomock-motor via the shared `make_mongomock_collection` helper —
goals tools use plain find/insert with no $vectorSearch or $dateTrunc, so
the mock supports the full code path.
"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from agent.tests._fakes import make_mongomock_collection
from agent.tools.write_goal import (
    WriteGoalInput,
    WriteGoalResult,
    write_goal,
)


@pytest.fixture
def collection():
    return make_mongomock_collection(collection_name="goals")


# ─── Happy path ─────────────────────────────────────────────────────


async def test_inserts_a_minimal_goal_and_returns_id(collection):
    result = await write_goal(
        WriteGoalInput(
            user_id="u_482",
            title="Japan trip",
            target_amount=5000,
            target_date=date(2026, 12, 1),
        ),
        collection=collection,
    )
    assert isinstance(result, WriteGoalResult)
    assert result.user_id == "u_482"
    assert result.title == "Japan trip"
    assert result.target_amount == 5000.0
    assert result.current_amount == 0.0  # default
    assert result.status == "active"
    assert result.target_date == date(2026, 12, 1)
    assert ObjectIdParseable(result.goal_id)


async def test_persisted_shape_matches_data_model(collection):
    """Doc shape must match docs/data-model.md § goals exactly."""
    await write_goal(
        WriteGoalInput(
            user_id="u_482",
            title="Emergency fund",
            target_amount=10000,
            target_date=date(2026, 12, 31),
            current_amount=2400,
        ),
        collection=collection,
    )
    doc = await collection.find_one({"user_id": "u_482"})
    assert doc is not None
    assert set(doc.keys()) == {
        "_id",
        "user_id",
        "title",
        "target_amount",
        "current_amount",
        "target_date",
        "pace_check",
        "status",
        "created_at",
    }
    assert doc["pace_check"] == "weekly"
    assert doc["status"] == "active"
    # target_date persisted as naive midnight datetime (codebase convention)
    assert isinstance(doc["target_date"], datetime)
    assert doc["target_date"].hour == 0
    assert doc["target_date"].minute == 0


async def test_current_amount_defaults_to_zero(collection):
    await write_goal(
        WriteGoalInput(
            user_id="u_482",
            title="New laptop",
            target_amount=2000,
            target_date=date(2026, 8, 15),
        ),
        collection=collection,
    )
    doc = await collection.find_one({"title": "New laptop"})
    assert doc["current_amount"] == 0.0


async def test_current_amount_honored_when_provided(collection):
    await write_goal(
        WriteGoalInput(
            user_id="u_482",
            title="Japan trip",
            target_amount=3000,
            target_date=date(2026, 12, 1),
            current_amount=1840,
        ),
        collection=collection,
    )
    doc = await collection.find_one({"title": "Japan trip"})
    assert doc["current_amount"] == 1840.0


async def test_multiple_goals_each_get_distinct_ids(collection):
    r1 = await write_goal(
        WriteGoalInput(
            user_id="u_482", title="A", target_amount=100, target_date=date(2026, 12, 1)
        ),
        collection=collection,
    )
    r2 = await write_goal(
        WriteGoalInput(
            user_id="u_482", title="B", target_amount=200, target_date=date(2026, 12, 1)
        ),
        collection=collection,
    )
    assert r1.goal_id != r2.goal_id
    assert await collection.count_documents({"user_id": "u_482"}) == 2


# ─── User isolation ────────────────────────────────────────────────


async def test_user_isolation_via_user_id_field(collection):
    """Goals written under one user_id must never surface for another."""
    await write_goal(
        WriteGoalInput(
            user_id="u_alice",
            title="alice goal",
            target_amount=500,
            target_date=date(2026, 12, 1),
        ),
        collection=collection,
    )
    await write_goal(
        WriteGoalInput(
            user_id="u_bob",
            title="bob goal",
            target_amount=500,
            target_date=date(2026, 12, 1),
        ),
        collection=collection,
    )
    alice_count = await collection.count_documents({"user_id": "u_alice"})
    bob_count = await collection.count_documents({"user_id": "u_bob"})
    assert alice_count == 1
    assert bob_count == 1


# ─── Validation tripwires ──────────────────────────────────────────


def test_empty_user_id_rejected():
    with pytest.raises(ValidationError):
        WriteGoalInput(
            user_id="",
            title="t",
            target_amount=100,
            target_date=date(2026, 12, 1),
        )


def test_empty_title_rejected():
    with pytest.raises(ValidationError):
        WriteGoalInput(
            user_id="u_482",
            title="",
            target_amount=100,
            target_date=date(2026, 12, 1),
        )


def test_zero_target_amount_rejected():
    with pytest.raises(ValidationError):
        WriteGoalInput(
            user_id="u_482",
            title="t",
            target_amount=0,
            target_date=date(2026, 12, 1),
        )


def test_negative_target_amount_rejected():
    with pytest.raises(ValidationError):
        WriteGoalInput(
            user_id="u_482",
            title="t",
            target_amount=-100,
            target_date=date(2026, 12, 1),
        )


def test_negative_current_amount_rejected():
    with pytest.raises(ValidationError):
        WriteGoalInput(
            user_id="u_482",
            title="t",
            target_amount=100,
            target_date=date(2026, 12, 1),
            current_amount=-1,
        )


# ─── Helpers ───────────────────────────────────────────────────────


def ObjectIdParseable(s: str) -> bool:
    """True iff s parses as a 24-char hex ObjectId."""
    from bson import ObjectId

    try:
        ObjectId(s)
        return True
    except Exception:
        return False
