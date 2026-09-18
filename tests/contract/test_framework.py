"""Executable framework constraints, not proof of concrete M0 implementations."""

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import JsonValue, ValidationError

from packages.application.runner import run_episode
from packages.application.trace import (
    JsonTraceRecorder,
    content_hash,
    read_artifact,
    write_artifact,
)
from packages.domain.models import (
    AgentSpec,
    Budget,
    EpisodeResult,
    EvaluationResult,
    EventType,
    ModelResponse,
    Observation,
    RunConfig,
    StepResult,
    TaskSpec,
    TerminationReason,
    ToolCall,
    ToolSchema,
    TraceEvent,
)
from packages.domain.ports import AgentRuntime, Environment, Evaluator, TraceRecorder

ROOT = Path(__file__).resolve().parents[2]


def load_task() -> TaskSpec:
    """Load the single native task schema, without asserting task execution."""
    return TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )


def make_agent() -> AgentSpec:
    """Provide a local test-only agent configuration."""
    return AgentSpec(
        id=uuid4(),
        name="contract-stub",
        version="1.0.0",
        description="test only",
        prompt_version="v1",
        tool_set_version="v1",
    )


class StubEnvironment:
    """Minimal port witness; deliberately not ToolLab."""

    def reset(self, task: TaskSpec, seed: int) -> Observation:
        """Return a public test observation."""
        return Observation(content={"seed": seed})

    def available_tools(self) -> list[ToolSchema]:
        """No tools belong to this stub."""
        return []

    def step(self, action: ToolCall) -> StepResult:
        """Return inert feedback."""
        return StepResult(observation=Observation(content={}))

    def snapshot(self) -> dict[str, JsonValue]:
        """Return a fresh inert state."""
        return {}

    def restore(self, snapshot: dict[str, JsonValue]) -> None:
        """No state is maintained by this test witness."""


class StubRuntime:
    """Tests only the Runner boundary, not the planned control loop."""

    async def run(
        self, agent: AgentSpec, task: TaskSpec, environment: Environment, recorder: TraceRecorder
    ) -> EpisodeResult:
        """Return a provisional execution success with an isolated state."""
        task.initial_state["test_mutation"] = True
        observation = environment.reset(task, recorder.run_config.seed)
        recorder.record(EventType.OBSERVATION_CREATED, 0, observation.content)
        return EpisodeResult(
            episode_id=recorder.episode_id,
            termination_reason=TerminationReason.SUCCESS,
            detail="submitted",
            step_count=0,
            model_call_count=0,
            tool_call_count=0,
            duration_ms=0,
            final_state={"submission": "test"},
        )


class StubEvaluator:
    """Controlled verdict and hostile mutation test, not order evaluation."""

    def __init__(self, success: bool) -> None:
        self.success = success

    def evaluate(
        self, task: TaskSpec, episode: EpisodeResult, events: tuple[TraceEvent, ...]
    ) -> EvaluationResult:
        """Try to alter inputs to verify Runner copy isolation."""
        episode.final_state["corrupted"] = True
        events[0].payload["corrupted"] = True
        task.initial_state["corrupted"] = True
        return EvaluationResult(
            evaluator_version="test-only", success=self.success, reason="test", metrics={}
        )


class CrashingRuntime(StubRuntime):
    """Exercise containment without leaking raw exception text."""

    async def run(
        self, agent: AgentSpec, task: TaskSpec, environment: Environment, recorder: TraceRecorder
    ) -> EpisodeResult:
        """Raise an unsafe message that must never be persisted."""
        raise RuntimeError("secret-private-path")


@pytest.mark.parametrize(
    "invalid", ['{"max_steps":"6"}', '{"max_steps":true}', '{"unknown":1}', '{"max_steps":0}']
)
def test_budget_rejects_coercion_and_unknown_fields(invalid: str) -> None:
    """Budget values must be genuinely typed, positive, known fields."""
    with pytest.raises(ValidationError):
        Budget.model_validate_json(invalid)


