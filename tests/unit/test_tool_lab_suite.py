"""Suite-level validation and offline execution tests for ToolLab-Core."""

import asyncio
from collections import Counter
from pathlib import Path
from uuid import uuid4

from packages.application.runner import run_episode
from packages.domain.models import AgentSpec, EventType, RunConfig, TaskSpec, TerminationReason
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.handwritten.runtime import HandwrittenRuntime

ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = ROOT / "benchmarks/tool_lab_core/tasks"


def load_tasks() -> list[TaskSpec]:
    """Load every native task through the public TaskSpec boundary."""
    return [
        TaskSpec.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(TASKS_DIR.glob("*.json"))
    ]


def make_agent() -> AgentSpec:
    """Build an offline agent with the standard budget."""
    return AgentSpec(
        id=uuid4(),
        name="tool-lab-suite-fake",
        version="1.0.0",
        description="Deterministic suite verifier",
        prompt_version="v1",
        tool_set_version="tool-lab-v1",
    )


def test_tool_lab_suite_has_exact_shape_and_all_tools() -> None:
    """Validate the 12-task contract, uniqueness, and four-tool coverage."""
    paths = sorted(TASKS_DIR.glob("*.json"))
    tasks = load_tasks()
    assert len(paths) == len(tasks) == 12
    assert len({task.id for task in tasks}) == 12
    assert len({task.name for task in tasks}) == 12
    assert Counter(task.category for task in tasks) == {
        "tool_selection": 3,
        "parameter_generation": 3,
        "multi_step_planning": 3,
        "error_recovery": 3,
    }
    covered_tools = {tool for task in tasks for tool in task.expected_tools}
    assert covered_tools == {
        "search_documents",
        "read_document",
        "query_records",
        "submit_answer",
    }
    assert all("timeout_tool" not in task.initial_state for task in tasks)


def test_fake_completes_all_native_tasks_without_network() -> None:
    """Run the complete native suite offline and require successful evaluation."""
    agent = make_agent()
    evaluator = OrderStatusEvaluator()
    results = []
    for task in load_tasks():
        results.append(
            asyncio.run(
                run_episode(
                    agent=agent,
                    task=task,
                    config=RunConfig(seed=7),
                    runtime=HandwrittenRuntime(provider=FakeModelProvider(scenario="success")),
                    environment=ToolLabEnvironment(),
                    evaluator=evaluator,
                )
            )
        )
    assert len(results) == 12
    assert all(result.episode.termination_reason == TerminationReason.SUCCESS for result in results)
    assert all(result.evaluation.success for result in results)


def test_fake_recovery_completes_error_recovery_tasks() -> None:
    """The existing invalid-then-success contract recovers all three recovery tasks."""
    recovery_agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/recovery-m1.json").read_text(encoding="utf-8")
    )
    evaluator = OrderStatusEvaluator()
    recovery_tasks = [task for task in load_tasks() if task.category == "error_recovery"]
    for task in recovery_tasks:
        artifact = asyncio.run(
            run_episode(
                agent=recovery_agent,
                task=task,
                config=RunConfig(seed=7),
                runtime=HandwrittenRuntime(
                    provider=FakeModelProvider(scenario="invalid_then_success")
                ),
                environment=ToolLabEnvironment(),
                evaluator=evaluator,
            )
        )
        assert artifact.episode.termination_reason == TerminationReason.SUCCESS
        assert artifact.evaluation.success


def test_deterministic_timeout_is_traced_and_terminates() -> None:
    """A configured tool timeout produces a clear failure event and result."""
    source_task = load_tasks()[0]
    task = source_task.model_copy(
        update={
            "initial_state": {
                **source_task.initial_state,
                "timeout_tool": "query_records",
            }
        }
    )
    recovery_agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/recovery-m1.json").read_text(encoding="utf-8")
    )
    artifact = asyncio.run(
        run_episode(
            agent=recovery_agent,
            task=task,
            config=RunConfig(seed=3),
            runtime=HandwrittenRuntime(provider=FakeModelProvider(scenario="success")),
            environment=ToolLabEnvironment(),
            evaluator=OrderStatusEvaluator(),
        )
    )
    assert artifact.episode.termination_reason == TerminationReason.FAILED
    assert artifact.episode.model_call_count == 1
    assert [event.event_type for event in artifact.events][-3:] == [
        EventType.TOOL_STARTED,
        EventType.TOOL_FAILED,
        EventType.EPISODE_FINISHED,
    ]
    failed = [event for event in artifact.events if event.event_type == EventType.TOOL_FAILED]
    assert len(failed) == 1
    error = failed[0].payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == "TOOL_TIMEOUT"
