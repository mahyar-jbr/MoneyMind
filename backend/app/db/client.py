import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING


ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        mongo_uri = os.environ["MONGODB_URI"]
        _client = AsyncIOMotorClient(mongo_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    db_name = os.getenv("MONGODB_DB", "moneymind")
    return get_client()[db_name]


async def ping_mongo() -> bool:
    await get_client().admin.command("ping")
    return True


async def ensure_indexes() -> None:
    db = get_database()
    await db.transactions.create_index(
        [("user_id", ASCENDING), ("date", DESCENDING)],
        name="transactions_user_date",
    )
    await db.transactions.create_index(
        [("user_id", ASCENDING), ("category", ASCENDING), ("date", DESCENDING)],
        name="transactions_user_category_date",
    )
    await db.inbox_messages.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)],
        name="inbox_user_created",
    )
    await db.inbox_messages.create_index(
        [("user_id", ASCENDING), ("type", ASCENDING), ("metadata.week_start", ASCENDING)],
        name="inbox_user_type_week",
    )
    await db.reminders.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("fires_at", ASCENDING)],
        name="reminders_due",
    )
    await db.interventions.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("proposed_at", DESCENDING)],
        name="interventions_user_status_proposed",
    )


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
