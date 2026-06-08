"""Statement-ingest pipeline tests.

Real Gemini calls cost $0.02 and ~5s each, so tests inject a fake
parser that returns canned `StatementParseResult` objects mirroring
what we observed Gemini produces against docs/Summary.pdf. The
canonicalizer-override behavior is exercised separately in
test_merchant_canonical.py.

What's covered here:
  - Pipeline writes the right docs to atlas.transactions
  - Source-hash dedupe: second upload of same bytes inserts 0
  - Negative amounts split out as `skipped_payments` (not user spending)
  - by_category aggregates roll up by top-level prefix
  - LLM extraction failure produces a clean error, not a crash
"""

from datetime import date, datetime

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.ingestion.pipeline import run_ingest
from app.ingestion.statement_parser import StatementParseResult


def _doc(category: str, amount: float, merchant: str = "Tim Hortons") -> dict:
    """Build a transaction doc in the shape the parser produces.
    `source` is filled in by the fake parser per-call so it matches the
    pipeline's source-hash dedupe predicate.
    """
    return {
        "user_id": "user_test",
        "date": datetime(2026, 5, 1),
        "merchant": merchant,
        "merchant_canonical": merchant.lower().replace(" ", "_"),
        "category": category,
        "amount": amount,
        "currency": "CAD",
        "raw": {"description": merchant},
    }


def _fake_parser_factory(docs: list[dict], skipped_payments: list[dict] | None = None):
    """Returns a parser stand-in that yields the given canned docs.

    Stamps the same `source` string the pipeline's dedupe layer expects
    (suffix is `_<source_hash>`), so a re-upload of the same bytes hits
    the duplicate path.
    """

    def _fake(pdf_bytes, *, user_id, source_name, source_hash):
        source = f"statement_summary_pdf_{source_hash}"
        rewritten = [
            {**d, "user_id": user_id, "source": source} for d in docs
        ]
        return StatementParseResult(
            documents=rewritten,
            skipped_payments=skipped_payments or [],
            issuer="American Express",
            account_last4="71009",
            period_start=date(2026, 4, 20),
            period_end=date(2026, 5, 19),
            warnings=[],
            source=source,
        )

    return _fake


@pytest.fixture
def transactions():
    client = AsyncMongoMockClient()
    return client["moneymind"]["transactions"]


pytestmark = pytest.mark.asyncio


# ─── Happy path ────────────────────────────────────────────────────


async def test_writes_documents_and_returns_summary(transactions):
    """Pipeline writes docs + returns aggregate summary."""
    fake = _fake_parser_factory(
        docs=[
            _doc("food.coffee", -6.77, "Tim Hortons"),
            _doc("food.coffee", -1.92, "Tim Hortons"),
            _doc("transport.gas", -28.91, "Esso"),
            _doc("shopping.amazon", -58.08, "Amazon"),
        ],
        skipped_payments=[
            {
                "date": datetime(2026, 4, 20),
                "merchant": "PAYMENT RECEIVED - THANK YOU",
                "merchant_canonical": "card_payment",
                "amount": -800.00,
                "currency": "CAD",
                "reason": "payment_or_credit",
            }
        ],
    )

    result = await run_ingest(
        b"fake pdf bytes",
        user_id="user_test",
        source_name="Summary.pdf",
        transactions=transactions,
        parser=fake,
    )

    assert result.inserted == 4
    assert result.duplicate_of_prior_upload is False
    assert result.payment_count == 1
    assert result.payment_total == 800.00
    # Aggregates roll up by TOP-LEVEL category prefix
    assert result.by_category == {
        "food": 8.69,
        "transport": 28.91,
        "shopping": 58.08,
    }
    assert result.total_spend == 95.68
    # Docs actually landed in the collection
    assert await transactions.count_documents({"user_id": "user_test"}) == 4


async def test_payment_rows_excluded_from_transactions(transactions):
    """Skipped payments must NOT appear in transactions collection."""
    fake = _fake_parser_factory(
        docs=[_doc("food.coffee", -6.77)],
        skipped_payments=[
            {
                "date": datetime(2026, 4, 20),
                "merchant": "PAYMENT RECEIVED - THANK YOU",
                "merchant_canonical": "card_payment",
                "amount": -800.00,
                "currency": "CAD",
                "reason": "payment_or_credit",
            },
        ],
    )

    await run_ingest(
        b"fake", user_id="user_test", source_name="x.pdf",
        transactions=transactions, parser=fake,
    )

    # Only the food coffee row got inserted; the payment did not.
    assert await transactions.count_documents({}) == 1
    payments_in_collection = await transactions.count_documents(
        {"merchant_canonical": "card_payment"}
    )
    assert payments_in_collection == 0


