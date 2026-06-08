from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.auth.clerk import AuthenticatedUser, current_user
from app.db.client import get_database
from app.ingestion.csv import parse_transactions_csv
from app.ingestion.pipeline import run_ingest_streaming


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
) -> StreamingResponse:
    """V4 — bank-statement PDF upload, with **streaming progress events**.

    Multimodal Gemini extracts transactions, categorizes them against
    our vocab, runs the merchant canonicalizer for known merchants, and
    bulk-inserts into atlas.transactions tagged with a source hash so
    re-uploads dedupe to 0.

    Returns Server-Sent Events: one per pipeline phase
    (received → dedupe → extracting → extracted → categorizing →
    saving → done). The `done` frame's `data` is the same shape the
    old JSON response used to be, so the frontend renders the same
    StatementCard once the stream terminates.

    Why streaming: Gemini extraction takes 5-30s on a multi-page PDF.
    Without progress signals the user sees a spinner and assumes it
    hung. Each phase event lets the UI render a checkpoint timeline
    so the user can SEE where in the pipeline we are.
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
    generator = run_ingest_streaming(
        pdf_bytes,
        user_id=user.user_id,
        source_name=file.filename,
        transactions=db.transactions,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        # Disable proxy buffering so each SSE frame flushes immediately.
        # Required for both nginx (X-Accel-Buffering) AND Vercel's
        # Node-runtime edge (Cache-Control: no-transform).
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
