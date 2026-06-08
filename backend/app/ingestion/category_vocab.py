"""Category vocabulary used across the app.

The agent's `summarize_week`, `get_spend_anomaly`, `query_transactions`,
and `set_budget` tools all read transactions.category — this module is
the single source of truth for what category values are legal. New
strings ANYWHERE in this codebase must come from this list.

Format: "top_level.sub" — top-level is the bucket the dashboard +
BudgetProgress widget aggregate on (collapses via the .split('.')[0]
trick in frontend/lib/analytics.ts). Sub categorizes for richer agent
reasoning ("food.coffee spike" reads better than "food spike").
"""

from __future__ import annotations

from typing import Final


# Canonical list. Add new categories here AND in CATEGORY_HINTS below.
CATEGORIES: Final[tuple[str, ...]] = (
    # Food
    "food.coffee",
    "food.fast",
    "food.dining",
    "food.delivery",
    "food.groceries",
    # Transport
    "transport.gas",
    "transport.parking",
    "transport.rideshare",
    "transport.transit",
    "transport.tolls",
    # Shopping
    "shopping.amazon",
    "shopping.clothing",
    "shopping.electronics",
    "shopping.home",
    "shopping.general",
    # Subscriptions / digital
    "subscriptions.media",
    "subscriptions.software",
    "subscriptions.gym",
    "subscriptions.other",
    # Housing
    "housing.rent",
    "housing.utilities",
    "housing.internet",
    "housing.phone",
    # Health
    "health.pharmacy",
    "health.fitness",
    "health.medical",
    # Pets
    "pets.food",
    "pets.vet",
    "pets.general",
    # Services
    "services.business",
    "services.government",
    "services.professional",
    # Travel
    "travel.flights",
    "travel.hotels",
    "travel.activities",
    # Entertainment
    "entertainment.streaming",
    "entertainment.events",
    # Money
    "money.fees",
    "money.interest",
    # Income
    "income.salary",
    "income.refund",
    "income.other",
    # Catch-all
    "other.misc",
)


# Hints the LLM sees in the categorization prompt. Each line is a
# one-line nudge for what kinds of merchants land in each bucket.
# Hand-tuned against the 4 real Amex statements so the agent doesn't
# have to guess what 'food.fast' vs 'food.dining' means.
CATEGORY_HINTS: Final[dict[str, str]] = {
    "food.coffee": "Coffee shops, cafés — Tim Hortons, Starbucks, Second Cup",
    "food.fast": "Fast food + casual dining — McDonald's, Chipotle, Pita Land, Habibz, Wild Wing, Chuck's",
    "food.dining": "Sit-down restaurants — sushi, steakhouses, State & Main, mid-tier bistros",
    "food.delivery": "Food delivery — DoorDash, Uber Eats, Skip The Dishes, Grubhub",
    "food.groceries": "Supermarkets — Longo's, Metro, Loblaws, Whole Foods, Costco (food)",
    "transport.gas": "Gas stations — Esso, Shell, Petro-Canada, Chevron",
    "transport.parking": "Parking — Honk, Toronto Parking, Impark, paid lots",
    "transport.rideshare": "Uber, Lyft, taxis",
    "transport.transit": "Public transit — TTC, GO, subway/bus passes",
    "transport.tolls": "407 ETR, bridge tolls",
    "shopping.amazon": "Amazon (any AMZN MKTP, Amazon.ca/.com)",
    "shopping.clothing": "Apparel — Zara, H&M, Lululemon",
    "shopping.electronics": "Best Buy, Apple Store hardware (NOT Apple subscriptions)",
    "shopping.home": "HomeSense, Winners, IKEA, Home Depot, home goods",
    "shopping.general": "Misc retail / department stores not in another bucket",
    "subscriptions.media": "Spotify, Netflix, YouTube Premium, Apple Music",
    "subscriptions.software": "Claude.ai, ChatGPT, Canva, Adobe, GitHub, software SaaS",
    "subscriptions.gym": "Recurring gym membership debits — Movati monthly, GoodLife monthly",
    "subscriptions.other": "Other monthly recurring subscriptions",
    "housing.rent": "Rent payments",
    "housing.utilities": "Hydro, gas, water bills",
    "housing.internet": "Rogers, Bell, Telus internet",
    "housing.phone": "Cell phone plans",
    "health.pharmacy": "Shoppers Drug Mart, Rexall, prescriptions",
    "health.fitness": "One-off gym, fitness classes, sportswear (NOT subscriptions)",
    "health.medical": "Doctor, dentist, clinic copays",
    "pets.food": "Pet food and treats",
    "pets.vet": "Vet visits",
    "pets.general": "Pet stores — Pet Valu, PetSmart (general purchases)",
    "services.business": "Business filings, incorporation, MyCreds, NUANS, Corporations Canada",
    "services.government": "Government fees, ServiceOntario",
    "services.professional": "Lawyer, accountant, consultant fees",
    "travel.flights": "Airlines",
    "travel.hotels": "Hotels, Airbnb",
    "travel.activities": "Tours, attractions, foreign-currency travel charges (Railway SF, etc.)",
    "entertainment.streaming": "Movie/TV streaming bundles separate from media subs",
    "entertainment.events": "Concert tickets, sports tickets",
    "money.fees": "Card membership fees, annual fees, bank fees",
    "money.interest": "Interest charges on the card / loans",
    "income.salary": "Salary deposits",
    "income.refund": "Refunds posted as positive amounts",
    "income.other": "Other inflows",
    "other.misc": "Genuinely unclassifiable — use ONLY when nothing else fits",
}


def is_valid_category(c: str) -> bool:
    return c in CATEGORIES


def top_level(category: str) -> str:
    """Collapse 'food.delivery' → 'food'. Mirrors the frontend's
    `analytics.ts:topLevel` helper so BudgetProgress can match by
    bucket."""
    return category.split(".")[0]


def vocabulary_prompt_block() -> str:
    """Render the vocab as a markdown bullet list for the categorizer
    LLM. Kept here so the prompt and the source of truth never drift.
    """
    lines = ["Allowed categories (return ONLY one of these strings, exact match):"]
    for cat in CATEGORIES:
        hint = CATEGORY_HINTS.get(cat, "")
        lines.append(f"  - `{cat}` — {hint}")
    return "\n".join(lines)
