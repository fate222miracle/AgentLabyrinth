"""Application layer serial orchestration and aggregation for paired Agent experiments."""

import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict

from packages.application.checkpoint import (
    CheckpointStore,
    resume_checkpointed_episode,
    run_checkpointed_episode,
)
from packages.application.trace import read_artifact
from packages.domain.models import (
    AgentSpec,
    EpisodeArtifact,
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
from packages.runtime.factory import create_runtime, runtime_version
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator

ComparisonAxis = Literal["recovery_policy", "runtime_backend"]


class PairComparison(BaseModel):
    """Paired outcomes; legacy baseline/recovery keys identify left/right arms."""

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
    retry_recovery_count: int | None = None
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

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.2"
    experiment_id: UUID
    created_at: str
    config: dict[str, Any]
    config_hash: str
    episode_ids: list[UUID]
    pairs: list[PairComparison]
    metrics: ExperimentAggregateMetrics


class ExperimentCheckpoint(BaseModel):
    """Frozen paired-run plan; completed Episode artifacts are the progress ledger."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    experiment_id: UUID
    created_at: str
    baseline_agent: AgentSpec
    recovery_agent: AgentSpec
    tasks: list[TaskSpec]
    seeds: list[int]
    repeat_count: int
    comparison_axis: ComparisonAxis
    config_metadata: dict[str, Any]
    plan_hash: str

    def verify(self) -> None:
        """Reject any changed matrix input before reusing prior Episode output."""
        fields = self.model_dump(mode="json", exclude={"plan_hash"})
        if compute_config_hash(fields) != self.plan_hash:
            raise ValueError("Experiment checkpoint provenance mismatch")


def experiment_checkpoint_path(artifacts_dir: Path, experiment_id: UUID) -> Path:
    """Keep in-progress plans separate from final experiment artifacts."""
    return artifacts_dir / "experiments" / "checkpoints" / f"{experiment_id}.json"


def read_experiment_checkpoint(path: Path) -> ExperimentCheckpoint:
    """Validate a durable plan before resuming any model or tool call."""
    state = ExperimentCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
    state.verify()
    return state


def write_experiment_checkpoint(path: Path, state: ExperimentCheckpoint) -> None:
    """Publish a complete plan before launching the first matrix cell."""
    state.verify()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as output:
            output.write(state.model_dump_json(indent=2) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
    comparison_axis: ComparisonAxis = "recovery_policy",
    checkpoint_state: ExperimentCheckpoint | None = None,
    resume_provider_factory: Callable[[int], ModelProvider] | None = None,
) -> ExperimentArtifact:
    """Run or resume a fixed paired matrix, reusing completed Episode artifacts."""
    if not tasks:
        raise ValueError("Experiment requires at least one task")
    resolved_seeds = list(seeds) if seeds is not None else [seed]
    if not resolved_seeds:
        raise ValueError("Experiment requires at least one seed")
    if len(set(resolved_seeds)) != len(resolved_seeds):
        raise ValueError("Experiment seeds must be unique")
    if repeat_count < 1:
        raise ValueError("Experiment repeat_count must be at least 1")
    for field in ("model", "prompt_version", "tool_set_version", "budget"):
        if getattr(baseline_agent, field) != getattr(recovery_agent, field):
            raise ValueError(f"Paired agents must share {field}")
    if comparison_axis == "runtime_backend":
        if (
            baseline_agent.runtime_backend != "handwritten"
            or recovery_agent.runtime_backend != "langgraph"
            or baseline_agent.runtime_strategy != recovery_agent.runtime_strategy
        ):
            raise ValueError("Runtime comparison requires Reference/LangGraph with the same policy")
    elif comparison_axis == "recovery_policy":
        if (
            baseline_agent.runtime_backend != recovery_agent.runtime_backend
            or baseline_agent.recovery_policy != "none"
            or recovery_agent.recovery_policy != "invalid_arguments_once"
        ):
            raise ValueError("Recovery comparison requires the same backend and baseline/recovery")
    else:
        raise ValueError("Unknown comparison axis")

    if checkpoint_state is None:
        plan = {
            "schema_version": "1.0",
            "experiment_id": str(uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
            "baseline_agent": baseline_agent.model_dump(mode="json"),
            "recovery_agent": recovery_agent.model_dump(mode="json"),
            "tasks": [task.model_dump(mode="json") for task in tasks],
            "seeds": resolved_seeds,
            "repeat_count": repeat_count,
            "comparison_axis": comparison_axis,
            "config_metadata": config_metadata or {},
        }
        checkpoint_state = ExperimentCheckpoint.model_validate_json(
            json.dumps({**plan, "plan_hash": compute_config_hash(plan)})
        )
        write_experiment_checkpoint(
            experiment_checkpoint_path(artifacts_dir, checkpoint_state.experiment_id),
            checkpoint_state,
        )
    else:
        checkpoint_state.verify()
        if (
            baseline_agent != checkpoint_state.baseline_agent
            or recovery_agent != checkpoint_state.recovery_agent
            or tasks != checkpoint_state.tasks
            or resolved_seeds != checkpoint_state.seeds
            or repeat_count != checkpoint_state.repeat_count
            or comparison_axis != checkpoint_state.comparison_axis
        ):
            raise ValueError("Experiment resume configuration mismatch")
    experiment_id = checkpoint_state.experiment_id
    created_at = checkpoint_state.created_at
    episode_ids: list[UUID] = []
    pairs: list[PairComparison] = []

    async def run_arm(
        agent: AgentSpec, task: TaskSpec, current_seed: int, episode_id: UUID
    ) -> EpisodeArtifact:
        """Read completed work, restore a safe point, or start one planned Episode."""
        config = RunConfig(
            seed=current_seed, runtime_version=runtime_version(agent.runtime_backend)
        )
        registry = create_tool_lab_registry()
        validator = DefaultToolValidator(registry)
        environment = ToolLabEnvironment(
            registry=registry,
            executor=ToolExecutor(registry, validator),
            validator=validator,
        )
        artifact_path = artifacts_dir / f"{episode_id}.json"
        if artifact_path.is_file():
            artifact = read_artifact(artifact_path)
            if artifact.agent != agent or artifact.task != task or artifact.run_config != config:
                raise ValueError("Saved experiment Episode provenance mismatch")
            return artifact
        store = CheckpointStore(artifacts_dir / "checkpoints")
        if store.path(episode_id).is_file():
            if resume_provider_factory is None:
                raise ValueError("A resumable provider factory is required")
            saved = store.load(episode_id)
            if saved.agent != agent or saved.task != task or saved.run_config != config:
                raise ValueError("Saved experiment checkpoint provenance mismatch")
            return await resume_checkpointed_episode(
                episode_id,
                create_runtime(
                    agent,
                    resume_provider_factory(saved.session.budget.model_call_count),
                    validator,
                ),
                environment,
                OrderStatusEvaluator(),
                artifacts_dir,
            )
        return await run_checkpointed_episode(
            agent,
            task,
            config,
            create_runtime(agent, provider_factory(), validator),
            environment,
            OrderStatusEvaluator(),
            artifacts_dir,
            fake_scenario=(config_metadata or {}).get("scenario"),
            episode_id=episode_id,
        )

    runs = (
        (task, current_seed, repeat_index)
        for current_seed in resolved_seeds
        for repeat_index in range(1, repeat_count + 1)
        for task in tasks
    )

    # Run every matrix cell serially: Baseline then Recovery under exact same conditions.
    for pair_index, (task, current_seed, repeat_index) in enumerate(runs):
        # 1. Execute Baseline Episode
        base_id = uuid5(experiment_id, f"{pair_index}:baseline")
        art_base = await run_arm(baseline_agent, task, current_seed, base_id)
        episode_ids.append(base_id)

        # 2. Execute Recovery Episode
        rec_id = uuid5(experiment_id, f"{pair_index}:recovery")
        art_rec = await run_arm(recovery_agent, task, current_seed, rec_id)
        episode_ids.append(rec_id)

        # 3. Assess paired outcome
        base_success = art_base.evaluation.success
        rec_success = art_rec.evaluation.success
        base_term = art_base.episode.termination_reason
        rec_term = art_rec.episode.termination_reason

        # retry_eligible is True iff baseline failed specifically due to INVALID_ARGUMENTS
        base_detail = art_base.episode.detail or ""
        is_retry_eligible = comparison_axis == "recovery_policy" and (
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
                retry_eligible=is_retry_eligible if comparison_axis == "recovery_policy" else None,
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
        retry_eligible_count=retry_eligible_count if comparison_axis == "recovery_policy" else None,
        retry_recovery_count=recovered_count if comparison_axis == "recovery_policy" else None,
        retry_recovery_rate=retry_recovery_rate if comparison_axis == "recovery_policy" else None,
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
        "comparison_axis": comparison_axis,
        "arm_labels": (
            {"baseline": "Reference Runtime", "recovery": "LangGraph Runtime"}
            if comparison_axis == "runtime_backend"
            else {"baseline": "Baseline Policy", "recovery": "Recovery Policy"}
        ),
        "baseline_agent": {
            "id": str(baseline_agent.id),
            "name": baseline_agent.name,
            "version": baseline_agent.version,
            "runtime_strategy": baseline_agent.runtime_strategy,
            "runtime_backend": baseline_agent.runtime_backend,
            "runtime_version": runtime_version(baseline_agent.runtime_backend),
            "recovery_policy": baseline_agent.recovery_policy,
        },
        "recovery_agent": {
            "id": str(recovery_agent.id),
            "name": recovery_agent.name,
            "version": recovery_agent.version,
            "runtime_strategy": recovery_agent.runtime_strategy,
            "runtime_backend": recovery_agent.runtime_backend,
            "runtime_version": runtime_version(recovery_agent.runtime_backend),
            "recovery_policy": recovery_agent.recovery_policy,
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
        schema_version="1.2",
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
    experiment_checkpoint_path(artifacts_dir, experiment_id).unlink(missing_ok=True)

    return experiment_artifact


def write_experiment(artifact: ExperimentArtifact, path: Path) -> None:
    """Serialize and write validated ExperimentArtifact JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(artifact.model_dump(mode="json"), ensure_ascii=False, indent=2)
    path.write_text(serialized + "\n", encoding="utf-8")


def read_experiment(path: Path) -> ExperimentArtifact:
    """Strictly deserialize previously saved ExperimentArtifact without model calls."""
    return ExperimentArtifact.model_validate_json(path.read_text(encoding="utf-8"))
