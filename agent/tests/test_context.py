"""Unit tests for agent/graphs/context.py — active-on-date predicate + formatter."""

from datetime import date, datetime

import pytest

from agent.graphs.context import fetch_active_context, format_active_context
from agent.tests._fakes import make_mongomock_collection


@pytest.fixture
async def user_context_coll():
    return make_mongomock_collection(collection_name="user_context")


async def _seed(coll, **doc):
    defaults = {
        "user_id": "u_482",
        "text": "default ctx",
        "type": "lifestyle",
        "active_from": datetime(2026, 5, 1),
        "active_until": None,
        "created_at": datetime(2026, 5, 1, 12, 0),
    }
    defaults.update(doc)
    return await coll.insert_one(defaults)


# ─── predicate behavior ─────────────────────────────────────────────


async def test_returns_ongoing_context_for_today(user_context_coll):
    await _seed(user_context_coll, active_from=datetime(2026, 5, 1), active_until=None)
    docs = await fetch_active_context(
        "u_482", as_of=date(2026, 6, 1), collection=user_context_coll
    )
    assert len(docs) == 1


async def test_returns_bounded_context_when_in_range(user_context_coll):
    await _seed(
        user_context_coll,
        type="event",
        text="exam week",
        active_from=datetime(2026, 2, 12),
        active_until=datetime(2026, 2, 19),
    )
    docs = await fetch_active_context(
        "u_482", as_of=date(2026, 2, 15), collection=user_context_coll
    )
    assert len(docs) == 1
    assert docs[0]["type"] == "event"


async def test_excludes_bounded_context_after_window(user_context_coll):
    await _seed(
        user_context_coll,
        type="event",
        active_from=datetime(2026, 2, 12),
        active_until=datetime(2026, 2, 19),
    )
    docs = await fetch_active_context(
        "u_482", as_of=date(2026, 3, 1), collection=user_context_coll
    )
    assert docs == []


async def test_excludes_future_active_from(user_context_coll):
    await _seed(user_context_coll, active_from=datetime(2026, 6, 1), active_until=None)
    docs = await fetch_active_context(
        "u_482", as_of=date(2026, 2, 15), collection=user_context_coll
    )
    assert docs == []


async def test_inclusive_at_lower_bound(user_context_coll):
    await _seed(
        user_context_coll,
        active_from=datetime(2026, 5, 1),
        active_until=datetime(2026, 5, 31),
    )
    docs = await fetch_active_context(
        "u_482", as_of=date(2026, 5, 1), collection=user_context_coll
    )
    assert len(docs) == 1


async def test_inclusive_at_upper_bound(user_context_coll):
    await _seed(
        user_context_coll,
        active_from=datetime(2026, 5, 1),
        active_until=datetime(2026, 5, 31),
    )
    docs = await fetch_active_context(
        "u_482", as_of=date(2026, 5, 31), collection=user_context_coll
    )
    assert len(docs) == 1


async def test_user_isolation(user_context_coll):
    await _seed(user_context_coll, user_id="u_482", active_from=datetime(2026, 5, 1))
    await _seed(user_context_coll, user_id="u_other", active_from=datetime(2026, 5, 1))
    docs = await fetch_active_context(
        "u_482", as_of=date(2026, 6, 1), collection=user_context_coll
    )
    assert len(docs) == 1
    assert docs[0]["user_id"] == "u_482"


async def test_empty_when_no_docs(user_context_coll):
    docs = await fetch_active_context(
        "u_482", as_of=date(2026, 6, 1), collection=user_context_coll
    )
    assert docs == []


# ─── formatter behavior ─────────────────────────────────────────────


def test_format_empty_returns_empty_string():
    assert format_active_context([]) == ""


def test_format_ongoing_includes_since():
    out = format_active_context([{
        "type": "lifestyle",
        "text": "I'm bulking",
        "active_from": datetime(2026, 6, 1),
        "active_until": None,
    }])
    assert "Active context for the user:" in out
    assert "lifestyle: I'm bulking" in out
    assert "since 2026-06-01" in out
    assert "ongoing" in out


def test_format_bounded_includes_until():
    out = format_active_context([{
        "type": "event",
        "text": "exam week",
        "active_from": datetime(2026, 2, 12),
        "active_until": datetime(2026, 2, 19),
    }])
    assert "until 2026-02-19" in out


def test_format_multiple_docs():
    out = format_active_context([
        {
            "type": "lifestyle",
            "text": "I'm bulking",
            "active_from": datetime(2026, 6, 1),
            "active_until": None,
        },
        {
            "type": "constraint",
            "text": "no spend after the 25th",
            "active_from": datetime(2026, 6, 1),
            "active_until": datetime(2026, 6, 25),
        },
    ])
    assert "lifestyle:" in out and "constraint:" in out
