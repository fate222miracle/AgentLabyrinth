"""Total active time is shared by both schedulers and survives safe-point resume."""

import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder, content_hash
from packages.domain.models import (
    AgentSpec,
    Budget,
    EpisodeArtifact,
    EventType,
    Message,
    ModelConfig,
    ModelResponse,
    RunConfig,
    RuntimeBackend,
    StepResult,
    TaskSpec,
    TerminationReason,
    ToolCall,
    ToolSchema,
)
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime
from packages.runtime.session import CheckpointFailure, SessionState

ROOT = Path(__file__).resolve().parents[2]


def inputs(backend: RuntimeBackend) -> tuple[AgentSpec, TaskSpec]:
    """Enable one second of total active time on the published order task."""
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    )
    agent = agent.model_copy(
        update={
            "runtime_backend": backend,
            "budget": Budget(schema_version="1.1", max_execution_time_ms=1000),
        }
    )
    task = TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )
    return agent, task


def run(
    agent: AgentSpec,
    task: TaskSpec,
    provider: FakeModelProvider,
    environment: ToolLabEnvironment | None = None,
) -> EpisodeArtifact:
    """Exercise the public Runner, including evaluation and final-event ownership."""
    return asyncio.run(
        run_episode(
            agent,
            task,
            RunConfig(),
            create_runtime(agent, provider),
            environment or ToolLabEnvironment(),
            OrderStatusEvaluator(),
        )
    )


def assert_stopped(artifact: EpisodeArtifact, calls: int, tools: int) -> None:
    """A deadline stop produces a safe failed artifact and exactly one terminal event."""
    assert artifact.episode.termination_reason == TerminationReason.TIME_BUDGET_EXCEEDED
    assert not artifact.evaluation.success
    assert artifact.episode.model_call_count == calls
    assert artifact.episode.tool_call_count == tools
    assert sum(e.event_type == EventType.EPISODE_FINISHED for e in artifact.events) == 1
    assert EpisodeArtifact.model_validate_json(artifact.model_dump_json()) == artifact


