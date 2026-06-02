from datetime import UTC, date, datetime

from app.ingestion.csv import canonicalize_merchant, parse_transactions_csv


def test_canonicalize_merchant():
    assert canonicalize_merchant("Uber Eats!") == "uber_eats"
    assert canonicalize_merchant("McDonald's") == "mcdonalds"


def test_parse_transactions_csv_builds_documents():
    content = b"date,merchant,category,amount,currency\n2026-02-12,DoorDash,food.delivery,-38.42,USD\n"

    result = parse_transactions_csv(
        content,
        source_date=date(2026, 5, 24),
        source_name="synthetic.csv",
    )

    assert result.source.startswith("csv_import_2026-05-24_synthetic_csv_")
    assert result.errors == []
    assert result.documents[0]["user_id"] == "u_482"
    assert result.documents[0]["merchant_canonical"] == "doordash"
    assert result.documents[0]["amount"] == -38.42


def test_parse_transactions_csv_ignores_user_id_column():
    content = (
        b"date,merchant,category,amount,currency,user_id\n"
        b"2026-02-12,DoorDash,food.delivery,-38.42,USD,u_attacker\n"
    )

    result = parse_transactions_csv(content, default_user_id="user_clerk_123")

    assert result.errors == []
    assert result.documents[0]["user_id"] == "user_clerk_123"


def test_parse_transactions_csv_source_changes_with_content():
    first = b"date,merchant,category,amount,currency\n2026-02-12,DoorDash,food.delivery,-38.42,USD\n"
    second = b"date,merchant,category,amount,currency\n2026-02-12,DoorDash,food.delivery,-39.42,USD\n"

    first_result = parse_transactions_csv(
        first,
        source_date=date(2026, 5, 24),
        source_name="synthetic.csv",
    )
    second_result = parse_transactions_csv(
        second,
        source_date=date(2026, 5, 24),
        source_name="synthetic.csv",
    )

    assert first_result.source != second_result.source


def test_parse_transactions_csv_converts_timezone_offsets_to_utc():
    content = b"date,merchant,category,amount,currency\n2026-02-12T09:00-05:00,DoorDash,food.delivery,-38.42,USD\n"

    result = parse_transactions_csv(content)

    assert result.errors == []
    assert result.documents[0]["date"] == datetime(2026, 2, 12, 14, 0, tzinfo=UTC)


def test_parse_transactions_csv_reports_bad_rows():
    content = b"date,merchant,category,amount,currency\nnope,DoorDash,food.delivery,abc,USD\n"

    result = parse_transactions_csv(content)

    assert result.documents == []
    assert result.errors[0]["row"] == 2
