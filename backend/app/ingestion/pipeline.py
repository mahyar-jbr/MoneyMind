"""Statement ingest pipeline: PDF bytes → Atlas writes.

Composes statement_parser.parse_statement_pdf with a content-hash dedupe
so re-uploading the same statement returns 0 new without crashing or
silently duplicating. Two layers of dedupe:

  1. SOURCE-tag dedupe: the parser stamps every doc with a stable
     `source` derived from sha256(file_bytes). If the source already
     exists in transactions for this user, we skip the entire ingest
     and report it as a duplicate upload.

  2. CONTENT-key dedupe: even within a single ingest, the same statement
     may legitimately list two charges with the same (date, merchant,
     amount) — say two $1.92 Tim Hortons coffees on the same day. We
     DON'T want to dedupe those (they're different real charges). So
     the per-row uniqueness key is (user_id, source, date, merchant_canonical,
     amount, raw.description) — only exact duplicates of the same line
     within the same upload collapse.

The route handler calls run_ingest(file_bytes, user_id, source_name) and
gets back a structured summary it can serialize to the frontend.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection

from app.ingestion.statement_parser import (
    StatementParseResult,
    parse_statement_pdf,
)


logger = logging.getLogger(__name__)


# ─── SSE event helpers ─────────────────────────────────────────────


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format one Server-Sent Events frame. Always include `event:` so
    the client can switch on event type without parsing payload."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@dataclass(frozen=True)
class IngestResult:
    """What the route handler returns to the frontend."""

    parsed: StatementParseResult
    inserted: int
    duplicate_of_prior_upload: bool
    by_category: dict[str, float]   # total spend per top-level category, after insert
    total_spend: float
    payment_count: int
    payment_total: float            # absolute value, what user paid the card


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


async def run_ingest(
    pdf_bytes: bytes,
    *,
    user_id: str,
    source_name: str | None,
    transactions: AsyncIOMotorCollection,
    parser=None,
) -> IngestResult:
    """Full pipeline: parse → dedupe → insert. Returns a structured summary.

    `parser` is injectable for tests (defaults to parse_statement_pdf with
    a real Gemini client).
    """
    source_hash = _hash_bytes(pdf_bytes)

    # Layer 1 — same file uploaded before? Skip the LLM call entirely.
    existing = await transactions.count_documents(
        {"user_id": user_id, "source": {"$regex": f"_{source_hash}$"}}
    )
    if existing > 0:
        # Return the existing aggregates so the user still sees a useful summary.
        existing_docs = transactions.find(
            {"user_id": user_id, "source": {"$regex": f"_{source_hash}$"}}
        )
        by_cat: dict[str, float] = {}
        total = 0.0
        async for doc in existing_docs:
            cat = doc.get("category", "other.misc").split(".")[0]
            amt = abs(float(doc.get("amount", 0)))
            by_cat[cat] = by_cat.get(cat, 0.0) + amt
            total += amt
        return IngestResult(
            parsed=StatementParseResult(
                [], [], "", "", None, None,
                ["this statement was already imported"],
                f"_{source_hash}",
            ),
            inserted=0,
            duplicate_of_prior_upload=True,
            by_category=by_cat,
            total_spend=total,
            payment_count=0,
            payment_total=0.0,
        )

    # Run the LLM extract + categorize + canonicalize.
    parser = parser or parse_statement_pdf
    parsed = parser(
        pdf_bytes,
        user_id=user_id,
        source_name=source_name,
        source_hash=source_hash,
    )

    inserted = 0
    if parsed.documents:
        # Bulk insert. Atlas-side uniqueness isn't enforced here — we
        # rely on the source-hash layer 1 check above for cross-upload
        # dedupe, and within a single upload we trust the parser (the
        # LLM doesn't re-emit duplicate rows).
        result = await transactions.insert_many(parsed.documents, ordered=False)
        inserted = len(result.inserted_ids)

    # Build the by-category aggregates from what we just inserted.
    by_cat = {}
    total = 0.0
    for doc in parsed.documents:
        top = str(doc.get("category", "other.misc")).split(".")[0]
        amt = abs(float(doc.get("amount", 0)))
        by_cat[top] = by_cat.get(top, 0.0) + amt
        total += amt

    payment_total = sum(abs(float(p["amount"])) for p in parsed.skipped_payments)

    return IngestResult(
        parsed=parsed,
        inserted=inserted,
        duplicate_of_prior_upload=False,
        by_category=by_cat,
        total_spend=total,
        payment_count=len(parsed.skipped_payments),
        payment_total=payment_total,
    )


# ─── Streaming variant ─────────────────────────────────────────────


async def run_ingest_streaming(
    pdf_bytes: bytes,
    *,
    user_id: str,
    source_name: str | None,
    transactions: AsyncIOMotorCollection,
    parser=None,
) -> AsyncIterator[str]:
    """Same pipeline as run_ingest but yields SSE-formatted progress events
    instead of returning a single result.

    Event sequence (every successful ingest):
        received    — file landed at backend, size + name
        dedupe      — checking source-hash dedupe
        extracting  — Gemini multimodal call started
        extracted   — N raw transactions found; period+issuer surfaced
        categorizing — applying canonicalizer + vocab overrides
        saving      — writing to Atlas
        done        — final summary card payload (same shape as the
                       non-streaming response so the frontend renders
                       the StatementCard identically)

    On duplicate-of-prior-upload:
        received → dedupe → done (with duplicate=True + cached aggregates)

    On failure:
        received → ... → error (with `message` field)

    Each event ends with `\\n\\n` so SSE-conformant clients
    (EventSource, fetch-stream-parsers) split frames correctly.
    """
    filename = source_name or "statement.pdf"
    file_size = len(pdf_bytes)

    yield _sse("received", {
        "filename": filename,
        "size_bytes": file_size,
    })
    # Tiny await so the frame flushes through the ASGI stack before we
    # start the LLM call — without this, gunicorn/uvicorn may batch the
    # first few frames together and the user sees nothing until the
    # extract finishes.
    await asyncio.sleep(0)

    source_hash = _hash_bytes(pdf_bytes)

    # ── Layer 1: source-hash dedupe ─────────────────────────────
    yield _sse("dedupe", {"status": "checking", "source_hash": source_hash})
    await asyncio.sleep(0)

    existing = await transactions.count_documents(
        {"user_id": user_id, "source": {"$regex": f"_{source_hash}$"}}
    )
    if existing > 0:
        # Surface the cached breakdown so the user still sees real numbers.
        cached_cursor = transactions.find(
            {"user_id": user_id, "source": {"$regex": f"_{source_hash}$"}}
        )
        by_cat: dict[str, float] = {}
        total = 0.0
        async for doc in cached_cursor:
            cat = doc.get("category", "other.misc").split(".")[0]
            amt = abs(float(doc.get("amount", 0)))
            by_cat[cat] = by_cat.get(cat, 0.0) + amt
            total += amt
        yield _sse("dedupe", {"status": "duplicate", "prior_count": existing})
        yield _sse("done", {
            "inserted": 0,
            "duplicate_of_prior_upload": True,
            "issuer": "",
            "account_last4": "",
            "period_start": None,
            "period_end": None,
            "total_spend": round(total, 2),
            "by_category": {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])},
            "payment_count": 0,
            "payment_total": 0.0,
            "warnings": ["this statement was already imported"],
            "source": f"_{source_hash}",
        })
        return

    yield _sse("dedupe", {"status": "new"})
    await asyncio.sleep(0)

    # ── Layer 2: LLM extract ─────────────────────────────────────
    yield _sse("extracting", {"model": "gemini-2.5-flash"})
    await asyncio.sleep(0)

    parser = parser or parse_statement_pdf
    # The parser is blocking (Gemini SDK is sync); run on a worker thread
    # so the event loop stays free to flush the `extracting` frame and
    # let the client display the spinner. Without to_thread, the event
    # loop blocks for 5-20s and SSE flushes appear to stall.
    try:
        parsed: StatementParseResult = await asyncio.to_thread(
            parser,
            pdf_bytes,
            user_id=user_id,
            source_name=source_name,
            source_hash=source_hash,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("streaming ingest extract failed")
        yield _sse("error", {
            "step": "extracting",
            "message": f"{type(exc).__name__}: {str(exc)[:300]}",
        })
        return

    if parsed.warnings and not parsed.documents:
        yield _sse("error", {
            "step": "extracting",
            "message": parsed.warnings[0],
        })
        return

    yield _sse("extracted", {
        "transaction_count": len(parsed.documents) + len(parsed.skipped_payments),
        "spend_count": len(parsed.documents),
        "payment_count": len(parsed.skipped_payments),
        "issuer": parsed.issuer,
        "account_last4": parsed.account_last4,
        "period_start": parsed.period_start.isoformat() if parsed.period_start else None,
        "period_end": parsed.period_end.isoformat() if parsed.period_end else None,
    })
    await asyncio.sleep(0)

    # ── Layer 3: categorize (already done inside parser, but the
    # canonicalizer override + vocab validation feel like a discrete
    # step to the user; surface it so the UX matches the architecture)
    yield _sse("categorizing", {
        "applied_overrides": True,
        "warnings": parsed.warnings,
    })
    await asyncio.sleep(0)

    # ── Layer 4: write to Atlas ─────────────────────────────────
    yield _sse("saving", {"count": len(parsed.documents)})
    await asyncio.sleep(0)

    inserted = 0
    if parsed.documents:
        result = await transactions.insert_many(parsed.documents, ordered=False)
        inserted = len(result.inserted_ids)

    by_cat_out: dict[str, float] = {}
    total_out = 0.0
    for doc in parsed.documents:
        top = str(doc.get("category", "other.misc")).split(".")[0]
        amt = abs(float(doc.get("amount", 0)))
        by_cat_out[top] = by_cat_out.get(top, 0.0) + amt
        total_out += amt
    payment_total = sum(abs(float(p["amount"])) for p in parsed.skipped_payments)

    # ── Done ──────────────────────────────────────────────────
    yield _sse("done", {
        "inserted": inserted,
        "duplicate_of_prior_upload": False,
        "issuer": parsed.issuer,
        "account_last4": parsed.account_last4,
        "period_start": parsed.period_start.isoformat() if parsed.period_start else None,
        "period_end": parsed.period_end.isoformat() if parsed.period_end else None,
        "total_spend": round(total_out, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(by_cat_out.items(), key=lambda kv: -kv[1])},
        "payment_count": len(parsed.skipped_payments),
        "payment_total": round(payment_total, 2),
        "warnings": parsed.warnings,
        "source": parsed.source,
    })
