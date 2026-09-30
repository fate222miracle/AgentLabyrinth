"""Durable Experiment jobs stop only between Episodes and preserve completed arms."""

import asyncio
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4, uuid5

import httpx
import pytest

from apps.api.main import app, get_episode_service
from apps.api.service import EpisodeService
from packages.domain.models import Message, ModelConfig, ModelResponse, ToolSchema
from packages.providers.fake import FakeModelProvider


def test_job_recovers_after_process_exit(tmp_path: Path) -> None:
    """An orphaned real process leaves a resumable job and an immutable completed arm."""
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("_checkpoint_worker.py")),
            "experiment",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    plan = next((tmp_path / "experiments/checkpoints").glob("*.json"))
    job_id = plan.stem
    baseline = tmp_path / f"{uuid5(UUID(job_id), '0:baseline')}.json"
    before = baseline.read_bytes()
    service = EpisodeService(artifacts_dir=tmp_path)

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                assert (await client.get(f"/api/v1/experiments/jobs/{job_id}")).json()[
                    "status"
                ] == "interrupted"
                assert job_id in (await client.get("/api/v1/experiments/jobs/resumable")).json()
                assert (
                    await client.post(f"/api/v1/experiments/jobs/{job_id}/resume")
                ).status_code == 200
                for _ in range(200):
                    state = (await client.get(f"/api/v1/experiments/jobs/{job_id}")).json()
                    if state["status"] == "completed":
                        break
                    await asyncio.sleep(0.01)
                assert state["status"] == "completed"
                assert (await client.get("/api/v1/experiments/jobs/resumable")).json() == []
        finally:
            app.dependency_overrides.clear()

    asyncio.run(exercise())
    assert baseline.read_bytes() == before
    assert not plan.exists()


def test_failed_job_cannot_be_requeued(tmp_path: Path) -> None:
    """The API must reject failed jobs before overwriting their persisted error state."""
    service = EpisodeService(artifacts_dir=tmp_path)
    job_id = uuid4()
    service.reserve_experiment_job(job_id)
    service.update_experiment_job(
        job_id, status="failed", error_code="REFERENCE_COST_BUDGET_EXCEEDED"
    )

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/api/v1/experiments/jobs/{job_id}/resume")
                assert response.status_code == 409
        finally:
            app.dependency_overrides.clear()

    asyncio.run(exercise())
    state = service.get_experiment_job(job_id)
    assert state is not None and state.status == "failed"
    assert state.error_code == "REFERENCE_COST_BUDGET_EXCEEDED"


@pytest.mark.parametrize("action", ["pause", "cancel"])
def test_experiment_job_stops_at_arm_boundary(tmp_path: Path, action: str) -> None:
    """A requested stop never discards or replays an already finished Episode."""
    service = EpisodeService(artifacts_dir=tmp_path)
    original = FakeModelProvider.generate
    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed(
        self: FakeModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        if not started.is_set():
            started.set()
            await release.wait()
        return await original(self, messages, tools, config)

    async def wait_status(client: httpx.AsyncClient, job_id: str, target: str) -> None:
        for _ in range(200):
            response = await client.get(f"/api/v1/experiments/jobs/{job_id}")
            if response.json()["status"] == target:
                return
            await asyncio.sleep(0.01)
        pytest.fail(f"Experiment did not reach {target}")

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/experiments/jobs",
                    json={
                        "provider": "fake",
                        "model": "fake-model",
                        "scenario": "success",
                        "task_ids": ["order-status-001"],
                    },
                )
                assert response.status_code == 202, response.text
                job_id = response.json()["experiment_id"]
                await asyncio.wait_for(started.wait(), 2)
                response = await client.post(f"/api/v1/experiments/jobs/{job_id}/{action}")
                assert response.status_code == 200
                release.set()
                await wait_status(client, job_id, "paused" if action == "pause" else "cancelled")
                baseline = tmp_path / f"{uuid5(UUID(job_id), '0:baseline')}.json"
                recovery = tmp_path / f"{uuid5(UUID(job_id), '0:recovery')}.json"
                assert baseline.is_file()
                assert not recovery.exists()
                baseline_bytes = baseline.read_bytes()
                if action == "pause":
                    await asyncio.sleep(0)
                    assert UUID(job_id) in service.resumable_experiment_job_ids()
                    assert job_id in (await client.get("/api/v1/experiments/jobs/resumable")).json()
                    assert (
                        await client.post(f"/api/v1/experiments/{job_id}/resume")
                    ).status_code == 400
                    resumed = await client.post(f"/api/v1/experiments/jobs/{job_id}/resume")
                    assert resumed.status_code == 200, resumed.text
                    await wait_status(client, job_id, "completed")
                    assert recovery.is_file()
                    assert baseline.read_bytes() == baseline_bytes
                    assert (tmp_path / "experiments" / f"{job_id}.json").is_file()
                else:
                    assert UUID(job_id) not in service.resumable_experiment_job_ids()
                    assert (
                        await client.post(f"/api/v1/experiments/jobs/{job_id}/resume")
                    ).status_code == 409
                    restarted = EpisodeService(artifacts_dir=tmp_path)
                    assert UUID(job_id) not in restarted.resumable_experiment_ids()
        finally:
            app.dependency_overrides.clear()

    with patch.object(FakeModelProvider, "generate", delayed):
        asyncio.run(exercise())


def test_two_experiments_run_while_third_waits(tmp_path: Path) -> None:
    """The local job scheduler bounds cross-Experiment concurrency at two."""
    service = EpisodeService(artifacts_dir=tmp_path)
    original = FakeModelProvider.generate
    two_started = asyncio.Event()
    release = asyncio.Event()
    started_count = 0

    async def delayed(
        self: FakeModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        nonlocal started_count
        if not release.is_set():
            started_count += 1
            if started_count == 2:
                two_started.set()
            await release.wait()
        return await original(self, messages, tools, config)

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                ids = []
                for _ in range(3):
                    response = await client.post(
                        "/api/v1/experiments/jobs",
                        json={
                            "provider": "fake",
                            "model": "fake-model",
                            "scenario": "success",
                            "task_ids": ["order-status-001"],
                        },
                    )
                    assert response.status_code == 202
                    ids.append(response.json()["experiment_id"])
                await asyncio.wait_for(two_started.wait(), 2)
                statuses = [
                    (await client.get(f"/api/v1/experiments/jobs/{job_id}")).json()["status"]
                    for job_id in ids
                ]
                assert statuses == ["running", "running", "queued"]
                assert started_count == 2
                release.set()
                for _ in range(200):
                    statuses = [
                        (await client.get(f"/api/v1/experiments/jobs/{job_id}")).json()["status"]
                        for job_id in ids
                    ]
                    if statuses == ["completed"] * 3:
                        break
                    await asyncio.sleep(0.01)
                assert statuses == ["completed"] * 3
        finally:
            app.dependency_overrides.clear()

    with patch.object(FakeModelProvider, "generate", delayed):
        asyncio.run(exercise())
