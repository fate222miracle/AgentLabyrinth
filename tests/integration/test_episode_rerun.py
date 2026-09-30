"""Explicit failed-Episode reruns preserve source data and provenance."""

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateEpisodeRequest
from apps.api.service import EpisodeService


def test_failed_episode_rerun_preserves_original(tmp_path: Path) -> None:
    """The new run gets a new ID, exact saved inputs, and a versioned lineage file."""
    service = EpisodeService(artifacts_dir=tmp_path)
    source = asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(
                provider="fake",
                model="fake-orders-v1",
                scenario="wrong-answer",
                task_id="order-status-001",
            )
        )
    )
    assert not source.evaluation.success
    source_id = source.episode.episode_id
    original_path = tmp_path / f"{source_id}.json"
    original_bytes = original_path.read_bytes()
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/v1/episodes/{source_id}/rerun")
            assert response.status_code == 201, response.text
            rerun = response.json()["artifact"]
            rerun_id = rerun["episode"]["episode_id"]
            assert rerun_id != str(source_id)
            assert rerun["task"]["id"] == str(source.task.id)
            assert rerun["run_config"] == source.run_config.model_dump(mode="json")
            lineage = json.loads((tmp_path / "reruns" / f"{rerun_id}.json").read_text())
            assert lineage["source_episode_id"] == str(source_id)
            assert lineage["rerun_episode_id"] == rerun_id
            assert client.post(f"/api/v1/episodes/{rerun_id}/rerun").status_code == 201
    finally:
        app.dependency_overrides.clear()
    assert original_path.read_bytes() == original_bytes


def test_successful_episode_cannot_be_rerun(tmp_path: Path) -> None:
    """The endpoint is limited to explicit failure investigation."""
    service = EpisodeService(artifacts_dir=tmp_path)
    source = asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(provider="fake", model="fake-orders-v1", scenario="success")
        )
    )
    assert source.evaluation.success
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/v1/episodes/{source.episode.episode_id}/rerun")
            assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()
