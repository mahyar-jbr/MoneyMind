from datetime import UTC, datetime
from typing import Any

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api import interventions as interventions_api
from app.auth.clerk import AuthenticatedUser


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]], seen: dict[str, Any]):
        self.docs = docs
        self.seen = seen

    def sort(self, field: str, direction: int):
        self.seen["sort"] = (field, direction)
        reverse = direction < 0
        self.docs.sort(key=lambda doc: doc[field], reverse=reverse)
        return self

    def limit(self, limit: int):
        self.seen["limit"] = limit
        self.docs = self.docs[:limit]
        return self

    def __aiter__(self):
        self._iter = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _InterventionsCollection:
    def __init__(self, docs: list[dict[str, Any]], seen: dict[str, Any]):
        self.docs = docs
        self.seen = seen

    def find(self, query: dict[str, Any]):
        self.seen["query"] = query
        matches = [
            doc
            for doc in self.docs
            if all(doc.get(key) == value for key, value in query.items())
        ]
        return _Cursor(matches, self.seen)


class _Db:
    def __init__(self, docs: list[dict[str, Any]], seen: dict[str, Any]):
        self.interventions = _InterventionsCollection(docs, seen)


class _RespondResult:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def model_dump(self, *, mode: str):
        assert mode == "json"
        return self.payload


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(user_id="user_clerk_123", token="jwt")


def test_intervention_routes_are_registered():
    routes = {
        route.path
        for route in interventions_api.router.routes
        if hasattr(route, "path")
    }

    assert "/interventions/pending" in routes
    assert "/interventions/{intervention_id}/respond" in routes


@pytest.mark.asyncio
async def test_list_pending_interventions_filters_sorts_and_serializes(monkeypatch):
    older_id = ObjectId()
    newer_id = ObjectId()
    seen: dict[str, Any] = {}
    docs = [
        {
            "_id": older_id,
            "user_id": "user_clerk_123",
            "status": "pending",
            "type": "sunday_reminder",
            "params": {"enabled": True},
            "related_memory_id": ObjectId(),
            "proposed_at": datetime(2026, 6, 1, 9, tzinfo=UTC),
        },
        {
            "_id": ObjectId(),
            "user_id": "other_user",
            "status": "pending",
            "proposed_at": datetime(2026, 6, 2, 9, tzinfo=UTC),
        },
        {
            "_id": newer_id,
            "user_id": "user_clerk_123",
            "status": "pending",
            "type": "coffee_cap",
            "params": {"limit": 20},
            "proposed_at": datetime(2026, 6, 2, 9, tzinfo=UTC),
        },
        {
            "_id": ObjectId(),
            "user_id": "user_clerk_123",
            "status": "responded",
            "proposed_at": datetime(2026, 6, 3, 9, tzinfo=UTC),
        },
    ]
    monkeypatch.setattr(interventions_api, "get_database", lambda: _Db(docs, seen))

    result = await interventions_api.list_pending_interventions(_user(), limit=10)

    assert seen["query"] == {"user_id": "user_clerk_123", "status": "pending"}
    assert seen["sort"] == ("proposed_at", -1)
    assert seen["limit"] == 10
    assert result["user_id"] == "user_clerk_123"
    assert [item["id"] for item in result["interventions"]] == [
        str(newer_id),
        str(older_id),
    ]
    assert result["interventions"][0]["proposed_at"] == "2026-06-02T09:00:00+00:00"
    assert isinstance(result["interventions"][1]["related_memory_id"], str)


@pytest.mark.asyncio
async def test_respond_to_intervention_delegates_to_agent_tool(monkeypatch):
    seen: dict[str, Any] = {}

    async def fake_call(**kwargs):
        seen.update(kwargs)
        return _RespondResult(
            {
                "intervention_id": kwargs["intervention_id"],
                "user_id": kwargs["user_id"],
                "new_status": "responded",
                "user_response": kwargs["user_response"],
            }
        )

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_call)

    result = await interventions_api.respond_to_pending_intervention(
        str(ObjectId()),
        interventions_api.InterventionResponseRequest(
            user_response="modified",
            modified_params={"day": "Saturday"},
        ),
        _user(),
    )

    assert seen == {
        "user_id": "user_clerk_123",
        "intervention_id": result["intervention_id"],
        "user_response": "modified",
        "modified_params": {"day": "Saturday"},
    }
    assert result["new_status"] == "responded"


@pytest.mark.asyncio
async def test_respond_to_intervention_validation_error_maps_to_400(monkeypatch):
    async def fake_call(**kwargs):
        raise ValueError("user_response='modified' requires non-empty modified_params")

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_call)

    with pytest.raises(HTTPException) as exc:
        await interventions_api.respond_to_pending_intervention(
            str(ObjectId()),
            interventions_api.InterventionResponseRequest(user_response="modified"),
            _user(),
        )

    assert exc.value.status_code == 400
    assert "modified_params" in exc.value.detail


@pytest.mark.asyncio
async def test_respond_to_intervention_already_responded_maps_to_409(monkeypatch):
    async def fake_call(**kwargs):
        raise LookupError("intervention abc is already in status 'responded'")

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_call)

    with pytest.raises(HTTPException) as exc:
        await interventions_api.respond_to_pending_intervention(
            str(ObjectId()),
            interventions_api.InterventionResponseRequest(user_response="accepted"),
            _user(),
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_respond_to_intervention_missing_maps_to_404(monkeypatch):
    async def fake_call(**kwargs):
        raise LookupError("intervention abc not found for user user_clerk_123")

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_call)

    with pytest.raises(HTTPException) as exc:
        await interventions_api.respond_to_pending_intervention(
            str(ObjectId()),
            interventions_api.InterventionResponseRequest(user_response="accepted"),
            _user(),
        )

    assert exc.value.status_code == 404
