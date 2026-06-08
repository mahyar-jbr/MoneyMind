"""PDF bank statement → normalized transactions.

Single-call LLM pipeline: Gemini 2.5 Flash on Vertex AI gets the PDF
+ category vocabulary in one prompt and returns a structured list of
{date, description, amount, currency, category}. Then we:

  1. Run the merchant canonicalizer over each description (deterministic
     Python — see merchant_canonical.py). Known merchants get a canonical
     key + a display name AND we OVERRIDE the LLM's category guess with
     the canonical-key→category map for high-confidence cases (Tim
     Hortons is ALWAYS food.coffee even if the model wandered).
  2. Validate every category is in our vocab; fall back to other.misc
     for stragglers and emit a warning in the result.
  3. Split out payments-to-card (amount < 0) so they don't pollute spend
     analysis — they're not user spending, they're the user paying their
     bill. Returned in a separate `skipped_payments` list for the agent
     to mention in its reply.
  4. Build the final transactions docs in the SAME shape as
     backend/app/ingestion/csv.py produces, so the rest of the app
     (aggregations, dashboard, agent tools) consumes them without
     changes.

NOT idempotent at this layer — dedupe happens in pipeline.py against the
collection. This module is pure parse + categorize.

Cost: ~$0.02 per statement extraction on Flash 2.5. Free tier covers the
demo budget many times over.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from datetime import date as DateType
from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_google_vertexai.chat_models import ChatVertexAI
from pydantic import BaseModel, Field, ValidationError

from app.ingestion.category_vocab import (
    is_valid_category,
    vocabulary_prompt_block,
)
from app.ingestion.merchant_canonical import canonicalize


logger = logging.getLogger(__name__)

# Override map: when canonicalize() returns one of these keys, force the
# category regardless of what the LLM guessed. Built from the curated
# rules in merchant_canonical.py — the LLM gets the soft hints in the
# vocab block, but for these specific known merchants we are MORE
# confident than any model output.
_CATEGORY_BY_CANONICAL_KEY: dict[str, str] = {
    # Coffee
    "tim_hortons": "food.coffee",
    "starbucks": "food.coffee",
    # Fast food
    "mcdonalds": "food.fast",
    "subway": "food.fast",
    "burger_king": "food.fast",
    "wendys": "food.fast",
    "kfc": "food.fast",
    "pizza_hut": "food.fast",
    "dominos": "food.fast",
    "chipotle": "food.fast",
    # Local resto cluster from the sample
    "habibz_corner": "food.fast",
    "pita_land": "food.fast",
    "sushi_kui": "food.dining",
    "wild_wing": "food.fast",
    "stacked_pancake": "food.dining",
    "state_and_main": "food.dining",
    "chucks_chicken": "food.fast",
    "five_star": "food.fast",
    # Delivery
    "doordash": "food.delivery",
    "uber_eats": "food.delivery",
    "skip_the_dishes": "food.delivery",
    "grubhub": "food.delivery",
    # Rideshare
    "uber": "transport.rideshare",
    "lyft": "transport.rideshare",
    # Gas
    "esso": "transport.gas",
    "shell": "transport.gas",
    "petro_canada": "transport.gas",
    "chevron": "transport.gas",
    "exxon_mobil": "transport.gas",
    # Parking
    "honk_parking": "transport.parking",
    "toronto_parking": "transport.parking",
    "impark": "transport.parking",
    # Groceries
    "longos": "food.groceries",
    "metro": "food.groceries",
    "loblaws": "food.groceries",
    "sobeys": "food.groceries",
    "walmart": "shopping.general",  # Walmart is mixed — let LLM hint if needed
    "costco": "food.groceries",
    "whole_foods": "food.groceries",
    "trader_joes": "food.groceries",
    "safeway": "food.groceries",
    # Pets
    "petvalu": "pets.general",
    "petsmart": "pets.general",
    # Home
    "homesense": "shopping.home",
    "winners": "shopping.clothing",
    "ikea": "shopping.home",
    "home_depot": "shopping.home",
    # Shopping
    "amazon": "shopping.amazon",
    # Fitness
    "movati": "subscriptions.gym",
    "goodlife": "subscriptions.gym",
    "planet_fitness": "subscriptions.gym",
    # Subscriptions / digital
    "spotify": "subscriptions.media",
    "netflix": "subscriptions.media",
    "apple": "subscriptions.software",  # APPLE.COM/BILL is almost always subs
    "claude_ai": "subscriptions.software",
    "openai": "subscriptions.software",
    "canva": "subscriptions.software",
    "google": "subscriptions.software",
    "microsoft": "subscriptions.software",
    "adobe": "subscriptions.software",
    # Business / gov
    "corporations_canada": "services.business",
    "nuans": "services.business",
    "mycreds": "services.business",
    "service_ontario": "services.government",
    # Card-issuer
    "card_fee": "money.fees",
    "annual_fee": "money.fees",
    "interest_charge": "money.interest",
    "card_payment": "income.refund",  # not really income, but the splitter handles it
}


MODEL_NAME = "gemini-2.5-flash"


# ─── LLM output schema ─────────────────────────────────────────────


class _ExtractedTxn(BaseModel):
    """One row as the LLM returns it. Field names chosen to avoid pydantic
    annotation collisions (date → txn_date)."""

    txn_date: DateType = Field(description="YYYY-MM-DD")
    description: str = Field(
        description="Verbatim merchant description from the statement line"
    )
    amount: float = Field(
        description=(
            "POSITIVE for charges (user spent), NEGATIVE for payments/credits "
            "to the card. Use the absolute value the cardholder paid in the "
            "currency below."
        )
    )
    currency: str = Field(
        default="CAD",
        description="ISO-4217. Default CAD; foreign rows use stated currency.",
    )
    category: str = Field(
        description=(
            "One of the allowed categories (see prompt). Use other.misc only "
            "when nothing else clearly fits."
        )
    )


class _ExtractedStatement(BaseModel):
    issuer: str = Field(description="Card issuer, e.g. 'American Express'")
    account_last4: str = Field(description="Last 4 digits or masked id")
    period_start: DateType | None = None
    period_end: DateType | None = None
    transactions: list[_ExtractedTxn]


# ─── Public result shape ───────────────────────────────────────────


@dataclass(frozen=True)
class StatementParseResult:
    """Output of parse_statement_pdf — same shape as ParseResult in csv.py
    so the route handler stays uniform."""

    documents: list[dict]              # ready for transactions.insert_many
    skipped_payments: list[dict]       # negative-amount rows excluded from spend
    issuer: str
    account_last4: str
    period_start: DateType | None
    period_end: DateType | None
    warnings: list[str]
    source: str                        # tags every doc for re-upload dedupe


# ─── LLM prompt ────────────────────────────────────────────────────


def _build_prompt() -> str:
    return f"""You are extracting transactions from a credit card statement PDF.

