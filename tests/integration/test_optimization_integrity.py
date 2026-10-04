"""Regression cases for existing context, recovery, and diagnostic trust boundaries."""

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore, resume_checkpointed_episode
from packages.application.experiment import compute_config_hash, read_experiment
from packages.application.regression import compare_experiments, fixed_config
from packages.application.runner import run_episode
from packages.application.trace import write_artifact
from packages.domain.models import (
    Budget,
    ContextPolicy,
    EventType,
    RuntimeBackend,
    TerminationReason,
)
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime import session as session_module
from packages.runtime.context import project_context
from packages.runtime.factory import create_runtime
from scripts.context_ablation import ContextReport, load_inputs, run_ablation
from scripts.course_demo import validate_preview_directory

ROOT = Path(__file__).resolve().parents[2]


def test_context_policy_is_a_fixed_variable_without_changing_legacy_fingerprint() -> None:
    """An otherwise identical context policy must never share a history group."""
    baseline = read_experiment(ROOT / "benchmarks/regression/course-smoke-baseline.json")
    legacy = fixed_config(baseline)
    assert all("context_policy" not in legacy[arm] for arm in ("baseline_agent", "recovery_agent"))
    config = json.loads(json.dumps(baseline.config))
    for arm in ("baseline_agent", "recovery_agent"):
        config[arm]["schema_version"] = "1.2"
        config[arm]["context_policy"] = ContextPolicy(
            mode="recent_tool_rounds", max_tool_rounds=1
        ).model_dump(mode="json")
    changed = baseline.model_copy(
        update={"config": config, "config_hash": compute_config_hash(config)}
    )
    assert compute_config_hash(fixed_config(changed)) != compute_config_hash(legacy)
    with pytest.raises(ValueError, match="identical fixed configuration"):
        compare_experiments(
            baseline, changed, baseline_revision="before", candidate_revision="after"
        )
    config["baseline_agent"]["context_policy"]["mode"] = "future"
    with pytest.raises(ValueError):
        fixed_config(changed.model_copy(update={"config_hash": compute_config_hash(config)}))


