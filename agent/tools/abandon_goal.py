"""Tool — abandon_goal (V1 follow-up).

Marks a user's goal as abandoned by flipping its status enum from
"active" → "abandoned". Status-flip instead of soft-delete because the
goals schema already has the abandoned enum value (docs/data-model.md
§ goals); no new field needed. list_goals's default status="active"
filter hides abandoned goals from the dashboard automatically.

Confidence model (mirrors forget_memory's UX but without vector search,
since goals aren't embedded):
  - Exactly one active goal whose title contains every query word
    (case-insensitive) → flip immediately + return the title so the
    agent can name it in the reply.
  - Multiple matches → return needs_confirmation=True + the candidate
    list so the agent asks "which one — Japan trip or Emergency fund?".
  - Zero matches → return found=False + a list of all active titles so
    the agent can tell the user what's actually on file.

The status flip is idempotent: the query filters on status="active" so
a second call against the same goal_id returns abandoned=False (the
goal is no longer active to flip).
"""

from datetime import UTC, datetime

from bson import ObjectId
from pydantic import BaseModel, Field

from agent.db.client import get_database


class AbandonGoalInput(BaseModel):
    user_id: str = Field(min_length=1)
    # Pass EITHER query (initial abandon request) OR goal_id (after
    # confirmation). query is fuzzy-matched against goal titles;
    # goal_id is the literal _id of a goal the agent surfaced via
    # needs_confirmation and the user just confirmed.
    query: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "What the user wants to abandon, in their words. e.g. 'the "
            "japan trip', 'that laptop goal'. Word-overlap matched against "
            "the title field. Pass this on the FIRST call; on a confirmation "
            "follow-up, pass goal_id instead."
        ),
    )
    goal_id: str | None = Field(
        default=None,
        description=(
            "Pass the goal_id returned by a previous needs_confirmation=True "
            "result when the user has just confirmed 'yes'. Skips the title "
            "match and flips the goal's status to abandoned directly. Cannot "
            "be passed together with query — pick one."
        ),
    )


class AbandonGoalCandidate(BaseModel):
    goal_id: str
    title: str


class AbandonGoalResult(BaseModel):
    user_id: str
    # True if the tool actually flipped a goal's status this call.
    abandoned: bool
    # True if multiple active goals matched the query — the agent should
    # name them and ask the user to confirm before re-calling with goal_id.
    needs_confirmation: bool
    # Populated when abandoned=True (the goal we flipped) or
    # needs_confirmation=True (the candidates the user must choose between).
    goal_id: str | None = None
    title: str | None = None
    candidates: list[AbandonGoalCandidate] = Field(default_factory=list)
    # Populated when abandoned=False AND needs_confirmation=False, so the
    # agent has something honest to say back ("you don't have any active
    # goals matching that — your active goals are: ...").
    active_goal_titles: list[str] = Field(default_factory=list)


def _title_matches(query: str, title: str) -> bool:
    """Every non-trivial word in query appears in title (case-insensitive).

    Trivial = stopwords + 1-character tokens. So "the japan trip" matches
    "Japan trip" even though the query has 'the'. Matches "japan" against
    "Japan trip". Doesn't match "japan emergency".
    """
    stopwords = {
        # Articles + common particles that never appear in goal titles.
        "the", "a", "an", "to", "for", "my", "that", "this", "it",
        "of", "in", "on", "and", "or",
        # Domain words that are not informative in the matching layer —
        # "goal" / "savings" are categories the user phrases around, not
        # the title itself.
        "goal", "savings",
        # Verbs the user uses in the trigger phrase ("forget the Japan
        # trip", "cancel my emergency fund", "drop that laptop one").
        # These are signals the AGENT routes on, not match tokens.
        "forget", "cancel", "drop", "abandon", "delete", "remove",
        "give", "up", "kill", "scrap", "nevermind", "stop",
    }
    q_words = [w for w in query.lower().split() if len(w) > 1 and w not in stopwords]
    if not q_words:
        # All-stopword query is too broad to act on; treat as no match
        # so the agent falls back to the "list active titles" branch.
        return False
    title_lower = title.lower()
    return all(w in title_lower for w in q_words)