For EVERY transaction line on EVERY page, return one row with:
  - txn_date as YYYY-MM-DD (dates appear in formats like "19 May 2026" or "30 Apr. 2026")
  - description: VERBATIM the merchant line (preserve location words, store numbers,
    keep any '?' characters which are apostrophe substitutions, collapse multi-space to single)
  - amount: POSITIVE for charges (user spent money), NEGATIVE for "PAYMENT RECEIVED" /
    "AUTOPAY" / "AUTO PAY" lines (user paying their bill — those are credits to the card,
    NOT user spending). If a row clearly shows a refund TO the user, also negative.
  - currency: "CAD" by default. If the row has a "Foreign Spend Amount" block with a
    different currency (e.g. "Foreign Spend Amount: 5.00 UNITED STATES DOLLAR"), the
    `currency` for that row should still be "CAD" because the amount field is what the
    cardholder ACTUALLY PAID in their card's currency. Only set currency to the foreign
    code if the statement does not also show a CAD-equivalent.
  - category: pick ONE from the allowed list below. Match the merchant name to the
    closest hint. Use other.misc only if nothing else fits.

Skip these (do NOT return as transactions):
  - page headers and footers
  - "This is not a billing Statement" disclaimers
  - page numbers
  - section headers like "Summary", "Transaction Details", column labels

Return EVERY transaction in chronological order (oldest first).

