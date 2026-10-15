"""Application layer serial orchestration and aggregation for paired Agent experiments."""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, model_validator

from packages.application.checkpoint import (
    CheckpointStore,
    read_completed_episode,
    resume_checkpointed_episode,
    run_checkpointed_episode,
)
from packages.application.trace import read_artifact, write_text_atomically
from packages.domain.models import (
    AgentSpec,
    ContextPolicy,
    EpisodeArtifact,
    EventType,
    RunConfig,
    TaskSpec,
    TerminationReason,
    TraceEvent,
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

ComparisonAxis = Literal["recovery_policy", "runtime_backend", "context_policy", "memory_ablation"]


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
    baseline_reference_cost: Decimal | None = None
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
    recovery_reference_cost: Decimal | None = None
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
    baseline_total_reference_cost: Decimal | None = None
    recovery_total_reference_cost: Decimal | None = None
    is_reference_cost_known: bool = False


class ReferenceCostBudgetExceeded(ValueError):
    """The configured model-maker reference budget cannot admit another Episode."""


class ExperimentTokenBudgetError(ValueError):
    """A reported-token boundary or unknown usage prevents further execution."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _global_token_limit(metadata: dict[str, Any]) -> int | None:
    """Validate the optional global threshold without coercing old inputs."""
    value = metadata.get("max_total_tokens")
    if value is not None and (type(value) is not int or not 1 <= value <= 1_000_000_000):
        raise ValueError("Global Token budget must be an integer between 1 and 1000000000")
    return value


class ExperimentArtifact(BaseModel):
    """Immutable persistent artifact of a complete paired comparison experiment."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0", "1.1", "1.2", "1.3", "1.4", "1.5"] = "1.2"
    experiment_id: UUID
    created_at: str
    config: dict[str, Any]
    config_hash: str
    episode_ids: list[UUID]
    pairs: list[PairComparison]
    metrics: ExperimentAggregateMetrics

    @model_validator(mode="after")
    def token_budget_revision(self) -> "ExperimentArtifact":
        """Require the new artifact revision for explicit global budget semantics."""
        if _global_token_limit(self.config) is not None and self.schema_version not in (
            "1.3",
            "1.4",
            "1.5",
        ):
            raise ValueError("Global Token budget requires experiment revision 1.3")
        if self.schema_version == "1.5" and self.config.get("comparison_axis") != "memory_ablation":
            raise ValueError("Experiment revision 1.5 supports only memory ablation")
        if self.config.get("comparison_axis") == "memory_ablation":
            if self.schema_version != "1.5":
                raise ValueError("Memory ablation requires experiment revision 1.5")
            left_arm = self.config.get("baseline_agent")
            right_arm = self.config.get("recovery_agent")
            if not isinstance(left_arm, dict) or not isinstance(right_arm, dict):
                raise ValueError("Memory ablation requires both saved arm configurations")
            left = ContextPolicy.model_validate(left_arm.get("context_policy"))
            right = ContextPolicy.model_validate(right_arm.get("context_policy"))
            if any(
                left_arm.get(field) is None or left_arm.get(field) != right_arm.get(field)
                for field in (
                    "runtime_backend",
                    "runtime_strategy",
                    "runtime_version",
                    "recovery_policy",
                )
            ):
                raise ValueError("Memory ablation requires the same Runtime and recovery policy")
            if (
                left_arm["runtime_backend"] not in ("handwritten", "langgraph")
                or left_arm["runtime_strategy"] not in ("handwritten", "handwritten_recovery")
                or not isinstance(left_arm["runtime_version"], str)
                or not left_arm["runtime_version"]
                or left_arm["recovery_policy"]
                != (
                    "invalid_arguments_once"
                    if left_arm["runtime_strategy"] == "handwritten_recovery"
                    else "none"
                )
            ):
                raise ValueError("Memory ablation requires valid Runtime provenance")
            _require_memory_arm_pair(left, right)
            if any(pair.retry_eligible is not None or pair.recovered for pair in self.pairs) or any(
                value is not None
                for value in (
                    self.metrics.retry_eligible_count,
                    self.metrics.retry_recovery_count,
                    self.metrics.retry_recovery_rate,
                )
            ):
                raise ValueError("Memory ablation has no recovery metrics")
        if self.config.get("comparison_axis") == "context_policy":
            if self.schema_version != "1.4":
                raise ValueError("Context comparison requires experiment revision 1.4")
            left = ContextPolicy.model_validate(
                self.config.get("baseline_agent", {}).get("context_policy")
            )
            right = ContextPolicy.model_validate(
                self.config.get("recovery_agent", {}).get("context_policy")
            )
            if any(
                self.config["baseline_agent"].get(field) != self.config["recovery_agent"].get(field)
                for field in ("runtime_backend", "runtime_strategy", "runtime_version")
            ):
                raise ValueError("Context comparison requires the same Runtime and recovery policy")
            if left.mode != "full" or right.mode != "recent_tool_rounds":
                raise ValueError("Context comparison requires full/recent_tool_rounds")
            if any(pair.retry_eligible is not None or pair.recovered for pair in self.pairs) or any(
                value is not None
                for value in (
                    self.metrics.retry_eligible_count,
                    self.metrics.retry_recovery_count,
                    self.metrics.retry_recovery_rate,
                )
            ):
                raise ValueError("Context comparison has no recovery metrics")
        return self


