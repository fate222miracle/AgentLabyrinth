"""Interrupt one real episode at a committed safe point, then resume it."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest  # noqa: E402
from apps.api.service import EpisodeService  # noqa: E402
from packages.application.checkpoint import CheckpointStore  # noqa: E402
from packages.application.trace import JsonTraceRecorder  # noqa: E402
from packages.domain.models import AgentSpec, EventType, RunConfig, TaskSpec  # noqa: E402
from packages.runtime.session import SessionState  # noqa: E402

MODEL = "coding-minimax-m2.7-free"


def interrupted_run(directory: Path, suite: str, backend: str) -> None:
    """Stop the child only after the first tool result has been saved."""
    original_save = CheckpointStore.save
    experiment_request = CreateExperimentRequest(
        provider="aihubmix",
        model=MODEL,
        task_ids=["order-status-001"],
        token_budget=8000,
        runtime_backend=backend,
    )

    def stop_after_first_tool(
        store: CheckpointStore,
        state: SessionState,
        agent: AgentSpec,
        task: TaskSpec,
        config: RunConfig,
        recorder: JsonTraceRecorder,
        fake_scenario: str | None = None,
    ) -> None:
        original_save(store, state, agent, task, config, recorder, fake_scenario)
        if suite == "experiment":
            if recorder.episode_id == uuid5(experiment_request.request_id, "0:recovery"):
                os._exit(75)
            return
        succeeded = [
            event for event in recorder.events if event.event_type == EventType.TOOL_SUCCEEDED
        ]
        names = {
            str(event.payload.get("call_id")): event.payload.get("name")
            for event in recorder.events
            if event.event_type == EventType.TOOL_STARTED
        }
        committed = (
            state.next_node == "end" and state.budget.tool_call_count == 1
            if suite == "bfcl"
            else state.next_node == "model"
            and any(
                names.get(str(event.payload.get("call_id")))
                == ("read_document" if suite == "mcp" else "query_records")
                for event in succeeded
            )
        )
        if committed:
            os._exit(75)

    CheckpointStore.save = stop_after_first_tool  # type: ignore[method-assign,assignment]
    service = EpisodeService(artifacts_dir=directory, live_model_catalog=True)
    if suite == "experiment":
        service.reserve_experiment_job(experiment_request.request_id)
        service.update_experiment_job(experiment_request.request_id, status="running")
        asyncio.run(
            service.execute_experiment(experiment_request, job_id=experiment_request.request_id)
        )
        raise RuntimeError("The experiment did not reach its second arm")
    asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(
                provider="aihubmix",
                model=MODEL,
                task_id={
                    "tool_lab": "order-status-001",
                    "bfcl": "bfcl-simple_python_1",
                    "mcp": "order-status-007",
                }[suite],
                suite="bfcl_adapted" if suite == "bfcl" else "tool_lab_core",
                tool_transport="mcp" if suite == "mcp" else "local",
                runtime_backend=backend,
                max_steps=1 if suite == "bfcl" else 6,
                token_budget=8000,
            )
        )
    )
    raise RuntimeError("The model did not reach the requested committed safe point")


def resume_experiment_probe(directory: Path) -> None:
    """Verify a completed real arm survives process exit without another model request."""
    plan = next((directory / "experiments/checkpoints").glob("*.json"))
    experiment_id = UUID(plan.stem)
    baseline = directory / f"{uuid5(experiment_id, '0:baseline')}.json"
    before = baseline.read_bytes()
    service = EpisodeService(artifacts_dir=directory, live_model_catalog=True)
    assert experiment_id in service.resumable_experiment_job_ids()
    artifact = asyncio.run(service.resume_experiment_job(experiment_id))
    service.update_experiment_job(experiment_id, status="completed")
    assert baseline.read_bytes() == before
    assert artifact.experiment_id == experiment_id
    assert not plan.exists()
    assert artifact.metrics.baseline_success_count == artifact.metrics.recovery_success_count == 1
    assert experiment_id not in service.resumable_experiment_job_ids()
    report = {
        "schema_version": "1.0",
        "experiment_id": str(experiment_id),
        "model": MODEL,
        "baseline_episode_id": str(artifact.episode_ids[0]),
        "recovery_episode_id": str(artifact.episode_ids[1]),
        "success": True,
        "baseline_file_unchanged": True,
        "tokens": artifact.metrics.baseline_total_tokens + artifact.metrics.recovery_total_tokens,
    }
    (directory / "probe-result.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report))


def main() -> None:
    """Resume in a fresh process and report only nonsecret verification facts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", choices=("tool_lab", "bfcl", "mcp", "experiment"), default="tool_lab"
    )
    parser.add_argument("--runtime", choices=("handwritten", "langgraph"), default="handwritten")
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    directory = (
        args.artifacts_dir
        or ROOT / "artifacts" / "live-resume-probe" / f"{args.suite}-{args.runtime}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    if args.child:
        interrupted_run(directory, args.suite, args.runtime)
        return
    if list((directory / "checkpoints").glob("*.json")):
        raise RuntimeError("A prior unfinished probe exists; inspect it before rerunning")
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            "--suite",
            args.suite,
            "--runtime",
            args.runtime,
            "--artifacts-dir",
            str(directory),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode != 75:
        raise RuntimeError(
            f"Probe did not reach its safe point (exit {result.returncode}); inspect {directory}"
        )
    if args.suite == "experiment":
        resume_experiment_probe(directory)
        return
    checkpoints = list((directory / "checkpoints").glob("*.json"))
    if len(checkpoints) != 1:
        raise RuntimeError(f"Expected one checkpoint, found {len(checkpoints)}")
    episode_id = UUID(checkpoints[0].stem)
    before = CheckpointStore(checkpoints[0].parent).load(episode_id)
    assert before.session.budget.model_call_count >= 1
    assert before.session.budget.tool_call_count >= 1
    committed_events = before.events
    service = EpisodeService(artifacts_dir=directory, live_model_catalog=True)
    artifact = asyncio.run(service.resume_episode(episode_id))
    types = [event.event_type for event in artifact.events]
    tool_calls = [
        event.payload.get("call_id")
        for event in artifact.events
        if event.event_type == EventType.TOOL_STARTED
    ]
    assert types.count(EventType.EPISODE_RESUMED) == 1
    assert types.count(EventType.EPISODE_FINISHED) == 1
    assert artifact.events[: len(committed_events)] == committed_events
    assert len(tool_calls) == len(set(tool_calls)) == artifact.episode.tool_call_count
    assert all(
        current.parent_event_id == previous.event_id
        for previous, current in zip(artifact.events, artifact.events[1:], strict=False)
    )
    assert not checkpoints[0].exists()
    assert (directory / f"{episode_id}.json").is_file()
    if args.suite == "bfcl":
        assert artifact.episode.model_call_count == before.session.budget.model_call_count
        assert artifact.episode.tool_call_count == before.session.budget.tool_call_count
    assert artifact.evaluation.success, artifact.episode.detail
    tokens = artifact.episode.token_usage
    report = {
        "schema_version": "1.0",
        "episode_id": str(episode_id),
        "model": MODEL,
        "suite": args.suite,
        "runtime": args.runtime,
        "success": artifact.evaluation.success,
        "checkpoint_model_calls": before.session.budget.model_call_count,
        "checkpoint_tool_calls": before.session.budget.tool_call_count,
        "model_calls": artifact.episode.model_call_count,
        "tool_calls": artifact.episode.tool_call_count,
        "tokens": tokens.prompt_tokens + tokens.completion_tokens,
        "committed_trace_preserved": True,
        "unique_tool_call_ids": True,
    }
    (directory / "probe-result.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
