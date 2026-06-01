"""Unit tests for summarize_week. All helpers via agent.tests._fakes (#14a).

mongomock-motor doesn't implement $dateTrunc, so we inject a scripted
aggregator instead of calling the real weekly_spend_by_category. Same
pattern as #13's embedder kwarg.
"""

from datetime import date, datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import get_database_tripwire, make_mongomock_collection
from agent.tools import summarize_week as summarize_week_module
from agent.tools.summarize_week import (
    SummarizeWeekInput,
    summarize_week,
)


@pytest.fixture
async def transactions_coll():
    return make_mongomock_collection(collection_name="transactions")


@pytest.fixture
async def goals_coll():
    return make_mongomock_collection(collection_name="goals")


def make_aggregator(by_category: dict[str, float] | None = None):
    """Return a scripted async aggregator. None = empty week."""

    async def _agg(user_id: str, date_from: datetime, date_to_exclusive: datetime):
        if by_category is None:
            return []
        return [
            {
                "week": date_from.date().isoformat(),
                "by_category": dict(by_category),
                "total_spend": round(sum(by_category.values()), 2),
            }
        ]

    return _agg


async def _seed_txn(coll, user_id, d: date, amount: float, category="food.delivery"):
    return await coll.insert_one({
        "user_id": user_id,
        "date": datetime(d.year, d.month, d.day),
        "merchant": "X",
        "category": category,
        "amount": amount,
        "currency": "USD",
    })


async def _seed_goal(coll, **overrides):
    defaults = {
        "_id": ObjectId(),
        "user_id": "u_482",
        "title": "Emergency Fund",
        "target_amount": 8000.0,
        "current_amount": 2400.0,
        "target_date": datetime(2026, 12, 31),
        "pace_check": "weekly",
        "status": "active",
        "created_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    await coll.insert_one(defaults)
    return defaults


def _input(**overrides):
    defaults = {
        "user_id": "u_482",
        "as_of": date(2026, 5, 24),  # Sunday — week May 18-24
        "week_offset": 0,
        "include_goals": True,
    }
    defaults.update(overrides)
    return SummarizeWeekInput(**defaults)


# ─── ISO Monday-Sunday week boundaries + offset ─────────────────────


async def test_week_boundaries_iso_monday_sunday(transactions_coll, goals_coll):
    result = await summarize_week(
        _input(as_of=date(2026, 5, 24)),  # Sunday → Monday of that week is 05-18
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    assert result.week_start == date(2026, 5, 18)
    assert result.week_end == date(2026, 5, 24)
    # Mid-week as_of must also resolve to the same Monday-Sunday week.
    result2 = await summarize_week(
        _input(as_of=date(2026, 5, 20)),  # Wednesday
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    assert result2.week_start == date(2026, 5, 18)
    assert result2.week_end == date(2026, 5, 24)


async def test_week_offset_shifts_by_seven_days(transactions_coll, goals_coll):
    result = await summarize_week(
        _input(as_of=date(2026, 5, 24), week_offset=-1),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    assert result.week_start == date(2026, 5, 11)
    assert result.week_end == date(2026, 5, 17)


# ─── Empty week ─────────────────────────────────────────────────────


async def test_empty_week_returns_zero_not_error(transactions_coll, goals_coll):
    result = await summarize_week(
        _input(include_goals=False),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),  # empty buckets
    )
    assert result.total_spend == 0.0
    assert result.transaction_count == 0
    assert result.top_categories == []
    assert result.goals == []
    assert "no spending recorded" in result.paragraph
    assert "Quiet week." in result.paragraph


# ─── Top categories sort + cap ──────────────────────────────────────


async def test_top_categories_sorted_desc(transactions_coll, goals_coll):
    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator({
            "food.delivery": 200.0,
            "transport.transit": 24.0,
            "shopping.amazon": 73.0,
        }),
    )
    cats = [c.category for c in result.top_categories]
    assert cats == ["food.delivery", "shopping.amazon", "transport.transit"]


async def test_top_categories_capped_at_5(transactions_coll, goals_coll):
    by_cat = {f"cat.{i}": float(100 - i) for i in range(8)}
    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(by_cat),
    )
    assert len(result.top_categories) == 5
    # Capped to the highest 5.
    expected = sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)[:5]
    assert [c.category for c in result.top_categories] == [k for k, _ in expected]


# ─── pct_of_total uses the WHOLE week total ─────────────────────────


async def test_pct_of_total_uses_full_week_total(transactions_coll, goals_coll):
    """Total $1000, top category $470 → pct_of_total = 47.0 (not 47/sum-of-top-5)."""
    by_cat = {
        "biggest": 470.0,
        "second": 200.0,
        "third": 150.0,
        "fourth": 100.0,
        "fifth": 50.0,
        "sixth": 30.0,
    }
    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(by_cat),
    )
    assert result.total_spend == 1000.0
    assert result.top_categories[0].category == "biggest"
    assert result.top_categories[0].pct_of_total == 47.0


# ─── transaction_count outflow only ─────────────────────────────────


async def test_transaction_count_outflow_only(transactions_coll, goals_coll):
    week_day = date(2026, 5, 20)
    await _seed_txn(transactions_coll, "u_482", week_day, -50.0)
    await _seed_txn(transactions_coll, "u_482", week_day, -30.0)
    await _seed_txn(transactions_coll, "u_482", week_day, 2400.0)  # income — excluded
    await _seed_txn(transactions_coll, "u_482", date(2026, 5, 10), -99.0)  # prior week — excluded

    result = await summarize_week(
        _input(include_goals=False),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator({"food.delivery": 80.0}),
    )
    assert result.transaction_count == 2


