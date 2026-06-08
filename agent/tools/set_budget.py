"""Tool — set_budget (V6).

Upsert a per-category monthly spending cap into the `budgets` collection.
Single tool covers both create + edit because the user's mental model is
the same ("cap food at $500" / "change my food cap to $400") and Gemini
conflates them anyway. Match key: (user_id, category, status="active") —
one active budget per category at any time. Re-setting bumps `limit` +
`updated_at` and leaves `created_at` intact.

When the user accepts a `propose_intervention(type="cap", ...)` flow, the
respond_to_intervention path can call set_budget directly with the
proposed params to materialize the cap (V6 closes that loop end-to-end).

Persisted shape (NEW collection — added 2026-06-08; see docs/data-model.md
budgets section when added):
    {
      _id: ObjectId,
      user_id: str,
      category: str,           # top-level: food / shopping / transport / ...
      limit: float,            # positive currency amount
      period: "month",         # single value today
      status: "active",        # active | abandoned (matches goals enum style)
      created_at: datetime,    # set on first insert; preserved on update
      updated_at: datetime,    # bumped on every set
    }
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent.db.client import get_database


BudgetStatus = Literal["active", "abandoned"]
BudgetPeriod = Literal["month"]


class SetBudgetInput(BaseModel):
    user_id: str = Field(min_length=1)
    category: str = Field(
        min_length=1,
        max_length=60,
        description=(
            "Top-level category to cap — 'food', 'shopping', 'transport', "
            "'subscriptions', 'health', etc. Lowercased automatically. Match "
            "what the user said ('food delivery' → 'food'; the cap covers the "
            "whole top-level bucket, not subcategories)."
        ),
    )
    limit: float = Field(
        gt=0,
        description="Monthly spending cap in the user's currency, > 0.",
    )
    period: BudgetPeriod = Field(
        default="month",
        description="Cap period. Only 'month' supported today.",
    )


class SetBudgetResult(BaseModel):
    budget_id: str
    user_id: str
    category: str
    limit: float
    period: BudgetPeriod
    status: BudgetStatus
    # True when an existing active budget for this (user, category) was
    # found and its limit was updated; False on first-time insert.
    updated: bool
    created_at: datetime
    updated_at: datetime


def _normalize_category(c: str) -> str:
    """Collapse to a single top-level category token.

    The vocabulary lives in `transactions.category` prefixes — single
    lowercase words like 'food', 'shopping', 'transport'. Strip the
    subcategory after a '.' ('food.delivery' → 'food'). Also strip
    multi-word inputs like 'Food Delivery' / 'Coffee Shop' down to the
    first word ('food', 'coffee') — the user phrases the category
    however they want but the bucket on the transaction is the
    top-level word. Without this collapse, capping 'food' then capping
    'food delivery' would silently create two separate budgets that
    both compete to show on the same dashboard row.
    """
    return c.strip().lower().split(".")[0].split()[0] if c.strip() else ""


async def set_budget(
    params: SetBudgetInput,
    *,
    collection=None,
) -> SetBudgetResult:
    """Set or update a monthly spending cap for one top-level category.

    Use when the user explicitly states a cap ("cap food at $500/month",
    "limit DoorDash to $300", "I want to spend no more than $150 on
    coffee") OR when materializing an accepted `cap` intervention from
    propose_intervention. Upserts: one active budget per (user_id,
    category) — re-calling with a new limit updates the existing doc,
    preserves created_at, bumps updated_at, and returns updated=True.
    """
    if collection is None:
        collection = get_database().budgets

    category = _normalize_category(params.category)
    now = datetime.now(UTC)

    existing = await collection.find_one(
        {"user_id": params.user_id, "category": category, "status": "active"},
        {"_id": 1, "created_at": 1},
    )

    if existing is None:
        doc = {
            "user_id": params.user_id,
            "category": category,
            "limit": float(params.limit),
            "period": params.period,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        result = await collection.insert_one(doc)
        return SetBudgetResult(
            budget_id=str(result.inserted_id),
            user_id=params.user_id,
            category=category,
            limit=float(params.limit),
            period=params.period,
            status="active",
            updated=False,
            created_at=now,
            updated_at=now,
        )

    # Existing active budget — update the limit + bump updated_at; leave
    # created_at intact for audit.
    await collection.update_one(
        {"_id": existing["_id"]},
        {"$set": {"limit": float(params.limit), "updated_at": now, "period": params.period}},
    )
    return SetBudgetResult(
        budget_id=str(existing["_id"]),
        user_id=params.user_id,
        category=category,
        limit=float(params.limit),
        period=params.period,
        status="active",
        updated=True,
        created_at=existing.get("created_at", now),
        updated_at=now,
    )
