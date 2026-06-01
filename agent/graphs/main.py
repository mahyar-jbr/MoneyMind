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
from collections.abc import Iterator
from typing import Annotated, Any, NotRequired

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import InjectedState, create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from pydantic import BaseModel, create_model

from agent.graphs.context import fetch_active_context, format_active_context
from agent.prompts.system import SYSTEM_PROMPT
from agent.tools.get_spend_anomaly import GetSpendAnomalyInput, get_spend_anomaly
from agent.tools.query_transactions import QueryTransactionsInput, query_transactions
from agent.tools.recall_memory import RecallMemoryInput, recall_memory
from agent.tools.update_user_context import (
    UpdateUserContextInput,
    update_user_context,
)
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
        "Save a new memory the agent has discovered: a behavioral pattern, "
        "stated preference, observed reaction, or stated fact. Use only when "
        "confidence > 0.5 AND there are at least 2 evidence points. Summary "
        "is what gets vector-searched — make it a single concrete sentence."
    ),
    "update_user_context": (
        "Save something the user just told the agent about themselves: a "
        "lifestyle ('I'm bulking'), event ('exam week'), preference, or "
        "constraint. Insert-only — never used to correct prior context. Set "
        "active_from/active_until if the user gave a time range."
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


def _build_tools() -> list[StructuredTool]:
    return [
        _wrap_tool(query_transactions, name="query_transactions", input_model=QueryTransactionsInput),
        _wrap_tool(get_spend_anomaly, name="get_spend_anomaly", input_model=GetSpendAnomalyInput),
        _wrap_tool(recall_memory, name="recall_memory", input_model=RecallMemoryInput),
        _wrap_tool(write_memory, name="write_memory", input_model=WriteMemoryInput),
        _wrap_tool(update_user_context, name="update_user_context", input_model=UpdateUserContextInput),
    ]


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
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=api_key)


def build_graph(
    *,
    llm: BaseChatModel | None = None,
    context_collection=None,
):
    """Compile the agent graph. llm + context_collection are kept for
    tests that need to inject; production callers leave them None.

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
        tools=_build_tools(),
        state_schema=ChatState,
        prompt=_prompt_builder,
    )


async def _build_initial_state(
    user_id: str, message: str, *, context_collection=None
) -> dict:
    """Pre-fetch active context and build the graph's initial state.

    Doing this BEFORE invoking the graph avoids motor's "Future attached
    to a different loop" error that fires when an async DB fetch happens
    inside the graph's sync prompt builder.
    """
    docs = await fetch_active_context(user_id, collection=context_collection)
    return {
        "user_id": user_id,
        "active_context_block": format_active_context(docs),
        "messages": [HumanMessage(content=message)],
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
    compiled = build_graph()
    initial = await _build_initial_state(user_id, message)
    result = await compiled.ainvoke(initial)
    return _content_to_text(result["messages"][-1].content)


def run_chat(user_id: str, message: str) -> str:
    """Sync entry point. Uses asyncio.run — must NOT be called from inside
    a running event loop; use arun_chat there instead."""
    return asyncio.run(arun_chat(user_id, message))


def stream_chat(user_id: str, message: str) -> Iterator[str]:
    """Sync streaming entry point — yields only final-LLM tokens as plain text.

    Must NOT be called from inside a running event loop. Coerces content
    blocks (gemini-2.5-flash sometimes wraps in list[dict]) to plain text
    so the wire format stays text/plain.
    """
    compiled = build_graph()
    initial = asyncio.run(_build_initial_state(user_id, message))
    for chunk, metadata in compiled.stream(initial, stream_mode="messages"):
        if metadata.get("langgraph_node") != "agent":
            continue
        text = _content_to_text(getattr(chunk, "content", ""))
        if text:
            yield text
