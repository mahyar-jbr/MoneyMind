"""Demo proof for BACKLOG #20 — summarize_week against Atlas.

Run from the agent/ directory:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_summarize_week

Seeds 8 outflow rows + 1 income row + 1 active Emergency Fund goal
under u_demo_summarize_20, calls summarize_week with as_of=2026-05-24
(Sunday of the seeded week), prints the full result + paragraph, asserts
every contract, then cleans up.
"""

import asyncio
from datetime import date, datetime

from bson import ObjectId

from agent.db.client import close_mongo, get_database
from agent.tools.summarize_week import SummarizeWeekInput, summarize_week


USER_ID = "u_demo_summarize_20"


async def main() -> None:
    db = get_database()
    txn = db.transactions
    goals = db.goals

    # Clean slate.
    await txn.delete_many({"user_id": USER_ID})
    await goals.delete_many({"user_id": USER_ID})

    # 1. Seed 8 outflow rows across 4 categories for the week of 2026-05-18..24.
    rows = [
        # food.delivery $211 (4 rows summing to ~211)
        (date(2026, 5, 19), "DoorDash", "food.delivery", -52.10),
        (date(2026, 5, 20), "DoorDash", "food.delivery", -38.42),
        (date(2026, 5, 22), "Uber Eats", "food.delivery", -73.48),
        (date(2026, 5, 23), "DoorDash", "food.delivery", -47.00),
        # transport.transit $24 (2 rows)
        (date(2026, 5, 18), "Presto", "transport.transit", -12.00),
        (date(2026, 5, 21), "Presto", "transport.transit", -12.00),
        # shopping.amazon $73 (1 row)
        (date(2026, 5, 21), "Amazon", "shopping.amazon", -73.00),
        # food.coffee $32 (1 row)
        (date(2026, 5, 22), "Balzac's", "food.coffee", -32.00),
        # Income row — should be EXCLUDED from totals + count.
        (date(2026, 5, 20), "Direct Deposit", "income.salary", 2400.00),
    ]
    for d, merchant, category, amount in rows:
        await txn.insert_one({
            "user_id": USER_ID,
            "date": datetime(d.year, d.month, d.day),
            "merchant": merchant,
            "merchant_canonical": merchant.lower().replace(" ", "_").replace("'", ""),
            "category": category,
            "amount": amount,
            "currency": "USD",
            "source": "demo_summarize_20",
        })

    # 2. Seed one active Emergency Fund goal (matches #16's demo).
    goal_id = ObjectId()
    await goals.insert_one({
        "_id": goal_id,
        "user_id": USER_ID,
        "title": "Emergency Fund",
        "target_amount": 8000.0,
        "current_amount": 2400.0,
        "target_date": datetime(2026, 12, 31),
        "pace_check": "weekly",
        "status": "active",
        "created_at": datetime(2026, 1, 1),
    })

    print(f"\n=== SEEDED: {len(rows)} transactions + 1 goal under {USER_ID} ===")

    # 3. Call summarize_week.
    result = await summarize_week(
        SummarizeWeekInput(
            user_id=USER_ID,
            as_of=date(2026, 5, 24),
            week_offset=0,
            include_goals=True,
        )
    )

    print("\n=== STRUCTURED RESULT ===")
    print(f"  week_start:        {result.week_start}")
    print(f"  week_end:          {result.week_end}")
    print(f"  total_spend:       ${result.total_spend:.2f}")
    print(f"  transaction_count: {result.transaction_count}")
    print("  top_categories:")
    for c in result.top_categories:
        print(f"    - {c.category:25s}  ${c.spend:>7.2f}  ({c.pct_of_total:>4.1f}% of total)")
    print("  goals:")
    for g in result.goals:
        print(f"    - {g.title:20s}  {g.pct_complete:>5.1f}%  note={g.note!r}")

    print("\n=== PARAGRAPH ===")
    print(f"  {result.paragraph}")

    # 4. Assertions.
    print("\n=== ASSERTIONS ===")
    assert result.week_start == date(2026, 5, 18), f"week_start was {result.week_start}"
    assert result.week_end == date(2026, 5, 24), f"week_end was {result.week_end}"
    expected_total = 211.00 + 24.00 + 73.00 + 32.00  # 340.00
    assert abs(result.total_spend - expected_total) < 0.01, (
        f"total_spend was {result.total_spend}, expected {expected_total}"
    )
    assert result.transaction_count == 8, (
        f"transaction_count was {result.transaction_count}, expected 8 (excluding income)"
    )
    assert result.top_categories[0].category == "food.delivery"
    assert abs(result.top_categories[0].spend - 211.00) < 0.01
    # 211/340 = 62.058... → rounded to 62.1
    assert result.top_categories[0].pct_of_total == 62.1, (
        f"pct_of_total was {result.top_categories[0].pct_of_total}, expected 62.1"
    )
    assert len(result.goals) == 1
    assert result.goals[0].pct_complete == 30.0
    assert "Behind" in result.goals[0].note, f"goal note was {result.goals[0].note!r}"
    # Paragraph must mention the top-3 categories + the goal status.
    assert "Food Delivery" in result.paragraph
    assert "Shopping Amazon" in result.paragraph
    assert "$211" in result.paragraph
    assert "Emergency Fund" in result.paragraph
    print("  ALL ASSERTIONS PASSED")

    # 5. Cleanup.
    print(f"\n=== CLEANUP: removing {USER_ID} data ===")
    t_del = (await txn.delete_many({"user_id": USER_ID})).deleted_count
    g_del = (await goals.delete_many({"user_id": USER_ID})).deleted_count
    print(f"deleted {t_del} transactions, {g_del} goal(s)")

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
