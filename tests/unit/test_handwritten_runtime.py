"""Unit tests for HandwrittenRuntime."""

import asyncio
from pathlib import Path
from uuid import uuid4

from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    AgentSpec,
    EventType,
    RunConfig,
    TaskSpec,
    TerminationReason,
)
from packages.environments.tool_lab.environment import ToolLabEnvironment
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


def test_runtime_normal_execution_flow() -> None:
    """HandwrittenRuntime successfully executes normal episode sequence
    with correct event sequence."""
    task = load_task()
    agent = make_agent()
    env = ToolLabEnvironment()
    provider = FakeModelProvider(scenario="normal")
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, task, env, recorder))

    assert res.termination_reason == TerminationReason.SUCCESS
    assert res.detail == "submitted"
    assert res.step_count == 2
    assert res.model_call_count == 2
    assert res.tool_call_count == 2

    events = [e.event_type for e in recorder.events]
    assert EventType.OBSERVATION_CREATED in events
    assert EventType.MODEL_REQUESTED in events
    assert EventType.MODEL_RESPONDED in events
    assert EventType.TOOL_CALL_PROPOSED in events
    assert EventType.TOOL_CALL_VALIDATED in events
    assert EventType.TOOL_STARTED in events
    assert EventType.TOOL_SUCCEEDED in events
    assert EventType.ENVIRONMENT_UPDATED in events


def test_runtime_handles_invalid_arguments_rejection() -> None:
    """HandwrittenRuntime rejects invalid arguments without executing tool."""
    task = load_task()
    agent = make_agent()
    env = ToolLabEnvironment()
    provider = FakeModelProvider(scenario="invalid_arguments")
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, task, env, recorder))

    assert res.termination_reason == TerminationReason.FAILED
    assert "invalid_arguments" in res.detail
    assert res.tool_call_count == 0  # No tool execution started!

    events = [e.event_type for e in recorder.events]
    assert EventType.TOOL_CALL_VALIDATED in events
    assert EventType.TOOL_STARTED not in events


def test_runtime_handles_duplicate_call_id() -> None:
    """Runtime rejects duplicate tool call IDs."""
    task = load_task()
    agent = make_agent()
    env = ToolLabEnvironment()
    recorder = JsonTraceRecorder(RunConfig())

    # Turn 1 succeeds with duplicate_id_001
    # We can inject 2 identical call_ids
    from packages.domain.models import ModelResponse, ToolCall

    resp_dup = ModelResponse(
        action=ToolCall(
            call_id="dup_id",
            name="query_records",
            arguments={"table": "orders", "filters": {"order_id": "ORD-001"}},
        )
    )
    p_dup = FakeModelProvider(custom_responses=[resp_dup, resp_dup])
    rt_dup = HandwrittenRuntime(provider=p_dup)

    res = asyncio.run(rt_dup.run(agent, task, env, recorder))
    assert res.termination_reason == TerminationReason.FAILED
    assert res.detail == "duplicate_call_id"
