from datetime import UTC, datetime

from fastapi import HTTPException
import pytest

from app.api.aggregations import parse_date_param


def test_parse_date_param_attaches_utc_to_naive_dates():
    assert parse_date_param("2026-05-31", "to") == datetime(2026, 5, 31, tzinfo=UTC)


def test_parse_date_param_rolls_date_only_upper_bound_to_next_day():
    assert parse_date_param("2026-05-31", "to", upper_bound=True) == datetime(2026, 6, 1, tzinfo=UTC)


def test_parse_date_param_keeps_explicit_time_upper_bound():
    assert parse_date_param("2026-05-31T12:30:00", "to", upper_bound=True) == datetime(
        2026,
        5,
        31,
        12,
        30,
        tzinfo=UTC,
    )


def test_parse_date_param_rejects_bad_dates():
    with pytest.raises(HTTPException):
        parse_date_param("not-a-date", "to")
