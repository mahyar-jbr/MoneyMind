"""Demo proof script for BACKLOG #14 — write_memory + recall round-trip.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_write

Writes ONE memory under user_id="u_demo_write_14" (with an inline document
embedding via Voyage, Path A — auto-embed is off on this cluster), then
recalls it via #13's recall_memory with a semantically-related query, and
cleans up after.

Voyage free-tier rate limits are tight (~3 RPM). The script spaces the
embed + recall calls accordingly. If the rate limit bites, wait ~5 min and
re-run.
"""

import asyncio
from datetime import date

from agent.db.client import close_mongo, get_database
from agent.tools.recall_memory import RecallMemoryInput, recall_memory
from agent.tools.write_memory import EvidenceItem, WriteMemoryInput, write_memory


USER_ID = "u_demo_write_14"
QUERY = "what does the user do on weekends with food"


async def main() -> None:
    coll = get_database().memories

    # Clean slate (idempotent demo).
    await coll.delete_many({"user_id": USER_ID})

    # 1. Write
    print(f"\n=== WRITE: 1 memory under {USER_ID} ===")
    params = WriteMemoryInput(
        user_id=USER_ID,
        type="pattern",
        tag="weekend_dining_out",
        summary="User dines out 3-4× on weekends, averaging $45 per meal.",
        evidence=[
            EvidenceItem(date=date(2026, 5, 17), note="brunch at Pai Northern, $52"),
            EvidenceItem(date=date(2026, 5, 18), note="dinner at Khao San, $48"),
        ],
        confidence=0.72,
        intervention={"weekly_cap": {"category": "food.dining", "amount_usd": 200}},
    )
    result = await write_memory(params)
    print(f"  memory_id:  {result.memory_id}")
    print(f"  embedded:   {result.embedded}")
    print(f"  created_at: {result.created_at.isoformat()}")
    print(f"  tag:        {result.tag}")

    # Atlas vector index is eventually-consistent on writes — give it a moment.
    # Also spaces the next Voyage call vs. the embed_document we just made.
    print("\nwaiting 20s for index propagation + Voyage rate-limit window...")
    await asyncio.sleep(20)

    # 2. Recall
    print(f"\n=== RECALL: query={QUERY!r} ===")
    recall = await recall_memory(
        RecallMemoryInput(user_id=USER_ID, query=QUERY, k=3, min_score=0.3)
    )
    print(f"  count: {recall.count}")
    for i, m in enumerate(recall.memories, 1):
        print(f"  [{i}] score={m.score:.3f}  type={m.type}  tag={m.tag}")
        print(f"      summary: {m.summary}")

    # 3. Cleanup
    print(f"\n=== CLEANUP: removing {USER_ID} memories ===")
    deleted = await coll.delete_many({"user_id": USER_ID})
    print(f"deleted {deleted.deleted_count} memories")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
