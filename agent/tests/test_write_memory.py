"""Unit tests for write_memory.

mongomock-motor implements insert_one/find_one, so we use a real fake DB
for round-trip + shape tests. A separate FakeDB asserts the tool only
touches the memories collection.
"""

import asyncio
from datetime import date, datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import (
    get_database_tripwire,
    make_fake_embedder,
    make_mongomock_collection,
)
from agent.tools import write_memory as write_memory_module
from agent.tools.write_memory import (
    EvidenceItem,
    WriteMemoryInput,
    WriteMemoryResult,
    write_memory,
)


fake_embedder = make_fake_embedder()


@pytest.fixture
async def memories_coll():
    return make_mongomock_collection(collection_name="memories")


def _input(**overrides):
    defaults = {
        "user_id": "u_482",
        "type": "pattern",
        "tag": "food_spike→no_prep",
        "summary": "Food delivery spikes correlate with work stress and no meal prep.",
        "evidence": [
            EvidenceItem(date=date(2026, 2, 12), note="exam week, +$70 DoorDash"),
            EvidenceItem(date=date(2026, 5, 18), note="busy work week, +$70 DoorDash"),
        ],
        "confidence": 0.78,
        "intervention": {"sunday_reminder": True},
    }
    defaults.update(overrides)
    return WriteMemoryInput(**defaults)


# ─── AC: doc shape matches data-model contract ────────────────────────


async def test_inserts_document_with_correct_shape(memories_coll):
    result = await write_memory(_input(), collection=memories_coll, embedder=fake_embedder)
    assert isinstance(result, WriteMemoryResult)
    assert result.embedded is True

    doc = await memories_coll.find_one({"_id": ObjectId(result.memory_id)})
    assert doc is not None
    # Required schema fields from docs/data-model.md
    assert doc["user_id"] == "u_482"
    assert doc["type"] == "pattern"
    assert doc["tag"] == "food_spike→no_prep"
    assert doc["summary"].startswith("Food delivery spikes")
    assert isinstance(doc["evidence"], list) and len(doc["evidence"]) == 2
    assert doc["intervention"] == {"sunday_reminder": True}
    assert doc["confidence"] == 0.78
    assert isinstance(doc["embedding"], list) and len(doc["embedding"]) == 1024
    assert doc["last_used"] is None
    assert doc["use_count"] == 0
    assert isinstance(doc["created_at"], datetime)


# ─── AC: created_at is server-stamped (not from input) ─────────────────


async def test_created_at_is_server_stamped(memories_coll):
    r1 = await write_memory(_input(tag="t1"), collection=memories_coll, embedder=fake_embedder)
    await asyncio.sleep(0.01)
    r2 = await write_memory(_input(tag="t2"), collection=memories_coll, embedder=fake_embedder)
    assert r1.created_at < r2.created_at
    assert r1.created_at.tzinfo is not None  # UTC-aware


# ─── AC: last_used null + use_count 0 ─────────────────────────────────


async def test_last_used_null_and_use_count_zero(memories_coll):
    result = await write_memory(_input(), collection=memories_coll, embedder=fake_embedder)
    doc = await memories_coll.find_one({"_id": ObjectId(result.memory_id)})
    assert doc["last_used"] is None
    assert doc["use_count"] == 0


# ─── AC: evidence dates converted to midnight datetimes ───────────────


async def test_evidence_date_persisted_as_datetime(memories_coll):
    params = _input(
        evidence=[EvidenceItem(date=date(2026, 5, 18), note="testing date conversion")]
    )
    result = await write_memory(params, collection=memories_coll, embedder=fake_embedder)
    doc = await memories_coll.find_one({"_id": ObjectId(result.memory_id)})
    persisted = doc["evidence"][0]["date"]
    assert isinstance(persisted, datetime)
    assert persisted == datetime(2026, 5, 18, 0, 0)


# ─── AC: embedding is populated (Path A) ──────────────────────────────


async def test_path_a_embedding_persisted(memories_coll):
    result = await write_memory(_input(), collection=memories_coll, embedder=fake_embedder)
    doc = await memories_coll.find_one({"_id": ObjectId(result.memory_id)})
    assert len(doc["embedding"]) == 1024
    # fake_embedder seeds first slot with len(summary)
    assert doc["embedding"][0] == float(len(_input().summary))
    assert result.embedded is True


# ─── AC: memory_id round-trip ─────────────────────────────────────────


async def test_memory_id_round_trips(memories_coll):
    result = await write_memory(_input(), collection=memories_coll, embedder=fake_embedder)
    doc = await memories_coll.find_one({"_id": ObjectId(result.memory_id)})
    assert doc is not None
    assert str(doc["_id"]) == result.memory_id


