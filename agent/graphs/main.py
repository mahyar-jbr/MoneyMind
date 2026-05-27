import os
from collections.abc import Iterator
from typing import Annotated, TypedDict

import httpx
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agent.prompts.system import SYSTEM_PROMPT


MODEL_NAME = "gemini-2.5-flash"


class ChatState(TypedDict):
    user_id: str
    messages: Annotated[list[AnyMessage], add_messages]


def _build_llm() -> ChatGoogleGenerativeAI:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=api_key)


def _fetch_weekly_context(user_id: str) -> str:
    """Pull the user's latest week of spend from the backend aggregation.

    Reuses the tested /agg/weekly route (PR #3, #5) rather than re-querying
    Mongo. The CSV's most recent week may not be the current calendar week,
    so we summarize the latest week that actually has data — the last entry
    the aggregation returns.
    """
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    response = httpx.get(
        f"{backend_url}/agg/weekly",
        params={"user_id": user_id},
        timeout=10.0,
    )
    response.raise_for_status()
    weeks = response.json().get("weeks", [])
    if not weeks:
        return "No spending data is available for this user yet."

    latest = weeks[-1]
    lines = [f"- {category}: ${spend:.2f}" for category, spend in latest["by_category"].items()]
    return (
        f"Week of {latest['week']} (most recent week with data), "
        f"total spend ${latest['total_spend']:.2f}:\n" + "\n".join(lines)
    )


def _build_messages(user_id: str, messages: list[AnyMessage]) -> list[AnyMessage]:
    context = _fetch_weekly_context(user_id)
    system = SystemMessage(
        content=(
            f"{SYSTEM_PROMPT}\n\nHere is the user's most recent weekly spend. "
            f"Ground your reply in these real figures — cite specific categories "
            f"and dollar amounts:\n{context}"
        )
    )
    return [system, *messages]


def respond(state: ChatState) -> ChatState:
    llm = _build_llm()
    reply = llm.invoke(_build_messages(state["user_id"], state["messages"]))
    return {"messages": [reply]}


def build_graph():
    graph = StateGraph(ChatState)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile()


def run_chat(user_id: str, message: str) -> str:
    compiled = build_graph()
    result = compiled.invoke(
        {"user_id": user_id, "messages": [HumanMessage(content=message)]}
    )
    return result["messages"][-1].content


def stream_chat(user_id: str, message: str) -> Iterator[str]:
    """Yield the agent's reply token by token as the LLM generates it.

    First token leaves before generation finishes, so the proxy legs can
    forward chunks live (no buffering). Bypasses the graph because the single
    respond node has nothing to stream around — we stream the LLM call directly.
    """
    llm = _build_llm()
    for chunk in llm.stream(_build_messages(user_id, [HumanMessage(content=message)])):
        if chunk.content:
            yield chunk.content
