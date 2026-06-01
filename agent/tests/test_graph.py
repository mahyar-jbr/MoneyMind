"""Graph-level tests with a scripted FakeChatModel.

Verifies the create_react_agent loop with InjectedState user_id wiring +
active-context injection works end-to-end without touching any real LLM
or Mongo cluster.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent.graphs.context import fetch_active_context, format_active_context
from agent.graphs.main import build_graph
from agent.tests._fakes import make_fake_chat_model, make_mongomock_collection


# ─── helpers ────────────────────────────────────────────────────────


def _tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture
async def context_coll():
    return make_mongomock_collection(collection_name="user_context")


# ─── scenario 1: no tool calls ──────────────────────────────────────


async def test_simple_reply_no_tool_call(context_coll):
    llm, _received = make_fake_chat_model([AIMessage(content="Hello! How can I help?")])
    graph = build_graph(llm=llm, context_collection=context_coll)
    result = await graph.ainvoke({
        "user_id": "u_482",
        "messages": [{"role": "user", "content": "hi"}],
    })
    final = result["messages"][-1]
    assert final.content == "Hello! How can I help?"


# ─── scenario 2: anomaly tool call ─────────────────────────────────


async def test_anomaly_detection_flow(context_coll):
    """LLM calls get_spend_anomaly with the LLM-facing args; wrapper injects user_id."""
    llm, _received = make_fake_chat_model([
        _tool_call("get_spend_anomaly", {"category": "food.delivery"}, "c1"),
        AIMessage(content="Food delivery is up this week."),
    ])

    captured_params = {}

    async def fake_anomaly(params):
        captured_params["seen"] = params
        from agent.tools.get_spend_anomaly import GetSpendAnomalyResult
        from datetime import date
        return GetSpendAnomalyResult(
            user_id=params.user_id,
            category=params.category,
            window_days=params.window_days,
            window_start=date(2026, 5, 17),
            window_end=date(2026, 5, 23),
            current_spend=250.0,
            baseline_mean=70.0,
            baseline_std=10.0,
            z_score=18.0,
            is_anomaly=True,
            baseline_weeks_used=8,
            note="Food Delivery is 3.6x your 8-week average ($70).",
        )

    with patch("agent.graphs.main.get_spend_anomaly", fake_anomaly):
        graph = build_graph(llm=llm, context_collection=context_coll)
        result = await graph.ainvoke({
            "user_id": "u_482",
            "messages": [{"role": "user", "content": "how's my food spend?"}],
        })

    # The tool was called with user_id from state, not from LLM args.
    assert captured_params["seen"].user_id == "u_482"
    assert captured_params["seen"].category == "food.delivery"
    # Final reply is the second scripted AIMessage.
    assert result["messages"][-1].content == "Food delivery is up this week."


# ─── scenario 3: memory write flow ─────────────────────────────────


async def test_memory_write_flow(context_coll):
    """LLM calls update_user_context then write_memory; both reach the tools."""
    llm, _received = make_fake_chat_model([
        _tool_call(
            "update_user_context",
            {"type": "lifestyle", "text": "I'm bulking this month"},
            "c1",
        ),
        _tool_call(
            "write_memory",
            {
                "type": "pattern",
                "tag": "bulk_food_spend",
                "summary": "User is bulking and expects elevated food spend.",
                "confidence": 0.8,
                "evidence": [
                    {"date": "2026-06-01", "note": "user stated bulking"},
                    {"date": "2026-05-25", "note": "DoorDash $80"},
                ],
            },
            "c2",
        ),
        AIMessage(content="Got it — I'll remember you're bulking."),
    ])

    write_memory_calls = []
    update_ctx_calls = []

    async def fake_write_memory(params):
        write_memory_calls.append(params)
        from agent.tools.write_memory import WriteMemoryResult
        return WriteMemoryResult(
            memory_id="mem1",
            user_id=params.user_id,
            type=params.type,
            tag=params.tag,
            created_at=datetime(2026, 6, 1, 12, 0),
            embedded=True,
        )

    async def fake_update_ctx(params):
        update_ctx_calls.append(params)
        from agent.tools.update_user_context import UpdateUserContextResult
        return UpdateUserContextResult(
            context_id="ctx1",
            user_id=params.user_id,
            type=params.type,
            text=params.text,
            active_from=params.active_from or datetime(2026, 6, 1).date(),
            active_until=params.active_until,
            created_at=datetime(2026, 6, 1, 12, 0),
        )

    with (
        patch("agent.graphs.main.write_memory", fake_write_memory),
        patch("agent.graphs.main.update_user_context", fake_update_ctx),
    ):
        graph = build_graph(llm=llm, context_collection=context_coll)
        await graph.ainvoke({
            "user_id": "u_482",
            "messages": [{"role": "user", "content": "I'm bulking this month."}],
        })

    assert len(update_ctx_calls) == 1
    assert update_ctx_calls[0].user_id == "u_482"
    assert update_ctx_calls[0].type == "lifestyle"

    assert len(write_memory_calls) == 1
    assert write_memory_calls[0].user_id == "u_482"
    assert write_memory_calls[0].confidence == 0.8


# ─── scenario 4: recall before anomaly ─────────────────────────────


async def test_recall_before_anomaly(context_coll):
    """When the script puts recall_memory before get_spend_anomaly, that's the
    order the tools fire — proving the graph routes per scripted tool_calls."""
    llm, _received = make_fake_chat_model([
        _tool_call("recall_memory", {"query": "food spike pattern"}, "c1"),
        _tool_call("get_spend_anomaly", {"category": "food.delivery"}, "c2"),
        AIMessage(content="Same as the February exam-week pattern."),
    ])

    call_order = []

    async def fake_recall(params):
        call_order.append("recall_memory")
        from agent.tools.recall_memory import RecallMemoryResult
        return RecallMemoryResult(user_id=params.user_id, query=params.query, k=params.k, count=0, memories=[])

    async def fake_anomaly(params):
        call_order.append("get_spend_anomaly")
        from agent.tools.get_spend_anomaly import GetSpendAnomalyResult
        from datetime import date
        return GetSpendAnomalyResult(
            user_id=params.user_id, category=params.category, window_days=params.window_days,
            window_start=date(2026, 5, 17), window_end=date(2026, 5, 23),
            current_spend=100.0, baseline_mean=80.0, baseline_std=10.0,
            z_score=2.0, is_anomaly=False, baseline_weeks_used=8, note=None,
        )

    with (
        patch("agent.graphs.main.recall_memory", fake_recall),
        patch("agent.graphs.main.get_spend_anomaly", fake_anomaly),
    ):
        graph = build_graph(llm=llm, context_collection=context_coll)
        await graph.ainvoke({
            "user_id": "u_482",
            "messages": [{"role": "user", "content": "my food spend feels off"}],
        })

    assert call_order == ["recall_memory", "get_spend_anomaly"]


# ─── scenario 5: user_id NOT trusted from LLM args ─────────────────


async def test_user_id_injected_not_from_llm(context_coll):
    """LLM tries to pass user_id='EVIL_USER' in args; the wrapper overrides it
    with the real user_id from graph state."""
    llm, _received = make_fake_chat_model([
        # Even if the LLM tried to forge user_id, the args_schema strips it
        # so the call effectively only carries `category`.
        _tool_call(
            "get_spend_anomaly",
            {"category": "food.delivery", "user_id": "EVIL_USER"},
            "c1",
        ),
        AIMessage(content="Ok."),
    ])

    captured = {}

    async def fake_anomaly(params):
        captured["user_id"] = params.user_id
        from agent.tools.get_spend_anomaly import GetSpendAnomalyResult
        from datetime import date
        return GetSpendAnomalyResult(
            user_id=params.user_id, category=params.category, window_days=7,
            window_start=date(2026, 5, 17), window_end=date(2026, 5, 23),
            current_spend=0.0, baseline_mean=0.0, baseline_std=0.0,
            z_score=0.0, is_anomaly=False, baseline_weeks_used=0, note=None,
        )

    with patch("agent.graphs.main.get_spend_anomaly", fake_anomaly):
        graph = build_graph(llm=llm, context_collection=context_coll)
        await graph.ainvoke({
            "user_id": "u_482_legit",
            "messages": [{"role": "user", "content": "ok"}],
        })

    assert captured["user_id"] == "u_482_legit"
    assert captured["user_id"] != "EVIL_USER"


# ─── scenario 6: active context surfaces in system message ─────────


async def test_active_context_in_system_message(context_coll):
    """Pre-seed a user_context doc, fetch it (as run_chat would), pass via
    state, assert the LLM saw the context in its system message."""
    await context_coll.insert_one({
        "user_id": "u_482",
        "type": "lifestyle",
        "text": "I'm bulking — food spend will be high all summer",
        "active_from": datetime(2026, 5, 1),
        "active_until": None,
        "created_at": datetime(2026, 5, 1, 12, 0),
    })
    docs = await fetch_active_context("u_482", collection=context_coll)
    block = format_active_context(docs)

    llm, received = make_fake_chat_model([AIMessage(content="Noted.")])
    graph = build_graph(llm=llm)
    await graph.ainvoke({
        "user_id": "u_482",
        "active_context_block": block,
        "messages": [{"role": "user", "content": "hey"}],
    })

    # First captured invocation's first message should be the SystemMessage
    # with both the static prompt AND the active-context block.
    assert received, "FakeChatModel was never invoked"
    sys_msg = received[0][0]
    assert isinstance(sys_msg, SystemMessage)
    assert "Active context for the user:" in sys_msg.content
    assert "I'm bulking" in sys_msg.content


# ─── scenario 7: streaming yields only final reply ─────────────────


async def test_streaming_yields_only_final_reply(context_coll):
    """stream_chat must not leak tool-call deltas or ToolMessage content."""
    llm, _received = make_fake_chat_model([
        _tool_call("recall_memory", {"query": "anything"}, "c1"),
        AIMessage(content="Final reply."),
    ])

    async def fake_recall(params):
        from agent.tools.recall_memory import RecallMemoryResult
        return RecallMemoryResult(
            user_id=params.user_id, query=params.query, k=params.k, count=0, memories=[]
        )

    with patch("agent.graphs.main.recall_memory", fake_recall):
        graph = build_graph(llm=llm, context_collection=context_coll)
        state = {"user_id": "u_482", "messages": [{"role": "user", "content": "hi"}]}
        # Apply the SAME filter stream_chat uses: agent-node text only.
        chunks = []
        async for chunk, metadata in graph.astream(state, stream_mode="messages"):
            if metadata.get("langgraph_node") != "agent":
                # Tool-call output and ToolMessages from the tools node MUST
                # be filtered out here — that's the contract stream_chat
                # enforces. The fact that they exist in the raw stream is
                # expected; the fact that we DON'T forward them is the test.
                assert isinstance(chunk, ToolMessage) or not getattr(chunk, "content", None), (
                    f"unexpected non-agent chunk leaked: {chunk!r}"
                )
                continue
            content = getattr(chunk, "content", None)
            if isinstance(content, str) and content:
                chunks.append(content)

    joined = "".join(chunks)
    assert "Final reply." in joined
    # Critically: the tool's JSON output (which mentions 'memories' and 'count')
    # must NOT appear in what the user sees.
    assert "memories" not in joined
    assert "count" not in joined
