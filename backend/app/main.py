from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import aggregations, chat, cron, inbox, ingest, transactions
from app.db.client import close_mongo, ensure_indexes, ping_mongo


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    yield
    await close_mongo()


app = FastAPI(title="MoneyMind Backend", version="0.1.0", lifespan=lifespan)
app.include_router(ingest.router)
app.include_router(aggregations.router)
app.include_router(transactions.router)
app.include_router(chat.router)
app.include_router(inbox.router)
app.include_router(cron.router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "mongo": await ping_mongo()}
