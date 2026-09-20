"""Unit tests for HandwrittenRuntime recovery strategy in M1 Slice C."""

import asyncio
from pathlib import Path
from uuid import uuid4

from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    AgentSpec,
    EventType,
    ModelResponse,
    RunConfig,
    TaskSpec,
    TerminationReason,
    ToolCall,
)
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.providers.fake import FakeModelProvider
from packages.runtime.handwritten.runtime import HandwrittenRuntime

ROOT = Path(__file__).resolve().parents[2]


def load_task(task_id: str = "order-status-001") -> TaskSpec:
    """Load sample TaskSpec."""
    return TaskSpec.model_validate_json(
        (ROOT / f"benchmarks/tool_lab_core/tasks/{task_id}.json").read_text(encoding="utf-8")
    )


def make_agent(strategy: str = "handwritten") -> AgentSpec:
    """Make sample AgentSpec with specified runtime strategy."""
    return AgentSpec(
        id=uuid4(),
        name=f"test-agent-{strategy}",
        version="1.0.0",
        description="test agent",
        prompt_version="v1",
        tool_set_version="v1",
        runtime_strategy=strategy,  # type: ignore[arg-type]
    )


def test_baseline_fails_on_invalid_arguments() -> None:
    """Baseline agent without recovery terminates immediately on invalid arguments."""
    task = load_task()
    agent = make_agent("handwritten")
    env = ToolLabEnvironment()
    provider = FakeModelProvider(scenario="invalid_then_success")
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, task, env, recorder))

    assert res.termination_reason == TerminationReason.FAILED
    assert "invalid_arguments" in res.detail
    # Baseline did not execute the invalid tool
    assert res.tool_call_count == 0
    assert res.step_count == 1


def test_recovery_succeeds_on_invalid_then_success() -> None:
    """Recovery agent retries once with feedback and completes successfully."""
    task = load_task()
    agent = make_agent("handwritten_recovery")
    env = ToolLabEnvironment()
    provider = FakeModelProvider(scenario="invalid_then_success")
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, task, env, recorder))

    assert res.termination_reason == TerminationReason.SUCCESS
    assert res.detail == "submitted"
    assert res.tool_call_count == 2  # query_records + submit_answer executed!
    assert res.model_call_count == 3  # Turn 1 (invalid), Turn 2 (query), Turn 3 (submit)

    events = [e.event_type for e in recorder.events]
    # Event causality check
    assert EventType.OBSERVATION_CREATED in events
    assert EventType.TOOL_CALL_VALIDATED in events
    assert EventType.TOOL_SUCCEEDED in events


def test_recovery_terminates_if_invalid_arguments_persist() -> None:
    """Recovery agent terminates with FAILED if second attempt also has invalid arguments."""
    task = load_task()
    agent = make_agent("handwritten_recovery")
    env = ToolLabEnvironment()
    provider = FakeModelProvider(scenario="invalid_arguments")
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, task, env, recorder))

    assert res.termination_reason == TerminationReason.FAILED
    assert "invalid_arguments" in res.detail
    # Must have stopped after exactly 2 model calls (first attempt + 1 retry)
    assert res.model_call_count == 2
    assert res.tool_call_count == 0


def test_recovery_does_not_retry_unknown_or_forbidden_tool() -> None:
    """Recovery agent does NOT retry on unregistered or forbidden tools."""
    task = load_task()
    agent = make_agent("handwritten_recovery")
    env = ToolLabEnvironment()
    provider = FakeModelProvider(scenario="forbidden_tool")
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, task, env, recorder))

    assert res.termination_reason == TerminationReason.FAILED
    assert res.detail in ("unknown_tool", "forbidden_tool")
    assert res.model_call_count == 1  # No retry performed!

    # Test explicitly forbidden tool
    forbidden_task = task.model_copy(update={"forbidden_tools": ["query_records"]})
    provider2 = FakeModelProvider(scenario="normal")
    runtime2 = HandwrittenRuntime(provider=provider2)
    recorder2 = JsonTraceRecorder(RunConfig())

    res2 = asyncio.run(runtime2.run(agent, forbidden_task, env, recorder2))
    assert res2.termination_reason == TerminationReason.FAILED
    assert "forbidden_tool" in res2.detail
    assert res2.model_call_count == 1  # Immediate termination!


