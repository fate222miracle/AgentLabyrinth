"""Run a fixed offline context-policy ablation through the production episode path."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from packages.application.runner import run_episode
from packages.application.trace import (
    JsonTraceRecorder,
    content_hash,
    read_artifact,
    write_artifact,
    write_text_atomically,
)
from packages.domain.models import (
    AgentSpec,
    ContextPolicy,
    Contract,
    EpisodeArtifact,
    EventType,
    NonNegativeInt,
    RunConfig,
    RuntimeBackend,
    TaskSpec,
    TerminationReason,
)
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime, runtime_version

ROOT = Path(__file__).resolve().parents[1]
POLICIES = (
    ContextPolicy(),
    ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=1),
    ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=2),
)
BACKENDS: tuple[RuntimeBackend, ...] = ("handwritten", "langgraph")


class ContextCase(Contract):
    """Actual per-episode observations; byte counts are distinct from simulated tokens."""

    episode_id: UUID
    task_name: str
    seed: int
    agent: AgentSpec
    config_hashes: dict[str, str]
    success: bool
    termination_reason: TerminationReason
    steps: NonNegativeInt
    model_calls: NonNegativeInt
    tool_calls: NonNegativeInt
    simulated_prompt_tokens: NonNegativeInt
    simulated_completion_tokens: NonNegativeInt
    input_messages_bytes: NonNegativeInt
    dropped_messages_count: NonNegativeInt
    visible_messages_counts: tuple[NonNegativeInt, ...]


class ContextReport(Contract):
    """Diagnostic CLI report, explicitly separate from the Experiment contract."""

    report_kind: Literal["fake-context-ablation-v1"] = "fake-context-ablation-v1"
    report_id: UUID
    created_at: datetime
    provider: Literal["fake"] = "fake"
    simulated: Literal[True] = True
    input_measurement: Literal["canonical-message-json-utf8-bytes"] = (
        "canonical-message-json-utf8-bytes"
    )
    cases: tuple[ContextCase, ...]
    expected_outcomes_match: bool

    def validate_artifacts(self, directory: Path) -> None:
        """Cross-check the complete fixed matrix against its saved Episode evidence."""
        if not self.expected_outcomes_match:
            raise ValueError("Context ablation did not match its fixed expectations")
        expected_cells = {
            (backend, task, seed, policy.mode, policy.max_tool_rounds)
            for backend in BACKENDS
            for task in ("order-status-001", "order-status-007")
            for seed in (1, 17)
            for policy in POLICIES
        }
        cells: set[tuple[str, str, int, str, int | None]] = set()
        identities: set[UUID] = set()
        fixed_groups: dict[tuple[str, str, int], tuple[dict[str, object], str, str]] = {}
        for case in self.cases:
            policy = case.agent.context_policy
            if policy is None or case.episode_id in identities:
                raise ValueError("Duplicate or incomplete context matrix")
            identities.add(case.episode_id)
            cell = (
                case.agent.runtime_backend,
                case.task_name,
                case.seed,
                policy.mode,
                policy.max_tool_rounds,
            )
            if cell not in expected_cells or cell in cells:
                raise ValueError("Invalid context matrix cell")
            cells.add(cell)
            try:
                artifact = read_artifact(directory / f"{case.episode_id}.json")
            except (OSError, ValueError) as exc:
                raise ValueError("Missing or invalid context Episode artifact") from exc
            if case_from_artifact(artifact) != case:
                raise ValueError("Context report and Episode evidence mismatch")
            forgets = case.task_name == "order-status-007" and policy.max_tool_rounds == 1
            reason = TerminationReason.MAX_STEPS if forgets else TerminationReason.SUCCESS
            if case.success != (not forgets) or case.termination_reason != reason:
                raise ValueError("Context ablation did not match its fixed expectations")
            group = (case.agent.runtime_backend, case.task_name, case.seed)
            fixed = (
                artifact.agent.model_dump(exclude={"context_policy"}),
                artifact.config_hashes["task"],
                artifact.config_hashes["run_config"],
            )
            if group in fixed_groups and fixed_groups[group] != fixed:
                raise ValueError("Context comparison changed a fixed variable")
            fixed_groups[group] = fixed
        if cells != expected_cells:
            raise ValueError("Incomplete context matrix")


def load_inputs(backend: RuntimeBackend) -> tuple[AgentSpec, tuple[TaskSpec, ...], RunConfig]:
    """Load the unchanged native tasks and fix all variables except the projection."""
    directory = ROOT / "benchmarks/tool_lab_core"
    base = AgentSpec.model_validate_json(
        (directory / "agents/baseline-m0.json").read_text(encoding="utf-8")
    )
    # All three arms use the same identity, prompt, budget and recovery configuration.
    agent = AgentSpec.model_validate(
        {**base.model_dump(), "schema_version": "1.2", "runtime_backend": backend}
    )
    tasks = tuple(
        TaskSpec.model_validate_json(
            (directory / f"tasks/order-status-{number}.json").read_text(encoding="utf-8")
        )
        for number in ("001", "007")
    )
    return agent, tasks, RunConfig(seed=1, runtime_version=runtime_version(backend))


def diagnostic_count(value: object) -> int:
    """Reject missing or malformed measurements instead of inventing zero values."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("Invalid context measurement")
    return value