# ─── AC: user_id persisted (basic isolation sanity) ───────────────────


async def test_user_id_persisted(memories_coll):
    await write_memory(_input(user_id="u_alpha"), collection=memories_coll, embedder=fake_embedder)
    await write_memory(_input(user_id="u_beta"), collection=memories_coll, embedder=fake_embedder)
    alpha_count = await memories_coll.count_documents({"user_id": "u_alpha"})
    beta_count = await memories_coll.count_documents({"user_id": "u_beta"})
    assert alpha_count == 1
    assert beta_count == 1


# ─── AC: empty evidence is allowed ────────────────────────────────────


async def test_empty_evidence_allowed(memories_coll):
    result = await write_memory(
        _input(evidence=[]), collection=memories_coll, embedder=fake_embedder
    )
    doc = await memories_coll.find_one({"_id": ObjectId(result.memory_id)})
    assert doc["evidence"] == []


# ─── AC: intervention may be omitted ──────────────────────────────────


async def test_intervention_optional(memories_coll):
    result = await write_memory(
        _input(intervention=None), collection=memories_coll, embedder=fake_embedder
    )
    doc = await memories_coll.find_one({"_id": ObjectId(result.memory_id)})
    assert doc["intervention"] is None


# ─── AC: no modification of other collections ─────────────────────────


async def test_no_modification_of_other_collections(memories_coll, monkeypatch):
    """Any silent fallback to the global db handle must fail loudly."""
    with get_database_tripwire(monkeypatch, write_memory_module):
        await write_memory(_input(), collection=memories_coll, embedder=fake_embedder)
    doc_count = await memories_coll.count_documents({})
    assert doc_count == 1


# ─── Validation ───────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        WriteMemoryInput(
            user_id="", type="fact", tag="t", summary="x" * 20, confidence=0.5
        )


def test_tag_optional_for_llm():
    """tag is optional in the schema so Gemini Flash doesn't refuse to
    call write_memory; the tool derives a tag from summary when missing.
    Was previously required (min_length=1) and that caused 0 memory
    writes in prod — Flash silently skipped the tool entirely."""
    params = WriteMemoryInput(
        user_id="u", type="fact", summary="x" * 20, confidence=0.5
    )
    assert params.tag is None  # the LLM didn't supply one; tool will derive


def test_tag_derived_from_summary_when_omitted():
    """When the LLM omits tag, the tool synthesizes one from summary."""
    import asyncio

    from agent.tests._fakes import make_mongomock_collection

    async def _embedder(_text: str) -> list[float]:
        return [0.0] * 1024

    async def _run() -> None:
        coll = make_mongomock_collection()
        result = await write_memory(
            WriteMemoryInput(
                user_id="u_482",
                type="reaction",
                summary="User is bulking this month — expect food spend up",
                confidence=0.4,
            ),
            collection=coll,
            embedder=_embedder,
        )
        # Doc was actually written with a non-empty tag.
        doc = await coll.find_one({"_id": ObjectId(result.memory_id)})
        assert doc["tag"]
        assert doc["tag"] == "user_is_bulking"

    asyncio.run(_run())


def test_validation_tag_too_long():
    with pytest.raises(ValidationError):
        WriteMemoryInput(
            user_id="u", type="fact", tag="t" * 81, summary="x" * 20, confidence=0.5
        )


def test_validation_summary_too_short():
    with pytest.raises(ValidationError):
        WriteMemoryInput(user_id="u", type="fact", tag="t", summary="short", confidence=0.5)


def test_validation_summary_too_long():
    with pytest.raises(ValidationError):
        WriteMemoryInput(
            user_id="u", type="fact", tag="t", summary="x" * 501, confidence=0.5
        )


def test_validation_confidence_below_zero():
    with pytest.raises(ValidationError):
        WriteMemoryInput(
            user_id="u", type="fact", tag="t", summary="x" * 20, confidence=-0.1
        )


def test_validation_confidence_above_one():
    with pytest.raises(ValidationError):
        WriteMemoryInput(
            user_id="u", type="fact", tag="t", summary="x" * 20, confidence=1.1
        )


def test_validation_evidence_too_long():
    items = [EvidenceItem(date=date(2026, 1, 1), note="x") for _ in range(21)]
    with pytest.raises(ValidationError):
        WriteMemoryInput(
            user_id="u",
            type="fact",
            tag="t",
            summary="x" * 20,
            confidence=0.5,
            evidence=items,
        )


def test_validation_evidence_item_empty_note():
    with pytest.raises(ValidationError):
        EvidenceItem(date=date(2026, 1, 1), note="")
