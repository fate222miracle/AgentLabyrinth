"""Unit tests for FastAPI endpoints (apps.api)."""

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.schemas import MetaResponse
from apps.api.service import EpisodeService


@pytest.fixture
def temp_artifacts_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for episode artifacts."""
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    return artifacts


@pytest.fixture
def client(temp_artifacts_dir: Path) -> Generator[TestClient, None, None]:
    """Test client with isolated temporary artifacts storage."""
    service = EpisodeService(artifacts_dir=temp_artifacts_dir)
    app.dependency_overrides[get_episode_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_meta(client: TestClient) -> None:
    """Verify discovery endpoint returns valid options and defaults."""
    resp = client.get("/api/v1/meta")
    assert resp.status_code == 200
    data = resp.json()
    meta = MetaResponse.model_validate(data)
    assert meta.default_model == "coding-glm-5.3-free"
    assert any(m.id == "coding-glm-5.3-free" and m.is_default for m in meta.models)
    assert any(m.id == "fake" for m in meta.models)
    assert any(m.id == "coding-kimi-k3-free" and m.is_experimental for m in meta.models)
    assert any(t.id == "order-status-001" for t in meta.tasks)


def test_create_fake_episode_success(client: TestClient, temp_artifacts_dir: Path) -> None:
    """Verify executing a fake success episode creates an artifact on disk and returns 201."""
    payload = {
        "provider": "fake",
        "model": "fake-model",
        "scenario": "success",
        "task_id": "order-status-001",
    }
    resp = client.post("/api/v1/episodes", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["schema_version"] == "1.0"
    artifact = body["artifact"]
    assert artifact["episode"]["termination_reason"] == "SUCCESS"
    assert artifact["evaluation"]["success"] is True

    # Verify file saved on disk
    episode_id = artifact["episode"]["episode_id"]
    saved_file = temp_artifacts_dir / f"{episode_id}.json"
    assert saved_file.is_file()


def test_create_fake_episode_failure(client: TestClient) -> None:
    """Verify failed runs still return 201 with viewable failed artifact, not fake success."""
    payload = {
        "provider": "fake",
        "model": "fake-model",
        "scenario": "wrong-answer",
        "task_id": "order-status-001",
    }
    resp = client.post("/api/v1/episodes", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    artifact = body["artifact"]
    assert artifact["episode"]["termination_reason"] == "FAILED"
    assert artifact["evaluation"]["success"] is False


def test_disallowed_model_rejected(client: TestClient) -> None:
    """Prohibit arbitrary or paid model strings from being executed."""
    payload = {
        "provider": "aihubmix",
        "model": "gpt-4o",  # Not in whitelist
        "task_id": "order-status-001",
    }
    resp = client.post("/api/v1/episodes", json=payload)
    assert resp.status_code in (400, 422)
    data = resp.json()
    assert data["schema_version"] == "1.0"
    assert "error_code" in data


def test_extra_forbidden_fields_rejected(client: TestClient) -> None:
    """Strict schema validation forbids unexpected fields."""
    payload = {
        "provider": "fake",
        "model": "fake-model",
        "extra_evil_field": "injected",
    }
    resp = client.post("/api/v1/episodes", json=payload)
    assert resp.status_code == 422


def test_get_episode_persistence_and_read_isolation(
    client: TestClient, temp_artifacts_dir: Path
) -> None:
    """Verify saved episode can be reloaded and reading NEVER invokes any model provider."""
    # 1. Create episode
    resp = client.post(
        "/api/v1/episodes",
        json={"provider": "fake", "model": "fake-model", "scenario": "success"},
    )
    assert resp.status_code == 201
    created_artifact = resp.json()["artifact"]
    episode_id = created_artifact["episode"]["episode_id"]

    # 2. Retrieve episode and assert no model provider call happens
    with patch("packages.providers.fake.FakeModelProvider.generate") as mock_fake_generate:
        with patch("packages.providers.aihubmix.AIHubMixModelProvider.generate") as mock_real:
            get_resp = client.get(f"/api/v1/episodes/{episode_id}")
            assert get_resp.status_code == 200
            retrieved_artifact = get_resp.json()["artifact"]
            assert retrieved_artifact["episode"]["episode_id"] == episode_id
            assert retrieved_artifact == created_artifact
            mock_fake_generate.assert_not_called()
            mock_real.assert_not_called()


def test_get_nonexistent_episode_404(client: TestClient) -> None:
    """Querying an unknown UUID returns sanitized 404."""
    random_id = uuid4()
    resp = client.get(f"/api/v1/episodes/{random_id}")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "REQUEST_FAILED"


def test_path_traversal_prevention(client: TestClient) -> None:
    """Attempting path traversal is rejected by path UUID validation."""
    resp = client.get("/api/v1/episodes/../../etc/passwd")
    assert resp.status_code in (404, 422)


def test_no_secret_or_absolute_path_leaks(client: TestClient) -> None:
    """Ensure response body and headers never leak environment secrets or local absolute paths."""
    test_secret = os.environ.get("AIHUBMIX_API_KEY", "")
    resp = client.post(
        "/api/v1/episodes",
        json={"provider": "fake", "model": "fake-model", "scenario": "success"},
    )
    assert resp.status_code == 201
    resp_text = resp.text

    if test_secret and len(test_secret) > 8:
        assert test_secret not in resp_text

    # Verify no local Windows user directory path leak
    assert "C:\\Users\\" not in resp_text
    assert "c:/users/" not in resp_text.lower()


def test_get_meta_returns_all_four_tasks(client: TestClient) -> None:
    """Verify get_meta includes all 4 native evaluation tasks."""
    resp = client.get("/api/v1/meta")
    assert resp.status_code == 200
    task_ids = {t["id"] for t in resp.json()["tasks"]}
    expected = {
        "order-status-001",
        "order-status-002",
        "order-status-003",
        "order-status-004",
    }
    assert expected.issubset(task_ids)


def test_create_and_get_experiment(client: TestClient, temp_artifacts_dir: Path) -> None:
    """Execute paired comparison experiment and verify persistence and read isolation."""
    payload = {
        "provider": "fake",
        "model": "fake-model",
        "scenario": "invalid-then-success",
        "task_ids": ["order-status-001", "order-status-002"],
        "seed": 1,
    }
    resp = client.post("/api/v1/experiments", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["schema_version"] == "1.0"
    exp = body["experiment"]
    assert exp["metrics"]["total_pairs"] == 2
    assert exp["metrics"]["baseline_success_count"] == 0
    assert exp["metrics"]["recovery_success_count"] == 2
    assert exp["metrics"]["retry_recovery_count"] == 2

    exp_id = exp["experiment_id"]
    saved_file = temp_artifacts_dir / "experiments" / f"{exp_id}.json"
    assert saved_file.is_file()

    # Read back and ensure no model invocation
    with patch("packages.providers.fake.FakeModelProvider.generate") as mock_fake:
        get_resp = client.get(f"/api/v1/experiments/{exp_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["experiment"]["experiment_id"] == exp_id
        mock_fake.assert_not_called()


def test_get_nonexistent_experiment_404(client: TestClient) -> None:
    """Non-existent experiment UUID returns 404."""
    random_id = uuid4()
    resp = client.get(f"/api/v1/experiments/{random_id}")
    assert resp.status_code == 404
