"""The metrics index reads only complete, provenance-matching experiments."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.service import EpisodeService


def test_dashboard_reads_saved_experiment_and_counts_corruption(tmp_path: Path) -> None:
    """A broken sibling file cannot hide the valid run or trigger model calls."""
    service = EpisodeService(artifacts_dir=tmp_path)
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/experiments",
                json={
                    "provider": "fake",
                    "model": "fake-model",
                    "scenario": "success",
                    "task_ids": ["order-status-001"],
                },
            )
            assert created.status_code == 201, created.text
            experiment_id = created.json()["experiment"]["experiment_id"]
            (tmp_path / "experiments" / "broken.json").write_text("{", encoding="utf-8")
            with patch("packages.providers.fake.FakeModelProvider.generate") as model:
                response = client.get("/api/v1/experiments")
                model.assert_not_called()
            assert response.status_code == 200
            dashboard = response.json()
            assert dashboard["skipped_count"] == 1
            assert len(dashboard["items"]) == 1
            item = dashboard["items"][0]
            assert item["experiment_id"] == experiment_id
            assert item["environment_version"] == "tool-lab-m0-v1"
            assert item["total_pairs"] == 1
            assert item["baseline_success_rate"] == 1
    finally:
        app.dependency_overrides.clear()