async def abandon_goal(
    params: AbandonGoalInput,
    *,
    collection=None,
) -> AbandonGoalResult:
    """Mark one of the user's active goals as abandoned.

    Use when the user says they want to give up on, drop, cancel, or
    forget a goal — "forget the Japan trip, I changed my mind", "I gave
    up on the new laptop goal", "cancel my emergency fund goal". The
    tool flips status from active → abandoned (the goal stays in Atlas
    as an audit trail; future list_goals with status='all' or
    status='abandoned' surfaces it). Does NOT delete the goal.

    Two call shapes mirror forget_memory:
    (A) FIRST request — pass query=<user's own words>. Tool finds active
        goals whose titles match (word overlap, case-insensitive, stopwords
        ignored). Exactly one match → flip + return title. Multiple matches
        → needs_confirmation=True with the candidate list.
    (B) USER CONFIRMED a previous needs_confirmation question with
        "yes — the Japan one" → pass goal_id=<the id from that result>.
        Flips directly without re-matching.
    """
    if collection is None:
        collection = get_database().goals

    # Path B: direct goal_id (confirmation follow-up).
    if params.goal_id is not None:
        if params.query is not None:
            raise ValueError("abandon_goal: pass query OR goal_id, not both")
        try:
            oid = ObjectId(params.goal_id)
        except Exception as exc:
            raise ValueError(f"invalid goal_id: {params.goal_id}") from exc
        target = await collection.find_one(
            {"_id": oid, "user_id": params.user_id, "status": "active"},
            {"title": 1},
        )
        if target is None:
            # Already abandoned, complete, paused, or someone else's goal —
            # all of these silently no-op (the user shouldn't be told someone
            # else owns it; status mismatch reads fine as "no active match").
            return AbandonGoalResult(
                user_id=params.user_id,
                abandoned=False,
                needs_confirmation=False,
            )
        result = await collection.update_one(
            {"_id": oid, "user_id": params.user_id, "status": "active"},
            {"$set": {"status": "abandoned", "abandoned_at": datetime.now(UTC)}},
        )
        return AbandonGoalResult(
            user_id=params.user_id,
            abandoned=result.modified_count > 0,
            needs_confirmation=False,
            goal_id=params.goal_id,
            title=str(target.get("title", "")),
        )

    # Path A: query-driven (initial request).
    if params.query is None:
        raise ValueError("abandon_goal: must pass either query or goal_id")

    cursor = collection.find(
        {"user_id": params.user_id, "status": "active"},
        {"_id": 1, "title": 1},
    )
    active: list[dict] = []
    async for doc in cursor:
        active.append(doc)

    matches = [d for d in active if _title_matches(params.query, str(d.get("title", "")))]

    if len(matches) == 0:
        # No matches — return the active titles so the agent can be specific
        # in its reply ("I don't see a goal matching that. Your active goals
        # are: Japan trip, Emergency fund.").
        return AbandonGoalResult(
            user_id=params.user_id,
            abandoned=False,
            needs_confirmation=False,
            active_goal_titles=[str(d.get("title", "")) for d in active],
        )

    if len(matches) > 1:
        # Multiple matches — agent must disambiguate before re-calling
        # with a specific goal_id.
        return AbandonGoalResult(
            user_id=params.user_id,
            abandoned=False,
            needs_confirmation=True,
            candidates=[
                AbandonGoalCandidate(
                    goal_id=str(d["_id"]),
                    title=str(d.get("title", "")),
                )
                for d in matches
            ],
        )

    # Exactly one match — flip immediately.
    target = matches[0]
    target_id = target["_id"]
    target_title = str(target.get("title", ""))
    result = await collection.update_one(
        {"_id": target_id, "user_id": params.user_id, "status": "active"},
        {"$set": {"status": "abandoned", "abandoned_at": datetime.now(UTC)}},
    )
    return AbandonGoalResult(
        user_id=params.user_id,
        abandoned=result.modified_count > 0,
        needs_confirmation=False,
        goal_id=str(target_id),
        title=target_title,
    )
