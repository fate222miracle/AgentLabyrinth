"""Unit tests for Application experiment runner and metrics aggregation."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from packages.application.experiment import (
    compute_config_hash,
    read_experiment,
    run_experiment,
)
from packages.domain.models import AgentSpec, TaskSpec
from packages.providers.fake import FakeModelProvider

ROOT = Path(__file__).resolve().parents[2]


def load_tasks() -> list[TaskSpec]:
    """Load the 4 native tasks for testing."""
    task_files = [
        "order-status-001.json",
        "order-status-002.json",
        "order-status-003.json",
        "order-status-004.json",
    ]
    tasks = []
    for f in task_files:
        tasks.append(
            TaskSpec.model_validate_json(
                (ROOT / f"benchmarks/tool_lab_core/tasks/{f}").read_text(encoding="utf-8")
            )
        )
    return tasks


def make_agents() -> tuple[AgentSpec, AgentSpec]:
    """Create sample baseline and recovery agent specs."""
    base = AgentSpec(
        id=uuid4(),
        name="test-baseline",
        version="1.0.0",
        description="baseline agent",
        prompt_version="v1",
        tool_set_version="v1",
        runtime_strategy="handwritten",
    )
    rec = AgentSpec(
        id=uuid4(),
        name="test-recovery",
        version="1.0.0",
        description="recovery agent",
        prompt_version="v1",
        tool_set_version="v1",
        runtime_strategy="handwritten_recovery",
    )
    return base, rec


def test_runtime_comparison_marks_recovery_metrics_not_applicable() -> None:
    """Runtime backend comparisons cannot claim parameter-error recovery."""
    base_agent, _ = make_agents()
    graph_agent = base_agent.model_copy(update={"runtime_backend": "langgraph"})
    with TemporaryDirectory() as tmp_dir:
        artifact = asyncio.run(
            run_experiment(
                baseline_agent=base_agent,
                recovery_agent=graph_agent,
                tasks=load_tasks()[:1],
                provider_factory=lambda: FakeModelProvider(scenario="success"),
                artifacts_dir=Path(tmp_dir),
                comparison_axis="runtime_backend",
            )
        )
        assert artifact.metrics.baseline_success_count == 1
        assert artifact.metrics.recovery_success_count == 1
        assert artifact.metrics.retry_eligible_count is None
        assert artifact.metrics.retry_recovery_count is None
        assert artifact.metrics.retry_recovery_rate is None
        assert (
            read_experiment(
                Path(tmp_dir) / "experiments" / f"{artifact.experiment_id}.json"
            ).metrics.retry_recovery_count
            is None
        )


def test_experiment_runner_deterministic_recovery() -> None:
    """Paired experiment under invalid_then_success demonstrates 100% recovery."""
    tasks = load_tasks()
    base_agent, rec_agent = make_agents()

    with TemporaryDirectory() as tmp_dir:
        artifacts_dir = Path(tmp_dir)

        artifact = asyncio.run(
            run_experiment(
                baseline_agent=base_agent,
                recovery_agent=rec_agent,
                tasks=tasks,
                provider_factory=lambda: FakeModelProvider(scenario="invalid_then_success"),
                seed=42,
                artifacts_dir=artifacts_dir,
                config_metadata={"model": {"temperature": 1.5}, "seed": 999},
            )
        )

        assert artifact.metrics.total_pairs == 4
        assert artifact.config["model"]["temperature"] == base_agent.model.temperature
        assert artifact.config["seed"] == 42
        # Baseline failed on all 4 because of initial invalid arguments
        assert artifact.metrics.baseline_success_count == 0
        assert artifact.metrics.baseline_success_rate == 0.0

        # Recovery succeeded on all 4 because it retried with schema feedback
        assert artifact.metrics.recovery_success_count == 4
        assert artifact.metrics.recovery_success_rate == 1.0

        # All 4 were successfully recovered
        assert artifact.metrics.retry_recovery_count == 4
        assert artifact.metrics.retry_recovery_rate == 1.0

        # Cost known for fake provider
        assert artifact.metrics.is_cost_known is True
        assert artifact.metrics.baseline_total_cost is not None
        assert artifact.metrics.recovery_total_cost is not None
        assert artifact.metrics.recovery_total_cost > artifact.metrics.baseline_total_cost > 0

        # Check each pair
        for pair in artifact.pairs:
            assert pair.baseline_success is False
            assert pair.recovery_success is True
            assert pair.recovered is True
            # Recovery used more tokens and steps
            assert pair.recovery_tokens > pair.baseline_tokens
            assert pair.recovery_steps > pair.baseline_steps

        # Test persistence and pure read
        exp_file = artifacts_dir / "experiments" / f"{artifact.experiment_id}.json"
        assert exp_file.is_file()

        loaded = read_experiment(exp_file)
        assert loaded.experiment_id == artifact.experiment_id
        assert loaded.config_hash == artifact.config_hash
        assert loaded.metrics.retry_recovery_count == 4
        assert loaded.metrics.retry_eligible_count == 4
        assert loaded.metrics.retry_recovery_rate == 1.0

        # Fixed variables preservation check
        assert "baseline_agent" in loaded.config
        assert "recovery_agent" in loaded.config
        assert "model" in loaded.config
        assert "budget" in loaded.config
        assert "tasks" in loaded.config
        assert "evaluator" in loaded.config
        assert len(loaded.config["tasks"]) == 4


def test_experiment_runner_clean_baseline() -> None:
    """Paired experiment under normal scenario shows tied success (recovered=0)."""
    tasks = load_tasks()[:2]
    base_agent, rec_agent = make_agents()

    with TemporaryDirectory() as tmp_dir:
        artifacts_dir = Path(tmp_dir)

        artifact = asyncio.run(
            run_experiment(
                baseline_agent=base_agent,
                recovery_agent=rec_agent,
                tasks=tasks,
                provider_factory=lambda: FakeModelProvider(scenario="normal"),
                seed=1,
                artifacts_dir=artifacts_dir,
            )
        )

        assert artifact.metrics.total_pairs == 2
        assert artifact.metrics.baseline_success_count == 2
        assert artifact.metrics.recovery_success_count == 2
        assert artifact.metrics.retry_eligible_count == 0
        assert artifact.metrics.retry_recovery_count == 0
        assert artifact.metrics.retry_recovery_rate == 0.0

        for pair in artifact.pairs:
            assert pair.baseline_success is True
            assert pair.recovery_success is True
            assert pair.retry_eligible is False
            assert pair.recovered is False


def test_experiment_runner_seed_repeat_matrix_is_paired_and_serializable() -> None:
    """Every seed and repeat produces one identifiable Baseline/Recovery pair per task."""
    base_agent, rec_agent = make_agents()

    with TemporaryDirectory() as tmp_dir:
        artifact = asyncio.run(
            run_experiment(
                baseline_agent=base_agent,
                recovery_agent=rec_agent,
                tasks=load_tasks()[:1],
                provider_factory=lambda: FakeModelProvider(scenario="normal"),
                seeds=[7, 9],
                repeat_count=2,
                artifacts_dir=Path(tmp_dir),
            )
        )

        assert artifact.schema_version == "1.2"
        assert artifact.metrics.total_pairs == 4
        assert len(artifact.episode_ids) == 8
        assert {(pair.seed, pair.repeat_index) for pair in artifact.pairs} == {
            (7, 1),
            (7, 2),
            (9, 1),
            (9, 2),
        }
        assert artifact.config["seed"] == 7
        assert artifact.config["seeds"] == [7, 9]
        assert artifact.config["repeat_count"] == 2


def test_misattribution_non_invalid_arguments_not_recovered() -> None:
    """Baseline failures from forbidden_tool must NOT be marked retry_eligible or recovered."""
    tasks = load_tasks()[:2]
    base_agent, rec_agent = make_agents()

    with TemporaryDirectory() as tmp_dir:
        artifacts_dir = Path(tmp_dir)

        artifact = asyncio.run(
            run_experiment(
                baseline_agent=base_agent,
                recovery_agent=rec_agent,
                tasks=tasks,
                provider_factory=lambda: FakeModelProvider(scenario="forbidden_tool"),
                seed=1,
                artifacts_dir=artifacts_dir,
            )
        )

        assert artifact.metrics.total_pairs == 2
        assert artifact.metrics.baseline_success_count == 0
        assert artifact.metrics.recovery_success_count == 0
        # Crucial: forbidden_tool is NOT retry eligible!
        assert artifact.metrics.retry_eligible_count == 0
        assert artifact.metrics.retry_recovery_count == 0
        assert artifact.metrics.retry_recovery_rate == 0.0

        for pair in artifact.pairs:
            assert pair.baseline_success is False
            assert pair.retry_eligible is False
            assert pair.recovered is False


def test_config_hash_deterministic() -> None:
    """Config hash must be deterministic regardless of dictionary insertion order."""
    cfg1 = {"b": 2, "a": 1, "c": [3, 4]}
    cfg2 = {"a": 1, "c": [3, 4], "b": 2}
    assert compute_config_hash(cfg1) == compute_config_hash(cfg2)


def test_read_legacy_experiment_artifact_preserves_none() -> None:
    """Reading legacy experiment artifact without new metric fields preserves None."""
    legacy_file = ROOT / "tests/fixtures/legacy_experiment.json"
    assert legacy_file.is_file()

    loaded = read_experiment(legacy_file)
    assert loaded.metrics.retry_eligible_count is None
    assert loaded.metrics.baseline_avg_model_calls is None
    assert loaded.metrics.recovery_avg_model_calls is None
    assert loaded.metrics.baseline_avg_tool_calls is None
    assert loaded.metrics.recovery_avg_tool_calls is None
    assert loaded.metrics.retry_recovery_count == 4
    assert loaded.metrics.baseline_total_cost is None
    assert loaded.metrics.recovery_total_cost is None

    for pair in loaded.pairs:
        assert pair.repeat_index == 1
        assert pair.retry_eligible is None
        assert pair.baseline_model_calls is None
        assert pair.recovery_model_calls is None


def test_forbidden_tool_with_invalid_arguments_not_retry_eligible() -> None:
    """Forbidden tool with invalid arguments must have retry_eligible=False."""
    tasks = [t.model_copy(update={"forbidden_tools": ("query_records",)}) for t in load_tasks()[:2]]
    base_agent, rec_agent = make_agents()

    with TemporaryDirectory() as tmp_dir:
        artifacts_dir = Path(tmp_dir)

        artifact = asyncio.run(
            run_experiment(
                baseline_agent=base_agent,
                recovery_agent=rec_agent,
                tasks=tasks,
                provider_factory=lambda: FakeModelProvider(scenario="invalid_arguments"),
                seed=1,
                artifacts_dir=artifacts_dir,
            )
        )

        assert artifact.metrics.total_pairs == 2
        assert artifact.metrics.baseline_success_count == 0
        assert artifact.metrics.recovery_success_count == 0
        assert artifact.metrics.retry_eligible_count == 0
        assert artifact.metrics.retry_recovery_count == 0
        assert artifact.metrics.retry_recovery_rate == 0.0

        for pair in artifact.pairs:
            assert pair.baseline_success is False
            assert pair.recovery_success is False
            assert pair.retry_eligible is False
            assert pair.recovered is False
            assert pair.baseline_model_calls == 1
            assert pair.recovery_model_calls == 1
            assert pair.baseline_tool_calls == 0
            assert pair.recovery_tool_calls == 0
