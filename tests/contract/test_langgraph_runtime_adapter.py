"""Both schedulers must obey the same portable success and failure contracts."""

import asyncio
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from packages.application.runner import run_episode
from packages.application.trace import read_artifact, write_artifact
from packages.domain.models import (
    AgentSpec,
    Budget,
    EpisodeArtifact,
    EventType,
    RunConfig,
    RuntimeBackend,
    RuntimeStrategy,
    TaskSpec,
    TerminationReason,
)
from packages.domain.ports import ModelProviderError
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime, runtime_version

ROOT = Path(__file__).resolve().parents[2]
TASKS = sorted((ROOT / "benchmarks/tool_lab_core/tasks").glob("*.json"))


def load_agent(backend: RuntimeBackend, strategy: RuntimeStrategy) -> AgentSpec:
    """Read a legacy configuration and select the two independent variables."""
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    )
    return agent.model_copy(update={"runtime_backend": backend, "runtime_strategy": strategy})


def run(
    agent: AgentSpec,
    task: TaskSpec,
    provider: FakeModelProvider,
    environment: ToolLabEnvironment | None = None,
) -> EpisodeArtifact:
    """Use the public Runner with fresh environment, provider and recorder state."""
    return asyncio.run(
        run_episode(
            agent,
            task,
            RunConfig(seed=17, runtime_version=runtime_version(agent.runtime_backend)),
            create_runtime(agent, provider),
            environment or ToolLabEnvironment(),
            OrderStatusEvaluator(),
        )
    )


def assert_equivalent(left: EpisodeArtifact, right: EpisodeArtifact) -> None:
    """Ignore only independent identity and clock measurements."""
    assert left.episode.model_dump(
        exclude={"episode_id", "duration_ms"}
    ) == right.episode.model_dump(exclude={"episode_id", "duration_ms"})
    assert left.evaluation.model_dump(exclude={"metrics": {"duration_ms"}}) == (
        right.evaluation.model_dump(exclude={"metrics": {"duration_ms"}})
    )
    ignored = {"episode_id", "event_id", "parent_event_id", "timestamp", "duration_ms"}
    assert [e.model_dump(exclude=ignored) for e in left.events] == [
        e.model_dump(exclude=ignored) for e in right.events
    ]
    for artifact in (left, right):
        assert sum(e.event_type == EventType.EPISODE_FINISHED for e in artifact.events) == 1
        assert all(
            current.parent_event_id == previous.event_id
            for previous, current in zip(artifact.events, artifact.events[1:], strict=False)
        )


@pytest.mark.parametrize("task_path", TASKS, ids=lambda p: p.stem)
@pytest.mark.parametrize("strategy", ["handwritten", "handwritten_recovery"])
@pytest.mark.parametrize("scenario", ["success", "invalid-then-success"])
def test_same_suite_under_both_schedulers(
    task_path: Path, strategy: RuntimeStrategy, scenario: str
) -> None:
    """All native tasks preserve results, usage and trace under either scheduler."""
    task = TaskSpec.model_validate_json(task_path.read_text(encoding="utf-8"))
    reference = run(load_agent("handwritten", strategy), task, FakeModelProvider(scenario))
    with patch(
        "packages.runtime.handwritten.runtime.HandwrittenRuntime.run",
        side_effect=AssertionError("LangGraph must schedule independently"),
    ):
        graph = run(load_agent("langgraph", strategy), task, FakeModelProvider(scenario))
    assert_equivalent(reference, graph)
    if scenario == "success" or strategy == "handwritten_recovery":
        assert graph.evaluation.success


@pytest.mark.parametrize(
    "case, reason, calls, tools",
    [
        ("invalid_arguments", "FAILED", 2, 0),
        ("forbidden_tool", "FAILED", 1, 0),
        ("forbidden_invalid", "FAILED", 1, 0),
        ("duplicate_call_id", "FAILED", 2, 1),
        ("final_answer_only", "FAILED", 1, 0),
        ("unparseable", "RUNTIME_ERROR", 1, 0),
        ("provider_error", "RUNTIME_ERROR", 1, 0),
        ("environment_error", "RUNTIME_ERROR", 1, 1),
        ("tool_timeout", "FAILED", 1, 1),
        ("model_budget", "MAX_STEPS", 1, 0),
        ("token_budget", "TOKEN_BUDGET_EXCEEDED", 1, 0),
        ("cost_budget", "COST_BUDGET_EXCEEDED", 1, 0),
        ("tool_budget", "MAX_STEPS", 2, 1),
        ("long_loop", "MAX_STEPS", 12, 12),
    ],
)
def test_failure_boundaries(case: str, reason: str, calls: int, tools: int, tmp_path: Path) -> None:
    """A framework must not bypass permissions, budgets, stop reasons or one-retry limits."""
    task = TaskSpec.model_validate_json(TASKS[0].read_text(encoding="utf-8"))
    artifacts = []
    for backend in ("handwritten", "langgraph"):
        agent = load_agent(backend, "handwritten_recovery")
        active_task = task
        provider = FakeModelProvider(case)
        environment = ToolLabEnvironment()
        if case == "forbidden_invalid":
            active_task = task.model_copy(update={"forbidden_tools": ("query_records",)})
            provider = FakeModelProvider("invalid_arguments")
        elif case == "provider_error":
            provider.generate = AsyncMock(side_effect=ModelProviderError("RATE_LIMIT_EXCEEDED"))  # type: ignore[method-assign]
        elif case == "environment_error":
            environment.step = lambda _: (_ for _ in ()).throw(RuntimeError("private-secret"))  # type: ignore[assignment]
        elif case == "tool_timeout":
            active_task = task.model_copy(
                update={"initial_state": {**task.initial_state, "timeout_tool": "query_records"}}
            )
        elif case == "model_budget":
            agent = agent.model_copy(update={"budget": Budget(max_model_calls=1)})
            provider = FakeModelProvider("invalid_then_success")
        elif case == "token_budget":
            active_task = task.model_copy(update={"token_budget": 1})
        elif case == "cost_budget":
            agent = agent.model_copy(
                update={"budget": Budget(max_estimated_cost=Decimal("0.0001"))}
            )
        elif case == "tool_budget":
            agent = agent.model_copy(update={"budget": Budget(max_tool_calls=1)})
        elif case == "long_loop":
            active_task = task.model_copy(update={"max_steps": 12, "token_budget": 10000})
            agent = agent.model_copy(
                update={"budget": Budget(max_steps=12, max_model_calls=15, max_tool_calls=15)}
            )
            provider = FakeModelProvider("looping")
        artifact = run(agent, active_task, provider, environment)
        assert artifact.episode.termination_reason == TerminationReason(reason)
        assert artifact.episode.model_call_count == calls
        assert artifact.episode.tool_call_count == tools
        assert "private-secret" not in artifact.model_dump_json()
        write_artifact(artifact, tmp_path / f"{backend}.json")
        assert read_artifact(tmp_path / f"{backend}.json") == artifact
        artifacts.append(artifact)
    assert_equivalent(*artifacts)
    if case in ("tool_timeout", "environment_error"):
        assert [e.event_type for e in artifacts[1].events][-3:] == [
            EventType.TOOL_STARTED,
            EventType.TOOL_FAILED,
            EventType.EPISODE_FINISHED,
        ]
