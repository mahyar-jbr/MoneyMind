"""Main agent graph — ReAct loop over Sprint 2 tools.

Built on langgraph.prebuilt.create_react_agent. The graph state carries
`user_id` alongside the message list; each tool wrapper pulls `user_id`
from state via `InjectedState` so the LLM never sees it (and can't
forge it). LLM-facing args_schemas are derived from each tool's
production input model with `user_id` stripped.

Public API (kept stable for serve.py + existing tests):
    MODEL_NAME
    ChatState
    build_graph()
    run_chat(user_id, message) -> str
    stream_chat(user_id, message) -> Iterator[str]
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Any, NotRequired

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_google_vertexai.chat_models import ChatVertexAI
from langgraph.prebuilt import InjectedState, create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from pydantic import BaseModel, create_model

from agent.graphs.context import fetch_active_context, format_active_context
from agent.mcp_integration.client import get_mcp_tools
from agent.prompts.system import SYSTEM_PROMPT
from agent.tools.check_goal_pace import CheckGoalPaceInput, check_goal_pace
from agent.tools.get_spend_anomaly import GetSpendAnomalyInput, get_spend_anomaly
from agent.tools.log_outcome import LogOutcomeInput, log_outcome
from agent.tools.propose_intervention import (
    ProposeInterventionInput,
    propose_intervention,
)
from agent.tools.abandon_goal import AbandonGoalInput, abandon_goal
from agent.tools.forget_memory import ForgetMemoryInput, forget_memory
from agent.tools.list_goals import ListGoalsInput, list_goals
from agent.tools.query_transactions import QueryTransactionsInput, query_transactions
from agent.tools.recall_memory import RecallMemoryInput, recall_memory
from agent.tools.respond_to_intervention import (
    RespondToInterventionInput,
    respond_to_intervention,
)
from agent.tools.schedule_reminder import (
    ScheduleReminderInput,
    schedule_reminder,
)
from agent.tools.summarize_week import SummarizeWeekInput, summarize_week
from agent.tools.update_user_context import (
    UpdateUserContextInput,
    update_user_context,
)
from agent.tools.write_goal import WriteGoalInput, write_goal
from agent.tools.write_memory import WriteMemoryInput, write_memory


MODEL_NAME = "gemini-2.5-flash"


class ChatState(AgentState):
    """Graph state. Inherits `messages` + `remaining_steps` from AgentState.

    Adds `user_id` (injected into tool wrappers via InjectedState) and
    `active_context_block` (a pre-formatted string the prompt builder
    concatenates with SYSTEM_PROMPT). active_context_block is computed
    by `run_chat` / `stream_chat` BEFORE entering the graph — doing the
    async fetch inside the graph's sync prompt builder caused motor's
    cursor to attach to the wrong event loop.
    """

    user_id: NotRequired[str]
    active_context_block: NotRequired[str]


# ─── Tool descriptions (verbatim from the ticket — these are the prose the LLM reads) ──


_DESCRIPTIONS = {
    "query_transactions": (
        "Look up the user's actual transaction rows. Use when the user asks "
        "about specific merchants, individual purchases, or you need to drill "
        "into a date range. NOT for totals or trends — use summarize_week or "
        "get_spend_anomaly for those."
    ),
    "get_spend_anomaly": (
        "Check whether the user's spend in a category over the last "
        "window_days is unusually high vs. their recent baseline. Call this "
        "when the user mentions a category, when you suspect a spike, or "
        "before proposing an intervention. Returns z_score + is_anomaly + "
        "a one-line note you can paraphrase."
    ),
    "recall_memory": (
        "Search the user's behavioral memory for anything semantically "
        "similar to a query. Call this BEFORE flagging an anomaly to check "
        "whether the pattern is already known. Top results return ranked by "
        "cosine similarity; min_score filters low-quality matches."
    ),
    "write_memory": (
        "REQUIRED whenever the user reveals anything about themselves — a cause "
        "for spending ('busy week', 'I'm bulking'), a lifestyle/event/preference, "
        "a reaction to a nudge ('yes set the reminder'), a notable one-off. "
        "Call this every turn that has a behavioral signal; do NOT make it "
        "conditional on recall_memory returning anything. Four types: 'reaction' "
        "for a single observed event (the default — use this most of the time, "
        "confidence≈0.4), 'pattern' for a recurring behavior across 2+ events "
        "(confidence≈0.7), 'preference' for a stated like/dislike (confidence≈0.9), "
        "'fact' for a stable truth like rent or income (confidence≈0.9). Summary "
        "is vector-searched — write ONE concrete sentence describing the behavior "
        "in the user's own framing if possible. If a relevant memory came back "
        "from recall_memory and matches what the user said, still write — use "
        "type='pattern' and include both the prior date and today in evidence."
    ),
    "update_user_context": (
        "Save something the user just told the agent about themselves: a "
        "lifestyle ('I'm bulking'), event ('exam week'), preference, or "
        "constraint. Insert-only — never used to correct prior context. Set "
        "active_from/active_until if the user gave a time range."
    ),
    "forget_memory": (
        "REQUIRED whenever the user asks the agent to forget, delete, or "
        "drop something it remembers — 'forget what I said about X', "
        "'you were wrong about Y', 'delete that'. Two call patterns: "
        "(A) FIRST forget request: pass query=<user's own words>. Tool "
        "vector-searches and either soft-deletes the top match (returns "
        "deleted=True + summary) OR returns needs_confirmation=True with "
        "summary if the score is below the high-confidence threshold. "
        "(B) USER CONFIRMED a previous needs_confirmation question with "
        "'yes' / 'yeah' / 'that's the one': pass query=<the exact summary "
        "text you quoted to the user in your previous question>. That "
        "exact string scores ~0.88 against itself in vector search, well "
        "above the 0.75 threshold, so the tool will delete cleanly. DO "
        "NOT pass memory_id (the id from the previous result is not in "
        "your context — passing one would be hallucinated). DO NOT pass "
        "the user's 'yes' as the query. Pass the SUMMARY text only. "
        "Three result shapes: (1) deleted=True — tell the user what you "
        "just forgot. (2) needs_confirmation=True — quote the summary "
        "and ask 'is this the one?'. (3) deleted=False, memory_id=None "
        "— tell the user nothing matched."
    ),
    "check_goal_pace": (
        "Return a pace verdict for a single goal — ahead / on_track / "
        "behind / past_due / not_started / paused / abandoned / complete. "
        "Use when the user asks about a specific goal, when proposing an "
        "intervention that depends on goal progress, or as part of a "
        "weekly summary. Returns a structured verdict + a one-line note "
        "you can paraphrase. Pass the goal_id as a string — get it from "
        "list_goals."
    ),
    "list_goals": (
        "List the user's savings goals so you can discover goal_ids to "
        "feed into check_goal_pace. REQUIRED before check_goal_pace any "
        "time the user asks about goals in general ('how am I doing?', "
        "'what are my goals?', 'am I on track?') — without it, you have "
        "no goal_id to act on. Defaults to active goals only; pass "
        "status='all' if the user explicitly asks about paused / "
        "completed / abandoned goals. Returns one row per goal with "
        "title + target + current + target_date — use this to write a "
        "compact reply ('You're 64% to your Emergency fund, on track for "
        "March 2027') without calling check_goal_pace if the user just "
        "wants the rough picture."
    ),
    "write_goal": (
        "Persist a new savings goal the user just stated. Use when the "
        "user says they want to save for something concrete: 'I want to "
        "save $5000 for a Japan trip by December', 'I'm trying to build "
        "a $10k emergency fund by end of year', 'Help me save $2000 for "
        "a laptop in 6 months'. Resolve relative dates ('by December', "
        "'in 6 months', 'end of year') to a concrete YYYY-MM-DD BEFORE "
        "calling — the tool will not parse natural-language dates. If "
        "the user gives no current_amount, default to 0. Returns the "
        "goal_id; you can pass it to check_goal_pace in the same turn "
        "or list it back to the user in your reply."
    ),
    "abandon_goal": (
        "Mark one of the user's active goals as abandoned. Use when the "
        "user wants to give up on / drop / cancel / forget a goal: "
        "'forget the Japan trip', 'I gave up on the laptop goal', "
        "'cancel my emergency fund'. Status flip (active → abandoned), "
        "NOT a delete — the goal stays in Atlas as an audit trail and "
        "list_goals's default status='active' filter hides it from the "
        "dashboard. Two call patterns mirror forget_memory: "
        "(A) FIRST request: pass query=<user's own words>. Tool "
        "title-matches against the user's active goals (stopwords like "
        "'the' / 'my' / 'goal' ignored). Exactly one match → flips and "
        "returns the title. Multiple matches → needs_confirmation=True "
        "with a candidate list; ask 'which one — Japan trip or "
        "Emergency fund?' before re-calling. Zero matches → returns "
        "active_goal_titles so you can tell the user what's actually "
        "on file. "
        "(B) USER CONFIRMED a previous needs_confirmation question: "
        "pass goal_id=<the id from the candidates list>. Flips directly. "
        "Three result shapes: (1) abandoned=True — name the title in "
        "your reply ('Got it — Japan trip is off the list.'). "
        "(2) needs_confirmation=True — quote the candidates and ask. "
        "(3) abandoned=False, needs_confirmation=False — surface "
        "active_goal_titles in your reply."
    ),
    "propose_intervention": (
        "Propose an intervention the user can accept, decline, or modify: "
        "cap (limit spending in a category), reminder (Sunday meal-prep "
        "nudge), swap_suggestion (DoorDash → groceries), or reflection (a "
        "prompt). Writes a PENDING doc; the user's chat reply (or the UI) "
        "handles the response separately. ALWAYS carry triggered_by so "
        "the next reader knows why this fired. If anchored in a recalled "
        "memory, set related_memory_id. Do NOT call write_memory in the "
        "same turn — that fires on the response, not the proposal."
    ),
    "respond_to_intervention": (
        "Record the user's response to a pending intervention. Call this "
        "when the user replies in chat to a proposal — 'yes' / 'no' / "
        "'sure but make it Saturday' all map here. Flips the intervention "
        "from PENDING to RESPONDED (or IGNORED). For 'modified' responses, "
        "resolve the user's tweak into a new params dict and pass it via "
        "modified_params. Call this BEFORE write_memory — the memory write "
        "fires on the response, not the proposal."
    ),
    "log_outcome": (
        "Log the measured outcome of a past intervention — the 'did it "
        "work?' record. Pass before/after for a metric over window_days; "
        "the tool computes delta_pct itself. agent_judgment is YOUR "
        "interpretation (successful | partial | failed | inconclusive), "
        "not the user's. Use only after observing real post-intervention "
        "behavior; do NOT call this twice for the same intervention."
    ),
    "schedule_reminder": (
        "Schedule a one-off reminder to fire at a specific UTC instant. "
        "Use when the user explicitly asks ('remind me to cancel the gym "
        "trial in 7 days') OR when you want to self-schedule a follow-up. "
        "Distinct from propose_intervention: no approval, no outcome, "
        "fires once. Pass fires_at as an absolute UTC datetime — resolve "
        "'in N days' phrasing to a real instant at call time."
    ),
    "summarize_week": (
        "Produce a weekly spending digest for a user — structured spend "
        "breakdown + active-goal snapshots + a ready-to-post paragraph. "
        "Use for 'how am I doing this week?' style questions, for weekly "
        "check-ins, or before proposing an intervention that depends on "
        "recent context. ISO Monday-Sunday weeks; week_offset=0 is the "
        "current week, -1 is last week."
    ),
}


def _llm_facing_schema(model_cls: type[BaseModel]) -> type[BaseModel]:
    """Build a Pydantic schema mirror that omits `user_id`.

    The LLM sees this schema and cannot pass `user_id` itself. The wrapper
    re-adds it from graph state before calling the underlying tool.
    """
    fields: dict[str, Any] = {}
    for name, info in model_cls.model_fields.items():
        if name == "user_id":
            continue
        fields[name] = (info.annotation, info)
    return create_model(  # type: ignore[call-overload]
        f"{model_cls.__name__}LLMFacing",
        __base__=BaseModel,
        **fields,
    )


def _wrap_tool(
    tool_coro,
    *,
    name: str,
    input_model: type[BaseModel],
):
    """Build a StructuredTool that:
      - exposes an args_schema WITHOUT user_id (LLM can't pass it)
      - injects user_id from graph state via InjectedState
      - builds the production input model, calls the underlying coroutine
    """
    llm_schema = _llm_facing_schema(input_model)

    async def runner(
        state: Annotated[dict, InjectedState],
        **llm_args: Any,
    ) -> str:
        user_id = state.get("user_id")
        if not user_id:
            raise RuntimeError(f"{name}: user_id missing from graph state")
        params = input_model(user_id=user_id, **llm_args)
        result = await tool_coro(params)
        return result.model_dump_json()

    return StructuredTool.from_function(
        coroutine=runner,
        name=name,
        description=_DESCRIPTIONS[name],
        args_schema=llm_schema,
    )


async def _build_tools() -> list[BaseTool]:
    """Build the agent's tool list: 15 native tools + MongoDB MCP tools (R1).

    MCP tools come from a Node subprocess (`npx mongodb-mcp-server`) lazily
    spawned on first call. If the subprocess fails to start, get_mcp_tools()
    returns [] and the agent still boots with the 15 native tools.
    """
    native: list[BaseTool] = [
        _wrap_tool(query_transactions, name="query_transactions", input_model=QueryTransactionsInput),
        _wrap_tool(get_spend_anomaly, name="get_spend_anomaly", input_model=GetSpendAnomalyInput),
        _wrap_tool(recall_memory, name="recall_memory", input_model=RecallMemoryInput),
        _wrap_tool(write_memory, name="write_memory", input_model=WriteMemoryInput),
        _wrap_tool(forget_memory, name="forget_memory", input_model=ForgetMemoryInput),
        _wrap_tool(update_user_context, name="update_user_context", input_model=UpdateUserContextInput),
        _wrap_tool(write_goal, name="write_goal", input_model=WriteGoalInput),
        _wrap_tool(list_goals, name="list_goals", input_model=ListGoalsInput),
        _wrap_tool(abandon_goal, name="abandon_goal", input_model=AbandonGoalInput),
        _wrap_tool(check_goal_pace, name="check_goal_pace", input_model=CheckGoalPaceInput),
        _wrap_tool(propose_intervention, name="propose_intervention", input_model=ProposeInterventionInput),
        _wrap_tool(respond_to_intervention, name="respond_to_intervention", input_model=RespondToInterventionInput),
        _wrap_tool(log_outcome, name="log_outcome", input_model=LogOutcomeInput),
        _wrap_tool(schedule_reminder, name="schedule_reminder", input_model=ScheduleReminderInput),
        _wrap_tool(summarize_week, name="summarize_week", input_model=SummarizeWeekInput),
    ]
    mcp = await get_mcp_tools()
    return [*native, *mcp]


# ─── Prompt builder (called per turn by create_react_agent) ────────────────────────


def _prompt_builder(state: dict) -> list:
    """Pure-sync prompt builder.

    Reads `active_context_block` directly from state (pre-fetched by the
    entry-point callables) and concatenates with SYSTEM_PROMPT. No async,
    no thread tricks — fully compatible with create_react_agent's sync
    prompt-builder contract.
    """
    context_block = state.get("active_context_block") or ""
    parts: list[str] = [SYSTEM_PROMPT]
    if context_block:
        parts.append(context_block)
    return [SystemMessage(content="\n\n".join(parts))] + list(state["messages"])


# ─── LLM + graph ──────────────────────────────────────────────────────────────────


def _build_llm() -> BaseChatModel:
    """Build a Vertex AI chat model.

    Auth: `GOOGLE_APPLICATION_CREDENTIALS` (path to service-account JSON) is
    the only credential needed — `ChatVertexAI` discovers it via google-auth's
    default ADC chain. `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION` pin
    the region.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set")
    return ChatVertexAI(model=MODEL_NAME, project=project, location=location)


async def build_graph(
    *,
    llm: BaseChatModel | None = None,
    context_collection=None,
):
    """Compile the agent graph. llm + context_collection are kept for
    tests that need to inject; production callers leave them None.

    Async because R1's MongoDB MCP integration lazy-spawns a Node subprocess
    on the first tool-list call (`agent.mcp_integration.client.get_mcp_tools`). Tests
    that previously called `build_graph(...)` need to switch to
    `await build_graph(...)`.

    NOTE: context_collection is not used by the graph itself anymore —
    the active-context fetch happens in run_chat / stream_chat BEFORE
    invoking the graph. The kwarg is kept so tests can pre-fetch from
    the same fake collection they pass into other tools.
    """
    # context_collection is currently unused at the graph level; it
    # remains a kwarg so callers can `build_graph(context_collection=fake)`
    # and pass the same fake to the entry-point helpers below in the same
    # test setup. Silenced for the lint pass.
    _ = context_collection
    return create_react_agent(
        model=llm or _build_llm(),
        tools=await _build_tools(),
        state_schema=ChatState,
        prompt=_prompt_builder,
    )


async def _build_initial_state(
    user_id: str,
    message: str | list[dict],
    *,
    context_collection=None,
) -> dict:
    """Pre-fetch active context and build the graph's initial state.

    `message` accepts two shapes:
      - str — a single user utterance; treated as one HumanMessage.
        Kept for backwards-compat with run_chat / arun_chat callers.
      - list[dict] — full conversation history as
        [{"role": "user" | "assistant", "content": str}, ...]. Used by
        the chat wire format so multi-turn confirmations (V3 forget_memory
        follow-up, slide-8 proposal/respond chain) have prior tool calls
        + replies in scope.

    Doing this BEFORE invoking the graph avoids motor's "Future attached
    to a different loop" error that fires when an async DB fetch happens
    inside the graph's sync prompt builder.
    """
    docs = await fetch_active_context(user_id, collection=context_collection)
    if isinstance(message, str):
        messages: list = [HumanMessage(content=message)]
    else:
        messages = []
        for m in message:
            role = m.get("role")
            content = m.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        if not messages:
            raise ValueError("at least one user message is required")
    return {
        "user_id": user_id,
        "active_context_block": format_active_context(docs),
        "messages": messages,
    }


# ─── Public callables ─────────────────────────────────────────────────────────────


def _content_to_text(content: Any) -> str:
    """Coerce a langchain message content to plain text.

    gemini-2.5-flash returns content as a list of dicts when "thinking"
    content blocks are emitted (each dict has a 'type' and 'text'). The
    chat wire format is plain text, so we flatten to the concatenation
    of all 'text' parts.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                t = item.get("text", "")
                if t:
                    parts.append(t)
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content) if content else ""


async def arun_chat(user_id: str, message: str) -> str:
    """Run a single turn (async). Use this from inside an existing event loop."""
    compiled = await build_graph()
    initial = await _build_initial_state(user_id, message)
    result = await compiled.ainvoke(initial)
    return _content_to_text(result["messages"][-1].content)


def run_chat(user_id: str, message: str) -> str:
    """Sync entry point. Uses asyncio.run — must NOT be called from inside
    a running event loop; use arun_chat there instead."""
    return asyncio.run(arun_chat(user_id, message))


async def astream_chat(
    user_id: str,
    message: str | list[dict],
) -> AsyncIterator[str]:
    """Async streaming entry point — yields only final-LLM tokens as plain text.

    `message` can be either a single user utterance (str — kept for tests
    and backwards-compat callers) or the full conversation history as a
    list of {role, content} dicts. Multi-turn features like the V3
    forget_memory confirmation follow-up need the full history so the
    agent can see its own prior tool call + result and reason about a
    bare "yes" response.

    This is the production path. Stays on the caller's event loop end-to-end,
    so motor cursors (active-context fetch, memory recall, etc.) all live on
    a single loop and don't trip RuntimeError: Future attached to a different
    loop. The agent /chat handler awaits this directly.
    """
    compiled = await build_graph()
    initial = await _build_initial_state(user_id, message)
    async for chunk, metadata in compiled.astream(initial, stream_mode="messages"):
        if metadata.get("langgraph_node") != "agent":
            continue
        text = _content_to_text(getattr(chunk, "content", ""))
        if text:
            yield text


def stream_chat(user_id: str, message: str) -> Iterator[str]:
    """Sync streaming entry point — yields only final-LLM tokens as plain text.

    Kept for tests and any non-async caller. Drives astream_chat under
    asyncio.run. Must NOT be called from inside a running event loop.
    Production /chat in serve.py uses astream_chat directly to avoid the
    loop-straddling bug that hit motor cursors.
    """
    async def _drain() -> list[str]:
        out: list[str] = []
        async for text in astream_chat(user_id, message):
            out.append(text)
        return out

    yield from asyncio.run(_drain())
