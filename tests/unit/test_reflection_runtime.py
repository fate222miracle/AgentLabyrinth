"""Bounded no-progress reflection shared by every Runtime scheduler."""

import asyncio
from pathlib import Path

import pytest

from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    AgentSpec,
    EpisodeArtifact,
    EventType,
    FinalAnswer,
    Message,
    ModelConfig,
    ModelResponse,
    ReflectionConfig,
    RunConfig,
    RuntimeBackend,
    TaskSpec,
    ToolCall,
    ToolSchema,
)
from packages.domain.ports import ModelProviderError
from packages.environments.tool_lab.environment import ToolLabEnvironment, create_tool_lab_registry
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator

ROOT = Path(__file__).resolve().parents[2]


def inputs(reflection: bool = True) -> tuple[AgentSpec, TaskSpec]:
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    ).model_copy(
        update={
            "schema_version": "1.5" if reflection else "1.1",
            "reflection": ReflectionConfig() if reflection else None,
        }
    )
    task = TaskSpec.model_validate_json(
        (
            ROOT
            / "benchmarks/tool_lab_core/tasks/reflection_challenge/reflection-stale-alias-001.json"
        ).read_text(encoding="utf-8")
    )
    return agent, task


def run(
    provider: FakeModelProvider,
    backend: RuntimeBackend = "handwritten",
    reflection: bool = True,
    max_model_calls: int | None = None,
) -> EpisodeArtifact:
    agent, task = inputs(reflection)
    agent = agent.model_copy(
        update={
            "runtime_backend": backend,
            **(
                {"budget": agent.budget.model_copy(update={"max_model_calls": max_model_calls})}
                if max_model_calls is not None
                else {}
            ),
        }
    )
    registry = create_tool_lab_registry()
    validator = DefaultToolValidator(registry)
    config = RunConfig(runtime_version="test")
    recorder = JsonTraceRecorder(config)
    return asyncio.run(
        run_episode(
            agent,
            task,
            config,
            create_runtime(agent, provider, validator),
            ToolLabEnvironment(
                registry=registry,
                executor=ToolExecutor(registry, validator),
                validator=validator,
                tool_set_version=agent.tool_set_version,
            ),
            OrderStatusEvaluator(),
            recorder=recorder,
        )
    )


@pytest.mark.parametrize("backend", ["handwritten", "langgraph", "pydantic_ai"])
def test_reflection_revises_one_stale_alias_across_runtimes(backend: RuntimeBackend) -> None:
    artifact = run(FakeModelProvider("success"), backend)

    assert artifact.evaluation.success is True
    produced = [e for e in artifact.events if e.event_type == EventType.REFLECTION_PRODUCED]
    assert len(produced) == 1
    sources = produced[0].payload["source_event_ids"]
    assert isinstance(sources, list) and len(sources) == 2
    assert artifact.episode.model_call_count == 5
    assert artifact.episode.tool_call_count == 4


def test_plain_baseline_receives_no_hidden_canonical_hint() -> None:
    artifact = run(FakeModelProvider("success"), reflection=False)

    assert artifact.evaluation.success is False
    assert all(e.event_type != EventType.REFLECTION_PRODUCED for e in artifact.events)


def test_invalid_reflection_is_rejected_without_retry() -> None:
    responses = [
        ModelResponse(
            action=ToolCall(
                call_id=f"stale-{index}",
                name="query_records",
                arguments={"table": "orders", "filters": {"order_id": "ORD-OLD-001"}},
            )
        )
        for index in (1, 2)
    ]
    responses.append(ModelResponse(action=FinalAnswer(text="not-json")))
    artifact = run(FakeModelProvider(custom_responses=responses))

    assert artifact.episode.detail == "invalid_reflection"
    assert artifact.episode.model_call_count == 3
    assert sum(e.event_type == EventType.REFLECTION_REJECTED for e in artifact.events) == 1


class ReflectionProbe(FakeModelProvider):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__("success")
        self.fail = fail
        self.reflection_messages: list[Message] | None = None

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        if any(
            isinstance(message.content, dict)
            and "_agentlabyrinth_reflection_request" in message.content
            for message in messages
        ):
            self.reflection_messages = list(messages)
            if self.fail:
                raise ModelProviderError("NETWORK_CONNECTION_FAILED")
        return await super().generate(messages, tools, config)


def test_reflection_request_contains_only_public_task_feedback() -> None:
    provider = ReflectionProbe()
    artifact = run(provider)

    assert artifact.evaluation.success is True
    serialized = " ".join(
        message.model_dump_json() for message in provider.reflection_messages or []
    )
    assert "goal_conditions" not in serialized
    assert '"shipped"' not in serialized
    assert "ORD-001" in serialized  # Public task text, not a hidden evaluator answer.


def test_reflection_provider_failure_keeps_runtime_failure_and_never_retries() -> None:
    artifact = run(ReflectionProbe(fail=True))

    assert artifact.episode.termination_reason == "RUNTIME_ERROR"
    assert artifact.episode.detail == "provider_error: NETWORK_CONNECTION_FAILED"
    assert artifact.episode.model_call_count == 3
    assert sum(e.event_type == EventType.REFLECTION_REJECTED for e in artifact.events) == 1


def test_reflection_budget_failure_records_rejection_without_request() -> None:
    artifact = run(FakeModelProvider("success"), max_model_calls=2)

    assert artifact.episode.model_call_count == 2
    assert sum(e.event_type == EventType.REFLECTION_REJECTED for e in artifact.events) == 1
    reflection_requests = [
        e
        for e in artifact.events
        if e.event_type == EventType.MODEL_REQUESTED and e.payload.get("purpose") == "reflection"
    ]
    assert reflection_requests == []


def test_different_successful_read_does_not_trigger_reflection() -> None:
    responses = [
        ModelResponse(
            action=ToolCall(
                call_id="stale",
                name="query_records",
                arguments={"table": "orders", "filters": {"order_id": "ORD-OLD-001"}},
            )
        ),
        ModelResponse(
            action=ToolCall(
                call_id="canonical",
                name="query_records",
                arguments={"table": "orders", "filters": {"order_id": "ORD-001"}},
            )
        ),
        ModelResponse(
            action=ToolCall(
                call_id="submit",
                name="submit_answer",
                arguments={"answer": "shipped", "evidence": ["order:ORD-001"]},
            )
        ),
    ]
    artifact = run(FakeModelProvider(custom_responses=responses))

    assert artifact.evaluation.success is True
    assert all(
        event.event_type not in (EventType.REFLECTION_PRODUCED, EventType.REFLECTION_REJECTED)
        for event in artifact.events
    )
