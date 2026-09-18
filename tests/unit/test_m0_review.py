"""Regression checks for M0 trust and handoff boundaries."""

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.application.runner import run_episode
from packages.domain.models import AgentSpec, RunConfig, TaskSpec, TerminationReason, ToolCall
from packages.environments.tool_lab.environment import ToolLabEnvironment, create_tool_lab_registry
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.handwritten.runtime import HandwrittenRuntime
from packages.tools.registry import DefaultToolValidator

ROOT = Path(__file__).resolve().parents[2]


def load_inputs() -> tuple[AgentSpec, TaskSpec]:
    """Load the versioned M0 configuration."""
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    )
    task = TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )
    return agent, task


def test_environment_rejects_disallowed_tool_and_bad_snapshot() -> None:
    """Direct environment calls still enforce task permission and atomic restore."""
    _, task = load_inputs()
    task = task.model_copy(update={"expected_tools": ("query_records",)})
    environment = ToolLabEnvironment()
    environment.reset(task, 7)
    original = environment.snapshot()
    rejected = environment.step(
        ToolCall(
            call_id="submit-direct",
            name="submit_answer",
            arguments={"answer": "shipped", "evidence": ["order:ORD-001"]},
        )
    )
    assert rejected.error is not None
    assert environment.snapshot() == original

    malformed = {**original, "done": "true"}
    with pytest.raises(ValidationError):
        environment.restore(malformed)
    assert environment.snapshot() == original


def test_fake_uses_queried_status_and_runtime_sanitizes_provider_error() -> None:
    """Normal Fake answers from public tool data; provider failures retain state."""
    agent, task = load_inputs()
    task = task.model_copy(
        update={
            "initial_state": {
                "orders": [
                    {"order_id": "ORD-999", "status": "processing", "evidence_id": "order:ORD-999"}
                ]
            },
            "goal_conditions": {"answer": "processing", "evidence": ["order:ORD-999"]},
        }
    )
    registry = create_tool_lab_registry()
    environment = ToolLabEnvironment(registry)
    validator = DefaultToolValidator(registry)
    result = asyncio.run(
        run_episode(
            agent,
            task,
            RunConfig(),
            HandwrittenRuntime(FakeModelProvider(), validator),
            environment,
            OrderStatusEvaluator(),
        )
    )
    assert result.evaluation.success
    assert result.episode.final_state["submission"] == {
        "answer": "processing",
        "evidence": ["order:ORD-999"],
    }

    failed = asyncio.run(
        run_episode(
            agent,
            task,
            RunConfig(),
            HandwrittenRuntime(FakeModelProvider("unparseable"), validator),
            environment,
            OrderStatusEvaluator(),
        )
    )
    assert failed.episode.termination_reason == TerminationReason.RUNTIME_ERROR
    assert failed.episode.detail == "provider_error"
    assert failed.episode.final_state["target_order_id"] == "ORD-999"


def test_evaluation_metric_matches_final_episode_reason() -> None:
    """A rejected answer cannot leave a SUCCESS metric in its artifact."""
    agent, task = load_inputs()
    registry = create_tool_lab_registry()
    environment = ToolLabEnvironment(registry)
    result = asyncio.run(
        run_episode(
            agent,
            task,
            RunConfig(),
            HandwrittenRuntime(FakeModelProvider("wrong-answer"), DefaultToolValidator(registry)),
            environment,
            OrderStatusEvaluator(),
        )
    )
    assert result.episode.termination_reason == TerminationReason.FAILED
    assert result.evaluation.metrics["termination_reason"] == "FAILED"