def test_decimal_cost_roundtrip() -> None:
    """Cost stays exact across JSON serialization."""
    budget = Budget(max_estimated_cost=Decimal("0.123456789"))
    assert Budget.model_validate_json(budget.model_dump_json()) == budget
    with pytest.raises(ValidationError):
        Budget(max_estimated_cost=0.1)  # type: ignore[arg-type]


def test_response_rejects_ambiguous_action() -> None:
    """One request cannot silently become a mixed answer and tool call."""
    with pytest.raises(ValidationError):
        ModelResponse.model_validate_json(
            '{"action":{"kind":"tool_call","call_id":"1","name":"x",'
            '"arguments":{},"text":"also answer"}}'
        )


def test_native_task_schema_and_hash() -> None:
    """Input is versioned and its content hash changes with content."""
    task = load_task()
    assert task.expected_tools == ("query_records", "submit_answer")
    assert content_hash(task) == content_hash(TaskSpec.model_validate_json(task.model_dump_json()))
    altered = task.model_copy(update={"version": "2.0.0"})
    assert content_hash(task) != content_hash(altered)


def test_trace_copy_isolation_redaction_and_parent() -> None:
    """Neither writers nor readers can mutate stored history."""
    recorder: TraceRecorder = JsonTraceRecorder(RunConfig())
    payload: dict[str, JsonValue] = {"nested": {"api_key": "private", "value": 1}}
    event = recorder.record(EventType.EPISODE_STARTED, 0, payload)
    payload["nested"] = None
    event.payload["changed"] = True
    reader_copy = recorder.events
    reader_copy[0].payload["changed"] = True
    assert recorder.events[0].payload == {"nested": {"api_key": "[REDACTED]", "value": 1}}
    assert recorder.events[0].timestamp.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="parent"):
        recorder.record(EventType.MODEL_REQUESTED, 1, {}, parent_event_id=uuid4())
    recorder.record(EventType.EPISODE_FINISHED, 1, {}, parent_event_id=event.event_id)
    with pytest.raises(ValueError, match="finished"):
        recorder.record(EventType.MODEL_REQUESTED, 2, {})


def test_trace_rejects_naive_time_and_backward_steps() -> None:
    """UTC and monotonic step indices are persistent event invariants."""
    recorder = JsonTraceRecorder(RunConfig())
    event = recorder.record(EventType.MODEL_REQUESTED, 2, {})
    with pytest.raises(ValueError, match="backwards"):
        recorder.record(EventType.MODEL_RESPONDED, 1, {})
    data = event.model_dump()
    data["timestamp"] = datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        TraceEvent.model_validate(data)


@pytest.mark.parametrize("success", [True, False])
def test_runner_evaluation_and_roundtrip(success: bool, tmp_path: Path) -> None:
    """Runner finalizes success from independent evaluation and protects provenance."""
    runtime: AgentRuntime = StubRuntime()
    environment: Environment = StubEnvironment()
    evaluator: Evaluator = StubEvaluator(success)
    task = load_task()
    artifact = asyncio.run(
        run_episode(make_agent(), task, RunConfig(), runtime, environment, evaluator)
    )
    expected = TerminationReason.SUCCESS if success else TerminationReason.FAILED
    assert artifact.episode.termination_reason == expected
    assert "corrupted" not in artifact.episode.final_state
    assert "corrupted" not in artifact.events[0].payload
    assert "test_mutation" not in artifact.task.initial_state
    assert artifact.task == task
    assert [e.event_type for e in artifact.events].count(EventType.EPISODE_FINISHED) == 1
    destination = tmp_path / "trace.json"
    write_artifact(artifact, destination)
    assert read_artifact(destination) == artifact


def test_unhandled_exception_is_sanitized() -> None:
    """Contain unexpected adapter errors with an explicit incomplete-usage marker."""
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            RunConfig(),
            CrashingRuntime(),
            StubEnvironment(),
            StubEvaluator(True),
        )
    )
    assert artifact.episode.termination_reason == TerminationReason.RUNTIME_ERROR
    assert not artifact.evaluation.success
    assert artifact.evaluation.metrics["usage_complete"] is False
    assert "secret-private-path" not in artifact.model_dump_json()