class SlowProvider(FakeModelProvider):
    """Cooperative slow request makes cancellation observable without network access."""

    cancelled = False

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        """Wait longer than the configured deadline and track local cancellation."""
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return await super().generate(messages, tools, config)


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_model_deadline_cancels_wait(backend: RuntimeBackend) -> None:
    """An unanswered request has unknown cost and cannot lead to tool execution."""
    agent, task = inputs(backend)
    agent = agent.model_copy(
        update={"budget": Budget(schema_version="1.1", max_execution_time_ms=80)}
    )
    provider = SlowProvider("success")
    artifact = run(agent, task, provider)
    assert_stopped(artifact, 1, 0)
    assert provider.cancelled
    assert "upstream_usage_unknown" in artifact.episode.detail
    assert not artifact.episode.estimated_cost.is_known
    assert not any(e.event_type == EventType.MODEL_RESPONDED for e in artifact.events)


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_returned_response_accounts_usage_before_stopping(backend: RuntimeBackend) -> None:
    """A slow response that returns before cancellation retains its actual usage."""
    agent, task = inputs(backend)
    clock = [0.0]

    class LateResponse(FakeModelProvider):
        async def generate(
            self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
        ) -> ModelResponse:
            """Advance the controllable monotonic clock after producing one response."""
            response = await super().generate(messages, tools, config)
            clock[0] = 2.0
            return response

    with patch("packages.runtime.session.perf_counter", side_effect=lambda: clock[0]):
        artifact = run(agent, task, LateResponse("success"))
    assert_stopped(artifact, 1, 0)
    assert artifact.episode.token_usage.prompt_tokens > 0
    assert any(e.event_type == EventType.MODEL_RESPONDED for e in artifact.events)


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("after_submission", [False, True])
def test_tool_saves_state_before_deadline_stop(
    backend: RuntimeBackend, after_submission: bool
) -> None:
    """Do not detach a running tool, lose its result or claim a late submission passed."""
    agent, task = inputs(backend)
    clock = [0.0]

    class LateTool(ToolLabEnvironment):
        def step(self, action: ToolCall) -> StepResult:
            """Finish the real simulated action, then advance time at the chosen boundary."""
            result = super().step(action)
            if (action.name == "submit_answer") == after_submission:
                clock[0] = 2.0
            return result

    with patch("packages.runtime.session.perf_counter", side_effect=lambda: clock[0]):
        artifact = run(agent, task, FakeModelProvider("success"), LateTool())
    expected = 2 if after_submission else 1
    assert_stopped(artifact, expected, expected)
    assert artifact.episode.final_state["acquired_evidence"] == ["order:ORD-001"]
    assert artifact.episode.final_state["done"] == after_submission
    assert any(e.event_type == EventType.ENVIRONMENT_UPDATED for e in artifact.events)


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_resume_keeps_elapsed_time(backend: RuntimeBackend) -> None:
    """Restoring an exhausted safe point starts no new model and keeps the Trace chain."""
    agent, task = inputs(backend)
    recorder = JsonTraceRecorder(RunConfig())
    saved: list[SessionState] = []

    def interrupt(state: SessionState) -> None:
        """Persist the initial safe point and emulate process termination."""
        saved.append(state)
        raise OSError("controlled interruption")

    with pytest.raises(CheckpointFailure):
        asyncio.run(
            run_episode(
                agent,
                task,
                RunConfig(),
                create_runtime(agent, FakeModelProvider("success")),
                ToolLabEnvironment(),
                OrderStatusEvaluator(),
                recorder=recorder,
                save_checkpoint=interrupt,
            )
        )
    state = SessionState.model_validate_json(
        saved[0].model_copy(update={"elapsed_ms": 1001}).model_dump_json()
    )
    artifact = asyncio.run(
        run_episode(
            agent,
            task,
            RunConfig(),
            create_runtime(agent, FakeModelProvider("success")),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
            recorder=recorder,
            resume_state=state,
        )
    )
    assert_stopped(artifact, 0, 0)
    assert artifact.episode.duration_ms >= 1001
    assert any(e.event_type == EventType.EPISODE_RESUMED for e in artifact.events)


def test_legacy_budget_bytes_and_hash_are_stable() -> None:
    """Old nested Budget serialization has no added null key or changed revision."""
    raw = json.loads(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    )["budget"]
    budget = Budget.model_validate_json(json.dumps(raw))
    assert budget.model_dump(mode="json") == raw
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    assert content_hash(budget) == hashlib.sha256(canonical.encode()).hexdigest()
    agent, _ = inputs("handwritten")
    assert agent.model_dump(mode="json")["budget"]["max_execution_time_ms"] == 1000


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_provider_timeout_is_not_a_total_deadline(backend: RuntimeBackend) -> None:
    """A provider's own TimeoutError before the deadline remains a provider failure."""
    agent, task = inputs(backend)

    class ProviderTimeout(FakeModelProvider):
        async def generate(
            self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
        ) -> ModelResponse:
            """Raise the local provider error without exhausting the Episode limit."""
            raise TimeoutError("private provider details")

    artifact = run(agent, task, ProviderTimeout())
    assert artifact.episode.termination_reason == TerminationReason.RUNTIME_ERROR
    assert artifact.episode.detail == "provider_error"
    assert "private provider details" not in artifact.model_dump_json()


@pytest.mark.parametrize("limit", [0, -1, 1.5, True])
def test_time_limit_is_strict_positive_integer(limit: object) -> None:
    """Reject coercion and nonpositive limits at the Domain boundary."""
    with pytest.raises(ValidationError):
        Budget.model_validate({"schema_version": "1.1", "max_execution_time_ms": limit})
    with pytest.raises(ValidationError):
        Budget.model_validate({"max_execution_time_ms": 1000})