def case_from_artifact(artifact: EpisodeArtifact) -> ContextCase:
    """Derive measured observations from owned, internally consistent Fake evidence."""
    episode = artifact.episode
    policy = artifact.agent.context_policy
    expected_hashes = {
        "agent": content_hash(artifact.agent),
        "task": content_hash(artifact.task),
        "run_config": content_hash(artifact.run_config),
    }
    if (
        policy is None
        or artifact.agent.model.provider != "fake"
        or not episode.token_usage.simulated
        or artifact.config_hashes != expected_hashes
    ):
        raise ValueError("Context Episode provenance mismatch")
    events = artifact.events
    if (
        not events
        or events[0].event_type != EventType.EPISODE_STARTED
        or events[0].parent_event_id is not None
        or events[-1].event_type != EventType.EPISODE_FINISHED
        or len({event.event_id for event in events}) != len(events)
        or any(event.episode_id != episode.episode_id for event in events)
        or sum(event.event_type == EventType.EPISODE_STARTED for event in events) != 1
        or sum(event.event_type == EventType.EPISODE_FINISHED for event in events) != 1
        or any(
            current.parent_event_id != previous.event_id or current.step_index < previous.step_index
            for previous, current in zip(events, events[1:], strict=False)
        )
    ):
        raise ValueError("Context Episode Trace mismatch")
    requests = [event for event in events if event.event_type == EventType.MODEL_REQUESTED]
    responses = [event for event in events if event.event_type == EventType.MODEL_RESPONDED]
    if (
        len(requests) != episode.model_call_count
        or len(responses) != len(requests)
        or sum(event.event_type == EventType.TOOL_STARTED for event in events)
        != episode.tool_call_count
        or sum(event.token_usage.prompt_tokens for event in responses)
        != episode.token_usage.prompt_tokens
        or sum(event.token_usage.completion_tokens for event in responses)
        != episode.token_usage.completion_tokens
        or any(not event.token_usage.simulated for event in responses)
        or events[-1].step_index != episode.step_count
        or events[-1].payload.get("termination_reason") != episode.termination_reason.value
        or events[-1].payload.get("success") is not artifact.evaluation.success
    ):
        raise ValueError("Context Episode metrics and Trace mismatch")
    measurements: list[dict[str, object]] = []
    for request in requests:
        item = request.payload.get("context")
        if not isinstance(item, dict) or any(
            item.get(key) != value
            for key, value in (
                ("algorithm_version", policy.algorithm_version),
                ("mode", policy.mode),
                ("max_tool_rounds", policy.max_tool_rounds),
            )
        ):
            raise ValueError("Missing or mismatched context diagnostics")
        history = diagnostic_count(item.get("history_messages_count"))
        visible = diagnostic_count(item.get("visible_messages_count"))
        dropped = diagnostic_count(item.get("dropped_messages_count"))
        if history != visible + dropped or request.payload.get("messages_count") != visible:
            raise ValueError("Inconsistent context message counts")
        measurements.append(dict(item))
    return ContextCase(
        episode_id=episode.episode_id,
        task_name=artifact.task.name,
        seed=artifact.run_config.seed,
        agent=artifact.agent,
        config_hashes=artifact.config_hashes,
        success=artifact.evaluation.success,
        termination_reason=episode.termination_reason,
        steps=episode.step_count,
        model_calls=episode.model_call_count,
        tool_calls=episode.tool_call_count,
        simulated_prompt_tokens=episode.token_usage.prompt_tokens,
        simulated_completion_tokens=episode.token_usage.completion_tokens,
        input_messages_bytes=sum(
            diagnostic_count(item.get("input_messages_bytes")) for item in measurements
        ),
        dropped_messages_count=sum(
            diagnostic_count(item.get("dropped_messages_count")) for item in measurements
        ),
        visible_messages_counts=tuple(
            diagnostic_count(item.get("visible_messages_count")) for item in measurements
        ),
    )


