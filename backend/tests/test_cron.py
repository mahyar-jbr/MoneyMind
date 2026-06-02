from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bson import ObjectId

from app.cron.reminders import fire_due_reminders
from app.cron import weekly_summary
from app.cron.weekly_summary import fetch_agent_weekly_summary, post_weekly_summary


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


class _FakeAgentResponse:
    def __init__(self, seen: dict[str, Any]):
        self.seen = seen

    def raise_for_status(self):
        self.seen["raise_for_status_called"] = True

    async def aiter_text(self):
        yield "Week of Mon, Jun 1: "
        yield "you spent $42."


class _FakeAgentStream:
    def __init__(self, seen: dict[str, Any]):
        self.seen = seen

    async def __aenter__(self):
        return _FakeAgentResponse(self.seen)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAgentClient:
    def __init__(self, *, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url, *, headers, json):
        _AGENT_SEEN.update(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": self.timeout,
            }
        )
        return _FakeAgentStream(_AGENT_SEEN)


_AGENT_SEEN: dict[str, Any] = {}


@pytest.mark.asyncio
async def test_fetch_agent_weekly_summary_sends_internal_user_id(monkeypatch):
    _AGENT_SEEN.clear()
    monkeypatch.setattr(weekly_summary.httpx, "AsyncClient", _FakeAgentClient)

    result = await fetch_agent_weekly_summary("user_123", "http://agent.test/")

    assert result == "Week of Mon, Jun 1: you spent $42."
    assert _AGENT_SEEN["method"] == "POST"
    assert _AGENT_SEEN["url"] == "http://agent.test/chat"
    assert _AGENT_SEEN["headers"] == {"X-MoneyMind-User-Id": "user_123"}
    assert "Authorization" not in _AGENT_SEEN["headers"]
    assert _AGENT_SEEN["json"]["message"].startswith("Create my weekly MoneyMind")
    assert _AGENT_SEEN["raise_for_status_called"] is True


@pytest.mark.asyncio
async def test_post_weekly_summary_creates_inbox_message():
    db = _Db()
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)

    async def fake_fetch(user_id: str, agent_url: str) -> str:
        assert user_id == "user_123"
        assert agent_url == "http://agent.test"
        return "Week of Mon, Jun 1: you spent $42."

    result = await post_weekly_summary(
        db,
        user_id="user_123",
        now=now,
        agent_url="http://agent.test",
        fetch_summary=fake_fetch,
    )

    assert result["created"] is True
    assert result["week_start"] == "2026-06-01"
    assert db.inbox_messages.docs[0]["user_id"] == "user_123"
    assert db.inbox_messages.docs[0]["body"] == "Week of Mon, Jun 1: you spent $42."
    assert "status" not in db.inbox_messages.docs[0]
    assert "read_at" not in db.inbox_messages.docs[0]


@pytest.mark.asyncio
async def test_post_weekly_summary_is_idempotent_for_same_week():
    db = _Db()
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)
    calls = 0

    async def fake_fetch(user_id: str, agent_url: str) -> str:
        nonlocal calls
        assert user_id == "user_123"
        calls += 1
        return "summary"

    first = await post_weekly_summary(
        db,
        user_id="user_123",
        now=now,
        fetch_summary=fake_fetch,
    )
    second = await post_weekly_summary(
        db,
        user_id="user_123",
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
    assert result["skipped"] == 0
    assert db.inbox_messages.docs[0]["body"] == "cancel the trial"
    assert "status" not in db.inbox_messages.docs[0]
    assert "read_at" not in db.inbox_messages.docs[0]
    assert db.inbox_messages.docs[0]["metadata"]["reminder_id"] == str(due_id)
    assert db.reminders.docs[0]["status"] == "fired"
    assert db.reminders.docs[1]["status"] == "pending"


@pytest.mark.asyncio
async def test_fire_due_reminders_reports_existing_inbox_messages_as_skipped():
    db = _Db()
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)
    reminder_id = ObjectId()
    db.reminders.docs.append(
        {
            "_id": reminder_id,
            "user_id": "user_123",
            "fires_at": now - timedelta(minutes=5),
            "text": "cancel the trial",
            "source": "user",
            "status": "pending",
        }
    )
    db.inbox_messages.docs.append(
        {
            "_id": ObjectId(),
            "user_id": "user_123",
            "type": "reminder",
            "metadata": {"reminder_id": str(reminder_id)},
        }
    )

    result = await fire_due_reminders(db, user_id="user_123", now=now)

    assert result == {"fired": 0, "skipped": 1, "message_ids": []}
    assert db.reminders.docs[0]["status"] == "fired"
