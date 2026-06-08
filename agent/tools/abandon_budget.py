"""Tool — abandon_budget (V6).

Mark a user's active budget cap as abandoned by flipping its status enum
from "active" → "abandoned". Mirrors abandon_goal's pattern exactly: the
schema has the abandoned enum value (no new field), the budget stays in
Atlas as audit trail, and list_budgets's default status="active" filter
hides it from the dashboard.

Two call paths mirror abandon_goal:
  - query=<user's words> → category-substring match against active
    budgets, stopwords stripped. Exactly one match → flip immediately.
    Multiple matches → needs_confirmation=True with candidates.
  - budget_id=<id from previous needs_confirmation result> → skip search
    and flip directly.

The simpler shortcut path is also supported: if the user says "remove my
food cap" the agent can pass category="food" directly (matches exactly
to the normalized category field) without going through the title-match
heuristic.
"""

from datetime import UTC, datetime

from bson import ObjectId
from pydantic import BaseModel, Field

from agent.db.client import get_database


class AbandonBudgetInput(BaseModel):
    user_id: str = Field(min_length=1)
    # Pick ONE of query / category / budget_id.
    # - query: fuzzy match against active budgets' categories.
    # - category: exact match against the normalized category field.
    # - budget_id: skip search; flip the doc with this _id directly.
    query: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "What the user wants to remove, in their words. e.g. 'forget the "
            "food cap', 'drop my shopping budget'. Word-overlap matched. Pass "
            "on the FIRST call when the user names the cap loosely; on a "
            "confirmation follow-up, pass budget_id instead."
        ),
    )
    category: str | None = Field(
        default=None,
        max_length=60,
        description=(
            "Top-level category to remove the cap on. Use this when the "
            "user names the category cleanly ('remove my food cap', "
            "'cancel the transport budget'); exact match against the "
            "normalized category field. Skips the fuzzy query path."
        ),
    )
    budget_id: str | None = Field(
        default=None,
        description=(
            "Pass the budget_id from a previous needs_confirmation=True "
            "result when the user has confirmed the candidate. Skips the "
            "search and flips status directly."
        ),
    )


class AbandonBudgetCandidate(BaseModel):
    budget_id: str
    category: str
    limit: float


class AbandonBudgetResult(BaseModel):
    user_id: str
    abandoned: bool
    needs_confirmation: bool
    budget_id: str | None = None
    category: str | None = None
    limit: float | None = None
    candidates: list[AbandonBudgetCandidate] = Field(default_factory=list)
    active_categories: list[str] = Field(default_factory=list)


def _category_matches(query: str, category: str) -> bool:
    """Same stopword-stripping match as abandon_goal but against category text."""
    stopwords = {
        "the", "a", "an", "to", "for", "my", "that", "this", "it",
        "of", "in", "on", "and", "or",
        # Domain words.
        "budget", "cap", "limit", "spending", "spend",
        # Trigger verbs the user phrases around.
        "forget", "cancel", "drop", "abandon", "delete", "remove",
        "give", "up", "kill", "scrap", "nevermind", "stop",
    }
    q_words = [w for w in query.lower().split() if len(w) > 1 and w not in stopwords]
    if not q_words:
        return False
    cat_lower = category.lower()
    return all(w in cat_lower for w in q_words)


