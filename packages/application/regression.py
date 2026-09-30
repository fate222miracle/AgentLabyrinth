"""Compare complete, compatible paired Experiments across code revisions."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from packages.application.experiment import ExperimentArtifact, PairComparison, compute_config_hash

FIXED_FIELDS = (
    "comparison_axis",
    "model",
    "prompt_version",
    "tool_set_version",
    "budget",
    "tasks",
    "evaluator",
    "environment_version",
    "seeds",
    "repeat_count",
    "scenario",
    "fault_profile",
    "max_reference_cost_usd",
    "reference_price_version",
)
ARM_FIELDS = ("runtime_strategy", "runtime_backend", "recovery_policy")


class RegressionCell(BaseModel):
    """A single matched Task/Seed/Repeat/arm outcome."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    seed: int
    repeat_index: int
    arm: Literal["baseline", "recovery"]
    baseline_success: bool
    candidate_success: bool
    baseline_tokens: int
    candidate_tokens: int


class RegressionReport(BaseModel):
    """Versioned report suitable for saved CI evidence and local inspection."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    baseline_experiment_id: UUID
    candidate_experiment_id: UUID
    baseline_revision: str
    candidate_revision: str
    fixed_config_hash: str
    regressions: int
    improvements: int
    cells: list[RegressionCell]


def fixed_config(artifact: ExperimentArtifact) -> dict[str, Any]:
    """Drop only implementation identity; retain every fairness variable."""
    config = artifact.config
    if compute_config_hash(config) != artifact.config_hash:
        raise ValueError("Experiment configuration hash mismatch")
    required = FIXED_FIELDS[:10]
    if any(field not in config for field in required):
        raise ValueError("Experiment lacks required regression provenance")
    result = {field: config.get(field) for field in FIXED_FIELDS}
    for arm in ("baseline_agent", "recovery_agent"):
        agent = config.get(arm)
        if not isinstance(agent, dict) or any(key not in agent for key in ARM_FIELDS):
            raise ValueError("Experiment lacks arm configuration")
        result[arm] = {key: agent[key] for key in ARM_FIELDS}
    return result


def _cells(artifact: ExperimentArtifact) -> dict[tuple[str, int, int, str], tuple[bool, int]]:
    if not artifact.pairs or len(artifact.pairs) != artifact.metrics.total_pairs:
        raise ValueError("Experiment pair count is inconsistent")
    result: dict[tuple[str, int, int, str], tuple[bool, int]] = {}
    for pair in artifact.pairs:
        pair = PairComparison.model_validate(pair)
        for arm in ("baseline", "recovery"):
            key = (pair.task_id, pair.seed, pair.repeat_index, arm)
            if key in result:
                raise ValueError("Duplicate regression matrix cell")
            result[key] = (getattr(pair, f"{arm}_success"), getattr(pair, f"{arm}_tokens"))
    return result


def compare_experiments(
    baseline: ExperimentArtifact,
    candidate: ExperimentArtifact,
    *,
    baseline_revision: str,
    candidate_revision: str,
) -> RegressionReport:
    """Reject mixed protocols, then flag every successful cell that became a failure."""
    fixed = fixed_config(baseline)
    if fixed != fixed_config(candidate):
        raise ValueError("Regression comparison requires identical fixed configuration")
    before, after = _cells(baseline), _cells(candidate)
    if before.keys() != after.keys():
        raise ValueError("Regression matrix cells differ")
    cells = [
        RegressionCell(
            task_id=task_id,
            seed=seed,
            repeat_index=repeat_index,
            arm=arm,
            baseline_success=before[key][0],
            candidate_success=after[key][0],
            baseline_tokens=before[key][1],
            candidate_tokens=after[key][1],
        )
        for key in sorted(before)
        for task_id, seed, repeat_index, arm in (key,)
    ]
    return RegressionReport(
        baseline_experiment_id=baseline.experiment_id,
        candidate_experiment_id=candidate.experiment_id,
        baseline_revision=baseline_revision,
        candidate_revision=candidate_revision,
        fixed_config_hash=compute_config_hash(fixed),
        regressions=sum(cell.baseline_success and not cell.candidate_success for cell in cells),
        improvements=sum(not cell.baseline_success and cell.candidate_success for cell in cells),
        cells=cells,
    )
