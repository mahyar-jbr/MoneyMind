import argparse
import asyncio
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.db.client import close_mongo, get_database


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def duplicate_pipeline(user_id: str) -> list[dict[str, Any]]:
    return [
        {"$match": {"user_id": user_id}},
        {"$sort": {"_id": 1}},
        {
            "$group": {
                "_id": {
                    "user_id": "$user_id",
                    "date": "$date",
                    "merchant": "$merchant",
                    "merchant_canonical": "$merchant_canonical",
                    "category": "$category",
                    "amount": "$amount",
                    "currency": "$currency",
                    "raw": "$raw",
                },
                "ids": {"$push": "$_id"},
                "count": {"$sum": 1},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
    ]


async def dedupe_transactions(*, user_id: str, apply: bool) -> dict[str, int]:
    db = get_database()
    duplicate_groups = []
    async for group in db.transactions.aggregate(duplicate_pipeline(user_id)):
        duplicate_groups.append(group)

    duplicate_ids = [
        duplicate_id
        for group in duplicate_groups
        for duplicate_id in group["ids"][1:]
    ]

    deleted = 0
    if apply and duplicate_ids:
        result = await db.transactions.delete_many({"_id": {"$in": duplicate_ids}})
        deleted = result.deleted_count

    return {
        "duplicate_groups": len(duplicate_groups),
        "duplicate_rows": len(duplicate_ids),
        "deleted": deleted,
    }


async def _amain() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run or delete exact duplicate transaction rows for one user."
    )
    parser.add_argument("--user-id", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete duplicates. Omit for dry-run.",
    )
    args = parser.parse_args()

    try:
        result = await dedupe_transactions(user_id=args.user_id, apply=args.apply)
    finally:
        await close_mongo()

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"{mode}: duplicate_groups={result['duplicate_groups']} "
        f"duplicate_rows={result['duplicate_rows']} deleted={result['deleted']}"
    )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
