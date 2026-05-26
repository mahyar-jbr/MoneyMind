from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase


async def weekly_spend_by_category(
    db: AsyncIOMotorDatabase,
    *,
    user_id: str,
    date_from: datetime | None = None,
    date_to_exclusive: datetime | None = None,
    category: str | None = None,
) -> list[dict]:
    """Return weekly category totals for outflow transactions only."""
    match: dict = {"user_id": user_id, "amount": {"$lt": 0}}
    if date_from or date_to_exclusive:
        match["date"] = {}
        if date_from:
            match["date"]["$gte"] = date_from
        if date_to_exclusive:
            match["date"]["$lt"] = date_to_exclusive
    if category:
        match["category"] = category

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "week": {
                        "$dateTrunc": {
                            "date": "$date",
                            "unit": "week",
                            "startOfWeek": "monday",
                        }
                    },
                    "category": "$category",
                },
                "spend": {"$sum": {"$multiply": ["$amount", -1]}},
            }
        },
        {"$sort": {"_id.week": 1, "_id.category": 1}},
        {
            "$group": {
                "_id": "$_id.week",
                "categories": {
                    "$push": {
                        "category": "$_id.category",
                        "spend": {"$round": ["$spend", 2]},
                    }
                },
                "total_spend": {"$sum": "$spend"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    weeks: list[dict] = []
    async for row in db.transactions.aggregate(pipeline):
        by_category = {item["category"]: item["spend"] for item in row["categories"]}
        weeks.append(
            {
                "week": row["_id"].date().isoformat(),
                "by_category": by_category,
                "total_spend": round(row["total_spend"], 2),
            }
        )
    return weeks
