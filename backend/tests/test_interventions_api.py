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


# ─── V6 cap-intervention auto-materialize (post-audit fix) ─────────


class _FindOneCollection:
    """Minimal mock that exposes find_one for the auto-set_budget lookup."""

    def __init__(self, doc: dict[str, Any] | None):
        self.doc = doc
        self.last_query: dict[str, Any] | None = None

    async def find_one(self, query, projection=None):
        self.last_query = query
        return self.doc


class _BudgetResult:
    """Mimic SetBudgetResult.model_dump(mode='json')."""

    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def model_dump(self, *, mode: str):
        assert mode == "json"
        return self.payload


@pytest.mark.asyncio
async def test_accept_cap_intervention_auto_calls_set_budget(monkeypatch):
    """Demo-blocker fix: when a user accepts a cap intervention via the
    REST card flow (no agent turn), the backend must auto-materialize
    the cap into atlas.budgets so the BudgetProgress widget reflects it.
    """
    intervention_id = str(ObjectId())
    cap_doc = {
        "_id": ObjectId(intervention_id),
        "user_id": "user_clerk_123",
        "type": "cap",
        "params": {"category": "food", "limit": 500},
    }

    async def fake_respond(**kwargs):
        return _RespondResult(
            {
                "intervention_id": kwargs["intervention_id"],
                "user_id": kwargs["user_id"],
                "new_status": "responded",
                "user_response": "accepted",
            }
        )

    set_budget_calls: list[dict[str, Any]] = []

    async def fake_set_budget(**kwargs):
        set_budget_calls.append(kwargs)
        return _BudgetResult(
            {
                "budget_id": "b_123",
                "category": kwargs["category"],
                "limit": kwargs["limit"],
                "status": "active",
            }
        )

    class _DbWithFindOne:
        def __init__(self):
            self.interventions = _FindOneCollection(cap_doc)

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_respond)
    monkeypatch.setattr(interventions_api, "call_set_budget", fake_set_budget)
    monkeypatch.setattr(interventions_api, "get_database", lambda: _DbWithFindOne())

    result = await interventions_api.respond_to_pending_intervention(
        intervention_id,
        interventions_api.InterventionResponseRequest(user_response="accepted"),
        _user(),
    )

    # set_budget was called with the cap's category + limit
    assert len(set_budget_calls) == 1
    assert set_budget_calls[0] == {
        "user_id": "user_clerk_123",
        "category": "food",
        "limit": 500.0,
    }
    # The response includes the materialized budget so the frontend
    # can refresh the BudgetProgress widget without a second round-trip.
    assert result["budget"]["category"] == "food"
    assert result["budget"]["limit"] == 500.0


@pytest.mark.asyncio
async def test_accept_cap_with_modified_params_overrides_original(monkeypatch):
    """User tweaks the cap before accepting: modified_params wins."""
    intervention_id = str(ObjectId())
    cap_doc = {
        "_id": ObjectId(intervention_id),
        "user_id": "user_clerk_123",
        "type": "cap",
        "params": {"category": "food", "limit": 500},
    }

    async def fake_respond(**kwargs):
        return _RespondResult({"intervention_id": kwargs["intervention_id"]})

    set_budget_calls: list[dict[str, Any]] = []

    async def fake_set_budget(**kwargs):
        set_budget_calls.append(kwargs)
        return _BudgetResult({"budget_id": "b_x"})

    class _DbWithFindOne:
        def __init__(self):
            self.interventions = _FindOneCollection(cap_doc)

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_respond)
    monkeypatch.setattr(interventions_api, "call_set_budget", fake_set_budget)
    monkeypatch.setattr(interventions_api, "get_database", lambda: _DbWithFindOne())

    await interventions_api.respond_to_pending_intervention(
        intervention_id,
        interventions_api.InterventionResponseRequest(
            user_response="accepted",
            modified_params={"limit": 400},  # user tweaked to $400
        ),
        _user(),
    )

    # The tweaked limit, not the original 500.
    assert set_budget_calls[0]["limit"] == 400.0
    assert set_budget_calls[0]["category"] == "food"