def test_recovery_does_not_retry_duplicate_call_id() -> None:
    """Recovery agent must terminate immediately on duplicate call ID without retry."""
    task = load_task()
    agent = make_agent("handwritten_recovery")
    env = ToolLabEnvironment()
    tc = ToolCall(
        call_id="duplicate_id_001",
        name="query_records",
        arguments={"table": "orders", "filters": {"order_id": "ORD-001"}},
    )
    # First turn uses duplicate_id_001, second turn re-uses duplicate_id_001
    resp1 = ModelResponse(action=tc)
    resp2 = ModelResponse(action=tc)
    provider = FakeModelProvider(custom_responses=[resp1, resp2])
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, task, env, recorder))

    assert res.termination_reason == TerminationReason.FAILED
    assert res.detail == "duplicate_call_id"


def test_recovery_does_not_retry_when_budget_exceeded() -> None:
    """Recovery agent terminates with MAX_STEPS when max_model_calls budget is exhausted."""
    task = load_task()
    agent = make_agent("handwritten_recovery")
    # Restrict budget to 1 model call
    agent = agent.model_copy(
        update={"budget": agent.budget.model_copy(update={"max_model_calls": 1})}
    )
    env = ToolLabEnvironment()
    provider = FakeModelProvider(scenario="invalid_then_success")
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, task, env, recorder))

    # Even though invalid arguments occurred, max_model_calls == 1 prevents retry
    assert res.termination_reason == TerminationReason.MAX_STEPS
    assert "max_model_calls_reached" in res.detail
    assert res.model_call_count == 1


def test_forbidden_tool_with_invalid_arguments_terminates_immediately() -> None:
    """Forbidden tool with invalid arguments must terminate immediately without retry."""
    task = load_task()
    forbidden_task = task.model_copy(update={"forbidden_tools": ("query_records",)})
    agent = make_agent("handwritten_recovery")
    env = ToolLabEnvironment()
    provider = FakeModelProvider(scenario="invalid_arguments")
    runtime = HandwrittenRuntime(provider=provider)
    recorder = JsonTraceRecorder(RunConfig())

    res = asyncio.run(runtime.run(agent, forbidden_task, env, recorder))

    assert res.termination_reason == TerminationReason.FAILED
    assert "forbidden_tool" in res.detail
    # Must stop after exactly 1 model call with 0 tool executions
    assert res.model_call_count == 1
    assert res.tool_call_count == 0

    # Verify that validation recorded FORBIDDEN_TOOL and permitted=False
    validation_events = [
        e for e in recorder.events if e.event_type == EventType.TOOL_CALL_VALIDATED
    ]
    assert len(validation_events) == 1
    assert validation_events[0].payload["permitted"] is False
    assert validation_events[0].payload["error_code"] == "FORBIDDEN_TOOL"


def test_provider_failure_code_survives_without_retry() -> None:
    """Known safe provider errors reach the artifact, not their raw upstream body."""
    from unittest.mock import AsyncMock

    from packages.domain.ports import ModelProviderError

    provider = FakeModelProvider()
    provider.generate = AsyncMock(side_effect=ModelProviderError("RATE_LIMIT_EXCEEDED"))  # type: ignore[method-assign]
    result = asyncio.run(
        HandwrittenRuntime(provider).run(
            make_agent("handwritten_recovery"),
            load_task(),
            ToolLabEnvironment(),
            JsonTraceRecorder(RunConfig()),
        )
    )
    assert result.detail == "provider_error: RATE_LIMIT_EXCEEDED"
    assert result.model_call_count == 1
    assert result.tool_call_count == 0