async def run_ablation(directory: Path) -> ContextReport:
    """Save 24 independently evaluated episodes in a fresh directory; never use a Key."""
    directory.mkdir(parents=True, exist_ok=False)
    cases: list[ContextCase] = []
    expected_outcomes_match = True
    for backend in BACKENDS:
        base, tasks, config = load_inputs(backend)
        for task in tasks:
            for seed in (1, 17):
                for policy in POLICIES:
                    agent = AgentSpec.model_validate(
                        {**base.model_dump(), "context_policy": policy}
                    )
                    # Fail before running if the template accidentally changes another variable.
                    fixed = agent.model_dump(exclude={"context_policy"})
                    if fixed != base.model_dump(exclude={"context_policy"}):
                        raise ValueError("Context comparison changed a fixed variable")
                    run_config = config.model_copy(update={"seed": seed})
                    recorder = JsonTraceRecorder(run_config)
                    write_text_atomically(
                        directory / "episode-inputs" / f"{recorder.episode_id}.json",
                        json.dumps(
                            {
                                "schema_version": "1.0",
                                "episode_id": str(recorder.episode_id),
                                "scenario": "success",
                            }
                        )
                        + "\n",
                    )
                    artifact = await run_episode(
                        agent,
                        task,
                        run_config,
                        create_runtime(agent, FakeModelProvider("success")),
                        ToolLabEnvironment(),
                        OrderStatusEvaluator(),
                        recorder=recorder,
                    )
                    write_artifact(artifact, directory / f"{artifact.episode.episode_id}.json")
                    case = case_from_artifact(artifact)
                    cases.append(case)
                    forgets = task.name == "order-status-007" and policy.max_tool_rounds == 1
                    expected_reason = (
                        TerminationReason.MAX_STEPS if forgets else TerminationReason.SUCCESS
                    )
                    expected_outcomes_match &= (
                        case.success == (not forgets) and case.termination_reason == expected_reason
                    )
                    # Token usage remains the original Fake estimate, never byte-derived.
                    expected_outcomes_match &= artifact.episode.token_usage.simulated
    report = ContextReport(
        report_id=uuid4(),
        created_at=datetime.now(UTC),
        cases=tuple(cases),
        expected_outcomes_match=expected_outcomes_match,
    )
    if report.expected_outcomes_match:
        report.validate_artifacts(directory)
    write_text_atomically(
        directory / "context-ablation.json", report.model_dump_json(indent=2) + "\n"
    )
    return report


def main() -> int:
    """Print compact factual outcomes and fail if the fixed engineering expectations drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts-dir", type=Path, default=ROOT / "artifacts/context-ablation" / str(uuid4())
    )
    arguments = parser.parse_args()
    report = asyncio.run(run_ablation(arguments.artifacts_dir))
    print("Fake only; message bytes are not tokens or the full HTTP payload.")
    for case in report.cases:
        policy = case.agent.context_policy
        assert policy is not None
        print(
            f"{case.agent.runtime_backend} {case.task_name} seed={case.seed} "
            f"{policy.mode}/{policy.max_tool_rounds} {case.termination_reason} "
            f"success={case.success} steps={case.steps} input_bytes={case.input_messages_bytes}"
        )
    print(f"Report: {arguments.artifacts_dir / 'context-ablation.json'}")
    return 0 if report.expected_outcomes_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
