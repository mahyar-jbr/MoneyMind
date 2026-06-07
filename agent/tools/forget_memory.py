"""Tool — forget_memory (V3).

Lets the user say "forget what I said about X" and have the agent
soft-delete the matching memory from Atlas. Soft-delete: sets
`deleted_at = now()` on the doc; `recall_memory` filters those out.
Doc stays in the collection as an audit trail.

Confidence model:
  - High match (score >= HIGH_CONFIDENCE): tool deletes immediately
    AND returns the deleted memory's summary so the agent can name
    what was forgotten in the reply.
  - Low match (score below threshold): tool does NOT delete; returns
    the candidate with `deleted: false` so the agent asks the user
    to confirm in chat ("is this the one?").
  - No match at all: tool returns count=0; agent tells the user it
    couldn't find anything matching.

This pattern keeps the on-camera flow single-turn for clear cases while
preventing the agent from nuking the wrong memory on ambiguous queries.
"""

from datetime import UTC, datetime

from bson import ObjectId
from pydantic import BaseModel, Field

from agent.db.client import get_database
from agent.embeddings.voyage import embed_query


# Score threshold above which we delete without explicit user confirmation.
# Tuned to typical Voyage voyage-3 + cosine scores: exact-match user
# queries land around 0.78-0.85 in our seed data, paraphrased queries
# 0.65-0.75, unrelated 0.4-0.6.
HIGH_CONFIDENCE = 0.75


class ForgetMemoryInput(BaseModel):
    user_id: str = Field(min_length=1)
    # Pass EITHER query (initial search) OR memory_id (after confirmation).
    # query is vector-searched; memory_id is the literal Mongo _id of a memory
    # the agent previously surfaced via needs_confirmation and the user just
    # confirmed. memory_id bypasses the search entirely and deletes directly.
    query: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "What the user wants forgotten, in their words. e.g. 'the bulking "
            "thing' or 'that I don't like Chipotle'. Vector-searched. Pass "
            "this on the FIRST forget call; on a follow-up confirmation, pass "
            "memory_id instead."
        ),
    )
    memory_id: str | None = Field(
        default=None,
        description=(
            "Pass the memory_id returned by a previous needs_confirmation=True "
            "result when the user has just confirmed 'yes'. Skips the vector "
            "search and deletes the matched memory directly. Cannot be passed "
            "together with query — pick one."
        ),
    )


class ForgetMemoryResult(BaseModel):
    user_id: str
    query: str
    # True if the tool actually flipped deleted_at on a memory this call.
    deleted: bool
    # True if a candidate exists but the score was below HIGH_CONFIDENCE
    # — the agent should confirm with the user before re-calling.
    needs_confirmation: bool
    # Populated when deleted=True OR needs_confirmation=True.
    memory_id: str | None = None
    summary: str | None = None
    score: float | None = None


async def forget_memory(
    params: ForgetMemoryInput,
    *,
    collection=None,
    embedder=None,
) -> ForgetMemoryResult:
    """Forget a memory the user no longer wants the agent to remember.

    Vector-searches the user's NON-DELETED memories for the closest match
    to {query}. If the top hit's score is >= HIGH_CONFIDENCE, soft-deletes
    it (sets deleted_at) and returns deleted=True. If the top hit is below
    the threshold, returns needs_confirmation=True without deleting — the
    agent should name the candidate in the reply and ask the user to
    confirm before calling forget_memory again with a tighter query.
    Returns deleted=False, needs_confirmation=False, memory_id=None when
    no memory matches at all.
    """
    if collection is None:
        collection = get_database().memories
    if embedder is None:
        embedder = embed_query

    # Direct memory_id path: confirmation branch from a prior call. Skip
    # the vector search and delete the matched memory directly. The
    # filter clauses ensure user_id isolation + idempotency (won't
    # re-flip an already-deleted memory).
    if params.memory_id is not None:
        if params.query is not None:
            raise ValueError(
                "forget_memory: pass query OR memory_id, not both"
            )
        try:
            oid = ObjectId(params.memory_id)
        except Exception as exc:
            raise ValueError(f"invalid memory_id: {params.memory_id}") from exc
        # Fetch the summary so we can return it for the agent's reply.
        target = await collection.find_one(
            {"_id": oid, "user_id": params.user_id, "deleted_at": None},
            {"summary": 1},
        )
        if target is None:
            return ForgetMemoryResult(
                user_id=params.user_id,
                query=params.memory_id,
                deleted=False,
                needs_confirmation=False,
            )
        result = await collection.update_one(
            {"_id": oid, "user_id": params.user_id, "deleted_at": None},
            {"$set": {"deleted_at": datetime.now(UTC)}},
        )
        return ForgetMemoryResult(
            user_id=params.user_id,
            query=params.memory_id,
            deleted=result.modified_count > 0,
            needs_confirmation=False,
            memory_id=params.memory_id,
            summary=str(target.get("summary", "")),
            score=None,
        )

    # Vector-search path: initial forget request.
    if params.query is None:
        raise ValueError("forget_memory: must pass either query or memory_id")

    query_vector = await embedder(params.query)

    pipeline = [
        {
            "$vectorSearch": {
                "index": "memories_vector_idx",
                "path": "embedding",
                "queryVector": query_vector,
                # Over-fetch: deleted_at is filtered post-search since it's
                # not declared as a filterable field in the Atlas index. We
                # ask for 5 candidates to make sure a top match survives
                # even if some of the top hits happen to be soft-deleted.
                "numCandidates": 40,
                "limit": 5,
                "filter": {"user_id": {"$eq": params.user_id}},
            }
        },
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        # deleted_at is not in the Atlas vector index's filter fields, so
        # we filter post-search. {$eq: null} matches both missing and
        # explicitly-null deleted_at, so pre-V3 memories are still visible.
        {"$match": {"deleted_at": {"$eq": None}}},
        {"$limit": 1},
        {"$project": {"_id": 1, "summary": 1, "score": 1}},
    ]

    top: dict | None = None
    async for doc in collection.aggregate(pipeline):
        top = doc
        break

    if top is None:
        return ForgetMemoryResult(
            user_id=params.user_id,
            query=params.query,
            deleted=False,
            needs_confirmation=False,
        )

    memory_id = str(top["_id"])
    summary = str(top.get("summary", ""))
    score = float(top["score"])

    if score < HIGH_CONFIDENCE:
        return ForgetMemoryResult(
            user_id=params.user_id,
            query=params.query,
            deleted=False,
            needs_confirmation=True,
            memory_id=memory_id,
            summary=summary,
            score=score,
        )

    # High confidence — soft-delete now.
    result = await collection.update_one(
        {
            "_id": ObjectId(memory_id),
            "user_id": params.user_id,
            "deleted_at": None,
        },
        {"$set": {"deleted_at": datetime.now(UTC)}},
    )

    return ForgetMemoryResult(
        user_id=params.user_id,
        query=params.query,
        # update_one is idempotent — modified_count is 0 if someone else
        # already deleted the doc between our search and our update.
        deleted=result.modified_count > 0,
        needs_confirmation=False,
        memory_id=memory_id,
        summary=summary,
        score=score,
    )
