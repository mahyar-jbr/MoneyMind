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


# ─── #17-wire — newly wired tools (one e2e scenario each) ──────────


async def test_check_goal_pace_flow(context_coll):
    """LLM calls check_goal_pace. Wrapper injects user_id; LLM-facing schema
    omits user_id so a forged value in args has no effect."""
    from bson import ObjectId
    from datetime import date

    goal_id = str(ObjectId())
    llm, _r = make_fake_chat_model([
        _tool_call(
            "check_goal_pace",
            # LLM tries to forge user_id; LLM-facing schema strips it.
            {"goal_id": goal_id, "user_id": "EVIL"},
            "c1",
        ),
        AIMessage(content="You're 28% behind on the Emergency Fund."),
    ])

    captured = {}

    async def fake_pace(params):
        captured["seen"] = params
        from agent.tools.check_goal_pace import CheckGoalPaceResult
        return CheckGoalPaceResult(
            user_id=params.user_id,
            goal_id=params.goal_id,
            title="Emergency Fund",
            status="active",
            target_amount=8000.0,
            current_amount=2400.0,
            target_date=date(2026, 12, 31),
            as_of=date(2026, 6, 1),
            expected_amount=3319.0,
            delta_amount=-919.0,
            delta_pct=-27.7,
            verdict="behind",
            note="Emergency Fund: -28% behind pace.",
        )

    with patch("agent.graphs.main.check_goal_pace", fake_pace):
        graph = build_graph(llm=llm, context_collection=context_coll)
        await graph.ainvoke({
            "user_id": "u_482",
            "messages": [{"role": "user", "content": "how's my emergency fund?"}],
        })

    assert captured["seen"].user_id == "u_482"
    assert captured["seen"].goal_id == goal_id


async def test_propose_intervention_flow(context_coll):
    """LLM calls propose_intervention with a trigger; wrapper carries user_id."""
    llm, _r = make_fake_chat_model([
        _tool_call(
            "propose_intervention",
            {
                "type": "reminder",
                "params": {"day": "sunday", "what": "meal prep"},
                "triggered_by": {
                    "tool": "get_spend_anomaly",
                    "input": {"category": "food.delivery", "window_days": 7},
                },
            },
            "c1",
        ),
        AIMessage(content="Want me to set a Sunday meal-prep reminder?"),
    ])

    captured = {}

    async def fake_propose(params):
        captured["seen"] = params
        from datetime import UTC, datetime
        from agent.tools.propose_intervention import ProposeInterventionResult
        return ProposeInterventionResult(
            intervention_id="iv1",
            user_id=params.user_id,
            type=params.type,
            proposed_at=datetime.now(UTC),
            status="pending",
        )

    with patch("agent.graphs.main.propose_intervention", fake_propose):
        graph = build_graph(llm=llm, context_collection=context_coll)
        await graph.ainvoke({
            "user_id": "u_482",
            "messages": [{"role": "user", "content": "anything you'd suggest?"}],
        })

    assert captured["seen"].user_id == "u_482"
    assert captured["seen"].type == "reminder"
    assert captured["seen"].triggered_by.tool == "get_spend_anomaly"


async def test_log_outcome_flow(context_coll):
    """LLM calls log_outcome; delta_pct is computed server-side, not from args."""
    from bson import ObjectId
    from datetime import UTC, datetime

    intervention_id = str(ObjectId())
    llm, _r = make_fake_chat_model([
        _tool_call(
            "log_outcome",
            {
                "intervention_id": intervention_id,
                "window_days": 14,
                "metric": "weekly_food_spend",
                "before": 180.0,
                "after": 118.5,
                "agent_judgment": "successful",
            },
            "c1",
        ),
        AIMessage(content="Logged — food spending fell 34%."),
    ])

    captured = {}

    async def fake_log(params):
        captured["seen"] = params
        from agent.tools.log_outcome import LogOutcomeResult
        return LogOutcomeResult(
            outcome_id="o1",
            user_id=params.user_id,
            intervention_id=params.intervention_id,
            metric=params.metric,
            window_days=params.window_days,
            before=params.before,
            after=params.after,
            delta_pct=-34.17,
            agent_judgment=params.agent_judgment,
            measured_at=datetime.now(UTC),
        )

    with patch("agent.graphs.main.log_outcome", fake_log):
        graph = build_graph(llm=llm, context_collection=context_coll)
        await graph.ainvoke({
            "user_id": "u_482",
            "messages": [{"role": "user", "content": "the cap worked, food's way down"}],
        })

    assert captured["seen"].user_id == "u_482"
    assert captured["seen"].intervention_id == intervention_id
    assert captured["seen"].agent_judgment == "successful"


