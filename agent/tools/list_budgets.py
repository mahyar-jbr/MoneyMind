"""Tool — list_budgets (V6).

Read the user's budgets so the agent can name them in chat and the
dashboard can render real per-category caps. Read-only: single `find`.
Default status filter = "active" (abandoned hidden unless the user
explicitly asks "show me everything"). Sort: category ascending so the
UI renders a stable ordering across calls.

The dashboard's BudgetProgress widget consumes this via the backend
GET /budgets route (Vercel proxy). Once V6 ships, that widget's SAMPLE
pill is removed.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent.db.client import get_database


BudgetStatus = Literal["active", "abandoned"]
BudgetPeriod = Literal["month"]


class ListBudgetsInput(BaseModel):
    user_id: str = Field(min_length=1)
    status: BudgetStatus | Literal["all"] = Field(
        default="active",
        description=(
            "Filter by status. Default 'active' — surfaces only budgets the "
            "user is still enforcing. Pass 'all' to include abandoned ones."
        ),
    )
    limit: int = Field(default=20, ge=1, le=100)


class BudgetSummary(BaseModel):
    budget_id: str
    category: str
    limit: float
    period: BudgetPeriod
    status: BudgetStatus
    created_at: datetime
    updated_at: datetime


class ListBudgetsResult(BaseModel):
    user_id: str
    count: int
    budgets: list[BudgetSummary]


def _to_summary(doc: dict) -> BudgetSummary:
    return BudgetSummary(
        budget_id=str(doc["_id"]),
        category=str(doc.get("category", "")),
        limit=float(doc.get("limit", 0)),
        period=doc.get("period", "month"),
        status=doc.get("status", "active"),
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at", doc["created_at"]),
    )


async def list_budgets(
    params: ListBudgetsInput,
    *,
    collection=None,
) -> ListBudgetsResult:
    """List the user's per-category spending caps.

    Call this when the user asks about budgets/caps ("what are my caps?",
    "am I over budget on food?") or before proposing a `cap` intervention
    so you can check whether one already exists for that category. Default
    status='active' hides abandoned budgets. Returns category + limit so
    the agent can name actual numbers in its reply.
    """
    if collection is None:
        collection = get_database().budgets

    query: dict = {"user_id": params.user_id}
    if params.status != "all":
        query["status"] = params.status

    cursor = collection.find(query).sort("category", 1).limit(params.limit)
    budgets: list[BudgetSummary] = []
    async for doc in cursor:
        budgets.append(_to_summary(doc))

    return ListBudgetsResult(
        user_id=params.user_id,
        count=len(budgets),
        budgets=budgets,
    )
