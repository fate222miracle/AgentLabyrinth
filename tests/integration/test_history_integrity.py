"""History reads reject foreign identities and inconsistent saved comparisons."""

import asyncio
import json
import threading
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import pytest

from apps.api.main import _experiment_jobs, app, get_episode_service
from apps.api.schemas import CreateEpisodeRequest, ExperimentJobState
from apps.api.service import EpisodeService
from packages.application.checkpoint import read_completed_episode
from packages.application.experiment import read_experiment, write_experiment
from packages.application.trace import write_artifact


def test_corrupt_finished_episode_is_not_treated_as_missing(tmp_path: Path) -> None:
    """Never resume over a corrupt result: preserve its bytes and the checkpoint."""
    episode_id = uuid4()
    result = tmp_path / f"{episode_id}.json"
    result.write_bytes(b'{"damaged":')
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    checkpoint = checkpoints / f"{episode_id}.json"
    checkpoint.write_bytes(b"saved safe point")
    with pytest.raises(ValueError):
        read_completed_episode(episode_id, tmp_path)
    assert result.read_bytes() == b'{"damaged":'
    assert checkpoint.read_bytes() == b"saved safe point"


@pytest.mark.parametrize("damage", ["id", "hash", "pairs"])
def test_experiment_details_reject_inconsistent_history(tmp_path: Path, damage: str) -> None:
    """The details endpoint applies the same identity/hash/count checks as the index."""
    service = EpisodeService(artifacts_dir=tmp_path)
    legacy = read_experiment(Path(__file__).parents[1] / "fixtures/legacy_experiment.json")
    target_id = legacy.experiment_id
    changes: dict[str, object] = {}
    if damage == "id":
        changes["experiment_id"] = uuid4()
    elif damage == "hash":
        changes["config_hash"] = "wrong"
    else:
        changes["pairs"] = []
    write_experiment(
        legacy.model_copy(update=changes), tmp_path / "experiments" / f"{target_id}.json"
    )
    before = (tmp_path / "experiments" / f"{target_id}.json").read_bytes()

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get(f"/api/v1/experiments/{target_id}")
                assert response.status_code == 500
                assert response.json()["error_code"] == "INTERNAL_SERVER_ERROR"
                assert str(tmp_path) not in response.text
        finally:
            app.dependency_overrides.clear()

    with patch("packages.providers.fake.FakeModelProvider.generate") as model:
        asyncio.run(exercise())
        model.assert_not_called()
    assert (tmp_path / "experiments" / f"{target_id}.json").read_bytes() == before


def test_episode_foreign_file_is_rejected_before_rerun(tmp_path: Path) -> None:
    """A file placed under another UUID cannot become history or a rerun source."""
    service = EpisodeService(artifacts_dir=tmp_path)
    artifact = asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(provider="fake", model="fake-model", scenario="invalid-arguments")
        )
    )
    foreign_id = uuid4()
    write_artifact(artifact, tmp_path / f"{foreign_id}.json")
    with patch("packages.providers.fake.FakeModelProvider.generate") as model:
        with pytest.raises(ValueError, match="ID mismatch"):
            service.get_episode(foreign_id)
        with pytest.raises(ValueError, match="ID mismatch"):
            asyncio.run(service.rerun_failed_episode(foreign_id))
        model.assert_not_called()


