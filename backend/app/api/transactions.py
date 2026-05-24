from fastapi import APIRouter, Query

from app.db.client import get_database


router = APIRouter(tags=["transactions"])


@router.get("/transactions")
async def list_transactions(
    user_id: str = Query("u_482"),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    cursor = (
        get_database()
        .transactions.find({"user_id": user_id}, {"_id": 0})
        .sort("date", -1)
        .limit(limit)
    )
    transactions = []
    async for transaction in cursor:
        transaction["date"] = transaction["date"].date().isoformat()
        transactions.append(transaction)
    return {"user_id": user_id, "transactions": transactions}

