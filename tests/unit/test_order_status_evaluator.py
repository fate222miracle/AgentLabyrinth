"""Unit tests for OrderStatusEvaluator."""

import asyncio
from pathlib import Path
from uuid import uuid4

from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    AgentSpec,
    EpisodeResult,
    EventType,
    RunConfig,
    TaskSpec,
    TerminationReason,
    TraceEvent,
)
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.handwritten.runtime import HandwrittenRuntime

ROOT = Path(__file__).resolve().parents[2]


def load_task() -> TaskSpec:
    """Load sample TaskSpec."""
    return TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )


def make_agent() -> AgentSpec:
    """Make sample AgentSpec."""
    return AgentSpec(
        id=uuid4(),
        name="test-agent",
        version="1.0.0",
        description="test agent",
        prompt_version="v1",
        tool_set_version="v1",
    )


def test_evaluator_correct_and_wrong_answers() -> None:
    """OrderStatusEvaluator evaluates correct answers as success and wrong answers as failure."""
    task = load_task()
    agent = make_agent()
    evaluator = OrderStatusEvaluator()

    # Success scenario
    env1 = ToolLabEnvironment()
    prov1 = FakeModelProvider(scenario="normal")
    rt1 = HandwrittenRuntime(provider=prov1)
    rec1 = JsonTraceRecorder(RunConfig())
    ep1 = asyncio.run(rt1.run(agent, task, env1, rec1))
    eval1 = evaluator.evaluate(task, ep1, rec1.events)

    assert eval1.success
    assert eval1.metrics["tool_selection_accuracy"] == 1.0
    assert eval1.metrics["tool_argument_validity_rate"] == 1.0
    assert eval1.metrics["forbidden_tool_call_count"] == 0
    assert eval1.metrics["expected_tool_coverage"] == 1.0

    # Wrong answer scenario
    env2 = ToolLabEnvironment()
    prov2 = FakeModelProvider(scenario="wrong-answer")
    rt2 = HandwrittenRuntime(provider=prov2)
    rec2 = JsonTraceRecorder(RunConfig())
    ep2 = asyncio.run(rt2.run(agent, task, env2, rec2))
    eval2 = evaluator.evaluate(task, ep2, rec2.events)

    assert not eval2.success
    assert "answer_mismatch" in eval2.reason


def test_evaluator_rejects_unqueried_or_forged_evidence() -> None:
    """Evaluator rejects submission with evidence not obtained via query_records."""
    task = load_task()
    evaluator = OrderStatusEvaluator()

    ep_forged = EpisodeResult(
        episode_id=uuid4(),
        termination_reason=TerminationReason.SUCCESS,
        detail="submitted",
        step_count=2,
        model_call_count=2,
        tool_call_count=2,
        duration_ms=10,
        final_state={"submission": {"answer": "shipped", "evidence": ["order:ORD-001"]}},
    )

    # Events showing query_records succeeded for ORD-999 (different evidence)
    from datetime import UTC, datetime

    q_started = TraceEvent(
        event_id=uuid4(),
        episode_id=ep_forged.episode_id,
        step_index=1,
        event_type=EventType.TOOL_STARTED,
        timestamp=datetime.now(UTC),
        payload={"call_id": "c1", "name": "query_records"},
    )
    q_succ = TraceEvent(
        event_id=uuid4(),
        episode_id=ep_forged.episode_id,
        step_index=1,
        event_type=EventType.TOOL_SUCCEEDED,
        timestamp=datetime.now(UTC),
        payload={
            "call_id": "c1",
            "observation": {
                "result": {
                    "records": [{"order_id": "ORD-999", "evidence_id": "order:ORD-999"}],
                    "acquired_evidence": ["order:ORD-001"],
                }
            },
        },
    )
    s_started = TraceEvent(
        event_id=uuid4(),
        episode_id=ep_forged.episode_id,
        step_index=2,
        event_type=EventType.TOOL_STARTED,
        timestamp=datetime.now(UTC),
        payload={"call_id": "c2", "name": "submit_answer"},
    )
    s_succ = TraceEvent(
        event_id=uuid4(),
        episode_id=ep_forged.episode_id,
        step_index=2,
        event_type=EventType.TOOL_SUCCEEDED,
        timestamp=datetime.now(UTC),
        payload={"call_id": "c2", "name": "submit_answer"},
    )
    events = (q_started, q_succ, s_started, s_succ)

    eval_res = evaluator.evaluate(task, ep_forged, events)
    assert not eval_res.success
    assert "unqueried_or_forged_evidence" in eval_res.reason


def test_evaluator_rejects_forged_document_evidence() -> None:
    """A final submission cannot forge evidence absent from a successful document read."""
    task = TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-007.json").read_text(encoding="utf-8")
    )
    recorder = JsonTraceRecorder(RunConfig())
    episode = asyncio.run(
        HandwrittenRuntime(FakeModelProvider(scenario="success")).run(
            make_agent(), task, ToolLabEnvironment(), recorder
        )
    )
    forged = episode.model_copy(
        update={
            "final_state": {
                **episode.final_state,
                "submission": {
                    "answer": "approved",
                    "evidence": ["document:FORGED"],
                },
            }
        }
    )
    forged_task = task.model_copy(
        update={
            "goal_conditions": {
                "answer": "approved",
                "evidence": ["document:FORGED"],
            }
        }
    )

    result = OrderStatusEvaluator().evaluate(forged_task, forged, recorder.events)

    assert not result.success
    assert result.reason == "unqueried_or_forged_evidence: 'document:FORGED'"
