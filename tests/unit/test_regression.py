"""Fixed-suite comparison rejects mixed protocols and reports per-cell regressions."""

from pathlib import Path
from uuid import uuid4

import pytest

from apps.api.schemas import CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.experiment import compute_config_hash, read_experiment
from packages.application.regression import compare_experiments
from scripts.run_regression import preflight

BASELINE = Path(__file__).resolve().parents[2] / "benchmarks/regression/course-smoke-baseline.json"


def test_pinned_regression_reports_one_failed_arm() -> None:
    """Success to failure is a regression; unrelated token changes are informational."""
    baseline = read_experiment(BASELINE)
    pair = baseline.pairs[0].model_copy(update={"baseline_success": False})
    candidate = baseline.model_copy(update={"experiment_id": uuid4(), "pairs": [pair]})
    report = compare_experiments(
        baseline, candidate, baseline_revision="before", candidate_revision="after"
    )
    assert report.regressions == 1
    assert report.improvements == 0
    assert report.cells[0].task_id == "order-status-001"
    assert report.cells[0].arm == "baseline"
    assert report.cells[0].candidate_success is False
    changed_config = {**candidate.config, "seeds": [7]}
    with pytest.raises(ValueError, match="identical fixed configuration"):
        compare_experiments(
            baseline,
            candidate.model_copy(
                update={
                    "config": changed_config,
                    "config_hash": compute_config_hash(changed_config),
                }
            ),
            baseline_revision="before",
            candidate_revision="after",
        )


def test_preflight_rejects_task_or_model_change_before_execution(tmp_path: Path) -> None:
    """Pinned model and TaskSpec version are checked without invoking a provider."""
    baseline = read_experiment(BASELINE)
    service = EpisodeService(artifacts_dir=tmp_path)
    request = CreateExperimentRequest(
        provider="fake", model="fake-model", scenario="success", task_ids=["order-status-001"]
    )
    preflight(baseline, request, service)
    with pytest.raises(ValueError, match="agent or evaluation protocol"):
        preflight(baseline, request.model_copy(update={"max_execution_time_ms": 1000}), service)
    with pytest.raises(ValueError, match="pinned baseline"):
        preflight(baseline, request.model_copy(update={"model": "other"}), service)
    changed_config = {
        **baseline.config,
        "tasks": [{**baseline.config["tasks"][0], "version": "9.9.9"}],
    }
    changed = baseline.model_copy(
        update={"config": changed_config, "config_hash": compute_config_hash(changed_config)}
    )
    with pytest.raises(ValueError, match="task version"):
        preflight(changed, request, service)
