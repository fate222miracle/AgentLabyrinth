"""A paired experiment resumes its original matrix after a process interruption."""

import asyncio
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid5

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.experiment import read_experiment_checkpoint
from packages.domain.models import Message, ModelConfig, ModelResponse, ToolSchema
from packages.providers.fake import FakeModelProvider


def test_experiment_resume_reuses_completed_arm(tmp_path: Path) -> None:
    """The second arm may restart; the completed first arm must stay byte-identical."""
    service = EpisodeService(artifacts_dir=tmp_path)
    original = FakeModelProvider.generate
    calls = 0

    async def interrupt(
        self: FakeModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise SystemExit(0)
        return await original(self, messages, tools, config)

    request = CreateExperimentRequest(
        provider="fake", model="fake-model", scenario="success", task_ids=["order-status-001"]
    )
    with patch.object(FakeModelProvider, "generate", interrupt), pytest.raises(SystemExit):
        asyncio.run(service.execute_experiment(request))

    plans = list((tmp_path / "experiments" / "checkpoints").glob("*.json"))
    assert len(plans) == 1
    experiment_id = UUID(plans[0].stem)
    plan = read_experiment_checkpoint(plans[0])
    assert plan.experiment_id == experiment_id
    baseline_id = uuid5(experiment_id, "0:baseline")
    baseline_path = tmp_path / f"{baseline_id}.json"
    baseline_bytes = baseline_path.read_bytes()
    (tmp_path / "experiments" / f"{experiment_id}.json").write_text("{", encoding="utf-8")

    restarted = EpisodeService(artifacts_dir=tmp_path)
    app.dependency_overrides[get_episode_service] = lambda: restarted
    try:
        with TestClient(app) as client:
            assert str(experiment_id) in client.get("/api/v1/experiments/resumable").json()
            response = client.post(f"/api/v1/experiments/{experiment_id}/resume")
            assert response.status_code == 200, response.text
            result = response.json()["experiment"]
            assert result["experiment_id"] == str(experiment_id)
            assert result["episode_ids"][0] == str(baseline_id)
            assert result["metrics"]["total_pairs"] == 1
            assert client.get("/api/v1/experiments/resumable").json() == []
    finally:
        app.dependency_overrides.clear()
    assert baseline_path.read_bytes() == baseline_bytes
    assert not plans[0].exists()
    assert (tmp_path / "experiments" / f"{experiment_id}.json").is_file()


def test_changed_experiment_plan_rejected(tmp_path: Path) -> None:
    """A changed run matrix cannot silently reuse previously recorded episodes."""
    service = EpisodeService(artifacts_dir=tmp_path)
    request = CreateExperimentRequest(
        provider="fake", model="fake-model", task_ids=["order-status-001"]
    )

    async def interrupt(
        self: FakeModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        raise SystemExit(0)

    with patch.object(FakeModelProvider, "generate", interrupt), pytest.raises(SystemExit):
        asyncio.run(service.execute_experiment(request))
    plan = next((tmp_path / "experiments" / "checkpoints").glob("*.json"))
    text = plan.read_text(encoding="utf-8").replace('"repeat_count": 1', '"repeat_count": 2')
    plan.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        read_experiment_checkpoint(plan)
