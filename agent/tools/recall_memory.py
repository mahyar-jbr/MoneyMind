"""Tool #13 — recall_memory.

Semantic recall over the agent's `memories` collection via Atlas Vector
Search. Embeds the query text with Voyage AI, runs $vectorSearch filtered
by user_id (and optionally type), returns the top-k hits ranked by cosine
similarity score.

READ-only. Does NOT bump last_used or use_count — that's a separate write
the agent makes when it actually CONSUMES a recall (not every retrieval is
used). A follow-up tool will handle that bump.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent.db.client import get_database
from agent.embeddings.voyage import embed_query


MemoryType = Literal["pattern", "preference", "reaction", "fact"]


class RecallMemoryInput(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=20)
    type: MemoryType | None = None
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryHit(BaseModel):
    memory_id: str
    type: MemoryType
    tag: str
    summary: str
    evidence: list[dict]
    confidence: float
    score: float
    intervention: dict | None = None
    last_used: date | None = None
    use_count: int = 0


class RecallMemoryResult(BaseModel):
    user_id: str
    query: str
    k: int
    count: int
    memories: list[MemoryHit]


def _build_pipeline(params: RecallMemoryInput, query_vector: list[float]) -> list[dict]:
    vector_filter: dict = {"user_id": {"$eq": params.user_id}}
    if params.type is not None:
        vector_filter["type"] = {"$eq": params.type}

    return [
        {
            "$vectorSearch": {
                "index": "memories_vector_idx",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": params.k * 20,  # Atlas best practice: 10-20x limit
                "limit": params.k,
                "filter": vector_filter,
            }
        },
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$match": {"score": {"$gte": params.min_score}}},
        {
            "$project": {
                "_id": 1,
                "type": 1,
                "tag": 1,
                "summary": 1,
                "evidence": 1,
                "confidence": 1,
                "intervention": 1,
                "last_used": 1,
                "use_count": 1,
                "score": 1,
            }
        },
    ]


def _to_hit(doc: dict) -> MemoryHit:
    last_used = doc.get("last_used")
    if isinstance(last_used, datetime):
        last_used = last_used.date()
    return MemoryHit(
        memory_id=str(doc["_id"]),
        type=doc["type"],
        tag=doc["tag"],
        summary=doc["summary"],
        evidence=list(doc.get("evidence") or []),
        confidence=float(doc["confidence"]),
        score=float(doc["score"]),
        intervention=doc.get("intervention"),
        last_used=last_used,
        use_count=int(doc.get("use_count") or 0),
    )


async def recall_memory(
    params: RecallMemoryInput,
    *,
    collection=None,
    embedder=None,
) -> RecallMemoryResult:
    """Find memories semantically similar to {query} for this user.

    Use this when the user references something they've mentioned before,
    OR when you (the agent) want to check what you already know about a
    topic before generating a reply. Returns the top-k matches scored by
    cosine similarity; matches below min_score are dropped.

    Memories are READ-only here — the agent decides separately whether to
    mark a recall as actually used.
    """
    if collection is None:
        collection = get_database().memories
    if embedder is None:
        embedder = embed_query

    query_vector = await embedder(params.query)

    pipeline = _build_pipeline(params, query_vector)
    hits: list[MemoryHit] = []
    async for doc in collection.aggregate(pipeline):
        hits.append(_to_hit(doc))

    return RecallMemoryResult(
        user_id=params.user_id,
        query=params.query,
        k=params.k,
        count=len(hits),
        memories=hits,
    )
