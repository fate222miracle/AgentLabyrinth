"""The metrics index reads only complete, provenance-matching experiments."""

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.service import EpisodeService
from packages.application.experiment import read_experiment, write_experiment


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
            assert item["provider"] == "fake"
            assert item["comparison_key"] is not None
            assert item["baseline_reference_cost"] is None
    finally:
        app.dependency_overrides.clear()


def test_dashboard_compatibility_and_legacy_records(tmp_path: Path) -> None:
    """Fixed inputs partition history; old records stay visible without joining trends."""
    service = EpisodeService(artifacts_dir=tmp_path)
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as client:
            keys = []
            for changes in (
                {},
                {},
                {"seeds": [2]},
                {"scenario": "invalid-then-success"},
                {"model": "another-fake"},
            ):
                response = client.post(
                    "/api/v1/experiments",
                    json={
                        "provider": "fake",
                        "model": "fake-model",
                        "scenario": "success",
                        "task_ids": ["order-status-001"],
                        **changes,
                    },
                )
                assert response.status_code == 201
                artifact_id = response.json()["experiment"]["experiment_id"]
                items = client.get("/api/v1/experiments").json()["items"]
                keys.append(
                    next(
                        item["comparison_key"]
                        for item in items
                        if item["experiment_id"] == artifact_id
                    )
                )
            assert keys[0] == keys[1]
            assert len(set(keys)) == 4

            legacy = read_experiment(Path(__file__).parents[1] / "fixtures/legacy_experiment.json")
            write_experiment(legacy, tmp_path / "experiments" / f"{legacy.experiment_id}.json")
            tampered = legacy.model_copy(update={"experiment_id": uuid4(), "config_hash": "wrong"})
            write_experiment(tampered, tmp_path / "experiments" / f"{tampered.experiment_id}.json")
            inconsistent = legacy.model_copy(update={"experiment_id": uuid4(), "pairs": []})
            write_experiment(
                inconsistent, tmp_path / "experiments" / f"{inconsistent.experiment_id}.json"
            )
            with patch("packages.providers.fake.FakeModelProvider.generate") as model:
                dashboard = client.get("/api/v1/experiments").json()
                model.assert_not_called()
            assert dashboard["skipped_count"] == 2
            old = next(
                item
                for item in dashboard["items"]
                if item["experiment_id"] == str(legacy.experiment_id)
            )
            assert old["comparison_key"] is None
            assert old["model_id"] == "fake-orders-v1"
    finally:
        app.dependency_overrides.clear()
