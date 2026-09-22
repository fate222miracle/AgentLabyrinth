"""Application layer serial orchestration and aggregation for paired Agent experiments."""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from packages.application.runner import run_episode
from packages.application.trace import write_artifact
from packages.domain.models import (
    AgentSpec,
    RunConfig,
    TaskSpec,
    TerminationReason,
)
from packages.domain.ports import ModelProvider
from packages.environments.tool_lab.environment import (
    ToolLabEnvironment,
    create_tool_lab_registry,
)
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.runtime.handwritten.runtime import HandwrittenRuntime
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator


class PairComparison(BaseModel):
    """Comparison item for a single task evaluated with Baseline vs Recovery."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    task_name: str
    seed: int
    repeat_index: int = 1
    baseline_episode_id: UUID
    baseline_success: bool
    baseline_termination_reason: str
    baseline_steps: int
    baseline_tokens: int
    baseline_duration_ms: int
    baseline_cost: Decimal | None = None
    baseline_model_calls: int | None = None
    baseline_tool_calls: int | None = None
    baseline_tool_selection_accuracy: float | None = None
    baseline_tool_argument_validity_rate: float | None = None
    recovery_episode_id: UUID
    recovery_success: bool
    recovery_termination_reason: str
    recovery_steps: int
    recovery_tokens: int
    recovery_duration_ms: int
    recovery_cost: Decimal | None = None
    recovery_model_calls: int | None = None
    recovery_tool_calls: int | None = None
    recovery_tool_selection_accuracy: float | None = None
    recovery_tool_argument_validity_rate: float | None = None
    retry_eligible: bool | None = None
    recovered: bool = False


class ExperimentAggregateMetrics(BaseModel):
    """Aggregated quantitative evaluation metrics across all paired tasks."""

    model_config = ConfigDict(frozen=True)

    total_pairs: int
    baseline_success_count: int
    recovery_success_count: int
    baseline_success_rate: float
    recovery_success_rate: float
    retry_eligible_count: int | None = None
    retry_recovery_count: int
    retry_recovery_rate: float | None = None
    baseline_total_tokens: int
    recovery_total_tokens: int
    baseline_avg_steps: float
    recovery_avg_steps: float
    baseline_avg_model_calls: float | None = None
    recovery_avg_model_calls: float | None = None
    baseline_avg_tool_calls: float | None = None
    recovery_avg_tool_calls: float | None = None
    baseline_tool_selection_accuracy: float | None = None
    recovery_tool_selection_accuracy: float | None = None
    baseline_tool_argument_validity_rate: float | None = None
    recovery_tool_argument_validity_rate: float | None = None
    baseline_avg_duration_ms: float
    recovery_avg_duration_ms: float
    baseline_total_cost: Decimal | None = None
    recovery_total_cost: Decimal | None = None
    is_cost_known: bool


class ExperimentArtifact(BaseModel):
    """Immutable persistent artifact of a complete paired comparison experiment."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0", "1.1"] = "1.1"
    experiment_id: UUID
    created_at: str
    config: dict[str, Any]
    config_hash: str
    episode_ids: list[UUID]
    pairs: list[PairComparison]
    metrics: ExperimentAggregateMetrics


