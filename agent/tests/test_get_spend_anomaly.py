from datetime import date, datetime, timedelta

import pytest
from pydantic import ValidationError

from agent.tests._fakes import make_mongomock_collection
from agent.tools.get_spend_anomaly import (
    GetSpendAnomalyInput,
    get_spend_anomaly,
)


def _doc(user_id, d, category, amount, merchant="DoorDash"):
    return {
        "user_id": user_id,
        "date": datetime(d.year, d.month, d.day),
        "merchant": merchant,
        "merchant_canonical": merchant.lower().replace(" ", "_"),
        "category": category,
        "amount": amount,
        "currency": "USD",
    }


async def _collection_with(docs):
    coll = make_mongomock_collection()
    if docs:
        await coll.insert_many(docs)
    return coll


@pytest.fixture
async def spike_data():
    """8 baseline buckets averaging $70/bucket with realistic variation, then $250 current.

    For as_of=2026-05-23 and window_days=7:
      - window = [2026-05-17, 2026-05-23]
      - baseline_start = 2026-03-22 (= window_start - 8*7)
      - baseline buckets: [03-22, 03-29), [03-29, 04-05), ..., [05-10, 05-17)
    Bucket totals: 60, 80, 60, 80, 60, 80, 60, 80 → mean=70, std=10, $250 ⇒ z=18.
    Seed at +1 and +3 day offsets so nothing rides a bucket boundary.
    """
    docs = []
    baseline_start = date(2026, 3, 22)
    for bucket in range(8):
        bucket_anchor = baseline_start + timedelta(weeks=bucket)
        per_doc = 30.0 if bucket % 2 == 0 else 40.0  # 60 or 80 per bucket
        docs.append(_doc("u_482", bucket_anchor + timedelta(days=1), "food.delivery", -per_doc))
        docs.append(_doc("u_482", bucket_anchor + timedelta(days=3), "food.delivery", -per_doc))
    # Current window
    docs.append(_doc("u_482", date(2026, 5, 19), "food.delivery", -120.0))
    docs.append(_doc("u_482", date(2026, 5, 22), "food.delivery", -130.0))
    # Decoys
    docs.append(_doc("u_482", date(2026, 5, 22), "food.coffee", -10.0))
    docs.append(_doc("u_other", date(2026, 5, 22), "food.delivery", -9999.0))
    return await _collection_with(docs)


@pytest.fixture
async def flat_data():
    """8 baseline buckets where every bucket sums to exactly $23.45 in transport.transit.

    Each bucket gets 7 days * $3.35 = $23.45. Std must be exactly 0.
    """
    docs = []
    baseline_start = date(2026, 3, 22)
    for bucket in range(8):
        bucket_anchor = baseline_start + timedelta(weeks=bucket)
        for day_offset in range(7):
            docs.append(
                _doc(
                    "u_482",
                    bucket_anchor + timedelta(days=day_offset),
                    "transport.transit",
                    -3.35,
                    merchant="Presto",
                )
            )
    return await _collection_with(docs)


@pytest.fixture
async def empty_baseline_data():
    """Only current-window rows for u_482, nothing earlier."""
    docs = [
        _doc("u_482", date(2026, 5, 19), "food.delivery", -30.0),
        _doc("u_482", date(2026, 5, 22), "food.delivery", -40.0),
    ]
    return await _collection_with(docs)


# ─── AC: spike fires ────────────────────────────────────────────────


async def test_spike_fires_with_high_z(spike_data):
    result = await get_spend_anomaly(
        GetSpendAnomalyInput(
            user_id="u_482",
            category="food.delivery",
            window_days=7,
            baseline_weeks=8,
            as_of=date(2026, 5, 23),
        ),
        collection=spike_data,
    )
    assert result.is_anomaly is True
    assert result.z_score >= 2.0
    assert result.current_spend == 250.0
    assert result.baseline_mean == 70.0
    assert result.note is not None
    assert "Food Delivery" in result.note
    assert "x your" in result.note


# ─── AC: quiet category, std==0 ⇒ never anomaly ──────────────────────


async def test_flat_category_never_anomaly(flat_data):
    result = await get_spend_anomaly(
        GetSpendAnomalyInput(
            user_id="u_482",
            category="transport.transit",
            window_days=7,
            baseline_weeks=8,
            as_of=date(2026, 5, 23),
        ),
        collection=flat_data,
    )
    assert result.baseline_std == 0.0
    assert result.z_score == 0.0
    assert result.is_anomaly is False
    assert result.note is None


# ─── AC: empty baseline ──────────────────────────────────────────────