{vocabulary_prompt_block()}"""


# ─── Extractor ─────────────────────────────────────────────────────


def _make_llm():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not set; cannot extract from PDF"
        )
    return ChatVertexAI(
        model=MODEL_NAME,
        project=project,
        location=location,
    ).with_structured_output(_ExtractedStatement)


def _override_category(description: str, llm_category: str) -> tuple[str, str, str]:
    """Apply canonicalizer + curated category override.

    Returns (merchant_display, merchant_canonical_key, final_category).
    """
    canonical = canonicalize(description)
    override = _CATEGORY_BY_CANONICAL_KEY.get(canonical.key)
    if override is not None:
        return canonical.display, canonical.key, override
    # No override: trust the LLM, falling back to other.misc if invalid.
    final = llm_category if is_valid_category(llm_category) else "other.misc"
    return canonical.display, canonical.key, final


def parse_statement_pdf(
    pdf_bytes: bytes,
    *,
    user_id: str,
    source_name: str | None,
    source_hash: str,
    llm=None,
) -> StatementParseResult:
    """Run the full extract → canonicalize → categorize → split pipeline.

    `source_hash` is precomputed (sha256 of the file bytes, first 12 chars)
    so the caller can stamp every doc with a stable source tag for
    idempotency at the dedupe layer.

    `llm` is injectable for tests; production callers pass None and get
    a real ChatVertexAI client.
    """
    if not pdf_bytes:
        return StatementParseResult([], [], "", "", None, None, ["empty file"], "")

    llm = llm or _make_llm()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    msg = HumanMessage(
        content=[
            {"type": "text", "text": _build_prompt()},
            {"type": "media", "mime_type": "application/pdf", "data": pdf_b64},
        ]
    )

    try:
        extracted: _ExtractedStatement = llm.invoke([msg])
    except ValidationError as exc:
        logger.exception("LLM returned malformed structured output")
        return StatementParseResult(
            [],
            [],
            "",
            "",
            None,
            None,
            [f"extraction failed: {type(exc).__name__}: {str(exc)[:200]}"],
            source_hash,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini extraction call failed")
        return StatementParseResult(
            [],
            [],
            "",
            "",
            None,
            None,
            [f"extraction failed: {type(exc).__name__}: {str(exc)[:200]}"],
            source_hash,
        )

    source = _build_source(source_name, source_hash)

    documents: list[dict] = []
    skipped_payments: list[dict] = []
    warnings: list[str] = []
    invalid_category_count = 0

    for row in extracted.transactions:
        display, canonical_key, final_category = _override_category(
            row.description, row.category
        )

        # Negative amounts = payments to card / refunds, not user spend.
        # Split them out so spend analysis stays clean.
        if row.amount < 0:
            skipped_payments.append(
                {
                    "date": _at_midnight(row.txn_date),
                    "merchant": row.description,
                    "merchant_canonical": canonical_key,
                    "amount": float(row.amount),
                    "currency": (row.currency or "CAD").upper(),
                    "reason": "payment_or_credit",
                }
            )
            continue

        if not is_valid_category(row.category) and final_category == "other.misc":
            invalid_category_count += 1

        documents.append(
            {
                "user_id": user_id,
                "date": _at_midnight(row.txn_date),
                "merchant": display,
                "merchant_canonical": canonical_key,
                "category": final_category,
                # IMPORTANT: store SPEND as NEGATIVE per the convention used
                # everywhere else in this codebase. The seeded synthetic
                # transactions have negative amounts for spend; aggregations
                # filter t.amount < 0. We accept the LLM's positive charge
                # convention (more natural to read) then flip on the way in.
                "amount": -float(row.amount),
                "currency": (row.currency or "CAD").upper(),
                "source": source,
                "raw": {
                    "description": row.description,
                    "llm_category": row.category,
                    "issuer": extracted.issuer,
                    "account_last4": extracted.account_last4,
                },
            }
        )

    if invalid_category_count:
        warnings.append(
            f"{invalid_category_count} transactions fell through to other.misc"
            " (LLM returned non-vocab category and no canonicalizer override)"
        )

    return StatementParseResult(
        documents=documents,
        skipped_payments=skipped_payments,
        issuer=extracted.issuer,
        account_last4=extracted.account_last4,
        period_start=extracted.period_start,
        period_end=extracted.period_end,
        warnings=warnings,
        source=source,
    )


# ─── Helpers ───────────────────────────────────────────────────────


def _at_midnight(d: DateType) -> datetime:
    """Match the rest of the codebase's date persistence convention."""
    return datetime(d.year, d.month, d.day)


def _build_source(source_name: str | None, source_hash: str) -> str:
    """Stable source tag for every doc — same hash, same source, every time.
    Used by the dedupe layer to detect re-uploads."""
    slug = "statement"
    if source_name:
        import re

        slug = re.sub(r"[^a-zA-Z0-9]+", "_", source_name.lower()).strip("_") or "statement"
    return f"statement_{slug}_{source_hash}"
