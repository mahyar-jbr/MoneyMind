from datetime import date

from app.ingestion.csv import canonicalize_merchant, parse_transactions_csv


def test_canonicalize_merchant():
    assert canonicalize_merchant("Uber Eats!") == "uber_eats"
    assert canonicalize_merchant("McDonald's") == "mcdonalds"


def test_parse_transactions_csv_builds_documents():
    content = b"date,merchant,category,amount,currency\n2026-02-12,DoorDash,food.delivery,-38.42,USD\n"

    result = parse_transactions_csv(content, source_date=date(2026, 5, 24))

    assert result.source == "csv_import_2026-05-24"
    assert result.errors == []
    assert result.documents[0]["user_id"] == "u_482"
    assert result.documents[0]["merchant_canonical"] == "doordash"
    assert result.documents[0]["amount"] == -38.42


def test_parse_transactions_csv_reports_bad_rows():
    content = b"date,merchant,category,amount,currency\nnope,DoorDash,food.delivery,abc,USD\n"

    result = parse_transactions_csv(content)

    assert result.documents == []
    assert result.errors[0]["row"] == 2
