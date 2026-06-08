"""Canonicalizer tests driven by REAL merchant strings from the 4 Amex PDFs
in docs/Summary*.pdf — not synthetic. Every fixture below appears verbatim
on at least one of the real statements.

If you add a new rule to merchant_canonical._RULES, add a fixture row here
proving the consolidation works. If you change a rule, re-run this suite
to catch regressions across the live sample.
"""

import pytest

from app.ingestion.merchant_canonical import Canonical, canonicalize


# Each row: (raw merchant string verbatim from a real Amex line, expected key,
# expected display).
CURATED_RULE_CASES = [
    # Coffee
    ("TIM HORTONS #4281    KING CITY", "tim_hortons", "Tim Hortons"),
    ("TIM HORTONS #2882    AURORA", "tim_hortons", "Tim Hortons"),
    ("TIM HORTONS #4126    RICHMOND HILL", "tim_hortons", "Tim Hortons"),
    ("TIM HORTONS #6990    RICHMOND HILL", "tim_hortons", "Tim Hortons"),
    ("STARBUCKS 8007827282  800-782-7282", "starbucks", "Starbucks"),
    # Fast food (the '?' substitution is real Amex export noise for the apostrophe)
    ("MCDONALD?S # 41137    KING CITY", "mcdonalds", "McDonald's"),
    ("MCDONALD?S # 5260     AURORA", "mcdonalds", "McDonald's"),
    ("MCDONALD'S #40359    NORTH YORK", "mcdonalds", "McDonald's"),
    # Local restaurants
    ("HABIBZ CORNER       Aurora", "habibz_corner", "Habibz Corner"),
    ("PITA LAND YORK UNIVER  NORTH YORK", "pita_land", "Pita Land"),
    ("SUSHI KUI 00-0804105267 AURORA", "sushi_kui", "Sushi Kui"),
    ("WILD WING OAKRIDGES   RICHMOND HILL", "wild_wing", "Wild Wing"),
    ("STACKED PANCAKE & BREAK NEW MARKET", "stacked_pancake", "Stacked Pancake"),
    ("STATE & MAIN AURORA   AURORA", "state_and_main", "State & Main"),
    ("CHUCK'S CHICKEN PLUS 00 AURORA", "chucks_chicken", "Chuck's Chicken"),
    ("FIVE STAR NORTH AMERICA CALGARY", "five_star", "Five Star"),
    # Groceries
    ("LONGO'S # 19 AURORA   AURORA", "longos", "Longo's"),
    ("METRO  767            AURORA", "metro", "Metro"),
    # Gas
    ("ESSO CIRCLE K     NEWMARKET", "esso", "Esso"),
    ("ESSO CIRCLE K     RICHMOND HILL", "esso", "Esso"),
    ("ESSO CIRCLE K     CONCORD", "esso", "Esso"),
    ("ESSO CIRCLE K     AURORA", "esso", "Esso"),
    ("SHELL C80120          KING CITY", "shell", "Shell"),
    ("SHELL C21813          RICHMOND HILL", "shell", "Shell"),
    # Parking
    ("HONK - CAN          866-675-7337", "honk_parking", "Honk Parking"),
    ("TORONTO PARKING AUTHORI TORONTO", "toronto_parking", "Toronto Parking"),
    # Pets
    ("PETVALU OAK RIDGES    RICHMOND HILL", "petvalu", "Pet Valu"),
    # Shopping
    ("HOMESENSE 017        NEWMARKET", "homesense", "HomeSense"),
    ("AMZN MKTP CA*BJ64N73I1 866-216-1072", "amazon", "Amazon"),
    ("AMZN MKTP CA*BS1XH2AF0 866-216-1072", "amazon", "Amazon"),
    # Fitness
    ("MOVATI - RICHMOND HILL RICHMOND HILL", "movati", "Movati Athletic"),
    # Subscriptions
    ("APPLE.COM/BILL        TORONTO", "apple", "Apple"),
    ("SPOTIFY              STOCKHOLM", "spotify", "Spotify"),
    ("CLAUDE.AI SUBSCRIPTION SAN FRANCISCO", "claude_ai", "Claude.ai"),
    ("CANVA* I04869-8060373 AUSTIN", "canva", "Canva"),
    # Government / business
    ("CORP CANADA/19168287  OTTAWA", "corporations_canada", "Corporations Canada"),
    ("NUANS NAME SEARCH OTTAW OTTAWA", "nuans", "NUANS"),
    ("MYCREDSMESCERTIF       CALGARY", "mycreds", "MyCreds"),
    # Card-issuer special rows
    ("MEMBERSHIP FEE INSTALLMENT", "card_fee", "Card Membership Fee"),
    ("PAYMENT RECEIVED - THANK YOU", "card_payment", "Payment Received"),
]


