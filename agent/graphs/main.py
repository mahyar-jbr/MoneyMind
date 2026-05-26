import os
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agent.prompts.system import SYSTEM_PROMPT


MODEL_NAME = "gemini-2.5-flash"


class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _build_llm() -> ChatGoogleGenerativeAI:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=api_key)


def respond(state: ChatState) -> ChatState:
    llm = _build_llm()
    reply = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])
    return {"messages": [reply]}


def build_graph():
    graph = StateGraph(ChatState)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile()


def run_chat(message: str) -> str:
    compiled = build_graph()
    result = compiled.invoke({"messages": [HumanMessage(content=message)]})
    return result["messages"][-1].content
