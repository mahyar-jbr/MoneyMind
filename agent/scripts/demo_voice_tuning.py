"""#25 voice-tuning verifier — runs the 4 scripted turns from the ticket
against the LIVE production agent service (Railway) and prints transcripts +
a verdict per turn.

Two modes:

  1. AGAINST PROD (default) — calls the deployed agent's /chat directly with
     the loopback-style X-MoneyMind-User-Id header (#4a contract). This is
     how the backend talks to the agent on Railway, so it's the closest
     thing to "what the live chat does" without going through Vercel/Clerk.

  2. AGAINST LOCAL — if AGENT_URL points at a local boot, hits that instead.

Run from agent/:

    PYTHONPATH=.. uv run python -m agent.scripts.demo_voice_tuning [user_id]

Optional positional arg is the user_id to test as. Defaults to u_482 (the
seeded synthetic user from sprint 1). Gemini quota cost: 4-5 calls on the
happy path, capped by EARLY_EXIT_ON_RATE_LIMIT below.
"""

import asyncio
import os
import sys
from datetime import UTC, datetime

import httpx


PROD_AGENT_URL = "https://moneymind-production-2a7e.up.railway.app"
DEFAULT_USER_ID = "u_482"
EARLY_EXIT_ON_RATE_LIMIT = True
TIMEOUT_S = 90.0


TURNS: list[tuple[str, str, list[str]]] = [
    # (label, user message, expected substrings — match ANY one to pass)
    (
        "TURN 1 — empty-week fallback (#25p target a)",
        "How's my food spend this week?",
        # Pass if the reply names a real food category and a real dollar
        # figure OR explicitly says "last week" / "no spend this calendar
        # week" (the fallback we taught).
        ["food.delivery", "food delivery", "DoorDash", "doordash",
         "last week", "no spend", "calendar week", "$"],
    ),
    (
        "TURN 2 — slide-8 proposal chain",
        "Busy week at work — no time to meal prep.",
        # Pass if the reply acknowledges the cause AND mentions a Sunday
        # reminder / meal-prep proposal in some form. We verify the
        # update_user_context + propose_intervention calls separately via
        # the inbox check downstream.
        ["sunday", "meal prep", "remind", "reminder", "want me", "set up"],
    ),
    (
        "TURN 3 — same Q again, active context should land",
        "How's my food spend this week?",
        # Pass if the reply references the busy-week context the agent
        # just stored (a "busy work week" / "given the busy week" / "makes
        # sense" / "tracking with what you mentioned" style line).
        ["busy", "work week", "given", "makes sense", "you mentioned",
         "tracking with", "no time"],
    ),
    (
        "TURN 4 — bulking lifestyle, high spend should NOT flag",
        "I'm bulking this month — food spend will be high.",
        # Pass if the reply acknowledges the bulk AND does NOT use
        # anomaly-flagging language. We check the FAIL set below.
        ["bulk", "on-pattern", "on pattern", "noted", "tracking", "got it"],
    ),
]

# Words/phrases that should NEVER appear in TURN 4's reply (we don't want
# to flag the bulk-driven food spend as anomalous).
TURN_4_FAIL_PHRASES = [
    "concerning",
    "too high",
    "above baseline",
    "unusually high",
    "anomaly",
    "spike",
    "cut back",
    "want to lower",
]


async def _send(http: httpx.AsyncClient, base_url: str, user_id: str, message: str) -> str:
    """Send a single chat turn to the agent and concatenate the streamed text."""
    response = await http.post(
        f"{base_url}/chat",
        headers={"X-MoneyMind-User-Id": user_id, "content-type": "application/json"},
        json={"message": message},
        timeout=TIMEOUT_S,
    )
    response.raise_for_status()
    return response.text


def _matches_any(reply: str, needles: list[str]) -> str | None:
    lower = reply.lower()
    for n in needles:
        if n.lower() in lower:
            return n
    return None


def _contains_any(reply: str, fail_phrases: list[str]) -> str | None:
    lower = reply.lower()
    for f in fail_phrases:
        if f.lower() in lower:
            return f
    return None


def _verdict(turn_idx: int, label: str, reply: str, pass_needles: list[str]) -> bool:
    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")
    print(f"REPLY:\n{reply}\n")

    matched = _matches_any(reply, pass_needles)
    if turn_idx == 3:  # TURN 4 — also check FAIL set
        bad = _contains_any(reply, TURN_4_FAIL_PHRASES)
        if bad:
            print(f"VERDICT: ❌ FAIL — anomaly language present: {bad!r}")
            return False
    if matched is None:
        print(f"VERDICT: ❌ FAIL — none of {pass_needles!r} present")
        return False
    print(f"VERDICT: ✅ PASS — matched on {matched!r}")
    return True


async def main(user_id: str) -> int:
    base_url = os.getenv("AGENT_URL", PROD_AGENT_URL).rstrip("/")
    print(f"#25 voice-tuning verifier  ·  agent: {base_url}  ·  user: {user_id}")
    print(f"started: {datetime.now(UTC).isoformat(timespec='seconds')}")

    results: list[bool] = []
    async with httpx.AsyncClient() as http:
        for idx, (label, message, needles) in enumerate(TURNS):
            print(f"\n>>> sending: {message!r}", flush=True)
            try:
                reply = await _send(http, base_url, user_id, message)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429 and EARLY_EXIT_ON_RATE_LIMIT:
                    print(f"\n⚠️  429 quota — stopping early at turn {idx + 1}.")
                    break
                print(f"\n❌ HTTP {status}: {exc.response.text[:300]}")
                results.append(False)
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"\n❌ transport error: {type(exc).__name__}: {exc}")
                results.append(False)
                continue
            results.append(_verdict(idx, label, reply, needles))

    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    for idx, (label, _, _) in enumerate(TURNS[: len(results)]):
        flag = "✅" if results[idx] else "❌"
        print(f"  {flag} {label}")
    passed = sum(1 for r in results if r)
    print(f"\n  {passed}/{len(results)} turns passed")
    return 0 if passed == len(TURNS) else 1


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_USER_ID
    raise SystemExit(asyncio.run(main(uid)))