@pytest.mark.parametrize("raw,expected_key,expected_display", CURATED_RULE_CASES)
def test_curated_rules_match_real_amex_lines(raw, expected_key, expected_display):
    """Every fixture is a verbatim line from docs/Summary*.pdf — these
    are the merchants the demo will encounter."""
    result = canonicalize(raw)
    assert result.key == expected_key, f"{raw!r} → key {result.key!r}, want {expected_key!r}"
    assert result.display == expected_display, f"{raw!r} → display {result.display!r}, want {expected_display!r}"


def test_consolidation_same_merchant_same_key():
    """Different Tim Hortons store numbers / locations MUST collapse
    to the same canonical key so the dashboard's 'top categories'
    aggregates correctly."""
    keys = {
        canonicalize(s).key
        for s in [
            "TIM HORTONS #4281    KING CITY",
            "TIM HORTONS #2882    AURORA",
            "TIM HORTONS #4126    RICHMOND HILL",
            "TIM HORTONS #6990    RICHMOND HILL",
            "TIM HORTONS #5387    KING CITY",
        ]
    }
    assert keys == {"tim_hortons"}


def test_consolidation_amazon_marketplace_variants():
    """AMZN MKTP CA*<order_id> and other Amazon variants all roll up to amazon."""
    assert canonicalize("AMZN MKTP CA*BJ64N73I1 866-216-1072").key == "amazon"
    assert canonicalize("AMZN MKTP CA*BS1XH2AF0 866-216-1072").key == "amazon"
    assert canonicalize("AMAZON.CA   *RT4534DS3").key == "amazon"


# ─── Fallback path (no curated rule) ────────────────────────────────


def test_fallback_strips_phone_numbers():
    """Phone-number suffixes are noise from merchant processors."""
    result = canonicalize("WIDGET INC          866-555-1212")
    assert result.key == "widget_inc"
    assert "866" not in result.display


def test_fallback_strips_transaction_id_suffix():
    """*ID-style suffixes (PAYPAL *abc, SHOPIFY *xyz) shouldn't pollute the key."""
    result = canonicalize("PAYPAL *MERCHANT XYZ123")
    assert result.key == "paypal_merchant"


def test_fallback_empty_input():
    result = canonicalize("")
    assert result.key == "unknown"
    assert result.display == "Unknown"


def test_fallback_whitespace_only():
    assert canonicalize("   \t\n").key == "unknown"


def test_fallback_question_mark_apostrophe_substitution():
    """Some statement exporters use '?' where apostrophes should be —
    fallback must still produce a sensible key."""
    result = canonicalize("MARIO?S TRATTORIA  TORONTO")
    assert result.key == "marios_trattoria" or result.key == "marios"


def test_idempotent_same_input_same_output():
    """Critical contract: same input → same output, always.
    Same merchant_canonical key is how the dedupe pipeline works."""
    s = "RANDOM MERCHANT 123 SOMEWHERE"
    r1 = canonicalize(s)
    r2 = canonicalize(s)
    assert r1 == r2
    assert isinstance(r1, Canonical)
