"""Demo proof script for BACKLOG #13 — recall_memory live against Atlas.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_recall

Seeds three memories under user_id="u_demo_recall_13" (with document
embeddings — Atlas auto-embed is NOT configured on this cluster, so the
writer must populate the `embedding` field), then issues three queries
chosen to surface each memory by semantic similarity. Cleans up after.
"""

import asyncio
from datetime import datetime, UTC

from agent.db.client import close_mongo, get_database
from agent.embeddings.voyage import embed_document
from agent.tools.recall_memory import RecallMemoryInput, recall_memory


USER_ID = "u_demo_recall_13"

SEEDS = [
    {
        "user_id": USER_ID,
        "type": "pattern",
        "tag": "food_spike→no_prep",
        "summary": "Food delivery spikes correlate with work stress and no meal prep",
        "evidence": [{"date": datetime(2026, 2, 12, tzinfo=UTC), "note": "exam week"}],
        "confidence": 0.78,
        "use_count": 0,
    },
    {
        "user_id": USER_ID,
        "type": "preference",
        "tag": "morning_coffee",
        "summary": "Always buys coffee on the way to the office",
        "evidence": [{"date": datetime(2026, 5, 1, tzinfo=UTC), "note": "Starbucks 5x/week"}],
        "confidence": 0.91,
        "use_count": 0,
    },
    {
        "user_id": USER_ID,
        "type": "fact",
        "tag": "monthly_rent",
        "summary": "Pays $1,800 rent on the first of every month",
        "evidence": [{"date": datetime(2026, 5, 1, tzinfo=UTC), "note": "Interac e-transfer"}],
        "confidence": 1.0,
        "use_count": 0,
    },
]

QUERIES = [
    "Why does my food spend keep jumping when I'm busy?",  # should hit pattern
    "What do I usually grab in the mornings?",  # should hit preference
    "How much do I pay every month for my apartment?",  # should hit fact
]


async def main() -> None:
    db = get_database()
    coll = db.memories

    # Wipe prior runs cleanly (idempotent demo).
    await coll.delete_many({"user_id": USER_ID})

    # Embed each summary as a document and insert. Voyage rate-limits the
    # free tier aggressively; throttle to ~1 req/sec.
    print(f"\n=== SEEDING {len(SEEDS)} memories under {USER_ID} ===")
    for seed in SEEDS:
        seed["embedding"] = await embed_document(seed["summary"])
        seed["created_at"] = datetime.now(UTC)
        await asyncio.sleep(1.2)
    await coll.insert_many(SEEDS)
    print(f"inserted {len(SEEDS)} memories with document embeddings")

    # Atlas vector index is async-eventual on writes — give it a moment.
    print("waiting 5s for vector index to catch up...")
    await asyncio.sleep(5)

    # Recall each (also throttled).
    for q in QUERIES:
        print(f"\n--- query: {q!r} ---")
        result = await recall_memory(
            RecallMemoryInput(user_id=USER_ID, query=q, k=3, min_score=0.3)
        )
        print(f"  count: {result.count}")
        for i, m in enumerate(result.memories, 1):
            print(f"  [{i}] score={m.score:.3f}  type={m.type}  tag={m.tag}")
            print(f"      summary: {m.summary}")
        await asyncio.sleep(1.2)

    # Cleanup.
    print(f"\n=== CLEANUP: removing {USER_ID} memories ===")
    deleted = await coll.delete_many({"user_id": USER_ID})
    print(f"deleted {deleted.deleted_count} memories")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
