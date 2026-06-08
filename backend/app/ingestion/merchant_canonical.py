"""Merchant string → canonical key + display name.

Pure-Python normalization. NOT an LLM call (deterministic, fast, free).
Designed against real Amex statement noise — see docs/Summary*.pdf for
the sample set the regex was tuned to.

Real-world examples handled:
  "AMZN MKTP CA*BJ64N73I1 866-216-1072"  → ("amazon", "Amazon")
  "MCDONALD?S # 41137  KING CITY"        → ("mcdonalds", "McDonald's")
  "TIM HORTONS #4126    RICHMOND HILL"   → ("tim_hortons", "Tim Hortons")
  "ESSO CIRCLE K     RICHMOND HILL"      → ("esso", "Esso")
  "STARBUCKS 8007827282  800-782-7282"   → ("starbucks", "Starbucks")
  "PAYPAL *DOORDASH"                     → ("doordash", "DoorDash")
  "CLAUDE.AI SUBSCRIPTION SAN FRANCISCO" → ("claude_ai", "Claude.ai")

Stable contract:
  - same input string ALWAYS produces same (canonical_key, display) tuple
  - canonical_key is lowercase, underscore-only, [a-z0-9_]+
  - display is title-cased human-friendly text
  - merchants we recognize get a curated canonical key (so AMZN MKTP CA*X
    and AMZN MKTP CA*Y both → 'amazon')
  - unknown merchants get a deterministic fallback (strip location +
    store number suffixes, snake_case it)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ─── Curated merchant rules ────────────────────────────────────────
#
# Each rule: (regex matched against the UPPERCASE-NORMALIZED string,
# canonical_key, display_name). Order matters — first match wins.
# Patterns hand-tuned against the 4 real Amex PDFs in docs/.
#
# Add new rows as you encounter merchants in the wild. The fallback
# normalizer below handles anything not in this list reasonably well;
# this table is for "we know this merchant by name and want to
# consolidate its variants".

_RULES: list[tuple[re.Pattern[str], str, str]] = [
    # Tech / subscriptions
    (re.compile(r"\bAMZN\b|\bAMAZON\b"), "amazon", "Amazon"),
    (re.compile(r"\bAPPLE\.?COM\b|\bAPPLE STORE\b"), "apple", "Apple"),
    (re.compile(r"\bCLAUDE\.?AI\b|\bANTHROPIC\b"), "claude_ai", "Claude.ai"),
    (re.compile(r"\bOPENAI\b|\bCHATGPT\b"), "openai", "OpenAI"),
    (re.compile(r"\bSPOTIFY\b"), "spotify", "Spotify"),
    (re.compile(r"\bNETFLIX\b"), "netflix", "Netflix"),
    (re.compile(r"\bCANVA\b"), "canva", "Canva"),
    (re.compile(r"\bGOOGLE\b"), "google", "Google"),
    (re.compile(r"\bMICROSOFT\b|\bMSFT\b"), "microsoft", "Microsoft"),
    (re.compile(r"\bADOBE\b"), "adobe", "Adobe"),
    # Coffee
    (re.compile(r"\bTIM HORTONS\b|\bTIMHORTONS\b"), "tim_hortons", "Tim Hortons"),
    (re.compile(r"\bSTARBUCKS\b"), "starbucks", "Starbucks"),
    # Fast food
    (re.compile(r"\bMCDONALD"), "mcdonalds", "McDonald's"),
    (re.compile(r"\bSUBWAY\b"), "subway", "Subway"),
    (re.compile(r"\bBURGER KING\b"), "burger_king", "Burger King"),
    (re.compile(r"\bWENDY"), "wendys", "Wendy's"),
    (re.compile(r"\bKFC\b"), "kfc", "KFC"),
    (re.compile(r"\bPIZZA HUT\b"), "pizza_hut", "Pizza Hut"),
    (re.compile(r"\bDOMINO"), "dominos", "Domino's"),
    (re.compile(r"\bCHIPOTLE\b"), "chipotle", "Chipotle"),
    # Delivery
    (re.compile(r"\bDOORDASH\b"), "doordash", "DoorDash"),
    (re.compile(r"\bUBER\s?EATS\b"), "uber_eats", "Uber Eats"),
    (re.compile(r"\bSKIP\s?(THE\s?)?DISHES\b"), "skip_the_dishes", "Skip The Dishes"),
    (re.compile(r"\bGRUBHUB\b"), "grubhub", "Grubhub"),
    # Rideshare
    (re.compile(r"\bUBER\b(?!\s?EATS)"), "uber", "Uber"),
    (re.compile(r"\bLYFT\b"), "lyft", "Lyft"),
    # Gas
    (re.compile(r"\bESSO\b"), "esso", "Esso"),
    (re.compile(r"\bSHELL\b"), "shell", "Shell"),
    (re.compile(r"\bPETRO[\- ]?CANADA\b|\bPETROCAN\b"), "petro_canada", "Petro-Canada"),
    (re.compile(r"\bCHEVRON\b"), "chevron", "Chevron"),
    (re.compile(r"\b(EXXON|MOBIL)\b"), "exxon_mobil", "Exxon/Mobil"),
    # Parking
    (re.compile(r"\bHONK\b"), "honk_parking", "Honk Parking"),
    (re.compile(r"\bTORONTO PARKING\b|\bGREEN ?P\b"), "toronto_parking", "Toronto Parking"),
    (re.compile(r"\bIMPARK\b"), "impark", "Impark"),
    # Groceries (Canadian + US)
    (re.compile(r"\bLONGO"), "longos", "Longo's"),
    (re.compile(r"\bMETRO\s*\d"), "metro", "Metro"),
    (re.compile(r"\bLOBLAWS?\b"), "loblaws", "Loblaws"),
    (re.compile(r"\bSOBEYS\b"), "sobeys", "Sobeys"),
    (re.compile(r"\bWALMART\b"), "walmart", "Walmart"),
    (re.compile(r"\bCOSTCO\b"), "costco", "Costco"),
    (re.compile(r"\bWHOLE FOODS\b"), "whole_foods", "Whole Foods"),
    (re.compile(r"\bTRADER JOE"), "trader_joes", "Trader Joe's"),
    (re.compile(r"\bSAFEWAY\b"), "safeway", "Safeway"),
    # Pets
    (re.compile(r"\bPETVALU\b|\bPET VALU\b"), "petvalu", "Pet Valu"),
    (re.compile(r"\bPETSMART\b"), "petsmart", "PetSmart"),
    # Home / shopping
    (re.compile(r"\bHOMESENSE\b"), "homesense", "HomeSense"),
    (re.compile(r"\bWINNERS\b"), "winners", "Winners"),
    (re.compile(r"\bIKEA\b"), "ikea", "IKEA"),
    (re.compile(r"\bHOME DEPOT\b"), "home_depot", "Home Depot"),
    # Fitness
    (re.compile(r"\bMOVATI\b"), "movati", "Movati Athletic"),
    (re.compile(r"\bGOODLIFE\b"), "goodlife", "GoodLife Fitness"),
    (re.compile(r"\bPLANET FITNESS\b"), "planet_fitness", "Planet Fitness"),
    # Local restaurants seen in the sample Amex PDFs
    (re.compile(r"\bHABIBZ\b"), "habibz_corner", "Habibz Corner"),
    (re.compile(r"\bPITA LAND\b"), "pita_land", "Pita Land"),
    (re.compile(r"\bSUSHI KUI\b"), "sushi_kui", "Sushi Kui"),
    (re.compile(r"\bWILD WING\b"), "wild_wing", "Wild Wing"),
    (re.compile(r"\bSTACKED PANCAKE\b"), "stacked_pancake", "Stacked Pancake"),
    (re.compile(r"\bSTATE\s?&\s?MAIN\b"), "state_and_main", "State & Main"),
    (re.compile(r"\bCHUCK"), "chucks_chicken", "Chuck's Chicken"),
    (re.compile(r"\bFIVE STAR\b"), "five_star", "Five Star"),
    # Government / business
    (re.compile(r"\bCORP\s+CANADA\b"), "corporations_canada", "Corporations Canada"),
    (re.compile(r"\bNUANS\b"), "nuans", "NUANS"),
    (re.compile(r"\bMYCRED"), "mycreds", "MyCreds"),
    (re.compile(r"\bSERVICE ONTARIO\b"), "service_ontario", "ServiceOntario"),
    # Misc card-issuer
    (re.compile(r"\bMEMBERSHIP FEE\b"), "card_fee", "Card Membership Fee"),
    (re.compile(r"\bANNUAL FEE\b"), "annual_fee", "Annual Fee"),
    (re.compile(r"\bINTEREST\b"), "interest_charge", "Interest Charge"),
    # Payment to the card itself (excluded from spending — see ingest pipeline)
    (re.compile(r"\bPAYMENT RECEIVED\b|\bAUTOPAY\b|\bAUTO PAY\b"), "card_payment", "Payment Received"),
]


# Phone numbers (1-800, 800-NNN-NNNN, +1-NNN-...) often appear as
# transaction-line noise from merchant processors. Strip them before the
# fallback path so "STARBUCKS 8007827282 800-782-7282" → "starbucks".
_PHONE_RE = re.compile(r"(?:\+?\d[\s\-]?){7,}")

# Store / transaction IDs that follow the merchant name and pollute
# canonicalization — '*BJ64N73I1', '#41137', 'I04869-8060373', etc.
# Three patterns, all token-id flavored:
#  1. '*'/'#' followed by a token that contains a digit  (* and # only
#     prefix transaction/store ids in this domain; *MERCHANT-pure-letters
#     is a real merchant prefix on some processors like PAYPAL *MERCHANT,
#     so we leave purely-alphabetic stars/hashes alone.)
#  2. Bare token of ≥6 chars mixing letters AND digits ('I04869', 'BJ64N73I1')
#  3. Pure-numeric tokens of ≥4 digits ('41137', '4126')
_NOISE_RE = re.compile(
    r"[*#]\S*\d\S*"                                 # '*BJ64N73I1', '#41137'
    r"|\b(?=\w*\d)(?=\w*[A-Z])[A-Z0-9]{6,}\b"       # mixed alpha+digit ≥6
    r"|\b\d{4,}\b"                                   # pure-numeric ≥4
)

# City / location words tacked onto the end. The sample data has
# 'AURORA', 'RICHMOND HILL', 'CALGARY', 'TORONTO', etc. We don't have
# the full Canadian geography list so we use a simpler heuristic:
# drop ALL-CAPS trailing tokens AFTER we've stripped phone/noise, as
# long as ≥2 alphabetic merchant tokens remain.


@dataclass(frozen=True)
class Canonical:
    key: str          # snake_case, [a-z0-9_]+
    display: str      # human-readable


def canonicalize(merchant: str) -> Canonical:
    """Normalize a raw transaction-line merchant string.

    See module docstring for examples.
    """
    if not merchant or not merchant.strip():
        return Canonical("unknown", "Unknown")

    # Uppercase for rule matching; strip the '?' that some statement
    # exporters substitute for apostrophes ("MCDONALD?S").
    upper = re.sub(r"\s+", " ", merchant.upper().replace("?", ""))

    for pattern, key, display in _RULES:
        if pattern.search(upper):
            return Canonical(key, display)

    # Fallback: clean the string and snake_case the first 1–3 tokens.
    # Phone first (it contains digit runs the noise rule would chew on),
    # then noise (transaction ids, store numbers, etc.).
    cleaned = _PHONE_RE.sub(" ", upper)
    cleaned = _NOISE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return Canonical("unknown", "Unknown")

    tokens = cleaned.split()
    # Keep first 3 tokens, drop trailing single-letter or digit tokens.
    head = [t for t in tokens[:4] if not (len(t) == 1 and t.isalpha())]
    if not head:
        head = tokens[:1]
    # The display: title-cased, max 3 tokens
    display_tokens = head[:3]
    display = " ".join(t.title() for t in display_tokens)
    # The key: snake_case, first 2 tokens, [a-z0-9_]+ only
    raw_key = "_".join(head[:2]).lower()
    key = re.sub(r"[^a-z0-9]+", "_", raw_key).strip("_") or "unknown"
    return Canonical(key, display)
