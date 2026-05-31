"""Tool #11 — query_transactions.

Foundational read-side tool: fetches raw transaction rows from atlas.transactions
for a given user, optionally filtered by category, date range, amount range,
and direction. Returns Pydantic models (per agent/README.md convention).

LangGraph wiring is intentionally NOT part of this ticket — the tool is exposed
as a plain async callable so it can be invoked directly (per the ticket's
demo proof) and bound into a tool list once the graph migration lands.
"""

from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field

from agent.db.client import get_database


class QueryTransactionsInput(BaseModel):
    user_id: str = Field(min_length=1)
    category: str | None = None
    date_from: date | None = None  # inclusive lower bound
    date_to: date | None = None  # inclusive upper bound (end-of-day)
    min_amount: float | None = Field(default=None, ge=0)
    max_amount: float | None = Field(default=None, ge=0)
    outflow_only: bool = False
    limit: int = Field(default=50, ge=1, le=500)


class TransactionRow(BaseModel):
    date: date
    merchant: str
    merchant_canonical: str
    category: str
    amount: float
    currency: str


class QueryTransactionsResult(BaseModel):
    user_id: str
    count: int
    transactions: list[TransactionRow]


def _build_filter(params: QueryTransactionsInput) -> dict:
    """Build the Mongo $match dict.

    `amount: {$lt: 0}` means spending only (outflow). Income rows have
    positive amounts. See docs/architecture.md route convention #3.
    """
    f: dict = {"user_id": params.user_id}

    if params.category is not None:
        f["category"] = params.category

    if params.date_from is not None or params.date_to is not None:
        date_filter: dict = {}
        if params.date_from is not None:
            date_filter["$gte"] = datetime.combine(params.date_from, datetime.min.time())
        if params.date_to is not None:
            # End-of-day inclusivity: use $lt next_day so a doc dated exactly
            # date_to (stored at 00:00) is included. Matches route convention #2.
            next_day = datetime.combine(params.date_to + timedelta(days=1), datetime.min.time())
            date_filter["$lt"] = next_day
        f["date"] = date_filter

    if params.outflow_only:
        # Outflow means amount < 0 — see docstring in _build_filter.
        f["amount"] = {"$lt": 0}

    # min/max apply to absolute value so the same bounds work for spending or income.
    expr_clauses: list[dict] = []
    if params.min_amount is not None:
        expr_clauses.append({"$gte": [{"$abs": "$amount"}, params.min_amount]})
    if params.max_amount is not None:
        expr_clauses.append({"$lte": [{"$abs": "$amount"}, params.max_amount]})
    if expr_clauses:
        f["$expr"] = {"$and": expr_clauses} if len(expr_clauses) > 1 else expr_clauses[0]

    return f


async def query_transactions(
    params: QueryTransactionsInput,
    *,
    collection=None,
) -> QueryTransactionsResult:
    """Fetch transactions for a user, filtered by category/dates/amount/direction.

    Use this when you need the actual rows behind a number — specific merchants,
    individual purchases, or to drill into a date range. For aggregated totals
    (weekly spend, category breakdowns), use summarize_week instead.

    `outflow_only=True` restricts to spending (negative amounts). Default is
    False so income rows are included.
    """
    if collection is None:
        collection = get_database().transactions

    cursor = (
        collection.find(_build_filter(params), {"_id": 0, "raw": 0, "source": 0, "user_id": 0})
        .sort("date", -1)
        .limit(params.limit)
    )

    rows: list[TransactionRow] = []
    async for doc in cursor:
        # Stored 'date' is a naive datetime at midnight — convert to date.
        if isinstance(doc.get("date"), datetime):
            doc["date"] = doc["date"].date()
        rows.append(TransactionRow(**doc))

    return QueryTransactionsResult(
        user_id=params.user_id,
        count=len(rows),
        transactions=rows,
    )