def compute_config_hash(data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of experiment input configuration."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def run_experiment(
    baseline_agent: AgentSpec,
    recovery_agent: AgentSpec,
    tasks: list[TaskSpec],
    provider_factory: Callable[[], ModelProvider],
    *,
    seed: int = 1,
    seeds: list[int] | None = None,
    repeat_count: int = 1,
    artifacts_dir: Path,
    config_metadata: dict[str, Any] | None = None,
) -> ExperimentArtifact:
    """Run paired episodes serially, persist each episode, and aggregate comparative outcomes."""
    if not tasks:
        raise ValueError("Experiment requires at least one task")
    resolved_seeds = list(seeds) if seeds is not None else [seed]
    if not resolved_seeds:
        raise ValueError("Experiment requires at least one seed")
    if len(set(resolved_seeds)) != len(resolved_seeds):
        raise ValueError("Experiment seeds must be unique")
    if repeat_count < 1:
        raise ValueError("Experiment repeat_count must be at least 1")

    experiment_id = uuid4()
    created_at = datetime.now(UTC).isoformat()
    episode_ids: list[UUID] = []
    pairs: list[PairComparison] = []

    runs = (
        (task, current_seed, repeat_index)
        for current_seed in resolved_seeds
        for repeat_index in range(1, repeat_count + 1)
        for task in tasks
    )

    # Run every matrix cell serially: Baseline then Recovery under exact same conditions.
    for task, current_seed, repeat_index in runs:
        run_config = RunConfig(seed=current_seed, environment_version="tool-lab-m0-v1")
        # 1. Execute Baseline Episode
        provider_base = provider_factory()
        registry_base = create_tool_lab_registry()
        validator_base = DefaultToolValidator(registry_base)
        executor_base = ToolExecutor(registry_base, validator_base)
        env_base = ToolLabEnvironment(
            registry=registry_base, executor=executor_base, validator=validator_base
        )
        runtime_base = HandwrittenRuntime(provider=provider_base, validator=validator_base)
        eval_base = OrderStatusEvaluator()

        art_base = await run_episode(
            agent=baseline_agent,
            task=task,
            config=run_config,
            runtime=runtime_base,
            environment=env_base,
            evaluator=eval_base,
        )
        base_id = art_base.episode.episode_id
        episode_ids.append(base_id)
        write_artifact(art_base, artifacts_dir / f"{base_id}.json")

        # 2. Execute Recovery Episode
        provider_rec = provider_factory()
        registry_rec = create_tool_lab_registry()
        validator_rec = DefaultToolValidator(registry_rec)
        executor_rec = ToolExecutor(registry_rec, validator_rec)
        env_rec = ToolLabEnvironment(
            registry=registry_rec, executor=executor_rec, validator=validator_rec
        )
        runtime_rec = HandwrittenRuntime(provider=provider_rec, validator=validator_rec)
        eval_rec = OrderStatusEvaluator()

        art_rec = await run_episode(
            agent=recovery_agent,
            task=task,
            config=run_config,
            runtime=runtime_rec,
            environment=env_rec,
            evaluator=eval_rec,
        )
        rec_id = art_rec.episode.episode_id
        episode_ids.append(rec_id)
        write_artifact(art_rec, artifacts_dir / f"{rec_id}.json")

        # 3. Assess paired outcome
        base_success = art_base.evaluation.success
        rec_success = art_rec.evaluation.success
        base_term = art_base.episode.termination_reason
        rec_term = art_rec.episode.termination_reason

        # retry_eligible is True iff baseline failed specifically due to INVALID_ARGUMENTS
        base_detail = art_base.episode.detail or ""
        is_retry_eligible = (
            (not base_success)
            and (base_term == TerminationReason.FAILED)
            and ("invalid_arguments" in base_detail)
        )

        # Recovered is True iff task was retry_eligible and recovery succeeded
        is_recovered = is_retry_eligible and rec_success

        base_tokens = (
            art_base.episode.token_usage.prompt_tokens
            + art_base.episode.token_usage.completion_tokens
        )
        rec_tokens = (
            art_rec.episode.token_usage.prompt_tokens
            + art_rec.episode.token_usage.completion_tokens
        )

        base_metrics = art_base.evaluation.metrics or {}
        rec_metrics = art_rec.evaluation.metrics or {}

        base_sel_acc = base_metrics.get("tool_selection_accuracy")
        rec_sel_acc = rec_metrics.get("tool_selection_accuracy")
        base_arg_val = base_metrics.get("tool_argument_validity_rate")
        rec_arg_val = rec_metrics.get("tool_argument_validity_rate")

        pairs.append(
            PairComparison(
                task_id=task.name,
                task_name=task.name,
                seed=current_seed,
                repeat_index=repeat_index,
                baseline_episode_id=base_id,
                baseline_success=base_success,
                baseline_termination_reason=base_term.value,
                baseline_steps=art_base.episode.step_count,
                baseline_tokens=base_tokens,
                baseline_duration_ms=art_base.episode.duration_ms,
                baseline_cost=(
                    art_base.episode.estimated_cost.amount
                    if art_base.episode.estimated_cost.is_known
                    else None
                ),
                baseline_model_calls=art_base.episode.model_call_count,
                baseline_tool_calls=art_base.episode.tool_call_count,
                baseline_tool_selection_accuracy=(
                    float(base_sel_acc) if isinstance(base_sel_acc, (int, float)) else None
                ),
                baseline_tool_argument_validity_rate=(
                    float(base_arg_val) if isinstance(base_arg_val, (int, float)) else None
                ),
                recovery_episode_id=rec_id,
                recovery_success=rec_success,
                recovery_termination_reason=rec_term.value,
                recovery_steps=art_rec.episode.step_count,
                recovery_tokens=rec_tokens,
                recovery_duration_ms=art_rec.episode.duration_ms,
                recovery_cost=(
                    art_rec.episode.estimated_cost.amount
                    if art_rec.episode.estimated_cost.is_known
                    else None
                ),
                recovery_model_calls=art_rec.episode.model_call_count,
                recovery_tool_calls=art_rec.episode.tool_call_count,
                recovery_tool_selection_accuracy=(
                    float(rec_sel_acc) if isinstance(rec_sel_acc, (int, float)) else None
                ),
                recovery_tool_argument_validity_rate=(
                    float(rec_arg_val) if isinstance(rec_arg_val, (int, float)) else None
                ),
                retry_eligible=is_retry_eligible,
                recovered=is_recovered,
            )
        )

    # Compute aggregate metrics
    total = len(pairs)
    base_succ_count = sum(1 for p in pairs if p.baseline_success)
    rec_succ_count = sum(1 for p in pairs if p.recovery_success)
    retry_eligible_count = sum(1 for p in pairs if p.retry_eligible)
    recovered_count = sum(1 for p in pairs if p.recovered)

    base_tot_tokens = sum(p.baseline_tokens for p in pairs)
    rec_tot_tokens = sum(p.recovery_tokens for p in pairs)
    base_avg_steps = sum(p.baseline_steps for p in pairs) / total
    rec_avg_steps = sum(p.recovery_steps for p in pairs) / total
    base_avg_dur = sum(p.baseline_duration_ms for p in pairs) / total
    rec_avg_dur = sum(p.recovery_duration_ms for p in pairs) / total

    base_avg_models = sum(p.baseline_model_calls or 0 for p in pairs) / total
    rec_avg_models = sum(p.recovery_model_calls or 0 for p in pairs) / total
    base_avg_tools = sum(p.baseline_tool_calls or 0 for p in pairs) / total
    rec_avg_tools = sum(p.recovery_tool_calls or 0 for p in pairs) / total

    # Average tool selection accuracy across pairs where not None
    base_sel_list = [
        p.baseline_tool_selection_accuracy
        for p in pairs
        if p.baseline_tool_selection_accuracy is not None
    ]
    rec_sel_list = [
        p.recovery_tool_selection_accuracy
        for p in pairs
        if p.recovery_tool_selection_accuracy is not None
    ]
    base_avg_sel = round(sum(base_sel_list) / len(base_sel_list), 4) if base_sel_list else None
    rec_avg_sel = round(sum(rec_sel_list) / len(rec_sel_list), 4) if rec_sel_list else None

    # Average argument validity rate across pairs where not None
    base_arg_list = [
        p.baseline_tool_argument_validity_rate
        for p in pairs
        if p.baseline_tool_argument_validity_rate is not None
    ]
    rec_arg_list = [
        p.recovery_tool_argument_validity_rate
        for p in pairs
        if p.recovery_tool_argument_validity_rate is not None
    ]
    base_avg_arg = round(sum(base_arg_list) / len(base_arg_list), 4) if base_arg_list else None
    rec_avg_arg = round(sum(rec_arg_list) / len(rec_arg_list), 4) if rec_arg_list else None

    # Conversion rate: denominator is retry_eligible_count
    retry_recovery_rate = (
        round(recovered_count / retry_eligible_count, 4) if retry_eligible_count > 0 else 0.0
    )

    is_known = all(
        pair.baseline_cost is not None and pair.recovery_cost is not None for pair in pairs
    )
    baseline_total_cost = (
        sum((pair.baseline_cost for pair in pairs if pair.baseline_cost is not None), Decimal())
        if is_known
        else None
    )
    recovery_total_cost = (
        sum((pair.recovery_cost for pair in pairs if pair.recovery_cost is not None), Decimal())
        if is_known
        else None
    )

    metrics = ExperimentAggregateMetrics(
        total_pairs=total,
        baseline_success_count=base_succ_count,
        recovery_success_count=rec_succ_count,
        baseline_success_rate=round(base_succ_count / total, 4),
        recovery_success_rate=round(rec_succ_count / total, 4),
        retry_eligible_count=retry_eligible_count,
        retry_recovery_count=recovered_count,
        retry_recovery_rate=retry_recovery_rate,
        baseline_total_tokens=base_tot_tokens,
        recovery_total_tokens=rec_tot_tokens,
        baseline_avg_steps=round(base_avg_steps, 2),
        recovery_avg_steps=round(rec_avg_steps, 2),
        baseline_avg_model_calls=round(base_avg_models, 2),
        recovery_avg_model_calls=round(rec_avg_models, 2),
        baseline_avg_tool_calls=round(base_avg_tools, 2),
        recovery_avg_tool_calls=round(rec_avg_tools, 2),
        baseline_tool_selection_accuracy=base_avg_sel,
        recovery_tool_selection_accuracy=rec_avg_sel,
        baseline_tool_argument_validity_rate=base_avg_arg,
        recovery_tool_argument_validity_rate=rec_avg_arg,
        baseline_avg_duration_ms=round(base_avg_dur, 2),
        recovery_avg_duration_ms=round(rec_avg_dur, 2),
        baseline_total_cost=baseline_total_cost,
        recovery_total_cost=recovery_total_cost,
        is_cost_known=is_known,
    )

    exp_config: dict[str, Any] = {
        "baseline_agent": {
            "id": str(baseline_agent.id),
            "name": baseline_agent.name,
            "version": baseline_agent.version,
            "runtime_strategy": baseline_agent.runtime_strategy,
        },
        "recovery_agent": {
            "id": str(recovery_agent.id),
            "name": recovery_agent.name,
            "version": recovery_agent.version,
            "runtime_strategy": recovery_agent.runtime_strategy,
        },
        "model": {
            "provider": baseline_agent.model.provider,
            "model": baseline_agent.model.model,
            "temperature": baseline_agent.model.temperature,
            "max_tokens": baseline_agent.model.max_tokens,
        },
        "prompt_version": baseline_agent.prompt_version,
        "tool_set_version": baseline_agent.tool_set_version,
        "budget": baseline_agent.budget.model_dump(mode="json"),
        "tasks": [
            {
                "id": str(t.id),
                "name": t.name,
                "version": t.version,
                "max_steps": t.max_steps,
                "token_budget": t.token_budget,
                "evaluator_config": t.evaluator_config,
            }
            for t in tasks
        ],
        "evaluator": "order_status_v1",
        "environment_version": "tool-lab-m0-v1",
        "seed": resolved_seeds[0],
        "seeds": resolved_seeds,
        "repeat_count": repeat_count,
    }

    if config_metadata:
        # Execution inputs remain authoritative, including for non-API callers.
        for key, value in config_metadata.items():
            if key not in exp_config:
                exp_config[key] = value

    config_hash = compute_config_hash(exp_config)

    experiment_artifact = ExperimentArtifact(
        schema_version="1.1",
        experiment_id=experiment_id,
        created_at=created_at,
        config=exp_config,
        config_hash=config_hash,
        episode_ids=episode_ids,
        pairs=pairs,
        metrics=metrics,
    )

    # Persist experiment summary
    exp_dir = artifacts_dir / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    exp_file = exp_dir / f"{experiment_id}.json"
    write_experiment(experiment_artifact, exp_file)

    return experiment_artifact


def write_experiment(artifact: ExperimentArtifact, path: Path) -> None:
    """Serialize and write validated ExperimentArtifact JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(artifact.model_dump(mode="json"), ensure_ascii=False, indent=2)
    path.write_text(serialized + "\n", encoding="utf-8")


def read_experiment(path: Path) -> ExperimentArtifact:
    """Strictly deserialize previously saved ExperimentArtifact without model calls."""
    return ExperimentArtifact.model_validate_json(path.read_text(encoding="utf-8"))
