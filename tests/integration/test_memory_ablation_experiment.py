"""Same-window memory ablation uses the formal matrix, saved history and recovery boundaries."""

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.experiment import (
    ExperimentArtifact,
    ExperimentTokenBudgetError,
    compute_config_hash,
    create_experiment_plan,
    read_experiment_checkpoint,
    run_experiment,
)
from packages.application.regression import fixed_config
from packages.domain.models import ContextPolicy
from packages.providers.fake import FakeModelProvider
from scripts.run_regression import preflight

FIXED_VARIABLE_KEYS = ("model", "prompt_version", "tool_set_version", "budget")


def memory_policy(window: int = 1, memory: int = 8192) -> dict[str, object]:
    """Build the right-arm memory policy used by every memory lesion."""
    return {
        "schema_version": "1.1",
        "algorithm_version": "tool-round-window-memory-v1",
        "mode": "recent_tool_rounds",
        "max_tool_rounds": window,
        "memory_max_bytes": memory,
    }


def request(**changes: object) -> CreateExperimentRequest:
    """Build a small, fixed memory-ablation comparison without credentials."""
    return CreateExperimentRequest.model_validate(
        {
            "provider": "fake",
            "model": "fake-model",
            "scenario": "success",
            "task_ids": ["order-status-007"],
            "comparison_axis": "memory_ablation",
            "schema_version": "1.6",
            "context_policy": memory_policy(),
            **changes,
        }
    )


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_memory_matrix_outcome_and_saved_provenance(tmp_path: Path, backend: str) -> None:
    """Only the memory switch changes; the controlled Fake pair still holds."""
    service = EpisodeService(artifacts_dir=tmp_path)
    req = request(runtime_backend=backend)
    result = asyncio.run(service.execute_experiment(req))
    assert result.schema_version == "1.5"
    assert result.config["comparison_axis"] == "memory_ablation"
    assert result.config["arm_labels"] == {
        "baseline": "Recent Window",
        "recovery": "Recent Window + Memory",
    }
    pair = result.pairs[0]
    assert not pair.baseline_success and pair.baseline_termination_reason == "MAX_STEPS"
    assert pair.recovery_success and pair.recovery_termination_reason == "SUCCESS"
    assert pair.retry_eligible is None and pair.recovered is False
    assert result.metrics.retry_eligible_count is None
    assert result.metrics.retry_recovery_count is None
    assert result.metrics.retry_recovery_rate is None
    preflight(result, req, service)
    with pytest.raises(ValueError):
        preflight(
            result,
            request(runtime_backend=backend, context_policy=memory_policy(memory=4096)),
            service,
        )
    fingerprint = fixed_config(result)
    assert "memory_max_bytes" not in fingerprint["baseline_agent"]["context_policy"]
    assert fingerprint["baseline_agent"]["context_policy"]["max_tool_rounds"] == 1
    assert fingerprint["recovery_agent"]["context_policy"]["memory_max_bytes"] == 8192
    left = service.get_episode(pair.baseline_episode_id)
    right = service.get_episode(pair.recovery_episode_id)
    assert left is not None and right is not None
    left_policy = left.agent.context_policy
    right_policy = right.agent.context_policy
    assert left_policy is not None and right_policy is not None
    assert left.agent.runtime_backend == right.agent.runtime_backend == backend
    assert left.agent.budget == right.agent.budget
    assert left.agent.runtime_strategy == right.agent.runtime_strategy
    assert left.agent.recovery_policy == right.agent.recovery_policy
    assert left_policy.max_tool_rounds == right_policy.max_tool_rounds == 1
    assert left_policy.memory_max_bytes is None
    assert right_policy.memory_max_bytes == 8192
    for key in FIXED_VARIABLE_KEYS:
        assert getattr(left.agent, key) == getattr(right.agent, key)
    assert left.task == right.task and left.run_config == right.run_config
    stripped_left = left.agent.model_dump(exclude={"id", "name", "context_policy"})
    stripped_right = right.agent.model_dump(exclude={"id", "name", "context_policy"})
    assert stripped_left == stripped_right


