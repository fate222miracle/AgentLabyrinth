"""Prove a ToolLab checkpoint survives a process exit for both schedulers."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))

from packages.application.checkpoint import (  # noqa: E402
    CheckpointStore,
    resume_checkpointed_episode,
    run_checkpointed_episode,
)
from packages.application.runner import run_episode  # noqa: E402
from packages.application.trace import JsonTraceRecorder  # noqa: E402
from packages.domain.models import (  # noqa: E402
    AgentSpec,
    EpisodeArtifact,  # noqa: E402
    EventType,
    RunConfig,
    TaskSpec,
)
from packages.environments.tool_lab.environment import ToolLabEnvironment  # noqa: E402
from packages.evaluation.order_status import OrderStatusEvaluator  # noqa: E402
from packages.providers.fake import FakeModelProvider  # noqa: E402
from packages.runtime.factory import create_runtime, runtime_version  # noqa: E402


def inputs(backend: str, recovery: bool = False) -> tuple[AgentSpec, TaskSpec, RunConfig]:
    """Use the same published order task on both sides of the process break."""
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    ).model_copy(
        update={
            "runtime_backend": backend,
            "runtime_strategy": "handwritten_recovery" if recovery else "handwritten",
        }
    )
    task = TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )
    return agent, task, RunConfig(seed=17, runtime_version=runtime_version(agent.runtime_backend))


def child(backend: str, artifacts: Path, scenario: str = "success") -> None:
    """Exit exactly after the first committed ToolLab query checkpoint."""
    recovery = scenario == "invalid-then-success"
    agent, task, config = inputs(backend, recovery)
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(artifacts / "checkpoints")

    def save(state: object) -> None:
        from packages.runtime.session import SessionState

        assert isinstance(state, SessionState)
        store.save(state, agent, task, config, recorder, scenario)
        if state.next_node == "model" and (
            state.retried if recovery else state.budget.tool_call_count == 1
        ):
            os._exit(0)

    asyncio.run(
        run_episode(
            agent,
            task,
            config,
            create_runtime(agent, FakeModelProvider(scenario)),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
            recorder=recorder,
            save_checkpoint=save,
        )
    )
    raise AssertionError("Child failed to stop after the first tool")


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_resume_across_processes(backend: str, tmp_path: Path) -> None:
    """Committed tool, budget and Trace survive while one final event is produced."""
    result = subprocess.run(
        [sys.executable, str(__file__), "--child", backend, str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    files = list((tmp_path / "checkpoints").glob("*.json"))
    assert len(files) == 1
    episode_id = UUID(files[0].stem)
    checkpoint = CheckpointStore(files[0].parent).load(episode_id)
    assert checkpoint.session.budget.model_call_count == 1
    assert checkpoint.session.budget.tool_call_count == 1
    assert checkpoint.session.next_node == "model"

    from apps.api.main import app, get_episode_service
    from apps.api.service import EpisodeService

    service = EpisodeService(artifacts_dir=tmp_path)
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as client:
            listed = client.get("/api/v1/episodes/resumable")
            assert listed.status_code == 200
            assert str(episode_id) in listed.json()
            response = client.post(f"/api/v1/episodes/{episode_id}/resume")
            assert response.status_code == 200, response.text
            artifact = EpisodeArtifact.model_validate_json(json.dumps(response.json()["artifact"]))
            assert client.get("/api/v1/episodes/resumable").json() == []
    finally:
        app.dependency_overrides.clear()
    agent, _, _ = inputs(backend)
    assert artifact.evaluation.success
    assert artifact.episode.model_call_count == 2
    assert artifact.episode.tool_call_count == 2
    assert artifact.episode.token_usage.prompt_tokens == 80
    assert artifact.episode.episode_id == episode_id
    assert sum(e.event_type == EventType.EPISODE_RESUMED for e in artifact.events) == 1
    assert sum(e.event_type == EventType.EPISODE_FINISHED for e in artifact.events) == 1
    assert sum(e.event_type == EventType.TOOL_STARTED for e in artifact.events) == 2
    assert all(
        current.parent_event_id == previous.event_id
        for previous, current in zip(artifact.events, artifact.events[1:], strict=False)
    )
    assert not files[0].exists()
    assert (
        asyncio.run(
            resume_checkpointed_episode(
                episode_id,
                create_runtime(agent, FakeModelProvider("forbidden_tool")),
                ToolLabEnvironment(),
                OrderStatusEvaluator(),
                tmp_path,
            )
        )
        == artifact
    )


def test_tampered_checkpoint_rejected(tmp_path: Path) -> None:
    """A changed task cannot be resumed with an unchanged provenance hash."""
    agent, task, config = inputs("handwritten")
    recorder = JsonTraceRecorder(config)
    recorder.record(EventType.EPISODE_STARTED, 0, {"seed": config.seed})
    environment = ToolLabEnvironment()
    from packages.runtime.session import EpisodeSession

    session = EpisodeSession(agent, task, environment, recorder, FakeModelProvider(), None)
    session.observe()
    store = CheckpointStore(tmp_path)
    session.checkpoint("model", lambda state: store.save(state, agent, task, config, recorder))
    path = store.path(recorder.episode_id)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["task"]["name"] = "tampered"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        store.load(recorder.episode_id)


def test_completed_checkpointed_run_cleans_checkpoint(tmp_path: Path) -> None:
    """Normal completion leaves a readable artifact and no stale savepoint."""
    agent, task, config = inputs("handwritten")
    artifact = asyncio.run(
        run_checkpointed_episode(
            agent,
            task,
            config,
            create_runtime(agent, FakeModelProvider()),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
            tmp_path,
        )
    )
    assert artifact.evaluation.success
    assert (tmp_path / f"{artifact.episode.episode_id}.json").is_file()
    assert list((tmp_path / "checkpoints").glob("*.json")) == []


def test_fake_recovery_sequence_survives_restart(tmp_path: Path) -> None:
    """The Fake provider continues after its first invalid response."""
    result = subprocess.run(
        [
            sys.executable,
            str(__file__),
            "--child",
            "handwritten",
            str(tmp_path),
            "invalid-then-success",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    from apps.api.service import EpisodeService

    episode_id = UUID(next((tmp_path / "checkpoints").glob("*.json")).stem)
    service = EpisodeService(artifacts_dir=tmp_path)
    assert episode_id in service.resumable_episode_ids()
    artifact = asyncio.run(service.resume_episode(episode_id))
    assert artifact.evaluation.success
    assert artifact.episode.model_call_count == 3
    assert artifact.episode.tool_call_count == 2
    assert sum(e.event_type == EventType.EPISODE_RESUMED for e in artifact.events) == 1


if __name__ == "__main__" and sys.argv[1:2] == ["--child"]:
    child(sys.argv[2], Path(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else "success")
