"""Context comparison uses the formal matrix, saved history and recovery boundaries."""

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
import pytest
from pydantic import JsonValue, ValidationError

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.experiment import (
    ComparisonAxis,
    ExperimentTokenBudgetError,
    create_experiment_plan,
    read_experiment_checkpoint,
    run_experiment,
)
from packages.application.regression import fixed_config
from packages.providers.fake import FakeModelProvider
from scripts.run_regression import preflight


def request(window: int = 1, **changes: object) -> CreateExperimentRequest:
    """Build a small, fixed native context comparison without credentials."""
    return CreateExperimentRequest.model_validate(
        {
            "provider": "fake",
            "model": "fake-model",
            "scenario": "success",
            "task_ids": ["order-status-001", "order-status-007"],
            "comparison_axis": "context_policy",
            "context_policy": {"mode": "recent_tool_rounds", "max_tool_rounds": window},
            **changes,
        }
    )


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("window", [1, 2])
def test_context_matrix_outcomes_and_saved_provenance(
    tmp_path: Path, backend: str, window: int
) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    req = request(window, runtime_backend=backend)
    result = asyncio.run(service.execute_experiment(req))
    assert result.schema_version == "1.4"
    assert result.metrics.baseline_success_count == 2
    assert result.metrics.recovery_success_count == (1 if window == 1 else 2)
    assert result.metrics.retry_recovery_rate is None
    assert result.metrics.retry_eligible_count is None
    assert result.metrics.retry_recovery_count is None
    assert all(pair.retry_eligible is None and not pair.recovered for pair in result.pairs)
    preflight(result, req, service)
    with pytest.raises(ValueError, match="context policy"):
        preflight(result, request(3, runtime_backend=backend), service)
    fingerprint = fixed_config(result)
    assert fingerprint["baseline_agent"]["context_policy"]["mode"] == "full"
    assert fingerprint["recovery_agent"]["context_policy"]["max_tool_rounds"] == window
    for pair in result.pairs:
        left = service.get_episode(pair.baseline_episode_id)
        right = service.get_episode(pair.recovery_episode_id)
        assert left is not None and right is not None
        assert left.agent.runtime_backend == right.agent.runtime_backend == backend
        assert left.agent.budget == right.agent.budget
        assert left.agent.runtime_strategy == right.agent.runtime_strategy
        assert left.task == right.task and left.run_config == right.run_config
        requests = [
            cast(dict[str, JsonValue], e.payload["context"])
            for e in right.events
            if e.event_type == "MODEL_REQUESTED"
        ]
        assert requests and all(e["mode"] == "recent_tool_rounds" for e in requests)
        if pair.task_name == "order-status-007" and window == 1:
            assert pair.recovery_termination_reason == "MAX_STEPS"
            assert any(
                isinstance(e["dropped_messages_count"], int) and e["dropped_messages_count"] > 0
                for e in requests
            )
            assert len(right.events) > len(left.events)  # Full saved Trace is not the projection.
            rerun = asyncio.run(service.rerun_failed_episode(pair.recovery_episode_id))
            assert rerun.agent == right.agent and not rerun.evaluation.success
            assert service.get_episode(pair.recovery_episode_id) == right


@pytest.mark.parametrize(
    "policy",
    [
        None,
        {"mode": "full"},
        {"mode": "recent_tool_rounds", "max_tool_rounds": True},
        {"mode": "recent_tool_rounds", "max_tool_rounds": 0},
    ],
)
def test_context_axis_rejects_invalid_policy(policy: object) -> None:
    with pytest.raises(ValidationError):
        request(context_policy=policy)


def test_request_revisions_and_legacy_defaults() -> None:
    with pytest.raises(ValidationError, match="revision 1.5"):
        request(schema_version="1.4")
    with pytest.raises(ValidationError, match="revision 1.3"):
        CreateEpisodeRequest(
            provider="fake",
            model="fake-model",
            schema_version="1.2",
            context_policy={"mode": "full"},
        )
    assert (
        CreateEpisodeRequest(
            provider="fake", model="fake-model", schema_version="1.2"
        ).context_policy
        is None
    )