# ─── include_goals=False ────────────────────────────────────────────


async def test_include_goals_false_returns_empty(transactions_coll, goals_coll):
    await _seed_goal(goals_coll)
    result = await summarize_week(
        _input(include_goals=False),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    assert result.goals == []


# ─── include_goals=True + no active goals ──────────────────────────


async def test_no_active_goals_returns_empty(transactions_coll, goals_coll):
    # Paused goal — should NOT appear.
    await _seed_goal(goals_coll, status="paused")
    result = await summarize_week(
        _input(include_goals=True),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    assert result.goals == []


# ─── goal snapshots compute pace ────────────────────────────────────


async def test_goal_snapshots_compute_pace(transactions_coll, goals_coll):
    # Behind: 30% complete by 2026-05-24, ~40% elapsed of the year
    await _seed_goal(goals_coll, title="Behind goal", current_amount=2400.0)
    # Ahead: 80% complete by 2026-05-24
    await _seed_goal(goals_coll, title="Ahead goal", current_amount=6400.0)
    # On track: 41% complete by 2026-05-24 (close to expected ~40%)
    await _seed_goal(goals_coll, title="On-track goal", current_amount=3280.0)

    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    notes = {g.title: g.note for g in result.goals}
    assert "Behind" in notes["Behind goal"]
    assert "Ahead" in notes["Ahead goal"]
    assert "On track" in notes["On-track goal"]


# ─── past-due goal ──────────────────────────────────────────────────


async def test_past_due_goal_note(transactions_coll, goals_coll):
    await _seed_goal(
        goals_coll,
        target_date=datetime(2026, 1, 31),
        current_amount=2400.0,
        target_amount=8000.0,
    )
    result = await summarize_week(
        _input(as_of=date(2026, 5, 24)),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    assert result.goals[0].note.startswith("Past due")
    assert "5600" in result.goals[0].note  # 8000 - 2400 short


# ─── complete goal note ─────────────────────────────────────────────


async def test_complete_goal_note_via_status(transactions_coll, goals_coll):
    await _seed_goal(goals_coll, status="complete", current_amount=8000.0)
    # status="active" only filter — complete goals shouldn't even show up.
    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    assert result.goals == []  # status filter excludes them


async def test_complete_goal_note_via_pct(transactions_coll, goals_coll):
    """Edge: an 'active' goal whose current_amount already matches target."""
    await _seed_goal(goals_coll, status="active", current_amount=8000.0)
    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator(),
    )
    assert result.goals[0].note == "Goal reached."
    assert result.goals[0].pct_complete == 100.0


# ─── user isolation on BOTH collections ─────────────────────────────


async def test_user_isolation_both_collections(transactions_coll, goals_coll):
    # Seed another user's transactions + goal — must NOT influence u_482.
    await _seed_txn(transactions_coll, "u_other", date(2026, 5, 20), -999.0)
    await _seed_goal(goals_coll, user_id="u_other", current_amount=9999.0, title="Their goal")

    # u_482 has just one outflow row this week.
    await _seed_txn(transactions_coll, "u_482", date(2026, 5, 20), -50.0)

    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator({"food.delivery": 50.0}),
    )
    assert result.transaction_count == 1
    assert result.goals == []  # u_482 has no goal seeded
    assert "Their goal" not in result.paragraph


# ─── paragraph format ───────────────────────────────────────────────


async def test_paragraph_format_whole_dollars(transactions_coll, goals_coll):
    await _seed_goal(goals_coll, current_amount=2400.0)
    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator({
            "food.delivery": 211.0,
            "transport.transit": 24.0,
            "shopping.amazon": 73.0,
        }),
    )
    p = result.paragraph
    assert p, "paragraph must be non-empty"
    # Whole-dollar formatting (no decimals)
    assert "$211" in p and "211.00" not in p
    assert "$24" in p
    assert "$73" in p
    # Pretty category names
    assert "Food Delivery" in p
    assert "Transport Transit" in p
    # Single-goal tail clause
    assert "to Emergency Fund" in p


async def test_paragraph_multi_goal_attention_count(transactions_coll, goals_coll):
    await _seed_goal(goals_coll, current_amount=2400.0, title="g1")  # behind
    await _seed_goal(goals_coll, current_amount=6400.0, title="g2")  # ahead
    result = await summarize_week(
        _input(),
        collection=transactions_coll,
        goals_collection=goals_coll,
        aggregator=make_aggregator({"food.delivery": 100.0}),
    )
    assert "2 active goals" in result.paragraph
    assert "1 need attention" in result.paragraph  # one behind, one ahead


# ─── Validation ─────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        SummarizeWeekInput(user_id="")


def test_validation_week_offset_positive():
    with pytest.raises(ValidationError):
        SummarizeWeekInput(user_id="u", week_offset=1)


def test_validation_week_offset_below_minus_12():
    with pytest.raises(ValidationError):
        SummarizeWeekInput(user_id="u", week_offset=-13)


# ─── Tripwire (#14 pattern) ─────────────────────────────────────────


async def test_no_modification_of_any_collection(
    transactions_coll, goals_coll, monkeypatch
):
    """Any silent fallback to the global db handle must fail loud."""
    with get_database_tripwire(monkeypatch, summarize_week_module):
        await summarize_week(
            _input(),
            collection=transactions_coll,
            goals_collection=goals_coll,
            aggregator=make_aggregator(),
        )
    # Read-only on both collections.
    assert await transactions_coll.count_documents({}) == 0
    assert await goals_coll.count_documents({}) == 0
