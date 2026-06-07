"""Unit tests for forget_memory (V3).

Pattern: the same FakeCollection-with-$vectorSearch approach as
test_recall_memory, extended with an in-memory update_one so the soft-
delete write can be observed. See agent/tests/_fakes.py
VectorSearchWritableCollection.

We verify:
  - High-confidence match (score >= HIGH_CONFIDENCE) → deleted=True,
    deleted_at field set on the doc.
  - Low-confidence match → needs_confirmation=True, no write.
  - No match at all → deleted=False, no memory_id, no write.
  - Score threshold edge cases (= HIGH_CONFIDENCE, just under).
  - user_id isolation — never deletes another user's memory.
  - Pipeline shape — deleted_at: None is in the $vectorSearch filter.
  - Idempotency — calling forget_memory twice on the same memory
    returns deleted=True then deleted=False (the second call's
    update_one matches zero docs because deleted_at != None).
"""

from bson import ObjectId

from agent.tests._fakes import (
    VectorSearchWritableCollection,
    make_fake_embedder,
)
from agent.tools.forget_memory import (
    HIGH_CONFIDENCE,
    ForgetMemoryInput,
    forget_memory,
)


embedder = make_fake_embedder()


def _doc(
    *,
    memory_id: ObjectId | None = None,
    user_id: str = "u_482",
    summary: str = "User is bulking this month",
    score: float = 0.85,
    deleted_at=None,
) -> dict:
    return {
        "_id": memory_id or ObjectId(),
        "user_id": user_id,
        "summary": summary,
        "score": score,
        "deleted_at": deleted_at,
    }


# ─── High-confidence path ─────────────────────────────────────────────


async def test_high_confidence_deletes_and_returns_summary():
    target_id = ObjectId()
    coll = VectorSearchWritableCollection([
        _doc(memory_id=target_id, score=0.85),
    ])

    result = await forget_memory(
        ForgetMemoryInput(user_id="u_482", query="the bulking thing"),
        collection=coll,
        embedder=embedder,
    )

    assert result.deleted is True
    assert result.needs_confirmation is False
    assert result.memory_id == str(target_id)
    assert result.summary == "User is bulking this month"
    assert result.score == 0.85
    # The doc in the collection actually has deleted_at set now.
    target = next(d for d in coll._docs if d["_id"] == target_id)
    assert target["deleted_at"] is not None


async def test_score_exactly_at_threshold_deletes():
    """Score == HIGH_CONFIDENCE should delete (the comparison is <)."""
    target_id = ObjectId()
    coll = VectorSearchWritableCollection([
        _doc(memory_id=target_id, score=HIGH_CONFIDENCE),
    ])

    result = await forget_memory(
        ForgetMemoryInput(user_id="u_482", query="bulking"),
        collection=coll,
        embedder=embedder,
    )

    assert result.deleted is True


# ─── Low-confidence path ──────────────────────────────────────────────


async def test_below_threshold_returns_needs_confirmation_without_writing():
    target_id = ObjectId()
    coll = VectorSearchWritableCollection([
        _doc(memory_id=target_id, score=HIGH_CONFIDENCE - 0.01),
    ])

    result = await forget_memory(
        ForgetMemoryInput(user_id="u_482", query="maybe bulking?"),
        collection=coll,
        embedder=embedder,
    )

    assert result.deleted is False
    assert result.needs_confirmation is True
    assert result.memory_id == str(target_id)
    assert result.summary == "User is bulking this month"
    # No write happened.
    target = next(d for d in coll._docs if d["_id"] == target_id)
    assert target["deleted_at"] is None


# ─── No-match path ────────────────────────────────────────────────────


async def test_empty_collection_returns_deleted_false():
    coll = VectorSearchWritableCollection([])

    result = await forget_memory(
        ForgetMemoryInput(user_id="u_482", query="anything"),
        collection=coll,
        embedder=embedder,
    )

    assert result.deleted is False
    assert result.needs_confirmation is False
    assert result.memory_id is None
    assert result.summary is None
    assert result.score is None


async def test_other_users_memory_is_invisible():
    """Hard tripwire — must NEVER delete another user's memory."""
    other_id = ObjectId()
    coll = VectorSearchWritableCollection([
        _doc(memory_id=other_id, user_id="u_other", score=0.95),
    ])

    result = await forget_memory(
        ForgetMemoryInput(user_id="u_482", query="bulking"),
        collection=coll,
        embedder=embedder,
    )

    # No match — u_other's memory was filtered out by the user_id filter.
    assert result.deleted is False
    assert result.memory_id is None
    target = next(d for d in coll._docs if d["_id"] == other_id)
    assert target["deleted_at"] is None  # untouched


# ─── Pipeline shape ───────────────────────────────────────────────────


async def test_pipeline_excludes_already_deleted_memories():
    """forget_memory must filter out soft-deleted memories so the agent
    never offers to forget something it already forgot. The filter is in
    a POST-search $match stage (Atlas vector index doesn't have deleted_at
    as a filterable field), not inside $vectorSearch."""
    coll = VectorSearchWritableCollection([
        _doc(memory_id=ObjectId(), score=0.9),
    ])

    await forget_memory(
        ForgetMemoryInput(user_id="u_482", query="anything"),
        collection=coll,
        embedder=embedder,
    )

    pipeline = coll.pipelines[0]
    vs_filter = pipeline[0]["$vectorSearch"]["filter"]
    assert vs_filter == {"user_id": {"$eq": "u_482"}}
    deleted_filter_stages = [
        s for s in pipeline
        if "$match" in s and s["$match"].get("deleted_at") == {"$eq": None}
    ]
    assert deleted_filter_stages, "forget_memory pipeline must filter soft-deleted memories"


# ─── Idempotency ──────────────────────────────────────────────────────


async def test_second_forget_call_on_same_memory_finds_nothing():
    """After a successful forget, the same query against the same collection
    should find no match — the $vectorSearch filter (deleted_at: None)
    excludes the now-deleted memory. The user gets a 'nothing matched'
    response, not a duplicate delete."""
    target_id = ObjectId()
    coll = VectorSearchWritableCollection([
        _doc(memory_id=target_id, score=0.85),
    ])

    first = await forget_memory(
        ForgetMemoryInput(user_id="u_482", query="bulking"),
        collection=coll,
        embedder=embedder,
    )
    assert first.deleted is True
    assert coll._docs[0]["deleted_at"] is not None

    second = await forget_memory(
        ForgetMemoryInput(user_id="u_482", query="bulking"),
        collection=coll,
        embedder=embedder,
    )
    # Second call: $vectorSearch filter excludes already-deleted doc.
    # Result: no match, deleted=False, memory_id=None.
    assert second.deleted is False
    assert second.memory_id is None
