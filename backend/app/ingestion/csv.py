import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime


REQUIRED_COLUMNS = {"date", "merchant", "category", "amount", "currency"}


@dataclass(frozen=True)
class ParseResult:
    documents: list[dict]
    errors: list[dict]
    source: str


def canonicalize_merchant(merchant: str) -> str:
    normalized = merchant.lower().replace("'", "")
    canonical = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return canonical or "unknown"


def parse_transactions_csv(
    content: bytes,
    *,
    default_user_id: str = "u_482",
    source_date: date | None = None,
) -> ParseResult:
    source_day = source_date or datetime.now(UTC).date()
    source = f"csv_import_{source_day.isoformat()}"

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ParseResult([], [{"row": 0, "error": "CSV must be UTF-8 encoded"}], source)

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return ParseResult([], [{"row": 0, "error": "CSV is empty"}], source)

    headers = {header.strip() for header in reader.fieldnames}
    missing = sorted(REQUIRED_COLUMNS - headers)
    if missing:
        return ParseResult([], [{"row": 0, "error": f"Missing columns: {', '.join(missing)}"}], source)

    documents: list[dict] = []
    errors: list[dict] = []

    for row_number, raw_row in enumerate(reader, start=2):
        raw = {key.strip(): (value or "").strip() for key, value in raw_row.items() if key}
        try:
            merchant = raw["merchant"]
            category = raw["category"]
            currency = raw.get("currency", "USD") or "USD"

            if not merchant:
                raise ValueError("merchant is required")
            if not category:
                raise ValueError("category is required")

            transaction_date = datetime.fromisoformat(raw["date"]).replace(tzinfo=UTC)
            amount = float(raw["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append({"row": row_number, "error": str(exc), "raw": raw})
            continue

        documents.append(
            {
                "user_id": raw.get("user_id") or default_user_id,
                "date": transaction_date,
                "merchant": merchant,
                "merchant_canonical": canonicalize_merchant(merchant),
                "category": category,
                "amount": amount,
                "currency": currency.upper(),
                "source": source,
                "raw": raw,
            }
        )

    return ParseResult(documents, errors, source)
