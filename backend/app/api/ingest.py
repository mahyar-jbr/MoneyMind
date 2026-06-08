from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.clerk import AuthenticatedUser, current_user
from app.db.client import get_database
from app.ingestion.csv import parse_transactions_csv
from app.ingestion.pipeline import run_ingest


router = APIRouter(prefix="/ingest", tags=["ingest"])


# File-size guard for PDFs (~10 MB is enough for a 50-page statement).
_MAX_PDF_BYTES = 10 * 1024 * 1024


@router.post("/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(current_user),
) -> dict:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")

    result = parse_transactions_csv(
        await file.read(),
        default_user_id=user.user_id,
        source_name=file.filename,
    )
    if not result.documents:
        return {"inserted": 0, "errors": result.errors, "source": result.source}

    db = get_database()
    insert_result = await db.transactions.insert_many(result.documents)
    await db.transactions.delete_many(
        {
            "user_id": user.user_id,
            "source": result.source,
            "_id": {"$nin": insert_result.inserted_ids},
        }
    )

    return {
        "inserted": len(insert_result.inserted_ids),
        "errors": result.errors,
        "source": result.source,
    }


@router.post("/statement")
async def ingest_statement(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(current_user),
) -> dict:
    """V4 — bank-statement PDF upload.

    Multimodal Gemini extracts transactions, categorizes them against
    our vocab, runs the merchant canonicalizer for known merchants, and
    bulk-inserts into atlas.transactions tagged with a source hash so
    re-uploads dedupe to 0.

    Returns a structured summary the frontend renders as a system card
    in the chat thread.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Upload a .pdf bank statement. CSV is at /ingest/csv.",
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="file is empty")
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file too large (max {_MAX_PDF_BYTES // 1024 // 1024} MB)",
        )

    db = get_database()
    result = await run_ingest(
        pdf_bytes,
        user_id=user.user_id,
        source_name=file.filename,
        transactions=db.transactions,
    )

    return {
        "inserted": result.inserted,
        "duplicate_of_prior_upload": result.duplicate_of_prior_upload,
        "issuer": result.parsed.issuer,
        "account_last4": result.parsed.account_last4,
        "period_start": result.parsed.period_start.isoformat() if result.parsed.period_start else None,
        "period_end": result.parsed.period_end.isoformat() if result.parsed.period_end else None,
        "total_spend": round(result.total_spend, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(result.by_category.items(), key=lambda kv: -kv[1])},
        "payment_count": result.payment_count,
        "payment_total": round(result.payment_total, 2),
        "warnings": result.parsed.warnings,
        "source": result.parsed.source,
    }
