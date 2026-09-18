"""Integration tests for full M0 run_episode pipeline."""

import asyncio
from pathlib import Path
from uuid import uuid4

from packages.application.runner import run_episode
from packages.application.trace import read_artifact, write_artifact
from packages.domain.models import AgentSpec, RunConfig, TaskSpec, TerminationReason
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
        name="integration-agent",
        version="1.0.0",
        description="integration test agent",
        prompt_version="v1",
        tool_set_version="v1",
    )


def test_full_m0_pipeline_success_and_artifact_roundtrip(tmp_path: Path) -> None:
    """Run full episode pipeline, save artifact, load back and verify causal trace integrity."""
    agent = make_agent()
    task = load_task()
    config = RunConfig(seed=1)

    provider = FakeModelProvider(scenario="normal")
    environment = ToolLabEnvironment()
    runtime = HandwrittenRuntime(provider=provider)
    evaluator = OrderStatusEvaluator()

    artifact = asyncio.run(run_episode(agent, task, config, runtime, environment, evaluator))

    assert artifact.episode.termination_reason == TerminationReason.SUCCESS
    assert artifact.evaluation.success
    assert artifact.evaluation.metrics["tool_selection_accuracy"] == 1.0
    assert artifact.evaluation.metrics["tool_argument_validity_rate"] == 1.0
    assert artifact.events[0].parent_event_id is None
    assert all(
        current.parent_event_id == previous.event_id
        for previous, current in zip(artifact.events, artifact.events[1:], strict=False)
    )

    # Serialization roundtrip
    dest = tmp_path / "trace_artifact.json"
    write_artifact(artifact, dest)

    loaded = read_artifact(dest)
    assert loaded == artifact
    assert loaded.config_hashes["agent"] == artifact.config_hashes["agent"]
    assert loaded.config_hashes["task"] == artifact.config_hashes["task"]
