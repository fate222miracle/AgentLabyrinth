"""Reflection Challenge product entry and single-variable experiment."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore, resume_checkpointed_episode
from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import AgentSpec, EventType, ReflectionConfig, RunConfig, TaskSpec
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime
from packages.runtime.session import CheckpointFailure, SessionState

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    service = EpisodeService(
        artifacts_dir=tmp_path,
        database_path=tmp_path / "agentlabyrinth.sqlite3",
    )
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_single_reflection_is_explicit_and_saved(client: TestClient) -> None:
    meta = client.get("/api/v1/meta").json()
    task = next(item for item in meta["tasks"] if item["id"] == "reflection-stale-alias-001")
    assert task["supports_reflection"] is True

    response = client.post(
        "/api/v1/episodes",
        json={
            "schema_version": "1.8",
            "provider": "fake",
            "model": "fake",
            "scenario": "success",
            "task_id": "reflection-stale-alias-001",
            "reflection": {
                "schema_version": "1.0",
                "algorithm_version": "no-progress-revision-v1",
            },
        },
    )
    assert response.status_code == 201, response.text
    artifact = response.json()["artifact"]
    assert artifact["evaluation"]["success"] is True
    assert artifact["agent"]["reflection"]["algorithm_version"] == "no-progress-revision-v1"
    assert [event["event_type"] for event in artifact["events"]].count("REFLECTION_PRODUCED") == 1
    saved = client.get(f"/api/v1/episodes/{artifact['episode']['episode_id']}")
    assert saved.status_code == 200
    assert saved.json()["artifact"] == artifact


def test_reflection_experiment_changes_only_the_component(client: TestClient) -> None:
    response = client.post(
        "/api/v1/experiments",
        json={
            "schema_version": "1.11",
            "provider": "fake",
            "model": "fake",
            "scenario": "success",
            "task_ids": ["reflection-stale-alias-001"],
            "comparison_axis": "reflection",
            "runtime_backend": "handwritten",
            "runtime_strategy": "handwritten",
            "seed": 1,
            "repeat_count": 1,
        },
    )
    assert response.status_code == 201, response.text
    experiment = response.json()["experiment"]
    assert experiment["schema_version"] == "1.8"
    assert experiment["config"]["comparison_axis"] == "reflection"
    assert experiment["config"]["baseline_agent"].get("reflection") is None
    assert experiment["config"]["recovery_agent"]["reflection"]["algorithm_version"] == (
        "no-progress-revision-v1"
    )
    assert experiment["metrics"]["baseline_success_count"] == 0
    assert experiment["metrics"]["recovery_success_count"] == 1
    assert experiment["metrics"]["retry_eligible_count"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {
            "schema_version": "1.8",
            "provider": "fake",
            "model": "fake",
            "task_id": "order-status-001",
            "reflection": {"algorithm_version": "no-progress-revision-v1"},
        },
        {
            "schema_version": "1.11",
            "provider": "fake",
            "model": "fake",
            "task_ids": ["order-status-001"],
            "comparison_axis": "reflection",
        },
        {
            "schema_version": "1.8",
            "provider": "fake",
            "model": "fake",
            "task_id": "reflection-stale-alias-001",
            "tool_call_mode": "serial",
            "reflection": {"algorithm_version": "no-progress-revision-v1"},
        },
        {
            "schema_version": "1.11",
            "provider": "fake",
            "model": "fake",
            "task_ids": ["reflection-stale-alias-001"],
            "tool_call_mode": "serial",
            "comparison_axis": "reflection",
        },
    ],
)
def test_reflection_rejects_unapproved_tasks(
    client: TestClient, payload: dict[str, object]
) -> None:
    endpoint = "/api/v1/experiments" if "task_ids" in payload else "/api/v1/episodes"
    expected = 422 if payload.get("tool_call_mode") == "serial" else 400
    assert client.post(endpoint, json=payload).status_code == expected


def test_resume_after_reflection_does_not_repeat_it(tmp_path: Path) -> None:
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    ).model_copy(update={"schema_version": "1.5", "reflection": ReflectionConfig()})
    task = TaskSpec.model_validate_json(
        (
            ROOT
            / "benchmarks/tool_lab_core/tasks/reflection_challenge/reflection-stale-alias-001.json"
        ).read_text(encoding="utf-8")
    )
    config = RunConfig(runtime_version="handwritten-runtime-v1")
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(tmp_path / "checkpoints")

    def stop_after_reflection(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.reflection_overlay_pending:
            raise CheckpointFailure("simulated process stop")

    with pytest.raises(CheckpointFailure):
        asyncio.run(
            run_episode(
                agent,
                task,
                config,
                create_runtime(agent, FakeModelProvider("success")),
                ToolLabEnvironment(tool_set_version=agent.tool_set_version),
                OrderStatusEvaluator(),
                recorder=recorder,
                save_checkpoint=stop_after_reflection,
            )
        )
    checkpoint = store.load(recorder.episode_id)
    assert checkpoint.session.reflection_used is True
    assert checkpoint.session.reflection_overlay_pending is True

    artifact = asyncio.run(
        resume_checkpointed_episode(
            recorder.episode_id,
            create_runtime(
                agent,
                FakeModelProvider(
                    "success", initial_call_count=checkpoint.session.budget.model_call_count
                ),
            ),
            ToolLabEnvironment(tool_set_version=agent.tool_set_version),
            OrderStatusEvaluator(),
            tmp_path,
        )
    )
    assert artifact.evaluation.success is True
    assert sum(e.event_type == EventType.REFLECTION_PRODUCED for e in artifact.events) == 1