async def test_empty_baseline_no_anomaly_with_note(empty_baseline_data):
    result = await get_spend_anomaly(
        GetSpendAnomalyInput(
            user_id="u_482",
            category="food.delivery",
            window_days=7,
            baseline_weeks=8,
            as_of=date(2026, 5, 23),
        ),
        collection=empty_baseline_data,
    )
    assert result.baseline_mean == 0.0
    assert result.baseline_std == 0.0
    assert result.z_score == 0.0
    assert result.is_anomaly is False
    assert result.baseline_weeks_used == 0
    assert result.current_spend == 70.0
    assert result.note == "Food Delivery spend appeared this week (no prior history)."


# ─── AC: window inclusivity both ends ────────────────────────────────


async def test_window_endpoints_inclusive():
    """A row dated exactly window_start AND a row dated exactly window_end count."""
    docs = [
        _doc("u_482", date(2026, 5, 17), "food.delivery", -50.0),  # window_start
        _doc("u_482", date(2026, 5, 23), "food.delivery", -50.0),  # window_end
        _doc("u_482", date(2026, 5, 16), "food.delivery", -999.0),  # one day BEFORE window
        _doc("u_482", date(2026, 5, 24), "food.delivery", -999.0),  # one day AFTER window
    ]
    coll = await _collection_with(docs)
    result = await get_spend_anomaly(
        GetSpendAnomalyInput(
            user_id="u_482",
            category="food.delivery",
            window_days=7,
            baseline_weeks=2,
            as_of=date(2026, 5, 23),
        ),
        collection=coll,
    )
    assert result.window_start == date(2026, 5, 17)
    assert result.window_end == date(2026, 5, 23)
    assert result.current_spend == 100.0  # 50 + 50, decoys excluded


# ─── AC: user isolation ──────────────────────────────────────────────


async def test_user_isolation_prevents_baseline_contamination():
    """u_other's huge baseline must not influence u_482's verdict."""
    docs = []
    baseline_start = date(2026, 3, 22)
    for bucket in range(8):
        bucket_anchor = baseline_start + timedelta(weeks=bucket)
        # u_other has gigantic baseline
        docs.append(_doc("u_other", bucket_anchor + timedelta(days=2), "food.delivery", -1000.0))
        # u_482 averages $70/bucket with realistic variation (so std > 0)
        per_doc = 30.0 if bucket % 2 == 0 else 40.0  # 60 or 80 per bucket
        docs.append(_doc("u_482", bucket_anchor + timedelta(days=1), "food.delivery", -per_doc))
        docs.append(_doc("u_482", bucket_anchor + timedelta(days=3), "food.delivery", -per_doc))
    docs.append(_doc("u_482", date(2026, 5, 19), "food.delivery", -250.0))
    coll = await _collection_with(docs)

    r482 = await get_spend_anomaly(
        GetSpendAnomalyInput(
            user_id="u_482",
            category="food.delivery",
            window_days=7,
            baseline_weeks=8,
            as_of=date(2026, 5, 23),
        ),
        collection=coll,
    )
    assert r482.baseline_mean == 70.0  # NOT 1000
    assert r482.is_anomaly is True


# ─── AC: downside is never an anomaly ────────────────────────────────


async def test_downside_never_anomaly():
    """If current_spend < baseline_mean, is_anomaly is False even with high |z|."""
    docs = []
    baseline_start = date(2026, 3, 22)
    for bucket in range(8):
        bucket_anchor = baseline_start + timedelta(weeks=bucket)
        # Variable amounts so std > 0
        amt = -(50.0 if bucket % 2 == 0 else 80.0)
        docs.append(_doc("u_482", bucket_anchor + timedelta(days=2), "food.delivery", amt))
    # Current week: $0 (no rows). current_spend << mean.
    coll = await _collection_with(docs)
    result = await get_spend_anomaly(
        GetSpendAnomalyInput(
            user_id="u_482",
            category="food.delivery",
            window_days=7,
            baseline_weeks=8,
            as_of=date(2026, 5, 23),
        ),
        collection=coll,
    )
    assert result.current_spend == 0.0
    assert result.baseline_mean > 0
    assert result.is_anomaly is False


# ─── Validation ──────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        GetSpendAnomalyInput(user_id="", category="food.delivery")


def test_validation_empty_category():
    with pytest.raises(ValidationError):
        GetSpendAnomalyInput(user_id="u_482", category="")


def test_validation_zero_window_days():
    with pytest.raises(ValidationError):
        GetSpendAnomalyInput(user_id="u_482", category="food.delivery", window_days=0)


def test_validation_baseline_weeks_minimum():
    with pytest.raises(ValidationError):
        GetSpendAnomalyInput(user_id="u_482", category="food.delivery", baseline_weeks=1)