class ExperimentCheckpoint(BaseModel):
    """Frozen paired-run plan; completed Episode artifacts are the progress ledger."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["1.0", "1.1", "1.2", "1.3"] = "1.0"
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
        if _global_token_limit(self.config_metadata) is not None and self.schema_version not in (
            "1.1",
            "1.2",
            "1.3",
        ):
            raise ValueError("Global Token budget requires experiment plan revision 1.1")
        if self.comparison_axis == "context_policy" and self.schema_version != "1.2":
            raise ValueError("Context comparison requires plan revision 1.2")
        if self.comparison_axis == "memory_ablation" and self.schema_version != "1.3":
            raise ValueError("Memory ablation requires plan revision 1.3")
        if self.schema_version == "1.3" and self.comparison_axis != "memory_ablation":
            raise ValueError("Plan revision 1.3 supports only memory ablation")
        if self.comparison_axis == "context_policy":
            _validate_context_agents(self.baseline_agent, self.recovery_agent)
        if self.comparison_axis == "memory_ablation":
            _validate_memory_agents(self.baseline_agent, self.recovery_agent)


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
    write_text_atomically(path, state.model_dump_json(indent=2) + "\n")


def compute_config_hash(data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of experiment input configuration."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_context_agents(baseline_agent: AgentSpec, recovery_agent: AgentSpec) -> None:
    """Reject mixed context comparisons before creation or recovery."""
    if (
        baseline_agent.context_policy is None
        or baseline_agent.context_policy.mode != "full"
        or recovery_agent.context_policy is None
        or recovery_agent.context_policy.mode != "recent_tool_rounds"
        or baseline_agent.runtime_backend != recovery_agent.runtime_backend
        or baseline_agent.runtime_strategy != recovery_agent.runtime_strategy
    ):
        raise ValueError(
            "Context comparison requires full/recent with the same backend and recovery policy"
        )


def _require_memory_arm_pair(left: ContextPolicy, right: ContextPolicy) -> None:
    """Reject anything but a same-window window-only left against a memory right."""
    if left.mode != "recent_tool_rounds" or right.mode != "recent_tool_rounds":
        raise ValueError("Memory ablation requires recent windows on both arms")
    if left.max_tool_rounds != right.max_tool_rounds:
        raise ValueError("Memory ablation requires the same window on both arms")
    if left.memory_max_bytes is not None or right.memory_max_bytes is None:
        raise ValueError("Memory ablation requires a window-only left and a memory right")
    if left.schema_version != "1.0" or left.algorithm_version != "tool-round-window-v1":
        raise ValueError("Memory ablation baseline must use the window-only algorithm")
    if right.schema_version != "1.1" or right.algorithm_version != "tool-round-window-memory-v1":
        raise ValueError("Memory ablation recovery must use the tool-memory algorithm")


def _validate_memory_agents(baseline_agent: AgentSpec, recovery_agent: AgentSpec) -> None:
    """Reject mixed memory ablations before creation or recovery."""
    if (
        baseline_agent.context_policy is None
        or recovery_agent.context_policy is None
        or baseline_agent.runtime_backend != recovery_agent.runtime_backend
        or baseline_agent.runtime_strategy != recovery_agent.runtime_strategy
        or baseline_agent.recovery_policy != recovery_agent.recovery_policy
    ):
        raise ValueError(
            "Memory ablation requires both arms and the same backend and recovery policy"
        )
    fixed_fields = {"id", "name", "context_policy"}
    if baseline_agent.model_dump(exclude=fixed_fields) != recovery_agent.model_dump(
        exclude=fixed_fields
    ):
        raise ValueError("Memory ablation agents must share all inputs except identity and memory")
    _require_memory_arm_pair(baseline_agent.context_policy, recovery_agent.context_policy)


def create_experiment_plan(
    baseline_agent: AgentSpec,
    recovery_agent: AgentSpec,
    tasks: list[TaskSpec],
    seeds: list[int],
    repeat_count: int,
    comparison_axis: ComparisonAxis,
    config_metadata: dict[str, Any],
    experiment_id: UUID | None = None,
) -> ExperimentCheckpoint:
    """Validate and freeze a paired matrix before accepting or executing work."""
    if not tasks or not seeds or len(set(seeds)) != len(seeds) or repeat_count < 1:
        raise ValueError("Experiment requires tasks, unique seeds and a positive repeat count")
    for field in ("model", "prompt_version", "tool_set_version", "budget") + (
        () if comparison_axis in ("context_policy", "memory_ablation") else ("context_policy",)
    ):
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
    elif comparison_axis == "context_policy":
        _validate_context_agents(baseline_agent, recovery_agent)
    elif comparison_axis == "memory_ablation":
        _validate_memory_agents(baseline_agent, recovery_agent)
    else:
        raise ValueError("Unknown comparison axis")
    raw_limit = config_metadata.get("max_reference_cost_usd")
    if raw_limit is not None and (
        Decimal(str(raw_limit)) <= 0 or not config_metadata.get("reference_price_version")
    ):
        raise ValueError("Reference cost budget requires a positive limit and price version")
    token_limit = _global_token_limit(config_metadata)
    plan = {
        "schema_version": "1.3"
        if comparison_axis == "memory_ablation"
        else "1.2"
        if comparison_axis == "context_policy"
        else "1.1"
        if token_limit is not None
        else "1.0",
        "experiment_id": str(experiment_id or uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "baseline_agent": baseline_agent.model_dump(mode="json"),
        "recovery_agent": recovery_agent.model_dump(mode="json"),
        "tasks": [task.model_dump(mode="json") for task in tasks],
        "seeds": seeds,
        "repeat_count": repeat_count,
        "comparison_axis": comparison_axis,
        "config_metadata": config_metadata,
    }
    return ExperimentCheckpoint.model_validate_json(
        json.dumps({**plan, "plan_hash": compute_config_hash(plan)})
    )


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
    experiment_id: UUID | None = None,
    before_arm: Callable[[], None] | None = None,
) -> ExperimentArtifact:
    """Run or resume a fixed paired matrix, reusing completed Episode artifacts."""
    resolved_seeds = list(seeds) if seeds is not None else [seed]
    prepared = create_experiment_plan(
        baseline_agent,
        recovery_agent,
        tasks,
        resolved_seeds,
        repeat_count,
        comparison_axis,
        config_metadata or {},
        experiment_id,
    )
    raw_reference_limit = (config_metadata or {}).get("max_reference_cost_usd")
    reference_limit = Decimal(str(raw_reference_limit)) if raw_reference_limit is not None else None
    reference_version = (config_metadata or {}).get("reference_price_version")

    if checkpoint_state is None:
        new_id = prepared.experiment_id
        if (
            experiment_checkpoint_path(artifacts_dir, new_id).exists()
            or (artifacts_dir / "experiments" / f"{new_id}.json").exists()
        ):
            raise ValueError("Experiment ID already exists")
        checkpoint_state = prepared
        write_experiment_checkpoint(
            experiment_checkpoint_path(artifacts_dir, checkpoint_state.experiment_id),
            checkpoint_state,
        )
    else:
        checkpoint_state.verify()
        if experiment_id is not None and experiment_id != checkpoint_state.experiment_id:
            raise ValueError("Experiment resume ID mismatch")
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
    if (config_metadata or {}) != checkpoint_state.config_metadata:
        raise ValueError("Experiment resume metadata mismatch")
    created_at = checkpoint_state.created_at
    episode_ids: list[UUID] = []
    pairs: list[PairComparison] = []
    committed_reference_cost = Decimal("0")
    token_limit = _global_token_limit(checkpoint_state.config_metadata)
    token_ledger: dict[UUID, int] = {}

    def reported_tokens(
        events: tuple[TraceEvent, ...] | list[TraceEvent], calls: int, total: int
    ) -> int:
        """Fail closed if any requested response lacks trustworthy accounting."""
        requests = [event for event in events if event.event_type == EventType.MODEL_REQUESTED]
        responses = [event for event in events if event.event_type == EventType.MODEL_RESPONDED]
        measured = sum(
            event.token_usage.prompt_tokens + event.token_usage.completion_tokens
            for event in responses
        )
        if len(requests) != calls or len(responses) != calls or measured != total:
            raise ExperimentTokenBudgetError("EXPERIMENT_TOKEN_USAGE_UNKNOWN")
        return total

    runs = [
        (task, current_seed, repeat_index)
        for current_seed in resolved_seeds
        for repeat_index in range(1, repeat_count + 1)
        for task in tasks
    ]
    if token_limit is not None:
        # Rebuild once; later completions replace their own safe-point count.
        store = CheckpointStore(artifacts_dir / "checkpoints")
        for pair_index, (task, current_seed, _) in enumerate(runs):
            for arm, agent in (("baseline", baseline_agent), ("recovery", recovery_agent)):
                arm_id = uuid5(experiment_id, f"{pair_index}:{arm}")
                expected_config = RunConfig(
                    seed=current_seed, runtime_version=runtime_version(agent.runtime_backend)
                )
                artifact = read_completed_episode(arm_id, artifacts_dir)
                if artifact is not None:
                    if (
                        artifact.agent != agent
                        or artifact.task != task
                        or artifact.run_config != expected_config
                    ):
                        raise ValueError("Saved experiment Episode provenance mismatch")
                    usage = artifact.episode.token_usage
                    token_ledger[arm_id] = reported_tokens(
                        artifact.events,
                        artifact.episode.model_call_count,
                        usage.prompt_tokens + usage.completion_tokens,
                    )
                elif store.path(arm_id).is_file():
                    saved = store.load(arm_id)
                    if (
                        saved.agent != agent
                        or saved.task != task
                        or saved.run_config != expected_config
                    ):
                        raise ValueError("Saved experiment checkpoint provenance mismatch")
                    budget = saved.session.budget
                    token_ledger[arm_id] = reported_tokens(
                        saved.events,
                        budget.model_call_count,
                        budget.prompt_tokens + budget.completion_tokens,
                    )
                elif (artifacts_dir / f"{arm_id}.json").is_file():
                    raise ValueError("Malformed experiment result has no valid safe point")

    def record_tokens(artifact: EpisodeArtifact) -> None:
        """Replace one Episode's accumulated usage, never add it twice on resume."""
        if token_limit is not None:
            usage = artifact.episode.token_usage
            token_ledger[artifact.episode.episode_id] = reported_tokens(
                artifact.events,
                artifact.episode.model_call_count,
                usage.prompt_tokens + usage.completion_tokens,
            )

    def check_reference_budget() -> None:
        if reference_limit is not None and committed_reference_cost >= reference_limit:
            raise ReferenceCostBudgetExceeded("Experiment reference cost budget reached")

    def record_reference_cost(artifact: EpisodeArtifact) -> None:
        nonlocal committed_reference_cost
        if reference_limit is None:
            return
        cost = artifact.reference_cost
        if cost is None or cost.price_table_version != reference_version:
            raise ValueError("Experiment reference cost is unknown or price version changed")
        committed_reference_cost += cost.amount
        if committed_reference_cost > reference_limit:
            raise ReferenceCostBudgetExceeded("Experiment reference cost budget exceeded")

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
            tool_set_version=agent.tool_set_version,
        )
        artifact_path = artifacts_dir / f"{episode_id}.json"
        store = CheckpointStore(artifacts_dir / "checkpoints")
        if artifact_path.is_file():
            try:
                artifact = read_artifact(artifact_path)
            except ValueError:
                if not store.path(episode_id).is_file():
                    raise
            else:
                if (
                    artifact.episode.episode_id != episode_id
                    or artifact.agent != agent
                    or artifact.task != task
                    or artifact.run_config != config
                ):
                    raise ValueError("Saved experiment Episode provenance mismatch")
                return artifact
        check_reference_budget()
        saved = store.load(episode_id) if store.path(episode_id).is_file() else None
        if saved is not None and (
            saved.agent != agent or saved.task != task or saved.run_config != config
        ):
            raise ValueError("Saved experiment checkpoint provenance mismatch")
        if (
            token_limit is not None
            and sum(token_ledger.values()) >= token_limit
            and (saved is None or saved.session.next_node != "end")
        ):
            raise ExperimentTokenBudgetError("EXPERIMENT_TOKEN_BUDGET_EXCEEDED")
        if saved is not None:
            if resume_provider_factory is None:
                raise ValueError("A resumable provider factory is required")
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

    # Run every matrix cell serially: Baseline then Recovery under exact same conditions.
    for pair_index, (task, current_seed, repeat_index) in enumerate(runs):
        # 1. Execute Baseline Episode
        if before_arm is not None:
            before_arm()
        base_id = uuid5(experiment_id, f"{pair_index}:baseline")
        art_base = await run_arm(baseline_agent, task, current_seed, base_id)
        episode_ids.append(base_id)
        record_tokens(art_base)
        record_reference_cost(art_base)

        # 2. Execute Recovery Episode
        if before_arm is not None:
            before_arm()
        rec_id = uuid5(experiment_id, f"{pair_index}:recovery")
        art_rec = await run_arm(recovery_agent, task, current_seed, rec_id)
        episode_ids.append(rec_id)
        record_tokens(art_rec)
        record_reference_cost(art_rec)

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
                baseline_reference_cost=(
                    art_base.reference_cost.amount if art_base.reference_cost is not None else None
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
                recovery_reference_cost=(
                    art_rec.reference_cost.amount if art_rec.reference_cost is not None else None
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
    reference_known = all(
        pair.baseline_reference_cost is not None and pair.recovery_reference_cost is not None
        for pair in pairs
    )
    baseline_reference_total = (
        sum(
            (
                pair.baseline_reference_cost
                for pair in pairs
                if pair.baseline_reference_cost is not None
            ),
            Decimal(),
        )
        if reference_known
        else None
    )
    recovery_reference_total = (
        sum(
            (
                pair.recovery_reference_cost
                for pair in pairs
                if pair.recovery_reference_cost is not None
            ),
            Decimal(),
        )
        if reference_known
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
        baseline_total_reference_cost=baseline_reference_total,
        recovery_total_reference_cost=recovery_reference_total,
        is_reference_cost_known=reference_known,
    )

    exp_config: dict[str, Any] = {
        "comparison_axis": comparison_axis,
        "arm_labels": (
            {"baseline": "Reference Runtime", "recovery": "LangGraph Runtime"}
            if comparison_axis == "runtime_backend"
            else {"baseline": "Full Context", "recovery": "Recent Tool Rounds"}
            if comparison_axis == "context_policy"
            else {"baseline": "Recent Window", "recovery": "Recent Window + Memory"}
            if comparison_axis == "memory_ablation"
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
        "evaluator": "order_status_v2"
        if any(t.evaluator_config.get("evidence_order") == "unordered-v1" for t in tasks)
        else "order_status_v1",
        "environment_version": "tool-lab-m0-v1",
        "seed": resolved_seeds[0],
        "seeds": resolved_seeds,
        "repeat_count": repeat_count,
    }

    for arm, agent in (("baseline", baseline_agent), ("recovery", recovery_agent)):
        if agent.context_policy is not None:
            exp_config[f"{arm}_agent"]["context_policy"] = agent.context_policy.model_dump(
                mode="json"
            )

    if config_metadata:
        # Execution inputs remain authoritative, including for non-API callers.
        for key, value in config_metadata.items():
            if key not in exp_config:
                exp_config[key] = value

    config_hash = compute_config_hash(exp_config)

    experiment_artifact = ExperimentArtifact(
        schema_version="1.5"
        if comparison_axis == "memory_ablation"
        else "1.4"
        if comparison_axis == "context_policy"
        else "1.3"
        if token_limit is not None
        else "1.2",
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
    serialized = json.dumps(artifact.model_dump(mode="json"), ensure_ascii=False, indent=2)
    write_text_atomically(path, serialized + "\n")


def read_experiment(path: Path) -> ExperimentArtifact:
    """Strictly deserialize previously saved ExperimentArtifact without model calls."""
    return ExperimentArtifact.model_validate_json(path.read_text(encoding="utf-8"))
