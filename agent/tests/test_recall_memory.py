"""Unit tests for recall_memory.

The Atlas $vectorSearch pipeline cannot run against mongomock-motor, so we
inject a FakeCollection that captures the pipeline and returns canned docs.
This lets us verify:
  - the pipeline shape (filters, projection, score threshold) is correct
  - the result mapping (memory_id, last_used, evidence preservation) works
  - no writes happen
Live vector-search behavior is verified in agent/scripts/demo_recall.py.
"""

from datetime import datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

from agent.tests._fakes import FakeCollection, make_fake_embedder
from agent.tools.recall_memory import (
    MemoryHit,
    RecallMemoryInput,
    RecallMemoryResult,
    recall_memory,
)


fake_embedder = make_fake_embedder()


def _doc(
    *,
    user_id="u_482",
    type="pattern",
    tag="food_spike",
    summary="Food delivery spikes correlate with stress",
    score=0.85,
    last_used=None,
    use_count=0,
    evidence=None,
    intervention=None,
    confidence=0.78,
    _id=None,
):
    return {
        "_id": _id or ObjectId(),
        "user_id": user_id,
        "type": type,
        "tag": tag,
        "summary": summary,
        "evidence": evidence or [{"date": datetime(2026, 5, 18), "note": "DoorDash +$70"}],
        "confidence": confidence,
        "intervention": intervention,
        "last_used": last_used,
        "use_count": use_count,
        "score": score,
    }


# ─── empty result ────────────────────────────────────────────────────


async def test_empty_collection_returns_zero_count():
    coll = FakeCollection([])
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="anything"),
        collection=coll,
        embedder=fake_embedder,
    )
    assert isinstance(result, RecallMemoryResult)
    assert result.count == 0
    assert result.memories == []


# ─── user isolation ──────────────────────────────────────────────────


async def test_user_isolation():
    coll = FakeCollection(
        [
            _doc(user_id="u_482", tag="mine", score=0.9),
            _doc(user_id="u_other", tag="theirs", score=0.95),  # higher score, wrong user
        ]
    )
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="stress"),
        collection=coll,
        embedder=fake_embedder,
    )
    assert result.count == 1
    assert result.memories[0].tag == "mine"


# ─── type filter ─────────────────────────────────────────────────────


async def test_type_filter_excludes_other_types():
    coll = FakeCollection(
        [
            _doc(type="pattern", tag="p1", score=0.9),
            _doc(type="preference", tag="pref1", score=0.95),
            _doc(type="fact", tag="f1", score=0.85),
        ]
    )
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="anything", type="preference"),
        collection=coll,
        embedder=fake_embedder,
    )
    assert result.count == 1
    assert result.memories[0].type == "preference"


async def test_no_type_filter_returns_all_types():
    coll = FakeCollection(
        [
            _doc(type="pattern", tag="p1", score=0.9),
            _doc(type="preference", tag="pref1", score=0.85),
            _doc(type="fact", tag="f1", score=0.7),
        ]
    )
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="anything"),
        collection=coll,
        embedder=fake_embedder,
    )
    assert result.count == 3


# ─── min_score filter ────────────────────────────────────────────────


async def test_min_score_filter_drops_low_matches():
    coll = FakeCollection(
        [
            _doc(tag="strong", score=0.92),
            _doc(tag="weak", score=0.45),
        ]
    )
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="anything", min_score=0.5),
        collection=coll,
        embedder=fake_embedder,
    )
    assert result.count == 1
    assert result.memories[0].tag == "strong"


# ─── score ordering ──────────────────────────────────────────────────


async def test_results_sorted_score_desc():
    coll = FakeCollection(
        [
            _doc(tag="b", score=0.7),
            _doc(tag="a", score=0.95),
            _doc(tag="c", score=0.8),
        ]
    )
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="x"),
        collection=coll,
        embedder=fake_embedder,
    )
    assert [m.tag for m in result.memories] == ["a", "c", "b"]
    assert result.memories[0].score == 0.95


# ─── k limit ─────────────────────────────────────────────────────────


async def test_k_limits_results():
    coll = FakeCollection([_doc(tag=f"m{i}", score=0.9 - i * 0.01) for i in range(10)])
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="x", k=3),
        collection=coll,
        embedder=fake_embedder,
    )
    assert result.count == 3
    assert result.k == 3


# ─── memory_hit shape ────────────────────────────────────────────────