@pytest.mark.parametrize(
    "reader,path,status",
    [
        ("get_experiment", "/api/v1/experiments/{id}", 404),
        ("resumable_episode_ids", "/api/v1/episodes/resumable", 200),
        ("resumable_experiment_ids", "/api/v1/experiments/resumable", 200),
        ("resumable_experiment_job_ids", "/api/v1/experiments/jobs/resumable", 200),
        ("get_experiment_job", "/api/v1/experiments/jobs/{id}", 404),
    ],
)
def test_slow_history_read_does_not_block_the_event_loop(
    tmp_path: Path, reader: str, path: str, status: int
) -> None:
    """Another request can complete while a history file waits in the IO thread."""
    service = EpisodeService(artifacts_dir=tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def slow_read(*ids: UUID) -> list[UUID] | None:
        entered.set()
        assert release.wait(timeout=2)
        return [] if reader.endswith("_ids") else None

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                request = asyncio.create_task(client.get(path.format(id=uuid4())))
                try:
                    assert await asyncio.to_thread(entered.wait, 1)
                    response = await asyncio.wait_for(client.get("/api/v1/meta"), 0.5)
                    assert response.status_code == 200 and not request.done()
                finally:
                    release.set()
                assert (await request).status_code == status
        finally:
            app.dependency_overrides.clear()

    with patch.object(service, reader, side_effect=slow_read):
        asyncio.run(exercise())


@pytest.mark.parametrize("active_before_read", [False, True])
def test_job_finishing_during_read_is_not_reported_as_interrupted(
    tmp_path: Path, active_before_read: bool
) -> None:
    """A snapshot taken during execution remains running; the next poll sees completion."""
    service = EpisodeService(artifacts_dir=tmp_path)
    job_id = uuid4()
    service.reserve_experiment_job(job_id)
    running = service.update_experiment_job(job_id, status="running")
    completed = running.model_copy(update={"status": "completed"})
    original = service.get_experiment_job
    entered = threading.Event()
    release = threading.Event()

    def slow_read(experiment_id: UUID) -> ExperimentJobState | None:
        snapshot = original(experiment_id)
        entered.set()
        assert release.wait(timeout=2)
        return snapshot

    async def exercise() -> None:
        finish = asyncio.Event()

        async def worker() -> None:
            await finish.wait()
            _experiment_jobs[job_id] = job
            service._save_job(completed)
            _experiment_jobs.pop(job_id, None)

        job = asyncio.create_task(worker())
        if active_before_read:
            _experiment_jobs[job_id] = job
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                request = asyncio.create_task(client.get(f"/api/v1/experiments/jobs/{job_id}"))
                try:
                    assert await asyncio.to_thread(entered.wait, 1)
                    finish.set()
                    await job
                finally:
                    release.set()
                response = await request
                assert response.status_code == 200
                assert response.json()["status"] == (
                    "running" if active_before_read else "completed"
                )
                assert (await client.get(f"/api/v1/experiments/jobs/{job_id}")).json()[
                    "status"
                ] == "completed"
        finally:
            release.set()
            finish.set()
            try:
                await job
            finally:
                _experiment_jobs.pop(job_id, None)
                app.dependency_overrides.clear()

    with patch.object(service, "get_experiment_job", side_effect=slow_read):
        asyncio.run(exercise())


def test_discovery_read_failure_is_sanitized(tmp_path: Path) -> None:
    """Moving reads to a worker cannot turn IO failure into empty success or leak paths."""
    service = EpisodeService(artifacts_dir=tmp_path)

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/experiments/jobs/resumable")
                assert response.status_code == 500
                assert response.json()["error_code"] == "INTERNAL_SERVER_ERROR"
                assert "private-source" not in response.text
        finally:
            app.dependency_overrides.clear()

    with patch.object(
        service, "resumable_experiment_job_ids", side_effect=OSError("private-source")
    ):
        asyncio.run(exercise())


@pytest.mark.parametrize(
    "directory,url",
    [
        ("checkpoints", "/api/v1/episodes/resumable"),
        ("experiments/checkpoints", "/api/v1/experiments/resumable"),
        ("experiments/jobs", "/api/v1/experiments/jobs/resumable"),
    ],
)
def test_corrupt_discovery_is_not_reported_as_empty(
    tmp_path: Path, directory: str, url: str
) -> None:
    """A damaged saved record must not silently disappear from discovery."""
    folder = tmp_path / directory
    folder.mkdir(parents=True)
    record = folder / f"{uuid4()}.json"
    record.write_text("{broken", encoding="utf-8")
    original = record.read_bytes()
    service = EpisodeService(artifacts_dir=tmp_path)

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get(url)
                assert response.status_code == 500
                assert "broken" not in response.text
        finally:
            app.dependency_overrides.clear()

    asyncio.run(exercise())
    assert record.read_bytes() == original


@pytest.mark.parametrize("operation", ["review", "reviews", "new_review", "rerun"])
def test_invalid_saved_data_is_not_echoed_in_api_errors(tmp_path: Path, operation: str) -> None:
    """Corrupt persisted input must fail without exposing Pydantic's input_value."""
    service = EpisodeService(artifacts_dir=tmp_path)
    episode = asyncio.run(
        service.execute_episode(CreateEpisodeRequest(provider="fake", model="fake-model"))
    )
    episode_id = episode.episode.episode_id
    review_id = uuid4()
    marker = "private-saved-content"
    if operation in {"review", "reviews"}:
        damaged = tmp_path / "reviews" / f"{review_id}.json"
        damaged.parent.mkdir()
    else:
        damaged = tmp_path / f"{episode_id}.json"
    damaged.write_text(json.dumps({"schema_version": marker}), encoding="utf-8")
    before = damaged.read_bytes()

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                if operation == "review":
                    response = await client.get(f"/api/v1/episode-reviews/{review_id}")
                elif operation == "reviews":
                    response = await client.get(f"/api/v1/episodes/{episode_id}/reviews")
                elif operation == "new_review":
                    response = await client.post(
                        "/api/v1/episode-reviews",
                        json={"episode_id": str(episode_id), "method": "llm_judge"},
                    )
                else:
                    response = await client.post(f"/api/v1/episodes/{episode_id}/rerun")
                assert response.status_code == (400 if operation == "new_review" else 409)
                assert response.json()["error_code"] == "REQUEST_FAILED"
                assert marker not in response.text
                assert "input_value" not in response.text
                assert str(tmp_path) not in response.text
        finally:
            app.dependency_overrides.clear()

    with patch("packages.providers.fake.FakeModelProvider.generate") as model:
        asyncio.run(exercise())
        model.assert_not_called()
    assert damaged.read_bytes() == before


@pytest.mark.parametrize("streaming", [False, True])
def test_invalid_task_catalog_is_not_echoed_in_execution_errors(
    tmp_path: Path, streaming: bool
) -> None:
    """Both ordinary and live execution redact invalid on-disk task values."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    marker = "private-task-content"
    (tasks_dir / "broken.json").write_text(json.dumps({"schema_version": marker}), encoding="utf-8")
    service = EpisodeService(artifacts_dir=tmp_path / "artifacts", tasks_dir=tasks_dir)

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                path = "/api/v1/episodes/stream" if streaming else "/api/v1/episodes"
                response = await client.post(
                    path,
                    json=CreateEpisodeRequest(provider="fake", model="fake-model").model_dump(
                        mode="json"
                    ),
                )
                assert response.status_code == (200 if streaming else 400)
                if streaming:
                    assert "event: error" in response.text
                    assert "event: complete" not in response.text
                    assert "VALIDATION_ERROR" in response.text
                else:
                    assert response.json()["error_code"] == "REQUEST_FAILED"
                assert marker not in response.text
                assert "input_value" not in response.text
                service.tasks_dir = tmp_path / "empty-task-catalog"
                business_error = await client.post(
                    path, json={"provider": "fake", "model": "fake-model"}
                )
                assert business_error.status_code == (200 if streaming else 400)
                assert "Task not found in the selected suite" in business_error.text
        finally:
            app.dependency_overrides.clear()

    with patch("packages.providers.fake.FakeModelProvider.generate") as model:
        asyncio.run(exercise())
        model.assert_not_called()


def test_missing_source_during_review_does_not_expose_its_path(tmp_path: Path) -> None:
    """A file disappearing between existence check and read is a safe client error."""
    service = EpisodeService(artifacts_dir=tmp_path)
    private_path = tmp_path / "private-source.json"

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/episode-reviews",
                    json={"episode_id": str(uuid4()), "method": "llm_judge"},
                )
                assert response.status_code == 400
                assert "private-source" not in response.text
                assert str(tmp_path) not in response.text
        finally:
            app.dependency_overrides.clear()

    with patch.object(
        service, "get_episode", side_effect=FileNotFoundError(2, "No such file", str(private_path))
    ):
        asyncio.run(exercise())