async def abandon_budget(
    params: AbandonBudgetInput,
    *,
    collection=None,
) -> AbandonBudgetResult:
    """Remove a user's active spending cap by flipping its status to abandoned.

    Use when the user wants to drop / cancel / forget a cap they previously
    set ("forget the food cap", "cancel my shopping budget", "remove the
    coffee limit"). Status flip — NOT a delete. The cap stays in Atlas as
    audit trail; list_budgets's default status='active' filter hides it.

    Three call patterns (pick ONE):
    (A) query=<user's words> → fuzzy word-overlap against active budgets'
        categories, stopwords stripped. One match → flip + return.
        Multiple → needs_confirmation=True with candidates. None → returns
        active_categories so you can say "I don't see that, your active
        caps are: food, shopping".
    (B) category=<normalized category name> → exact match. Use when the
        user names the category cleanly. Faster + more reliable than (A).
    (C) budget_id=<id from previous needs_confirmation> → direct flip.
    """
    if collection is None:
        collection = get_database().budgets

    n_paths = sum(p is not None for p in (params.query, params.category, params.budget_id))
    if n_paths == 0:
        raise ValueError("abandon_budget: must pass one of query / category / budget_id")
    if n_paths > 1:
        raise ValueError("abandon_budget: pass only ONE of query / category / budget_id")

    # Path C: budget_id direct flip.
    if params.budget_id is not None:
        try:
            oid = ObjectId(params.budget_id)
        except Exception as exc:
            raise ValueError(f"invalid budget_id: {params.budget_id}") from exc
        target = await collection.find_one(
            {"_id": oid, "user_id": params.user_id, "status": "active"},
            {"category": 1, "limit": 1},
        )
        if target is None:
            return AbandonBudgetResult(
                user_id=params.user_id, abandoned=False, needs_confirmation=False
            )
        result = await collection.update_one(
            {"_id": oid, "user_id": params.user_id, "status": "active"},
            {"$set": {"status": "abandoned", "abandoned_at": datetime.now(UTC)}},
        )
        return AbandonBudgetResult(
            user_id=params.user_id,
            abandoned=result.modified_count > 0,
            needs_confirmation=False,
            budget_id=params.budget_id,
            category=str(target.get("category", "")),
            limit=float(target.get("limit", 0)),
        )

    # Path B: exact category match.
    if params.category is not None:
        # Same collapse as set_budget._normalize_category: "Food Delivery"
        # / "food.delivery" / "FOOD" all → "food", so the user's loose
        # phrasing finds the exact-match top-level cap.
        raw = params.category.strip()
        normalized = raw.lower().split(".")[0].split()[0] if raw else ""
        target = await collection.find_one(
            {
                "user_id": params.user_id,
                "category": normalized,
                "status": "active",
            },
            {"_id": 1, "category": 1, "limit": 1},
        )
        if target is None:
            # No exact match — surface active categories so the agent can
            # tell the user what's actually on file.
            return AbandonBudgetResult(
                user_id=params.user_id,
                abandoned=False,
                needs_confirmation=False,
                active_categories=await _active_categories(collection, params.user_id),
            )
        result = await collection.update_one(
            {"_id": target["_id"], "user_id": params.user_id, "status": "active"},
            {"$set": {"status": "abandoned", "abandoned_at": datetime.now(UTC)}},
        )
        return AbandonBudgetResult(
            user_id=params.user_id,
            abandoned=result.modified_count > 0,
            needs_confirmation=False,
            budget_id=str(target["_id"]),
            category=str(target.get("category", "")),
            limit=float(target.get("limit", 0)),
        )

    # Path A: fuzzy query.
    cursor = collection.find(
        {"user_id": params.user_id, "status": "active"},
        {"_id": 1, "category": 1, "limit": 1},
    )
    active: list[dict] = []
    async for doc in cursor:
        active.append(doc)

    matches = [d for d in active if _category_matches(params.query or "", str(d.get("category", "")))]

    if len(matches) == 0:
        return AbandonBudgetResult(
            user_id=params.user_id,
            abandoned=False,
            needs_confirmation=False,
            active_categories=[str(d.get("category", "")) for d in active],
        )

    if len(matches) > 1:
        return AbandonBudgetResult(
            user_id=params.user_id,
            abandoned=False,
            needs_confirmation=True,
            candidates=[
                AbandonBudgetCandidate(
                    budget_id=str(d["_id"]),
                    category=str(d.get("category", "")),
                    limit=float(d.get("limit", 0)),
                )
                for d in matches
            ],
        )

    target = matches[0]
    target_id = target["_id"]
    result = await collection.update_one(
        {"_id": target_id, "user_id": params.user_id, "status": "active"},
        {"$set": {"status": "abandoned", "abandoned_at": datetime.now(UTC)}},
    )
    return AbandonBudgetResult(
        user_id=params.user_id,
        abandoned=result.modified_count > 0,
        needs_confirmation=False,
        budget_id=str(target_id),
        category=str(target.get("category", "")),
        limit=float(target.get("limit", 0)),
    )


async def _active_categories(collection, user_id: str) -> list[str]:
    cursor = collection.find(
        {"user_id": user_id, "status": "active"}, {"category": 1}
    )
    out: list[str] = []
    async for doc in cursor:
        out.append(str(doc.get("category", "")))
    return out