async def test_memory_hit_shape():
    test_id = ObjectId()
    coll = FakeCollection(
        [
            _doc(
                _id=test_id,
                tag="t",
                evidence=[{"date": datetime(2026, 1, 1), "note": "n"}],
                last_used=datetime(2026, 5, 1),
                use_count=3,
                intervention={"sunday_reminder": True},
                confidence=0.91,
                score=0.88,
            )
        ]
    )
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="x"),
        collection=coll,
        embedder=fake_embedder,
    )
    h = result.memories[0]
    assert isinstance(h, MemoryHit)
    assert h.memory_id == str(test_id)
    assert isinstance(h.memory_id, str)
    assert h.evidence == [{"date": datetime(2026, 1, 1), "note": "n"}]
    assert h.last_used.year == 2026 and h.last_used.month == 5
    assert h.use_count == 3
    assert h.intervention == {"sunday_reminder": True}
    assert h.confidence == 0.91
    assert h.score == 0.88


async def test_missing_optional_fields_default_safely():
    """A memory doc may not have intervention/last_used/use_count yet."""
    coll = FakeCollection([{
        "_id": ObjectId(),
        "user_id": "u_482",
        "type": "fact",
        "tag": "rent",
        "summary": "rent $1800 first of month",
        "evidence": [],
        "confidence": 1.0,
        "score": 0.95,
    }])
    result = await recall_memory(
        RecallMemoryInput(user_id="u_482", query="rent"),
        collection=coll,
        embedder=fake_embedder,
    )
    h = result.memories[0]
    assert h.intervention is None
    assert h.last_used is None
    assert h.use_count == 0


# ─── no side effects ─────────────────────────────────────────────────


async def test_no_side_effects():
    coll = FakeCollection([_doc(tag="x", use_count=5, score=0.9)])
    await recall_memory(
        RecallMemoryInput(user_id="u_482", query="x"),
        collection=coll,
        embedder=fake_embedder,
    )
    assert coll.writes == []  # no update/insert/delete attempted


# ─── pipeline shape sanity ───────────────────────────────────────────


async def test_pipeline_includes_correct_filters_and_index_name():
    coll = FakeCollection([])
    await recall_memory(
        RecallMemoryInput(user_id="u_482", query="x", type="pattern", k=7, min_score=0.6),
        collection=coll,
        embedder=fake_embedder,
    )
    assert len(coll.pipelines) == 1
    pipeline = coll.pipelines[0]
    vs = pipeline[0]["$vectorSearch"]
    assert vs["index"] == "memories_vector_idx"
    assert vs["path"] == "embedding"
    assert vs["limit"] == 7
    assert vs["numCandidates"] == 7 * 20
    # V3: deleted_at is filtered POST-search via a $match stage (Atlas
    # vector index doesn't have deleted_at as a filterable field), so the
    # in-index filter remains user_id + optional type only.
    assert vs["filter"] == {"user_id": {"$eq": "u_482"}, "type": {"$eq": "pattern"}}
    # The pipeline must contain an explicit $match { deleted_at: null }
    # stage. {$eq: null} matches both missing and explicitly-null fields
    # so memories written before V3 landed are still recalled.
    deleted_filter_stages = [
        s for s in pipeline
        if "$match" in s and s["$match"].get("deleted_at") == {"$eq": None}
    ]
    assert deleted_filter_stages, "recall_memory must filter soft-deleted memories"
    # last stage projects only safe fields (no embedding leak)
    proj = pipeline[-1]["$project"]
    assert "embedding" not in proj


# ─── validation ──────────────────────────────────────────────────────


def test_validation_empty_user_id():
    with pytest.raises(ValidationError):
        RecallMemoryInput(user_id="", query="x")


def test_validation_empty_query():
    with pytest.raises(ValidationError):
        RecallMemoryInput(user_id="u_482", query="")


def test_validation_query_too_long():
    with pytest.raises(ValidationError):
        RecallMemoryInput(user_id="u_482", query="x" * 501)


def test_validation_k_zero():
    with pytest.raises(ValidationError):
        RecallMemoryInput(user_id="u_482", query="x", k=0)


def test_validation_k_too_high():
    with pytest.raises(ValidationError):
        RecallMemoryInput(user_id="u_482", query="x", k=21)


def test_validation_min_score_below_zero():
    with pytest.raises(ValidationError):
        RecallMemoryInput(user_id="u_482", query="x", min_score=-0.1)


def test_validation_min_score_above_one():
    with pytest.raises(ValidationError):
        RecallMemoryInput(user_id="u_482", query="x", min_score=1.1)
