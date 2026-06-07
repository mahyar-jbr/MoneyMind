"""Tool #14 — write_memory.

Persists a new memory the agent has just discovered. Embeds the summary
inline (Path A — Atlas auto-embed is not configured on this cluster; see
docs/decisions.md 2026-05-31). The persisted doc matches docs/data-model.md
§ memories.

WRITE-only. Does NOT bump use_count or last_used on other memories.
created_at is stamped server-side; the agent cannot control it.
"""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent.db.client import get_database
from agent.embeddings.voyage import embed_document


MemoryType = Literal["pattern", "preference", "reaction", "fact"]


class EvidenceItem(BaseModel):
    date: date
    note: str = Field(min_length=1, max_length=200)


class WriteMemoryInput(BaseModel):
    user_id: str = Field(min_length=1)
    type: MemoryType
    # tag is optional from the LLM's perspective — Gemini Flash was
    # silently refusing to call write_memory because it could not
    # synthesize a value for an undocumented required string field.
    # When omitted, we derive a tag from the first few words of summary.
    tag: str | None = Field(default=None, max_length=80)
    summary: str = Field(min_length=10, max_length=500)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
    intervention: dict | None = None


class WriteMemoryResult(BaseModel):
    memory_id: str
    user_id: str
    type: MemoryType
    tag: str
    created_at: datetime
    embedded: bool


def _at_midnight(d: date) -> datetime:
    """Match the rest of the codebase: dates persist as naive datetimes."""
    return datetime(d.year, d.month, d.day)


async def write_memory(
    params: WriteMemoryInput,
    *,
    collection=None,
    embedder=None,
) -> WriteMemoryResult:
    """Persist a new memory the agent has discovered about this user.

    Use this when you've inferred a pattern, observed a preference, captured
    a stated fact, or recorded the user's reaction to an intervention.
    Summary is what gets vector-searched — make it a single concrete
    sentence (not a label). Evidence is optional but cheap to include —
    later recalls become more credible with it.

    Does NOT update related memories' use_count or last_used. The agent
    decides separately when a recall has actually been consumed.
    """
    if collection is None:
        collection = get_database().memories
    if embedder is None:
        embedder = embed_document

    embedding = await embedder(params.summary)

    # Derive a tag if the LLM didn't supply one. First 3 lowercased,
    # underscored words of summary, capped at 80 chars (db constraint).
    tag = params.tag
    if not tag:
        words = params.summary.lower().split()[:3]
        tag = "_".join(w.strip(".,!?;:") for w in words)[:80] or "memory"

    created_at = datetime.now(UTC)
    doc = {
        "user_id": params.user_id,
        "type": params.type,
        "tag": tag,
        "summary": params.summary,
        "evidence": [
            {"date": _at_midnight(e.date), "note": e.note} for e in params.evidence
        ],
        "intervention": params.intervention,
        "confidence": params.confidence,
        "embedding": embedding,
        "created_at": created_at,
        "last_used": None,
        "use_count": 0,
        # V3 — forget_memory flips this to a datetime; recall_memory's
        # $vectorSearch filter excludes any doc where deleted_at != null.
        "deleted_at": None,
    }

    result = await collection.insert_one(doc)
    return WriteMemoryResult(
        memory_id=str(result.inserted_id),
        user_id=params.user_id,
        type=params.type,
        tag=tag,
        created_at=created_at,
        embedded=True,
    )