# ─── Idempotency ───────────────────────────────────────────────────


async def test_reupload_same_bytes_inserts_zero(transactions):
    """Source-hash dedupe: uploading the same PDF twice doesn't duplicate."""
    fake = _fake_parser_factory(docs=[_doc("food.coffee", -6.77)])

    first = await run_ingest(
        b"same bytes", user_id="user_test", source_name="x.pdf",
        transactions=transactions, parser=fake,
    )
    assert first.inserted == 1
    assert first.duplicate_of_prior_upload is False

    second = await run_ingest(
        b"same bytes", user_id="user_test", source_name="x.pdf",
        transactions=transactions, parser=fake,
    )
    assert second.inserted == 0
    assert second.duplicate_of_prior_upload is True
    # Still exactly 1 doc, not 2.
    assert await transactions.count_documents({"user_id": "user_test"}) == 1


async def test_reupload_returns_prior_aggregates_so_user_sees_summary(transactions):
    """Second upload should still report the by_category breakdown so the
    user sees a useful 'already imported, here's what we have' message."""
    fake = _fake_parser_factory(
        docs=[
            _doc("food.coffee", -6.77),
            _doc("transport.gas", -28.91),
        ],
    )
    await run_ingest(b"x", user_id="user_test", source_name="x.pdf",
                     transactions=transactions, parser=fake)

    second = await run_ingest(
        b"x", user_id="user_test", source_name="x.pdf",
        transactions=transactions, parser=fake,
    )
    assert second.duplicate_of_prior_upload is True
    assert second.by_category == {"food": 6.77, "transport": 28.91}
    assert second.total_spend == 35.68


async def test_different_file_same_user_still_inserts(transactions):
    """Two genuinely different statements both ingest fine."""
    fake_apr = _fake_parser_factory(docs=[_doc("food.coffee", -6.77, "Tim April")])
    fake_may = _fake_parser_factory(docs=[_doc("food.coffee", -1.92, "Tim May")])

    a = await run_ingest(
        b"april bytes", user_id="user_test", source_name="apr.pdf",
        transactions=transactions, parser=fake_apr,
    )
    b = await run_ingest(
        b"may bytes", user_id="user_test", source_name="may.pdf",
        transactions=transactions, parser=fake_may,
    )
    assert a.inserted == 1
    assert b.inserted == 1
    assert await transactions.count_documents({"user_id": "user_test"}) == 2


# ─── User isolation ────────────────────────────────────────────────


async def test_user_isolation_dedupe_per_user(transactions):
    """User A and User B uploading the SAME PDF bytes both ingest fully —
    the dedupe is scoped to (user_id, source_hash)."""
    fake = _fake_parser_factory(docs=[_doc("food.coffee", -6.77)])

    a = await run_ingest(
        b"same", user_id="user_alice", source_name="x.pdf",
        transactions=transactions, parser=fake,
    )
    b = await run_ingest(
        b"same", user_id="user_bob", source_name="x.pdf",
        transactions=transactions, parser=fake,
    )
    assert a.inserted == 1
    assert b.inserted == 1
    assert await transactions.count_documents({"user_id": "user_alice"}) == 1
    assert await transactions.count_documents({"user_id": "user_bob"}) == 1


# ─── Failure modes ─────────────────────────────────────────────────


async def test_empty_pdf_bytes_returns_clean_failure(transactions):
    result = await run_ingest(
        b"", user_id="user_test", source_name="empty.pdf",
        transactions=transactions, parser=None,
    )
    # parse_statement_pdf is the default parser; empty bytes returns a
    # warned StatementParseResult with no docs.
    assert result.inserted == 0
    assert result.duplicate_of_prior_upload is False


async def test_llm_failure_returns_zero_inserted_with_warning(transactions):
    """When the LLM call blows up, ingest returns a clean 0-inserted
    result with a warning — not a 500."""

    def _failing_parser(pdf_bytes, *, user_id, source_name, source_hash):
        return StatementParseResult(
            documents=[],
            skipped_payments=[],
            issuer="",
            account_last4="",
            period_start=None,
            period_end=None,
            warnings=["extraction failed: ValueError: model returned garbage"],
            source=f"statement_x_{source_hash}",
        )

    result = await run_ingest(
        b"bytes", user_id="user_test", source_name="x.pdf",
        transactions=transactions, parser=_failing_parser,
    )

    assert result.inserted == 0
    assert "extraction failed" in result.parsed.warnings[0]
    assert await transactions.count_documents({}) == 0
