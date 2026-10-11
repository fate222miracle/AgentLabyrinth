"""Global reported-token admission preserves stopped work and old experiment semantics."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid5

import httpx
import pytest
from pydantic import ValidationError

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.experiment import (
    ExperimentTokenBudgetError,
    read_experiment_checkpoint,
)
from packages.application.regression import fixed_config
from packages.domain.models import Message, ModelConfig, ModelResponse, ToolSchema
from packages.domain.ports import ModelProviderError
from packages.providers.fake import FakeModelProvider
from scripts.run_regression import preflight


def request(**changes: object) -> CreateExperimentRequest:
    """Use one two-call task with 120 simulated Tokens per completed arm."""
    return CreateExperimentRequest.model_validate(
        {
            "provider": "fake",
            "model": "fake-model",
            "scenario": "success",
            "task_ids": ["order-status-001"],
            **changes,
        }
    )


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "120", 1_000_000_001])
def test_invalid_global_limit_is_rejected(limit: object) -> None:
    with pytest.raises(ValidationError):
        request(max_total_tokens=limit)
    with pytest.raises(ValidationError, match="revision 1.4"):
        request(max_total_tokens=120, schema_version="1.3")


@pytest.mark.parametrize("limit,arms", [(1, 1), (120, 1), (121, 2), (240, 2), (241, 3)])
def test_boundary_stops_matrix_and_restart_cannot_reset_usage(
    tmp_path: Path, limit: int, arms: int
) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    with pytest.raises(ExperimentTokenBudgetError, match="BUDGET_EXCEEDED"):
        asyncio.run(
            service.execute_experiment(
                request(max_total_tokens=limit, seeds=[1, 17], repeat_count=2)
            )
        )
    saved = sorted(tmp_path.glob("*.json"))
    assert len(saved) == arms
    before = {path.name: path.read_bytes() for path in saved}
    plan_path = next((tmp_path / "experiments/checkpoints").glob("*.json"))
    plan = read_experiment_checkpoint(plan_path)
    assert plan.schema_version == "1.1" and plan.config_metadata["max_total_tokens"] == limit
    restarted = EpisodeService(artifacts_dir=tmp_path)
    with patch.object(FakeModelProvider, "generate") as model:
        with pytest.raises(ExperimentTokenBudgetError, match="BUDGET_EXCEEDED"):
            asyncio.run(restarted.resume_experiment(plan.experiment_id))
        model.assert_not_called()
    assert before == {path.name: path.read_bytes() for path in saved}
    assert not (tmp_path / "experiments" / f"{plan.experiment_id}.json").exists()


def test_final_arm_may_overshoot_without_changing_per_episode_budget(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    result = asyncio.run(service.execute_experiment(request(max_total_tokens=121)))
    assert result.schema_version == "1.3"
    assert result.metrics.baseline_total_tokens + result.metrics.recovery_total_tokens == 240
    assert result.config["max_total_tokens"] == 121
    for episode_id in result.episode_ids:
        artifact = service.get_episode(episode_id)
        assert artifact is not None
        assert artifact.agent.budget.max_prompt_tokens == 1000
        assert artifact.task.token_budget == 1000
    assert fixed_config(result)["max_total_tokens"] == 121
    with pytest.raises(ValueError, match="pinned baseline"):
        preflight(result, request(max_total_tokens=122), service)


@pytest.mark.parametrize("limit,resume_calls", [(180, 0), (181, 1)])
def test_cross_process_safe_point_is_counted_once(
    tmp_path: Path, limit: int, resume_calls: int
) -> None:
    worker = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("_checkpoint_worker.py")),
            "experiment-tokens",
            str(tmp_path),
            str(limit),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert worker.returncode == 0, worker.stderr
    plan = read_experiment_checkpoint(next((tmp_path / "experiments/checkpoints").glob("*.json")))
    base_path = tmp_path / f"{uuid5(plan.experiment_id, '0:baseline')}.json"
    before = base_path.read_bytes()
    service = EpisodeService(artifacts_dir=tmp_path)
    calls = 0
    original = FakeModelProvider.generate

    async def counted(
        self: FakeModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        nonlocal calls
        calls += 1
        return await original(self, messages, tools, config)

    with patch.object(FakeModelProvider, "generate", counted):
        with pytest.raises(ExperimentTokenBudgetError, match="BUDGET_EXCEEDED"):
            asyncio.run(service._resume_experiment_once(plan.experiment_id))
    assert calls == resume_calls
    assert base_path.read_bytes() == before
    if resume_calls:
        recovery = service.get_episode(uuid5(plan.experiment_id, "0:recovery"))
        assert recovery is not None and recovery.episode.model_call_count == 2
        assert (
            recovery.episode.token_usage.prompt_tokens
            + recovery.episode.token_usage.completion_tokens
            == 120
        )


def test_unreported_provider_usage_stops_now_and_after_restart(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    with patch.object(
        FakeModelProvider, "generate", side_effect=ModelProviderError("REQUEST_TIMEOUT")
    ) as model:
        with pytest.raises(ExperimentTokenBudgetError, match="USAGE_UNKNOWN"):
            asyncio.run(service.execute_experiment(request(max_total_tokens=1000)))
        assert model.call_count == 1
    assert len(list(tmp_path.glob("*.json"))) == 1
    plan_path = next((tmp_path / "experiments/checkpoints").glob("*.json"))
    with patch.object(FakeModelProvider, "generate") as model:
        with pytest.raises(ExperimentTokenBudgetError, match="USAGE_UNKNOWN"):
            asyncio.run(
                EpisodeService(artifacts_dir=tmp_path).resume_experiment(UUID(plan_path.stem))
            )
        model.assert_not_called()


def test_terminal_safe_point_can_publish_without_spending_more_tokens(tmp_path: Path) -> None:
    worker = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("_checkpoint_worker.py")),
            "experiment-tokens-end",
            str(tmp_path),
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert worker.returncode == 0, worker.stderr
    assert not list(tmp_path.glob("*.json"))
    plan = read_experiment_checkpoint(next((tmp_path / "experiments/checkpoints").glob("*.json")))
    service = EpisodeService(artifacts_dir=tmp_path)
    with patch.object(FakeModelProvider, "generate") as model:
        with pytest.raises(ExperimentTokenBudgetError, match="BUDGET_EXCEEDED"):
            asyncio.run(service._resume_experiment_once(plan.experiment_id))
        model.assert_not_called()
    baseline = service.get_episode(uuid5(plan.experiment_id, "0:baseline"))
    assert baseline is not None and baseline.evaluation.success
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_reported_failed_episode_still_consumes_global_budget(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    with pytest.raises(ExperimentTokenBudgetError, match="BUDGET_EXCEEDED"):
        asyncio.run(
            service.execute_experiment(request(max_total_tokens=60, scenario="invalid-arguments"))
        )
    artifact_path = next(tmp_path.glob("*.json"))
    artifact = service.get_episode(UUID(artifact_path.stem))
    assert artifact is not None and not artifact.evaluation.success
    assert (
        artifact.episode.token_usage.prompt_tokens + artifact.episode.token_usage.completion_tokens
        == 60
    )
    assert len(list(tmp_path.glob("*.json"))) == 1


@pytest.mark.parametrize("corruption", ["foreign", "usage", "trace"])
def test_saved_provenance_and_usage_cannot_bypass_admission(
    tmp_path: Path, corruption: str
) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    with pytest.raises(ExperimentTokenBudgetError):
        asyncio.run(service.execute_experiment(request(max_total_tokens=1)))
    artifact_path = next(tmp_path.glob("*.json"))
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    if corruption == "foreign":
        data["task"]["description"] = "different source"
    elif corruption == "usage":
        data["episode"]["token_usage"]["prompt_tokens"] = 0
    else:
        event = next(e for e in data["events"] if e["event_type"] == "MODEL_RESPONDED")
        event["event_type"] = "MODEL_REQUESTED"
    artifact_path.write_text(json.dumps(data), encoding="utf-8")
    plan_path = next((tmp_path / "experiments/checkpoints").glob("*.json"))
    with patch.object(FakeModelProvider, "generate") as model:
        with pytest.raises(ValueError):
            asyncio.run(
                EpisodeService(artifacts_dir=tmp_path).resume_experiment(UUID(plan_path.stem))
            )
        model.assert_not_called()


def test_legacy_default_retains_plan_hash_and_completed_config(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    old = asyncio.run(service.prepare_experiment(request(schema_version="1.3")))
    current = asyncio.run(service.prepare_experiment(request()))
    assert "max_total_tokens" not in old.config_metadata
    assert old.config_metadata == current.config_metadata
    assert old.schema_version == current.schema_version == "1.0"
    result = asyncio.run(service.execute_experiment(request()))
    assert result.schema_version == "1.2" and "max_total_tokens" not in result.config
    assert "max_total_tokens" not in fixed_config(result)


def test_job_reports_budget_code_and_get_never_runs_provider(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                accepted = await client.post(
                    "/api/v1/experiments/jobs",
                    json=request(max_total_tokens=1).model_dump(mode="json"),
                )
                assert accepted.status_code == 202
                job_id = accepted.json()["experiment_id"]
                for _ in range(100):
                    saved = (await client.get(f"/api/v1/experiments/jobs/{job_id}")).json()
                    if saved["status"] == "failed":
                        break
                    await asyncio.sleep(0.01)
                assert saved["error_code"] == "EXPERIMENT_TOKEN_BUDGET_EXCEEDED"
                with patch.object(FakeModelProvider, "generate") as model:
                    assert (await client.get(f"/api/v1/experiments/jobs/{job_id}")).json() == saved
                    assert (
                        await client.post(f"/api/v1/experiments/jobs/{job_id}/resume")
                    ).status_code == 409
                    model.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    asyncio.run(exercise())
