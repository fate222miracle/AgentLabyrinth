"""Unit tests for FastAPI endpoints (apps.api)."""

import hashlib
import json
import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.schemas import MetaResponse, is_model_permitted
from apps.api.service import EpisodeService
from packages.domain.models import ModelResponse, ToolCall
from packages.environments.bfcl.adapter import BFCLAdapter


def test_user_selected_models_are_permitted() -> None:
    """The four explicitly authorized model IDs pass the shared API gate."""
    for model in (
        "deepseek-v4-flash-0731-free",
        "qwen3.8-27b-free",
        "xiaomi-mimo-v2.5-pro-free",
        "coding-minimax-m2.7-free",
    ):
        assert is_model_permitted(model)
    assert not is_model_permitted("unapproved-paid-model")


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
    assert meta.default_model == "xiaomi-mimo-v2.5-pro-free"
    assert any(m.id == "xiaomi-mimo-v2.5-pro-free" and m.is_default for m in meta.models)
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


def test_execute_experiment_preserves_full_model_config_and_scenario(
    client: TestClient, temp_artifacts_dir: Path
) -> None:
    """API execution preserves authoritative model dictionary and resolved scenario."""
    # Scenario omitted, default should be resolved to 'invalid-then-success'
    payload = {
        "provider": "fake",
        "model": "fake-model",
        "task_ids": ["order-status-001"],
        "seed": 1,
    }
    resp = client.post("/api/v1/experiments", json=payload)
    assert resp.status_code == 201
    exp = resp.json()["experiment"]

    # Model configuration must be an authoritative dict, not a string
    assert isinstance(exp["config"]["model"], dict)
    assert exp["config"]["model"]["provider"] == "fake"
    assert exp["config"]["model"]["model"] == "fake-model"
    assert exp["config"]["model"]["temperature"] == 0.0
    assert exp["config"]["scenario"] == "invalid-then-success"

    config_hash_1 = exp["config_hash"]

    # Read back from disk via GET
    exp_id = exp["experiment_id"]
    get_resp = client.get(f"/api/v1/experiments/{exp_id}")
    assert get_resp.status_code == 200
    saved_cfg = get_resp.json()["experiment"]["config"]
    assert isinstance(saved_cfg["model"], dict)
    assert saved_cfg["scenario"] == "invalid-then-success"

    # Running with different scenario must change config_hash
    payload2 = {
        "provider": "fake",
        "model": "fake-model",
        "scenario": "success",
        "task_ids": ["order-status-001"],
        "seed": 1,
    }
    resp2 = client.post("/api/v1/experiments", json=payload2)
    assert resp2.status_code == 201
    exp2 = resp2.json()["experiment"]
    config_hash_2 = exp2["config_hash"]
    assert config_hash_1 != config_hash_2


def test_explicit_budget_is_saved_for_both_agents(client: TestClient) -> None:
    """An override is explicit and identical in both persisted episodes."""
    response = client.post(
        "/api/v1/experiments",
        json={
            "provider": "fake",
            "model": "fake-model",
            "task_ids": ["order-status-001"],
            "token_budget": 8000,
        },
    )
    assert response.status_code == 201
    experiment = response.json()["experiment"]
    assert experiment["config"]["token_budget"] == 8000
    for episode_id in experiment["episode_ids"]:
        artifact = client.get(f"/api/v1/episodes/{episode_id}").json()["artifact"]
        assert artifact["task"]["token_budget"] == 8000
        assert artifact["task"]["evaluator_config"]["source_token_budget"] == 1000
        assert artifact["agent"]["budget"]["max_prompt_tokens"] == 8000
    invalid = client.post(
        "/api/v1/episodes",
        json={
            "provider": "fake",
            "model": "fake-model",
            "token_budget": 20001,
        },
    )
    assert invalid.status_code == 422


def test_bfcl_episode_whitelist_and_readback_do_not_recall_model(
    tmp_path: Path,
) -> None:
    """Run one adapted case, reject unknown IDs, and read the saved trace offline."""
    case = {
        "id": "simple_python_test",
        "split": "evaluation",
        "question": "Calculate the factorial of 5.",
        "tool": {
            "name": "math.factorial",
            "description": "Calculate a factorial.",
            "parameters": {
                "type": "object",
                "properties": {"number": {"type": "integer"}},
                "required": ["number"],
            },
        },
        "ground_truth": {"math.factorial": {"number": [5]}},
    }
    subset = tmp_path / "subset.json"
    subset.write_text(json.dumps([case]), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "checksum": hashlib.sha256(subset.read_bytes()).hexdigest(),
                "selected_cases": {"development": [], "evaluation": [case["id"]]},
                "evaluator_version": "bfcl-local-exact-v1",
                "source_version_or_commit": "test",
                "adapter_version": "test",
                "result_label": "AgentLabyrinth-adapted subset",
            }
        ),
        encoding="utf-8",
    )
    service = EpisodeService(artifacts_dir=tmp_path / "artifacts")
    service.bfcl = BFCLAdapter(manifest, subset)
    app.dependency_overrides[get_episode_service] = lambda: service
    response = ModelResponse(
        action=ToolCall(call_id="bfcl-1", name="math.factorial", arguments={"number": 5})
    )
    try:
        with TestClient(app) as test_client:
            with patch(
                "packages.providers.fake.FakeModelProvider.generate",
                new=AsyncMock(return_value=response),
            ) as generate:
                created = test_client.post(
                    "/api/v1/episodes",
                    json={
                        "provider": "fake",
                        "model": "fake-model",
                        "suite": "bfcl_adapted",
                        "task_id": "bfcl-simple_python_test",
                    },
                )
                assert created.status_code == 201
                assert created.json()["artifact"]["evaluation"]["success"] is True
                assert generate.await_count == 1

            episode_id = created.json()["artifact"]["episode"]["episode_id"]
            with patch("packages.providers.fake.FakeModelProvider.generate") as generate:
                loaded = test_client.get(f"/api/v1/episodes/{episode_id}")
                assert loaded.status_code == 200
                generate.assert_not_called()

            invalid = test_client.post(
                "/api/v1/episodes",
                json={
                    "provider": "fake",
                    "model": "fake-model",
                    "suite": "bfcl_adapted",
                    "task_id": "unknown",
                },
            )
            assert invalid.status_code == 400
    finally:
        app.dependency_overrides.clear()
