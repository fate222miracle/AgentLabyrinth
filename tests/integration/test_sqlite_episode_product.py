"""Product checks for authoritative SQLite single-Episode persistence."""

import asyncio
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))

from apps.api.schemas import (  # noqa: E402
    CreateEpisodeRequest,
    CreateEpisodeReviewRequest,
    CreateExperimentRequest,
    HumanReviewInput,
)
from apps.api.service import EpisodeService  # noqa: E402
from packages.application.checkpoint import build_checkpoint  # noqa: E402
from packages.application.runner import run_episode  # noqa: E402
from packages.application.trace import JsonTraceRecorder, write_artifact  # noqa: E402
from packages.domain.models import AgentSpec, RunConfig, TaskSpec, TraceEvent  # noqa: E402
from packages.environments.tool_lab.environment import ToolLabEnvironment  # noqa: E402
from packages.evaluation.order_status import OrderStatusEvaluator  # noqa: E402
from packages.infrastructure.sqlite_episode_store import SQLiteEpisodeStore  # noqa: E402
from packages.providers.fake import FakeModelProvider  # noqa: E402
from packages.runtime.factory import create_runtime, runtime_version  # noqa: E402
from packages.runtime.session import SessionState  # noqa: E402


def _inputs() -> tuple[AgentSpec, TaskSpec, RunConfig]:
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    )
    task = TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )
    return agent, task, RunConfig(seed=1, runtime_version=runtime_version("handwritten"))


def _crash_after_first_tool(database: Path) -> None:
    agent, task, config = _inputs()
    recorder = JsonTraceRecorder(config)
    store = SQLiteEpisodeStore(database)

    def save(state: SessionState) -> None:
        store.save_checkpoint(build_checkpoint(state, agent, task, config, recorder, "success"))
        if state.next_node == "model" and state.budget.tool_call_count == 1:
            os._exit(0)

    asyncio.run(
        run_episode(
            agent,
            task,
            config,
            create_runtime(agent, FakeModelProvider()),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
            recorder=recorder,
            save_checkpoint=save,
        )
    )
    raise AssertionError("worker did not stop after its committed safety point")


def test_sqlite_service_is_authoritative_and_legacy_history_remains_readable(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"
    database = artifacts / "agentlabyrinth.sqlite3"
    service = EpisodeService(artifacts_dir=artifacts, database_path=database)
    arrived: list[TraceEvent] = []
    artifact = asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(provider="fake", model="fake-model", scenario="success"),
            on_event=arrived.append,
        )
    )
    episode_id = artifact.episode.episode_id
    assert database.is_file()
    assert not (artifacts / f"{episode_id}.json").exists()
    assert not (artifacts / "episode-inputs" / f"{episode_id}.json").exists()
    assert tuple(arrived) == artifact.events
    restarted = EpisodeService(artifacts_dir=artifacts, database_path=database)
    assert restarted.get_episode(episode_id) == artifact
    assert restarted._saved_fake_scenario(episode_id) == "success"

    legacy_service = EpisodeService(artifacts_dir=artifacts)
    legacy = asyncio.run(
        legacy_service.execute_episode(
            CreateEpisodeRequest(provider="fake", model="fake-model", scenario="success")
        )
    )
    assert restarted.get_episode(legacy.episode.episode_id) == legacy