@pytest.mark.asyncio
async def test_declined_cap_does_not_call_set_budget(monkeypatch):
    """Only `accepted` should materialize. Declined / ignored / modified-not-accepted should NOT."""
    cap_doc = {
        "_id": ObjectId(),
        "user_id": "user_clerk_123",
        "type": "cap",
        "params": {"category": "food", "limit": 500},
    }

    async def fake_respond(**kwargs):
        return _RespondResult({"intervention_id": "x"})

    set_budget_calls: list[dict[str, Any]] = []

    async def fake_set_budget(**kwargs):
        set_budget_calls.append(kwargs)
        return _BudgetResult({})

    class _DbWithFindOne:
        def __init__(self):
            self.interventions = _FindOneCollection(cap_doc)

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_respond)
    monkeypatch.setattr(interventions_api, "call_set_budget", fake_set_budget)
    monkeypatch.setattr(interventions_api, "get_database", lambda: _DbWithFindOne())

    for response in ("declined", "ignored"):
        await interventions_api.respond_to_pending_intervention(
            str(ObjectId()),
            interventions_api.InterventionResponseRequest(user_response=response),
            _user(),
        )

    assert set_budget_calls == []


@pytest.mark.asyncio
async def test_accept_non_cap_intervention_does_not_call_set_budget(monkeypatch):
    """Reminder / swap_suggestion / reflection accepts shouldn't trigger budget materialization."""
    reminder_doc = {
        "_id": ObjectId(),
        "user_id": "user_clerk_123",
        "type": "reminder",
        "params": {"text": "Sunday meal prep"},
    }

    async def fake_respond(**kwargs):
        return _RespondResult({"intervention_id": "x"})

    set_budget_calls: list[dict[str, Any]] = []

    async def fake_set_budget(**kwargs):
        set_budget_calls.append(kwargs)
        return _BudgetResult({})

    class _DbWithFindOne:
        def __init__(self):
            self.interventions = _FindOneCollection(reminder_doc)

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_respond)
    monkeypatch.setattr(interventions_api, "call_set_budget", fake_set_budget)
    monkeypatch.setattr(interventions_api, "get_database", lambda: _DbWithFindOne())

    await interventions_api.respond_to_pending_intervention(
        str(ObjectId()),
        interventions_api.InterventionResponseRequest(user_response="accepted"),
        _user(),
    )

    assert set_budget_calls == []


@pytest.mark.asyncio
async def test_accept_cap_with_malformed_params_silently_skips(monkeypatch):
    """Best-effort: bad cap params should NOT 500 the intervention response."""
    bad_cap_doc = {
        "_id": ObjectId(),
        "user_id": "user_clerk_123",
        "type": "cap",
        "params": {"category": "", "limit": "not a number"},
    }

    async def fake_respond(**kwargs):
        return _RespondResult({"intervention_id": "x", "new_status": "responded"})

    set_budget_calls: list[dict[str, Any]] = []

    async def fake_set_budget(**kwargs):
        set_budget_calls.append(kwargs)
        return _BudgetResult({})

    class _DbWithFindOne:
        def __init__(self):
            self.interventions = _FindOneCollection(bad_cap_doc)

    monkeypatch.setattr(interventions_api, "call_respond_to_intervention", fake_respond)
    monkeypatch.setattr(interventions_api, "call_set_budget", fake_set_budget)
    monkeypatch.setattr(interventions_api, "get_database", lambda: _DbWithFindOne())

    # Must not raise.
    result = await interventions_api.respond_to_pending_intervention(
        str(ObjectId()),
        interventions_api.InterventionResponseRequest(user_response="accepted"),
        _user(),
    )

    assert set_budget_calls == []
    assert result["new_status"] == "responded"
    assert "budget" not in result
