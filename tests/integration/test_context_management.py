"""Evaluate context loss and durable recovery using both production schedulers."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))

from packages.application.checkpoint import (  # noqa: E402
    CheckpointStore,
    resume_checkpointed_episode,
)
from packages.application.experiment import create_experiment_plan  # noqa: E402
from packages.application.runner import run_episode  # noqa: E402
from packages.application.trace import JsonTraceRecorder, content_hash, read_artifact  # noqa: E402
from packages.domain.models import (  # noqa: E402
    AgentSpec,
    ContextPolicy,
    EventType,
    Message,
    RuntimeBackend,
    TerminationReason,
)
from packages.environments.tool_lab.environment import ToolLabEnvironment  # noqa: E402
from packages.evaluation.order_status import OrderStatusEvaluator  # noqa: E402
from packages.providers.fake import FakeModelProvider  # noqa: E402
from packages.runtime.factory import create_runtime  # noqa: E402
from packages.runtime.session import EpisodeSession, SessionState  # noqa: E402
from scripts.context_ablation import (  # noqa: E402
    ContextReport,
    diagnostic_count,
    load_inputs,
    run_ablation,
)
from scripts.course_demo import validate_preview_directory  # noqa: E402


def configured(backend: RuntimeBackend, window: int) -> AgentSpec:
    """Window zero denotes the explicit full-history baseline."""
    agent, _, _ = load_inputs(backend)
    policy = (
        ContextPolicy(
            schema_version="1.1",
            algorithm_version="tool-round-window-memory-v1",
            mode="recent_tool_rounds",
            max_tool_rounds=1,
            memory_max_bytes=8192,
        )
        if window == -1
        else ContextPolicy()
        if window == 0
        else ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=window)
    )
    return AgentSpec.model_validate({**agent.model_dump(), "context_policy": policy})


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("window", [0, 1, 2, -1])
def test_document_loss_is_visible_and_budget_bounded(backend: RuntimeBackend, window: int) -> None:
    """Window one forgets the earlier search; this is a Fake engineering outcome."""
    agent = configured(backend, window)
    _, tasks, config = load_inputs(backend)
    artifact = asyncio.run(
        run_episode(
            agent,
            tasks[1],
            config,
            create_runtime(agent, FakeModelProvider()),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
        )
    )
    assert artifact.evaluation.success == (window != 1)
    assert artifact.episode.termination_reason == (
        TerminationReason.MAX_STEPS if window == 1 else TerminationReason.SUCCESS
    )
    assert artifact.episode.model_call_count == (6 if window == 1 else 3)
    requests = [event for event in artifact.events if event.event_type == EventType.MODEL_REQUESTED]
    assert [event.payload["messages_count"] for event in requests] == (
        [2, 4, 4, 4, 4, 4] if window == 1 else [2, 4, 4] if window == -1 else [2, 4, 6]
    )
    assert sum(event.event_type == EventType.EPISODE_FINISHED for event in artifact.events) == 1
    assert artifact.config_hashes["agent"] == content_hash(agent)


def child(backend: RuntimeBackend, window: int, directory: Path) -> None:
    """Actually terminate a separate process after two committed tool rounds."""
    agent = configured(backend, window)
    _, tasks, config = load_inputs(backend)
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(directory / "checkpoints")

    def save(state: SessionState) -> None:
        store.save(state, agent, tasks[1], config, recorder, "normal")
        if state.next_node == "model" and state.budget.tool_call_count == 2:
            os._exit(0)

    asyncio.run(
        run_episode(
            agent,
            tasks[1],
            config,
            create_runtime(agent, FakeModelProvider()),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
            recorder=recorder,
            save_checkpoint=save,
        )
    )
    raise AssertionError("Safe point was not reached")


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("window", [0, 1, 2, -1])
def test_projection_survives_process_exit_with_full_history(
    backend: RuntimeBackend, window: int, tmp_path: Path
) -> None:
    """Checkpoint retains dropped messages; continuation recomputes the same projection."""
    completed = subprocess.run(
        [sys.executable, str(__file__), backend, str(window), str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    store = CheckpointStore(tmp_path / "checkpoints")
    files = list(store.directory.glob("*.json"))
    assert len(files) == 1
    from uuid import UUID

    checkpoint = store.load(UUID(files[0].stem))
    assert len(checkpoint.session.messages) == 6  # Also true when the request window is one.
    assert checkpoint.agent == configured(backend, window)
    artifact = asyncio.run(
        resume_checkpointed_episode(
            checkpoint.episode_id,
            create_runtime(checkpoint.agent, FakeModelProvider(initial_call_count=2)),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
            tmp_path,
        )
    )
    assert artifact.evaluation.success == (window != 1)
    assert sum(event.event_type == EventType.EPISODE_RESUMED for event in artifact.events) == 1
    calls = [
        event.payload["call_id"]
        for event in artifact.events
        if event.event_type == EventType.TOOL_STARTED
    ]
    assert len(calls) == len(set(calls)) == (5 if window == 1 else 3)
    resumed_request = next(
        event
        for event in artifact.events
        if event.event_type == EventType.MODEL_REQUESTED and event.step_index == 3
    )
    assert resumed_request.payload["messages_count"] == (4 if window in (1, -1) else 6)
    if window == -1:
        context = resumed_request.payload["context"]
        assert isinstance(context, dict)
        assert context["memory_source_call_ids"] == ["call_search_1"]
    assert artifact.episode.token_usage.prompt_tokens == (240 if window == 1 else 120)
    altered = json.loads(checkpoint.model_dump_json())
    altered["agent"]["context_policy"] = json.loads(
        ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=3).model_dump_json()
    )
    files[0].write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance mismatch"):
        store.load(checkpoint.episode_id)


def test_invalid_history_stops_before_calling_provider() -> None:
    """Protocol errors have an explicit stop reason and consume no model call."""
    agent = configured("handwritten", 1)
    _, tasks, config = load_inputs("handwritten")
    session = EpisodeSession(
        agent, tasks[0], ToolLabEnvironment(), JsonTraceRecorder(config), FakeModelProvider(), None
    )
    session.observe()
    session.messages.append(Message(role="tool", tool_call_id="orphan"))
    assert asyncio.run(session.call_model()) == "end"
    assert session.detail == "invalid_context_history"
    assert session.budget.model_call_count == 0
    assert not any(
        event.event_type == EventType.MODEL_REQUESTED for event in session.recorder.events
    )


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_too_small_memory_is_a_visible_failure_not_an_automatic_full_fallback(
    backend: RuntimeBackend,
) -> None:
    """Size pressure cannot silently inflate the memory or model budget."""
    agent = configured(backend, -1)
    assert agent.context_policy is not None
    policy = ContextPolicy.model_validate(
        {**agent.context_policy.model_dump(), "memory_max_bytes": 256}
    )
    agent = agent.model_copy(update={"context_policy": policy})
    _, tasks, config = load_inputs(backend)
    artifact = asyncio.run(
        run_episode(
            agent,
            tasks[1],
            config,
            create_runtime(agent, FakeModelProvider()),
            ToolLabEnvironment(),
            OrderStatusEvaluator(),
        )
    )
    assert not artifact.evaluation.success
    assert artifact.episode.termination_reason == TerminationReason.MAX_STEPS
    contexts = [
        event.payload["context"]
        for event in artifact.events
        if event.event_type == EventType.MODEL_REQUESTED
    ]
    assert any(
        isinstance(context, dict) and diagnostic_count(context["memory_omitted_entries_count"]) > 0
        for context in contexts
    )
    assert all(
        isinstance(context, dict) and diagnostic_count(context["memory_bytes"]) <= 256
        for context in contexts
    )


def test_cli_template_records_actual_scores_and_only_one_variable(tmp_path: Path) -> None:
    """The fixed template can be rerun without a key and refuses overwriting evidence."""
    directory = tmp_path / "ablation"
    report = asyncio.run(run_ablation(directory))
    assert report.expected_outcomes_match
    assert len(report.cases) == 24
    assert sum(case.success for case in report.cases) == 20
    assert (
        ContextReport.model_validate_json(
            (directory / "context-ablation.json").read_text(encoding="utf-8")
        )
        == report
    )
    for index in range(0, len(report.cases), 3):
        group = report.cases[index : index + 3]
        assert len({case.config_hashes["task"] for case in group}) == 1
        assert len({case.config_hashes["run_config"] for case in group}) == 1
        assert all(
            case.agent.model_dump(exclude={"context_policy"})
            == group[0].agent.model_dump(exclude={"context_policy"})
            for case in group
        )
    for case in report.cases:
        artifact = read_artifact(directory / f"{case.episode_id}.json")
        assert case.success == artifact.evaluation.success
        assert case.config_hashes == artifact.config_hashes
    validate_preview_directory(directory)
    (directory / "context-ablation.json").write_text(
        report.model_copy(update={"expected_outcomes_match": False}).model_dump_json(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fixed expectations"):
        validate_preview_directory(directory)
    with pytest.raises(FileExistsError):
        asyncio.run(run_ablation(directory))


@pytest.mark.parametrize("axis", ["recovery_policy", "runtime_backend"])
def test_existing_comparisons_reject_context_as_second_variable(axis: str) -> None:
    """A new Agent field cannot silently confound historical comparison axes."""
    baseline = configured("handwritten", 0)
    candidate = configured("handwritten" if axis == "recovery_policy" else "langgraph", 1)
    if axis == "recovery_policy":
        candidate = candidate.model_copy(update={"runtime_strategy": "handwritten_recovery"})
    _, tasks, _ = load_inputs("handwritten")
    with pytest.raises(ValueError, match="share context_policy"):
        create_experiment_plan(baseline, candidate, list(tasks), [1], 1, axis, {})  # type: ignore[arg-type]


if __name__ == "__main__":
    child(sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]))  # type: ignore[arg-type]
