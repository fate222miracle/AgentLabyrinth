"""Run a pinned paired Experiment and report cross-version outcome regressions."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from apps.api.schemas import CreateExperimentRequest
from apps.api.service import DEFAULT_AIHUBMIX_AGENT, DEFAULT_FAKE_AGENT, EpisodeService
from packages.application.experiment import ExperimentArtifact, read_experiment
from packages.application.reference_pricing import reference_price_version
from packages.application.regression import compare_experiments, fixed_config
from packages.application.trace import write_text_atomically
from packages.domain.models import AgentSpec, ContextPolicy
from packages.environments.tool_lab.environment import TOOL_LAB_TOOL_SET_VERSIONS


class RegressionManifest(BaseModel):
    """A fixed request paired with an immutable saved baseline artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    baseline_artifact: str
    baseline_revision: str
    request: CreateExperimentRequest


def preflight(
    baseline: ExperimentArtifact, request: CreateExperimentRequest, service: EpisodeService
) -> None:
    """Reject changed fixed inputs before spending any model calls."""
    config = baseline.config
    fixed_config(baseline)
    if len(set(request.task_ids)) != len(request.task_ids):
        raise ValueError("Regression tasks must be unique")
    seeds = request.seeds if request.seeds is not None else [request.seed]
    scenario = request.scenario or "invalid-then-success"
    expected: dict[str, Any] = {
        "provider": request.provider,
        "requested_model": request.model,
        "task_ids": request.task_ids,
        "seeds": seeds,
        "repeat_count": request.repeat_count,
        "token_budget": request.token_budget,
        "max_total_tokens": request.max_total_tokens,
        "comparison_axis": request.comparison_axis,
        "fault_profile": request.fault_profile,
        "max_reference_cost_usd": (
            str(request.max_reference_cost_usd)
            if request.max_reference_cost_usd is not None
            else None
        ),
        "reference_price_version": (
            reference_price_version(request.model) if request.provider == "aihubmix" else None
        ),
        "scenario": ("success" if scenario == "clean" else scenario)
        if request.provider == "fake"
        else None,
        "baseline_backend": "handwritten"
        if request.comparison_axis == "runtime_backend"
        else request.runtime_backend,
        "recovery_backend": "langgraph"
        if request.comparison_axis == "runtime_backend"
        else request.runtime_backend,
        "baseline_strategy": request.runtime_strategy
        if request.comparison_axis in ("runtime_backend", "context_policy")
        else "handwritten",
        "recovery_strategy": request.runtime_strategy
        if request.comparison_axis in ("runtime_backend", "context_policy")
        else "handwritten_recovery",
    }
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError("Regression request differs from pinned baseline")
    policy = request.context_policy
    for arm in ("baseline", "recovery"):
        expected_policy = (
            ContextPolicy(mode="full")
            if request.comparison_axis == "context_policy" and arm == "baseline"
            else policy
        )
        saved_policy = config.get(f"{arm}_agent", {}).get("context_policy")
        if saved_policy != (
            expected_policy.model_dump(mode="json") if expected_policy is not None else None
        ):
            raise ValueError("Regression context policy differs from pinned baseline")
    tasks = [
        service._with_fault_profile(  # noqa: SLF001 - same local application composition
            service._with_token_budget(service._get_task(task_id), request.token_budget),
            request.fault_profile,
        )
        for task_id in request.task_ids
    ]
    current_tasks = [
        {
            "id": str(task.id),
            "name": task.name,
            "version": task.version,
            "max_steps": task.max_steps,
            "token_budget": task.token_budget,
            "evaluator_config": task.evaluator_config,
        }
        for task in tasks
    ]
    if config["tasks"] != current_tasks:
        raise ValueError("Regression task version or evaluation protocol changed")
    agent_path = DEFAULT_FAKE_AGENT if request.provider == "fake" else DEFAULT_AIHUBMIX_AGENT
    agent = AgentSpec.model_validate_json(agent_path.read_text(encoding="utf-8"))
    tool_version = config["tool_set_version"]
    if tool_version not in TOOL_LAB_TOOL_SET_VERSIONS:
        raise ValueError("Regression agent or evaluation protocol changed")
    agent = agent.model_copy(update={"tool_set_version": tool_version})
    agent = service._agent_with_token_budget(agent, request.token_budget)
    agent = service._agent_with_time_budget(agent, request.max_execution_time_ms)
    saved_model = config["model"]
    if not isinstance(saved_model, dict):
        raise ValueError("Regression model provenance is unavailable")
    if (
        config["prompt_version"] != agent.prompt_version
        or config["tool_set_version"] != agent.tool_set_version
        or config["budget"] != agent.budget.model_dump(mode="json")
        or saved_model.get("temperature") != agent.model.temperature
        or saved_model.get("max_tokens") != agent.model.max_tokens
        or config["environment_version"] != "tool-lab-m0-v1"
        or config["evaluator"] != "order_status_v1"
    ):
        raise ValueError("Regression agent or evaluation protocol changed")


def run(manifest_path: Path, artifacts_dir: Path, candidate_revision: str, allow_live: bool) -> int:
    """Execute one fixed matrix and save a report; return a CI-friendly exit code."""
    manifest = RegressionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.schema_version != "1.0":
        raise ValueError("Unsupported regression manifest version")
    if manifest.request.provider != "fake" and not allow_live:
        raise ValueError("Real-model regression requires --allow-live")
    baseline_path = (manifest_path.parent / manifest.baseline_artifact).resolve()
    baseline = read_experiment(baseline_path)
    service = EpisodeService(
        artifacts_dir=artifacts_dir, tool_set_version=baseline.config["tool_set_version"]
    )
    preflight(baseline, manifest.request, service)
    candidate = asyncio.run(service.execute_experiment(manifest.request))
    report = compare_experiments(
        baseline,
        candidate,
        baseline_revision=manifest.baseline_revision,
        candidate_revision=candidate_revision,
    )
    output = artifacts_dir / "regression-reports" / f"{candidate.experiment_id}.json"
    write_text_atomically(output, report.model_dump_json(indent=2) + "\n")
    print(f"Report: {output}")
    print(f"Cells: {len(report.cells)}; regressions: {report.regressions}")
    print(f"Improvements: {report.improvements}")
    return 1 if report.regressions else 0


def main() -> int:
    """Parse a pinned manifest and execute the local regression gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts/regression"))
    parser.add_argument("--candidate-revision", default="working-tree")
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    try:
        return run(args.manifest, args.artifacts_dir, args.candidate_revision, args.allow_live)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Regression refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
