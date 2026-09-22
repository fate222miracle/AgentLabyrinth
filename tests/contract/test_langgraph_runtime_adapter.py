"""Contract test for the V0.2 LangGraph bootstrap adapter."""

import asyncio
from pathlib import Path

from packages.application.runner import run_episode
from packages.domain.models import AgentSpec, EpisodeArtifact, EventType, RunConfig, TaskSpec
from packages.domain.ports import AgentRuntime
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.handwritten.runtime import HandwrittenRuntime
from packages.runtime.langgraph import LangGraphRuntimeAdapter

ROOT = Path(__file__).resolve().parents[2]


def test_langgraph_adapter_preserves_episode_and_trace_contract() -> None:
    """The bootstrap graph must preserve the reference runtime's public result."""
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    )
    task = TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )

    async def run(runtime: AgentRuntime) -> EpisodeArtifact:
        return await run_episode(
            agent,
            task,
            RunConfig(seed=17),
            runtime,
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
        )

    reference = asyncio.run(run(HandwrittenRuntime(FakeModelProvider("normal"))))
    adapted = asyncio.run(
        run(LangGraphRuntimeAdapter(HandwrittenRuntime(FakeModelProvider("normal"))))
    )

    assert adapted.evaluation.success == reference.evaluation.success
    assert adapted.evaluation.reason == reference.evaluation.reason
    assert {
        key: value for key, value in adapted.evaluation.metrics.items() if key != "duration_ms"
    } == {key: value for key, value in reference.evaluation.metrics.items() if key != "duration_ms"}
    assert adapted.episode.model_dump(exclude={"episode_id", "duration_ms"}) == (
        reference.episode.model_dump(exclude={"episode_id", "duration_ms"})
    )
    assert [event.event_type for event in adapted.events] == [
        event.event_type for event in reference.events
    ]
    assert adapted.events[-1].event_type == EventType.EPISODE_FINISHED
