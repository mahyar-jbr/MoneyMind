from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.db.client import get_database
from app.ingestion.csv import parse_transactions_csv


router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    user_id: str = Form("u_482"),
) -> dict:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")

    result = parse_transactions_csv(await file.read(), default_user_id=user_id)
    if not result.documents:
        return {"inserted": 0, "errors": result.errors, "source": result.source}

    db = get_database()
    await db.transactions.delete_many({"user_id": user_id, "source": result.source})
    insert_result = await db.transactions.insert_many(result.documents)

    return {
        "inserted": len(insert_result.inserted_ids),
        "errors": result.errors,
        "source": result.source,
    }

