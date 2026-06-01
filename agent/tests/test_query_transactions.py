from datetime import date, datetime

import pytest
from pydantic import ValidationError

from agent.tests._fakes import make_mongomock_collection
from agent.tools.query_transactions import (
    QueryTransactionsInput,
    TransactionRow,
    query_transactions,
)


SEED = [
    # u_482 — 8 rows spanning May 17 → May 24, mixed categories, mixed sign
    {"user_id": "u_482", "date": datetime(2026, 5, 17), "merchant": "Starbucks", "merchant_canonical": "starbucks", "category": "food.coffee", "amount": -6.50, "currency": "USD"},
    {"user_id": "u_482", "date": datetime(2026, 5, 18), "merchant": "DoorDash", "merchant_canonical": "doordash", "category": "food.delivery", "amount": -38.42, "currency": "USD"},
    {"user_id": "u_482", "date": datetime(2026, 5, 19), "merchant": "DoorDash", "merchant_canonical": "doordash", "category": "food.delivery", "amount": -52.10, "currency": "USD"},
    {"user_id": "u_482", "date": datetime(2026, 5, 20), "merchant": "Direct Deposit", "merchant_canonical": "direct_deposit", "category": "income.salary", "amount": 2400.00, "currency": "USD"},
    {"user_id": "u_482", "date": datetime(2026, 5, 21), "merchant": "Loblaws", "merchant_canonical": "loblaws", "category": "food.groceries", "amount": -78.95, "currency": "USD"},
    {"user_id": "u_482", "date": datetime(2026, 5, 22), "merchant": "DoorDash", "merchant_canonical": "doordash", "category": "food.delivery", "amount": -120.69, "currency": "USD"},
    {"user_id": "u_482", "date": datetime(2026, 5, 23), "merchant": "DoorDash", "merchant_canonical": "doordash", "category": "food.delivery", "amount": -46.10, "currency": "USD"},
    {"user_id": "u_482", "date": datetime(2026, 5, 24), "merchant": "Amazon", "merchant_canonical": "amazon", "category": "shopping.amazon", "amount": -73.13, "currency": "USD"},
    # Other user — should never appear in u_482's results
    {"user_id": "u_other", "date": datetime(2026, 5, 22), "merchant": "DoorDash", "merchant_canonical": "doordash", "category": "food.delivery", "amount": -999.99, "currency": "USD"},
]


@pytest.fixture
async def collection():
    coll = make_mongomock_collection()
    await coll.insert_many([dict(d) for d in SEED])
    return coll


async def test_returns_only_target_users_rows(collection):
    result = await query_transactions(
        QueryTransactionsInput(user_id="u_482"), collection=collection
    )
    assert result.user_id == "u_482"
    assert result.count == 8
    assert all(isinstance(r, TransactionRow) for r in result.transactions)
    # No leak from u_other
    assert all(r.amount != -999.99 for r in result.transactions)


async def test_sorted_date_desc(collection):
    result = await query_transactions(
        QueryTransactionsInput(user_id="u_482"), collection=collection
    )
    dates = [r.date for r in result.transactions]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == date(2026, 5, 24)


async def test_category_filter(collection):
    result = await query_transactions(
        QueryTransactionsInput(user_id="u_482", category="food.delivery"),
        collection=collection,
    )
    assert result.count == 4
    assert all(r.category == "food.delivery" for r in result.transactions)


async def test_date_range_inclusive_both_ends(collection):
    # Row on the upper bound (2026-05-23) MUST be included.
    result = await query_transactions(
        QueryTransactionsInput(
            user_id="u_482",
            date_from=date(2026, 5, 18),
            date_to=date(2026, 5, 23),
        ),
        collection=collection,
    )
    dates = {r.date for r in result.transactions}
    assert date(2026, 5, 18) in dates
    assert date(2026, 5, 23) in dates
    assert date(2026, 5, 17) not in dates
    assert date(2026, 5, 24) not in dates
    assert result.count == 6


async def test_outflow_only_excludes_income(collection):
    all_rows = await query_transactions(
        QueryTransactionsInput(user_id="u_482"), collection=collection
    )
    assert any(r.amount > 0 for r in all_rows.transactions)  # income is in there by default

    out = await query_transactions(
        QueryTransactionsInput(user_id="u_482", outflow_only=True),
        collection=collection,
    )
    assert all(r.amount < 0 for r in out.transactions)
    assert out.count == 7  # 8 total - 1 income row


async def test_amount_bounds_on_absolute_value(collection):
    result = await query_transactions(
        QueryTransactionsInput(user_id="u_482", min_amount=50, max_amount=100, outflow_only=True),
        collection=collection,
    )
    # rows with abs(amount) in [50, 100]: -52.10, -78.95, -73.13
    assert result.count == 3
    assert {round(r.amount, 2) for r in result.transactions} == {-52.10, -78.95, -73.13}


async def test_limit_caps_results(collection):
    result = await query_transactions(
        QueryTransactionsInput(user_id="u_482", limit=3), collection=collection
    )
    assert result.count == 3


def test_validation_rejects_empty_user_id():
    with pytest.raises(ValidationError):
        QueryTransactionsInput(user_id="")


def test_validation_rejects_zero_limit():
    with pytest.raises(ValidationError):
        QueryTransactionsInput(user_id="u_482", limit=0)


def test_validation_rejects_limit_over_500():
    with pytest.raises(ValidationError):
        QueryTransactionsInput(user_id="u_482", limit=501)


async def test_empty_result_returns_zero_count(collection):
    result = await query_transactions(
        QueryTransactionsInput(user_id="u_does_not_exist"), collection=collection
    )
    assert result.count == 0
    assert result.transactions == []


async def test_iso_string_dates_coerced(collection):
    # Demo proof in the ticket passes ISO strings; Pydantic v2 must coerce them.
    result = await query_transactions(
        QueryTransactionsInput.model_validate(
            {"user_id": "u_482", "date_from": "2026-05-18", "date_to": "2026-05-23"}
        ),
        collection=collection,
    )
    assert result.count == 6