def test_episode_api_accepts_context_and_rejects_legacy_revision(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = {
                    "provider": "fake",
                    "model": "fake-model",
                    "scenario": "success",
                    "task_id": "order-status-007",
                    "context_policy": {"mode": "recent_tool_rounds", "max_tool_rounds": 1},
                }
                response = await client.post("/api/v1/episodes", json=payload)
                assert response.status_code == 201
                saved = response.json()["artifact"]
                assert saved["agent"]["schema_version"] == "1.2"
                assert not saved["evaluation"]["success"]
                reply = await client.get(f"/api/v1/episodes/{saved['episode']['episode_id']}")
                assert reply.json()["artifact"] == saved
                payload["schema_version"] = "1.2"
                assert (await client.post("/api/v1/episodes", json=payload)).status_code == 422
        finally:
            app.dependency_overrides.clear()

    asyncio.run(exercise())


def test_context_plan_rejects_mixed_variables_and_old_axes(tmp_path: Path) -> None:
    plan = asyncio.run(EpisodeService(artifacts_dir=tmp_path).prepare_experiment(request()))
    assert plan.schema_version == "1.2"
    for axis, right in [
        (
            "context_policy",
            plan.recovery_agent.model_copy(update={"runtime_strategy": "handwritten_recovery"}),
        ),
        ("context_policy", plan.recovery_agent.model_copy(update={"runtime_backend": "langgraph"})),
        ("recovery_policy", plan.recovery_agent),
        ("runtime_backend", plan.recovery_agent),
    ]:
        with pytest.raises(ValueError):
            create_experiment_plan(
                plan.baseline_agent,
                right,
                plan.tasks,
                plan.seeds,
                1,
                cast(ComparisonAxis, axis),
                {},
            )


def test_saved_context_plan_resumes_without_rerunning_completed_arm(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    calls = 0

    def stop_after_left() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("controlled interruption")

    plan = asyncio.run(service.prepare_experiment(request(task_ids=["order-status-007"])))
    with pytest.raises(RuntimeError, match="controlled interruption"):
        asyncio.run(
            run_experiment(
                plan.baseline_agent,
                plan.recovery_agent,
                plan.tasks,
                lambda: FakeModelProvider(scenario="success"),
                artifacts_dir=tmp_path,
                comparison_axis=plan.comparison_axis,
                config_metadata=plan.config_metadata,
                experiment_id=plan.experiment_id,
                before_arm=stop_after_left,
            )
        )
    path = tmp_path / "experiments" / "checkpoints" / f"{plan.experiment_id}.json"
    saved = read_experiment_checkpoint(path)
    assert saved.baseline_agent == plan.baseline_agent
    completed = next(tmp_path.glob("*.json"))
    original = completed.read_bytes()
    result = asyncio.run(
        EpisodeService(artifacts_dir=tmp_path).resume_experiment(plan.experiment_id)
    )
    assert completed.read_bytes() == original
    assert result.metrics.baseline_success_count == 1 and result.metrics.recovery_success_count == 0
    assert not path.exists()


def test_context_axis_obeys_global_token_admission(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    with pytest.raises(ExperimentTokenBudgetError, match="EXPERIMENT_TOKEN_BUDGET_EXCEEDED"):
        asyncio.run(
            service.execute_experiment(request(task_ids=["order-status-001"], max_total_tokens=1))
        )
    assert len(list(tmp_path.glob("*.json"))) == 1
    with patch.object(
        EpisodeService, "_require_live_model", side_effect=AssertionError("no live requests")
    ):
        saved = read_experiment_checkpoint(
            next((tmp_path / "experiments" / "checkpoints").glob("*.json"))
        )
        assert saved.schema_version == "1.2" and saved.config_metadata["max_total_tokens"] == 1
        with pytest.raises(ExperimentTokenBudgetError):
            asyncio.run(
                EpisodeService(artifacts_dir=tmp_path).resume_experiment(saved.experiment_id)
            )