@pytest.fixture(scope="module")
def context_pack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate real saved Fake evidence once, without any API Key."""
    directory = tmp_path_factory.mktemp("context-source") / "pack"
    report = asyncio.run(run_ablation(directory))
    assert report.expected_outcomes_match
    return directory


@pytest.mark.parametrize(
    "damage", ["missing", "identity", "metric", "hash", "matrix", "trace", "tokens", "tools"]
)
def test_preview_rejects_report_or_artifact_corruption(
    context_pack: Path, tmp_path: Path, damage: str
) -> None:
    """A true completion flag cannot authorize replay of inconsistent saved evidence."""
    directory = tmp_path / "pack"
    shutil.copytree(context_pack, directory)
    report_file = directory / "context-ablation.json"
    report = json.loads(report_file.read_text(encoding="utf-8"))
    case = report["cases"][0]
    artifact_file = directory / f"{case['episode_id']}.json"
    artifact = json.loads(artifact_file.read_text(encoding="utf-8"))
    if damage == "missing":
        artifact_file.unlink()
    elif damage == "identity":
        artifact_file.write_bytes(
            (directory / f"{report['cases'][1]['episode_id']}.json").read_bytes()
        )
    elif damage == "metric":
        case["input_messages_bytes"] += 1
        report_file.write_text(json.dumps(report), encoding="utf-8")
    elif damage == "hash":
        artifact["agent"]["prompt_version"] = "changed-after-execution"
        artifact_file.write_text(json.dumps(artifact), encoding="utf-8")
    elif damage == "matrix":
        report["cases"][1] = case
        report_file.write_text(json.dumps(report), encoding="utf-8")
    elif damage == "trace":
        artifact["events"][0]["episode_id"] = report["cases"][1]["episode_id"]
        artifact_file.write_text(json.dumps(artifact), encoding="utf-8")
    else:
        field = "prompt_tokens" if damage == "tokens" else "tool_call_count"
        target = artifact["episode"]["token_usage"] if damage == "tokens" else artifact["episode"]
        target[field] += 1
        case["simulated_prompt_tokens" if damage == "tokens" else "tool_calls"] += 1
        artifact_file.write_text(json.dumps(artifact), encoding="utf-8")
        report_file.write_text(json.dumps(report), encoding="utf-8")
    with patch("packages.providers.fake.FakeModelProvider.generate") as model:
        with pytest.raises(ValueError):
            validate_preview_directory(directory)
        model.assert_not_called()


def test_cli_failure_rerun_retains_original_context_and_source(
    context_pack: Path, tmp_path: Path
) -> None:
    """The visible retry action is runnable with pinned Fake provenance and a new ID."""
    directory = tmp_path / "pack"
    shutil.copytree(context_pack, directory)
    report = ContextReport.model_validate_json(
        (directory / "context-ablation.json").read_text(encoding="utf-8")
    )
    failed = next(case for case in report.cases if not case.success)
    original_file = directory / f"{failed.episode_id}.json"
    before = original_file.read_bytes()
    artifact = asyncio.run(
        EpisodeService(artifacts_dir=directory).rerun_failed_episode(failed.episode_id)
    )
    assert artifact.episode.episode_id != failed.episode_id
    assert artifact.agent == failed.agent
    assert artifact.episode.termination_reason == TerminationReason.MAX_STEPS
    assert not artifact.evaluation.success
    assert original_file.read_bytes() == before


@pytest.mark.parametrize("damage", ["foreign_id", "wrong_source"])
def test_conflicting_complete_result_does_not_hide_safe_point_or_get_reused(
    tmp_path: Path, damage: str
) -> None:
    """A parseable wrong result cannot be treated as a completed requested Episode."""
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tests/integration/test_checkpoint_resume.py"),
            "--child",
            "handwritten",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    store = CheckpointStore(tmp_path / "checkpoints")
    checkpoint_file = next(store.directory.glob("*.json"))
    checkpoint = store.load(UUID(checkpoint_file.stem))
    foreign = asyncio.run(
        run_episode(
            checkpoint.agent,
            checkpoint.task,
            checkpoint.run_config,
            create_runtime(checkpoint.agent, FakeModelProvider()),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
        )
    )
    if damage == "wrong_source":
        # Self-consistent result hash, same requested ID, but a different pinned Agent.
        agent = foreign.agent.model_copy(update={"prompt_version": "foreign"})
        from packages.application.trace import content_hash

        foreign = foreign.model_copy(
            update={
                "episode": foreign.episode.model_copy(update={"episode_id": checkpoint.episode_id}),
                "agent": agent,
                "events": tuple(
                    event.model_copy(update={"episode_id": checkpoint.episode_id})
                    for event in foreign.events
                ),
                "config_hashes": {**foreign.config_hashes, "agent": content_hash(agent)},
            }
        )
    path = tmp_path / f"{checkpoint.episode_id}.json"
    write_artifact(foreign, path)
    before = path.read_bytes()
    service = EpisodeService(artifacts_dir=tmp_path)
    assert checkpoint.episode_id in service.resumable_episode_ids()
    with patch("packages.providers.fake.FakeModelProvider.generate") as model:
        with pytest.raises(ValueError, match="mismatch"):
            asyncio.run(
                resume_checkpointed_episode(
                    checkpoint.episode_id,
                    create_runtime(checkpoint.agent, FakeModelProvider()),
                    ToolLabEnvironment(),
                    OrderStatusEvaluator(),
                    tmp_path,
                )
            )
        model.assert_not_called()
    assert path.read_bytes() == before and checkpoint_file.exists()


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_projection_time_expiry_cannot_start_a_model_call(
    backend: RuntimeBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Advance a deterministic clock during projection; no real waiting or upstream call."""
    clock = [0.0]
    monkeypatch.setattr(session_module, "perf_counter", lambda: clock[0])
    original = project_context

    def project(*args: object, **kwargs: object) -> object:
        projection = original(*args, **kwargs)  # type: ignore[arg-type]
        clock[0] = 0.02
        return projection

    monkeypatch.setattr(session_module, "project_context", project)
    base, tasks, config = load_inputs(backend)
    agent = base.model_copy(
        update={
            "context_policy": ContextPolicy(),
            "budget": Budget(schema_version="1.1", max_execution_time_ms=10),
        }
    )
    artifact = asyncio.run(
        run_episode(
            agent,
            tasks[0],
            config,
            create_runtime(agent, FakeModelProvider()),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
        )
    )
    assert artifact.episode.termination_reason == TerminationReason.TIME_BUDGET_EXCEEDED
    assert artifact.episode.model_call_count == 0
    assert not any(event.event_type == EventType.MODEL_REQUESTED for event in artifact.events)