def test_sqlite_checkpoint_survives_process_exit_and_resumes(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    database = artifacts / "agentlabyrinth.sqlite3"
    result = subprocess.run(
        [sys.executable, str(__file__), "--crash", str(database)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    restarted = EpisodeService(artifacts_dir=artifacts, database_path=database)
    resumable = restarted.resumable_episode_ids()
    assert len(resumable) == 1
    artifact = asyncio.run(restarted.resume_episode(resumable[0]))
    assert artifact.evaluation.success
    assert restarted.resumable_episode_ids() == []
    assert restarted.get_episode(resumable[0]) == artifact
    assert not (artifacts / f"{resumable[0]}.json").exists()


def test_sqlite_rejects_conflicts_and_online_backup_restores(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    database = artifacts / "agentlabyrinth.sqlite3"
    service = EpisodeService(artifacts_dir=artifacts, database_path=database)
    artifact = asyncio.run(
        service.execute_episode(CreateEpisodeRequest(provider="fake", model="fake-model"))
    )
    episode_id = artifact.episode.episode_id
    backup = tmp_path / "backup" / "agentlabyrinth.sqlite3"
    assert service._sqlite_store is not None
    service._sqlite_store.backup(backup)
    restored = SQLiteEpisodeStore(backup)
    assert restored.load_completed(episode_id) == artifact

    conflicting = artifact.model_copy(
        update={"evaluation": artifact.evaluation.model_copy(update={"reason": "changed"})}
    )
    with pytest.raises(ValueError, match="cannot be overwritten"):
        service._sqlite_store.save_completed(conflicting)
    assert service._sqlite_store.load_completed(episode_id) == artifact
    write_artifact(conflicting, artifacts / f"{episode_id}.json")
    with pytest.raises(ValueError, match="sources conflict"):
        service.get_episode(episode_id)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE episode_records SET payload='{}' WHERE episode_id=?", (str(episode_id),)
        )
    with pytest.raises(ValueError, match="digest"):
        service.get_episode(episode_id)
    with pytest.raises(FileExistsError):
        restored.backup(backup)


def test_sqlite_rejects_an_unrecognized_existing_database(tmp_path: Path) -> None:
    database = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE foreign_data (value TEXT)")
    with pytest.raises(ValueError, match="Unrecognized"):
        SQLiteEpisodeStore(database)


def test_sqlite_experiment_job_and_review_are_authoritative(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    database = artifacts / "agentlabyrinth.sqlite3"
    service = EpisodeService(artifacts_dir=artifacts, database_path=database)
    experiment = asyncio.run(
        service.execute_experiment(
            CreateExperimentRequest(
                provider="fake",
                model="fake-model",
                scenario="clean",
                task_ids=["order-status-001"],
            )
        )
    )
    assert not (artifacts / "experiments" / f"{experiment.experiment_id}.json").exists()
    assert all(
        not (artifacts / f"{episode_id}.json").exists() for episode_id in experiment.episode_ids
    )

    episode = service.get_episode(experiment.episode_ids[0])
    assert episode is not None
    review = asyncio.run(
        service.create_episode_review(
            CreateEpisodeReviewRequest(
                episode_id=episode.episode.episode_id,
                method="human",
                human=HumanReviewInput(
                    reviewer_label="tester",
                    verdict="pass",
                    answer_correctness="pass",
                    evidence_support="pass",
                    process_safety="pass",
                    rationale="SQLite review",
                ),
            )
        )
    )
    assert not (artifacts / "reviews" / f"{review.review_id}.json").exists()

    job_id = CreateExperimentRequest(provider="fake", model="fake-model").request_id
    plan = asyncio.run(
        service.prepare_experiment(
            CreateExperimentRequest(
                request_id=job_id,
                provider="fake",
                model="fake-model",
                task_ids=["order-status-001"],
            ),
            experiment_id=job_id,
        )
    )
    queued = service.reserve_experiment_job(job_id, plan)
    assert queued.status == "queued"
    assert not service._job_path(job_id).exists()

    restarted = EpisodeService(artifacts_dir=artifacts, database_path=database)
    assert restarted.get_experiment(experiment.experiment_id) == experiment
    assert restarted.get_episode_review(review.review_id) == review
    assert restarted.list_episode_reviews(episode.episode.episode_id) == (review,)
    assert restarted.get_experiment_job(job_id) == queued
    assert restarted.get_experiment_plan(job_id) == plan
    resumed = asyncio.run(restarted.resume_experiment_job(job_id))
    assert resumed.experiment_id == job_id
    assert restarted.get_experiment(job_id) == resumed
    assert restarted.get_experiment_plan(job_id) is None
    assert all(
        not (artifacts / f"{episode_id}.json").exists() for episode_id in resumed.episode_ids
    )


if __name__ == "__main__" and sys.argv[1:2] == ["--crash"]:
    _crash_after_first_tool(Path(sys.argv[2]))