def test_memory_ablation_both_arms_succeed_on_a_large_window(tmp_path: Path) -> None:
    """A window wide enough that memory is not required lets both arms pass."""
    service = EpisodeService(artifacts_dir=tmp_path)
    result = asyncio.run(
        service.execute_experiment(request(context_policy=memory_policy(window=5, memory=32768)))
    )
    assert result.schema_version == "1.5"
    assert result.metrics.baseline_success_count == result.metrics.recovery_success_count == 1


def test_memory_ablation_right_arm_fails_when_capacity_is_too_small(tmp_path: Path) -> None:
    """A memory limit smaller than one round cannot rescue the right arm either."""
    service = EpisodeService(artifacts_dir=tmp_path)
    result = asyncio.run(
        service.execute_experiment(request(context_policy=memory_policy(window=1, memory=256)))
    )
    pair = result.pairs[0]
    assert not pair.baseline_success and not pair.recovery_success
    assert pair.baseline_termination_reason == "MAX_STEPS"
    assert pair.recovery_termination_reason == "MAX_STEPS"


@pytest.mark.parametrize(
    "override",
    [
        {"schema_version": "1.5"},
        {
            "schema_version": "1.6",
            "comparison_axis": "context_policy",
            "context_policy": {"mode": "recent_tool_rounds", "max_tool_rounds": 1},
        },
        {"context_policy": None},
        {"context_policy": {"mode": "full"}},
        {"context_policy": {"mode": "recent_tool_rounds", "max_tool_rounds": 1}},
        {"context_policy": memory_policy(memory=255)},
        {"context_policy": memory_policy(memory=True)},
    ],
)
def test_memory_ablation_rejects_invalid_requests(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        request(**override)


def test_memory_plan_rejects_mixed_variables(tmp_path: Path) -> None:
    """Creation, freezing and recovery all refuse a changed variable."""
    plan = asyncio.run(EpisodeService(artifacts_dir=tmp_path).prepare_experiment(request()))
    assert plan.schema_version == "1.3"
    left = plan.baseline_agent
    right = plan.recovery_agent
    memory = cast(ContextPolicy, right.context_policy)
    window_only = cast(ContextPolicy, left.context_policy)
    tampered = [
        (left.model_copy(update={"context_policy": memory}), right),
        (
            left.model_copy(
                update={"context_policy": memory.model_copy(update={"max_tool_rounds": 2})}
            ),
            right,
        ),
        (left, right.model_copy(update={"context_policy": window_only})),
        (left, right.model_copy(update={"runtime_backend": "langgraph"})),
        (left, right.model_copy(update={"runtime_strategy": "handwritten_recovery"})),
    ]
    for baseline, candidate in tampered:
        with pytest.raises(ValueError):
            create_experiment_plan(
                baseline,
                candidate,
                plan.tasks,
                plan.seeds,
                plan.repeat_count,
                "memory_ablation",
                plan.config_metadata,
            )


def test_saved_memory_plan_resumes_without_rerunning_completed_arm(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    calls = 0

    def stop_after_left() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("controlled interruption")

    plan = asyncio.run(service.prepare_experiment(request()))
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
    assert saved.schema_version == "1.3"
    completed = next(tmp_path.glob("*.json"))
    original = completed.read_bytes()
    result = asyncio.run(
        EpisodeService(artifacts_dir=tmp_path).resume_experiment(plan.experiment_id)
    )
    assert completed.read_bytes() == original
    assert result.metrics.baseline_success_count == 0
    assert result.metrics.recovery_success_count == 1
    assert not path.exists()


def test_memory_plan_verify_rejects_rehashed_mixed_inputs(tmp_path: Path) -> None:
    """A fresh hash cannot make a changed fixed variable a valid memory comparison."""
    plan = asyncio.run(EpisodeService(artifacts_dir=tmp_path).prepare_experiment(request()))
    right = plan.recovery_agent
    for field, value in (
        ("model", right.model.model_copy(update={"temperature": 0.5})),
        ("prompt_version", "changed"),
        ("tool_set_version", "changed"),
        ("budget", right.budget.model_copy(update={"max_steps": 99})),
    ):
        changed = plan.model_copy(
            update={"recovery_agent": right.model_copy(update={field: value})}
        )
        changed = changed.model_copy(
            update={
                "plan_hash": compute_config_hash(
                    changed.model_dump(mode="json", exclude={"plan_hash"})
                )
            }
        )
        with pytest.raises(ValueError):
            changed.verify()
    changed = plan.model_copy(update={"comparison_axis": "recovery_policy"})
    changed = changed.model_copy(
        update={
            "plan_hash": compute_config_hash(changed.model_dump(mode="json", exclude={"plan_hash"}))
        }
    )
    with pytest.raises(ValueError):
        changed.verify()


def test_memory_result_rejects_revision_axis_and_runtime_provenance_mismatches(
    tmp_path: Path,
) -> None:
    """Saved revision 1.5 is exclusive to memory comparisons with matching Runtime provenance."""
    result = asyncio.run(EpisodeService(artifacts_dir=tmp_path).execute_experiment(request()))
    for field, value in (
        ("comparison_axis", "recovery_policy"),
        ("baseline_agent", None),
        ("recovery_agent", []),
        ("runtime_version", "changed"),
        ("recovery_policy", "invalid_arguments_once"),
        ("runtime_backend", None),
    ):
        data = result.model_dump(mode="json")
        if field in ("comparison_axis", "baseline_agent", "recovery_agent"):
            data["config"][field] = value
        elif value is None:
            for arm in ("baseline_agent", "recovery_agent"):
                data["config"][arm].pop(field)
        else:
            data["config"]["recovery_agent"][field] = value
        data["config_hash"] = compute_config_hash(data["config"])
        with pytest.raises(ValidationError):
            ExperimentArtifact.model_validate(data)
    for field, value in (
        ("runtime_backend", "unknown"),
        ("runtime_strategy", "unknown"),
        ("runtime_version", ""),
        ("recovery_policy", "invalid_arguments_once"),
    ):
        data = result.model_dump(mode="json")
        for arm in ("baseline_agent", "recovery_agent"):
            data["config"][arm][field] = value
        data["config_hash"] = compute_config_hash(data["config"])
        with pytest.raises(ValidationError):
            ExperimentArtifact.model_validate(data)


def test_failed_left_arm_reruns_under_its_original_memory_policy(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    result = asyncio.run(service.execute_experiment(request()))
    pair = result.pairs[0]
    original = service.get_episode(pair.baseline_episode_id)
    assert original is not None
    rerun = asyncio.run(service.rerun_failed_episode(pair.baseline_episode_id))
    assert rerun.agent == original.agent and not rerun.evaluation.success
    assert rerun.agent.context_policy is not None
    assert rerun.agent.context_policy.memory_max_bytes is None
    assert service.get_episode(pair.baseline_episode_id) == original


def test_memory_axis_obeys_global_token_admission(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    with pytest.raises(ExperimentTokenBudgetError, match="EXPERIMENT_TOKEN_BUDGET_EXCEEDED"):
        asyncio.run(service.execute_experiment(request(max_total_tokens=1)))
    assert len(list(tmp_path.glob("*.json"))) == 1
    with patch.object(
        EpisodeService, "_require_live_model", side_effect=AssertionError("no live requests")
    ):
        saved = read_experiment_checkpoint(
            next((tmp_path / "experiments" / "checkpoints").glob("*.json"))
        )
        assert saved.schema_version == "1.3" and saved.config_metadata["max_total_tokens"] == 1
        with pytest.raises(ExperimentTokenBudgetError):
            asyncio.run(
                EpisodeService(artifacts_dir=tmp_path).resume_experiment(saved.experiment_id)
            )


def test_memory_ablation_api_accepts_new_axis_and_rejects_mismatch(tmp_path: Path) -> None:
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
                    "task_ids": ["order-status-007"],
                    "comparison_axis": "memory_ablation",
                    "schema_version": "1.6",
                    "context_policy": memory_policy(),
                }
                response = await client.post("/api/v1/experiments", json=payload)
                assert response.status_code == 201
                saved = response.json()["experiment"]
                assert saved["schema_version"] == "1.5"
                reply = await client.get(f"/api/v1/experiments/{saved['experiment_id']}")
                assert reply.json()["experiment"] == saved
                payload["schema_version"] = "1.5"
                assert (await client.post("/api/v1/experiments", json=payload)).status_code == 422
                payload["schema_version"] = "1.6"
                payload["context_policy"] = memory_policy(memory=999999)
                assert (await client.post("/api/v1/experiments", json=payload)).status_code == 422
        finally:
            app.dependency_overrides.clear()

    asyncio.run(exercise())
