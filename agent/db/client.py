"""Singleton Mongo client for the agent service.

Mirrors backend/app/db/client.py — same env vars, same DB name default.
Lives in the agent so tools can query Atlas without a backend HTTP hop.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[os.getenv("MONGODB_DB", "moneymind")]


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
