"""Read-only progress must expose owned saved work without executing missing arms."""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.experiment import (
    ExperimentArtifact,
    ExperimentCheckpoint,
    experiment_checkpoint_path,
    write_experiment_checkpoint,
)
from packages.application.trace import content_hash
from packages.domain.models import AgentSpec


def saved_sources(service: EpisodeService) -> tuple[ExperimentArtifact, dict[Path, bytes]]:
    """Capture genuine sources before normal successful cleanup removes them."""
    captured: dict[Path, bytes] = {}
    original_save = CheckpointStore.save

    def capture_plan(path: Path, plan: ExperimentCheckpoint) -> None:
        write_experiment_checkpoint(path, plan)
        captured[path] = path.read_bytes()

    def capture_checkpoint(store: CheckpointStore, *args: Any, **kwargs: Any) -> None:
        original_save(store, *args, **kwargs)
        captured.update({path: path.read_bytes() for path in store.directory.glob("*.json")})

    with (
        patch("apps.api.service.write_experiment_checkpoint", side_effect=capture_plan),
        patch.object(CheckpointStore, "save", capture_checkpoint),
    ):
        result = asyncio.run(
            service.execute_experiment(
                CreateExperimentRequest(
                    provider="fake",
                    model="fake-model",
                    scenario="clean",
                    task_ids=["order-status-001"],
                )
            )
        )
    plan_path = experiment_checkpoint_path(service.artifacts_dir, result.experiment_id)
    plan_path.write_bytes(captured[plan_path])
    return result, captured


@pytest.mark.parametrize(
    "damage",
    ["none", "checkpoint", "bad_checkpoint", "json", "hash", "agent", "trace", "duplicate"],
)
def test_progress_preserves_sources_and_classifies_each_arm(tmp_path: Path, damage: str) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    result, captured = saved_sources(service)
    pair = result.pairs[0]
    (tmp_path / "experiments" / f"{result.experiment_id}.json").unlink()
    right = tmp_path / f"{pair.recovery_episode_id}.json"
    if damage in ("none", "checkpoint", "bad_checkpoint"):
        right.unlink()
        if damage in ("checkpoint", "bad_checkpoint"):
            cp = tmp_path / "checkpoints" / right.name
            cp.write_bytes(captured[cp])
            if damage == "bad_checkpoint":
                cp.write_text("DO_NOT_ECHO", encoding="utf-8")
    elif damage == "json":
        right.write_text('{"secret":"DO_NOT_ECHO"', encoding="utf-8")
    else:
        data = json.loads(right.read_text(encoding="utf-8"))
        if damage == "hash":
            data["config_hashes"]["agent"] = "0" * 64
        elif damage == "agent":
            data["agent"]["name"] = "DO_NOT_ECHO"
            data["config_hashes"]["agent"] = content_hash(
                AgentSpec.model_validate_json(json.dumps(data["agent"]))
            )
        elif damage == "duplicate":
            data["events"].append(data["events"][0])
        else:
            data["events"][0]["episode_id"] = str(uuid4())
        right.write_text(json.dumps(data), encoding="utf-8")
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*.json")}
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with (
            TestClient(app) as client,
            patch("socket.socket.connect", side_effect=AssertionError("network")),
            patch(
                "packages.providers.fake.FakeModelProvider.generate", new_callable=AsyncMock
            ) as model,
            patch("packages.environments.tool_lab.environment.ToolLabEnvironment.step") as tool,
        ):
            response = client.get(f"/api/v1/experiments/{result.experiment_id}/progress")
            assert model.call_count == tool.call_count == 0
        assert response.status_code == 200, response.text
        left, missing = response.json()["arms"]
        assert left["state"] == "completed" and left["success"] is True
        assert left["episode_id"] == str(pair.baseline_episode_id)
        assert missing["episode_id"] == str(pair.recovery_episode_id)
        assert missing["state"] == {"none": "no_saved_record", "checkpoint": "checkpoint"}.get(
            damage, "invalid"
        )
        assert missing["success"] is missing["termination_reason"] is None
        assert "DO_NOT_ECHO" not in response.text
        assert before == {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*.json")
        }
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("damage", ["missing", "json", "identity"])
def test_unreadable_plan_has_sanitized_error(tmp_path: Path, damage: str) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    result, _ = saved_sources(service)
    path = experiment_checkpoint_path(tmp_path, result.experiment_id)
    if damage == "missing":
        path.unlink()
    elif damage == "json":
        path.write_text("DO_NOT_ECHO", encoding="utf-8")
    else:
        from packages.application.experiment import compute_config_hash

        data = json.loads(path.read_text(encoding="utf-8"))
        data["experiment_id"] = str(uuid4())
        data["plan_hash"] = compute_config_hash({k: v for k, v in data.items() if k != "plan_hash"})
        path.write_text(json.dumps(data), encoding="utf-8")
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/experiments/{result.experiment_id}/progress")
        assert response.status_code == (404 if damage == "missing" else 409)
        assert "DO_NOT_ECHO" not in response.text
    finally:
        app.dependency_overrides.clear()
