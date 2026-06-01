from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bson import ObjectId

from app.cron.reminders import fire_due_reminders
from app.cron.weekly_summary import post_weekly_summary


class _InsertResult:
    def __init__(self, inserted_id: ObjectId):
        self.inserted_id = inserted_id


class _UpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if "." in key:
            value: Any = doc
            for part in key.split("."):
                value = value.get(part)
        else:
            value = doc.get(key)
        if isinstance(expected, dict):
            if "$lte" in expected and value > expected["$lte"]:
                return False
            continue
        if value != expected:
            return False
    return True


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]]):
        self.docs = docs

    def sort(self, field: str, direction: int):
        reverse = direction < 0
        self.docs.sort(key=lambda doc: doc[field], reverse=reverse)
        return self

    def __aiter__(self):
        self._iter = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _Collection:
    def __init__(self, docs: list[dict[str, Any]] | None = None):
        self.docs = docs or []

    async def find_one(self, query: dict[str, Any]):
        return next((doc for doc in self.docs if _matches(doc, query)), None)

    async def insert_one(self, doc: dict[str, Any]):
        doc = dict(doc)
        doc["_id"] = ObjectId()
        self.docs.append(doc)
        return _InsertResult(doc["_id"])

    def find(self, query: dict[str, Any]):
        return _Cursor([doc for doc in self.docs if _matches(doc, query)])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        doc = await self.find_one(query)
        if doc is None:
            return _UpdateResult(0)
        doc.update(update.get("$set", {}))
        return _UpdateResult(1)


class _Db:
    def __init__(self):
        self.inbox_messages = _Collection()
        self.reminders = _Collection()


@pytest.mark.asyncio
async def test_post_weekly_summary_creates_inbox_message():
    db = _Db()
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)

    async def fake_fetch(token: str, agent_url: str) -> str:
        assert token == "jwt"
        assert agent_url == "http://agent.test"
        return "Week of Mon, Jun 1: you spent $42."

    result = await post_weekly_summary(
        db,
        user_id="user_123",
        user_token="jwt",
        now=now,
        agent_url="http://agent.test",
        fetch_summary=fake_fetch,
    )

    assert result["created"] is True
    assert result["week_start"] == "2026-06-01"
    assert db.inbox_messages.docs[0]["user_id"] == "user_123"
    assert db.inbox_messages.docs[0]["body"] == "Week of Mon, Jun 1: you spent $42."


@pytest.mark.asyncio
async def test_post_weekly_summary_is_idempotent_for_same_week():
    db = _Db()
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)
    calls = 0

    async def fake_fetch(token: str, agent_url: str) -> str:
        nonlocal calls
        calls += 1
        return "summary"

    first = await post_weekly_summary(
        db,
        user_id="user_123",
        user_token="jwt",
        now=now,
        fetch_summary=fake_fetch,
    )
    second = await post_weekly_summary(
        db,
        user_id="user_123",
        user_token="jwt",
        now=now + timedelta(hours=2),
        fetch_summary=fake_fetch,
    )

    assert first["created"] is True
    assert second["created"] is False
    assert calls == 1
    assert len(db.inbox_messages.docs) == 1


@pytest.mark.asyncio
async def test_fire_due_reminders_posts_messages_and_marks_fired():
    db = _Db()
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)
    due_id = ObjectId()
    future_id = ObjectId()
    db.reminders.docs.extend(
        [
            {
                "_id": due_id,
                "user_id": "user_123",
                "fires_at": now - timedelta(minutes=5),
                "text": "cancel the trial",
                "source": "user",
                "status": "pending",
            },
            {
                "_id": future_id,
                "user_id": "user_123",
                "fires_at": now + timedelta(days=1),
                "text": "future reminder",
                "source": "agent",
                "status": "pending",
            },
        ]
    )

    result = await fire_due_reminders(db, user_id="user_123", now=now)

    assert result["fired"] == 1
    assert db.inbox_messages.docs[0]["body"] == "cancel the trial"
    assert db.inbox_messages.docs[0]["metadata"]["reminder_id"] == str(due_id)
    assert db.reminders.docs[0]["status"] == "fired"
    assert db.reminders.docs[1]["status"] == "pending"