async def test_schedule_reminder_flow(context_coll):
    """LLM calls schedule_reminder with a future UTC instant."""
    from datetime import UTC, datetime, timedelta

    fires_at = datetime.now(UTC) + timedelta(days=7)
    llm, _r = make_fake_chat_model([
        _tool_call(
            "schedule_reminder",
            {
                # The fake LLM serializes datetimes as ISO strings —
                # the Pydantic input model coerces them.
                "fires_at": fires_at.isoformat(),
                "text": "cancel the gym trial",
                "source": "user",
            },
            "c1",
        ),
        AIMessage(content="Got it — I'll remind you in a week."),
    ])

    captured = {}

    async def fake_schedule(params):
        captured["seen"] = params
        from agent.tools.schedule_reminder import ScheduleReminderResult
        return ScheduleReminderResult(
            reminder_id="r1",
            user_id=params.user_id,
            fires_at=params.fires_at,
            text=params.text,
            source=params.source,
            status="pending",
            created_at=datetime.now(UTC),
        )

    with patch("agent.graphs.main.schedule_reminder", fake_schedule):
        graph = build_graph(llm=llm, context_collection=context_coll)
        await graph.ainvoke({
            "user_id": "u_482",
            "messages": [{"role": "user", "content": "remind me in 7 days to cancel the gym"}],
        })

    assert captured["seen"].user_id == "u_482"
    assert captured["seen"].source == "user"
    assert captured["seen"].text == "cancel the gym trial"


async def test_summarize_week_flow(context_coll):
    """LLM calls summarize_week. user_id injected; aggregator NOT in LLM schema."""
    from datetime import date

    llm, _r = make_fake_chat_model([
        _tool_call("summarize_week", {"as_of": "2026-05-24"}, "c1"),
        AIMessage(content="You spent $340 across 8 transactions."),
    ])

    captured = {}

    async def fake_summarize(params, *, collection=None, goals_collection=None, aggregator=None):
        # Wrapper does NOT forward collection/goals_collection/aggregator
        # because those aren't in the LLM-facing schema; assert they
        # arrived as their defaults (None).
        captured["seen"] = params
        captured["collection_kw"] = collection
        captured["goals_collection_kw"] = goals_collection
        captured["aggregator_kw"] = aggregator
        from agent.tools.summarize_week import (
            CategorySpend,
            SummarizeWeekResult,
        )
        return SummarizeWeekResult(
            user_id=params.user_id,
            week_start=date(2026, 5, 18),
            week_end=date(2026, 5, 24),
            total_spend=340.0,
            transaction_count=8,
            top_categories=[
                CategorySpend(category="food.delivery", spend=211.0, pct_of_total=62.1),
            ],
            goals=[],
            paragraph="Week of Mon, May 18: you spent $340 across 8 transactions.",
        )

    with patch("agent.graphs.main.summarize_week", fake_summarize):
        graph = build_graph(llm=llm, context_collection=context_coll)
        await graph.ainvoke({
            "user_id": "u_482",
            "messages": [{"role": "user", "content": "how am I doing this week?"}],
        })

    assert captured["seen"].user_id == "u_482"
    assert captured["seen"].as_of == date(2026, 5, 24)
    # The 3 kwarg-only injection slots must arrive as defaults (None).
    assert captured["collection_kw"] is None
    assert captured["goals_collection_kw"] is None
    assert captured["aggregator_kw"] is None
