"""Hermetic tests for abandon_goal (V1 follow-up)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import make_mongomock_collection
from agent.tools.abandon_goal import (
    AbandonGoalInput,
    abandon_goal,
)


def _seed_goal(
    *,
    user_id: str = "u_482",
    title: str = "Japan trip",
    status: str = "active",
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "title": title,
        "target_amount": 5000,
        "current_amount": 0,
        "target_date": datetime(2026, 12, 1),
        "pace_check": "weekly",
        "status": status,
        "created_at": datetime.now(UTC),
    }


@pytest.fixture
async def collection():
    coll = make_mongomock_collection(collection_name="goals")
    await coll.insert_many([
        _seed_goal(title="Japan trip"),
        _seed_goal(title="Emergency fund"),
        _seed_goal(title="New laptop"),
        _seed_goal(title="Old paused goal", status="paused"),
        _seed_goal(user_id="u_other", title="Japan trip"),  # someone else's
    ])
    return coll


# ─── Path A — query (initial request) ──────────────────────────────


async def test_single_match_flips_status_to_abandoned(collection):
    r = await abandon_goal(
        AbandonGoalInput(user_id="u_482", query="forget the Japan trip"),
        collection=collection,
    )
    assert r.abandoned is True
    assert r.needs_confirmation is False
    assert r.title == "Japan trip"
    # The flipped goal must now have status="abandoned" in Atlas.
    doc = await collection.find_one({"_id": ObjectId(r.goal_id)})
    assert doc["status"] == "abandoned"
    assert "abandoned_at" in doc
    # Other goals untouched.
    assert (
        await collection.count_documents({"user_id": "u_482", "status": "active"})
        == 2  # Emergency fund + New laptop still active
    )


async def test_multiple_matches_return_needs_confirmation(collection):
    # "the goal" is too generic — stopwords ("the", "goal") collapse it
    # to a no-op so we use a query that genuinely matches multiple titles.
    await collection.insert_one(_seed_goal(title="Japan emergency stash"))
    r = await abandon_goal(
        AbandonGoalInput(user_id="u_482", query="japan"),
        collection=collection,
    )
    assert r.abandoned is False
    assert r.needs_confirmation is True
    assert len(r.candidates) == 2
    titles = {c.title for c in r.candidates}
    assert titles == {"Japan trip", "Japan emergency stash"}
    # Nothing flipped — both must still be active.
    assert (
        await collection.count_documents(
            {"user_id": "u_482", "status": "active", "title": {"$in": list(titles)}}
        )
        == 2
    )


async def test_no_match_returns_active_titles_for_agent_reply(collection):
    r = await abandon_goal(
        AbandonGoalInput(user_id="u_482", query="forget my bitcoin moonshot"),
        collection=collection,
    )
    assert r.abandoned is False
    assert r.needs_confirmation is False
    # The agent uses this list to compose an honest "I don't see that, your
    # active goals are: ..." reply.
    assert set(r.active_goal_titles) == {"Japan trip", "Emergency fund", "New laptop"}
    # Paused goals not surfaced here either.
    assert "Old paused goal" not in r.active_goal_titles


async def test_all_stopword_query_falls_through_to_no_match(collection):
    """'forget the goal' matches no titles because every word is a stopword."""
    r = await abandon_goal(
        AbandonGoalInput(user_id="u_482", query="forget the goal"),
        collection=collection,
    )
    # No active titles got accidentally matched — query was effectively empty.
    assert r.abandoned is False
    assert r.needs_confirmation is False
    assert len(r.active_goal_titles) == 3


# ─── Path B — goal_id (confirmation follow-up) ─────────────────────


async def test_goal_id_path_skips_search_and_flips_directly(collection):
    # Get the laptop goal's ID.
    laptop = await collection.find_one({"user_id": "u_482", "title": "New laptop"})
    r = await abandon_goal(
        AbandonGoalInput(user_id="u_482", goal_id=str(laptop["_id"])),
        collection=collection,
    )
    assert r.abandoned is True
    assert r.needs_confirmation is False
    assert r.title == "New laptop"
    doc = await collection.find_one({"_id": laptop["_id"]})
    assert doc["status"] == "abandoned"


async def test_goal_id_idempotent_on_already_abandoned(collection):
    """Calling abandon_goal twice on the same goal flips once then no-ops."""
    laptop = await collection.find_one({"user_id": "u_482", "title": "New laptop"})
    first = await abandon_goal(
        AbandonGoalInput(user_id="u_482", goal_id=str(laptop["_id"])),
        collection=collection,
    )
    assert first.abandoned is True

    second = await abandon_goal(
        AbandonGoalInput(user_id="u_482", goal_id=str(laptop["_id"])),
        collection=collection,
    )
    # Second call finds nothing active to flip — the find_one with
    # status="active" returns None.
    assert second.abandoned is False
    assert second.needs_confirmation is False


async def test_goal_id_invalid_objectid_raises(collection):
    with pytest.raises(ValueError, match="invalid goal_id"):
        await abandon_goal(
            AbandonGoalInput(user_id="u_482", goal_id="not-an-objectid"),
            collection=collection,
        )


async def test_query_and_goal_id_both_present_raises(collection):
    laptop = await collection.find_one({"user_id": "u_482", "title": "New laptop"})
    with pytest.raises(ValueError, match="not both"):
        await abandon_goal(
            AbandonGoalInput(
                user_id="u_482",
                query="laptop",
                goal_id=str(laptop["_id"]),
            ),
            collection=collection,
        )


async def test_neither_query_nor_goal_id_raises(collection):
    with pytest.raises(ValueError, match="either query or goal_id"):
        await abandon_goal(
            AbandonGoalInput(user_id="u_482"),
            collection=collection,
        )


# ─── Hardening ──────────────────────────────────────────────────────


async def test_user_isolation_tripwire_query_path(collection):
    """u_482's query for 'Japan trip' must NEVER flip u_other's goal."""
    other_goal_before = await collection.find_one(
        {"user_id": "u_other", "title": "Japan trip"}
    )
    assert other_goal_before["status"] == "active"

    await abandon_goal(
        AbandonGoalInput(user_id="u_482", query="japan trip"),
        collection=collection,
    )

    other_goal_after = await collection.find_one(
        {"user_id": "u_other", "title": "Japan trip"}
    )
    assert other_goal_after["status"] == "active"  # untouched


async def test_user_isolation_tripwire_goal_id_path(collection):
    """u_482 cannot abandon u_other's goal even by passing its goal_id."""
    other_goal = await collection.find_one(
        {"user_id": "u_other", "title": "Japan trip"}
    )

    r = await abandon_goal(
        AbandonGoalInput(user_id="u_482", goal_id=str(other_goal["_id"])),
        collection=collection,
    )

    # Tool returns abandoned=False because the find_one filters on
    # user_id — u_other's goal is invisible to u_482.
    assert r.abandoned is False
    # u_other's goal must still be active.
    doc = await collection.find_one({"_id": other_goal["_id"]})
    assert doc["status"] == "active"


async def test_paused_goal_is_invisible_to_query_path(collection):
    """abandon_goal only matches active goals; paused goals are off-limits."""
    r = await abandon_goal(
        AbandonGoalInput(user_id="u_482", query="paused"),
        collection=collection,
    )
    assert r.abandoned is False
    # The paused goal didn't get flipped.
    paused = await collection.find_one(
        {"user_id": "u_482", "title": "Old paused goal"}
    )
    assert paused["status"] == "paused"


# ─── Validation ─────────────────────────────────────────────────────


def test_empty_user_id_rejected():
    with pytest.raises(ValidationError):
        AbandonGoalInput(user_id="", query="anything")
