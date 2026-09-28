"""Interrupt one real ToolLab run after a committed tool, then resume it."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.schemas import CreateEpisodeRequest  # noqa: E402
from apps.api.service import EpisodeService  # noqa: E402
from packages.application.checkpoint import CheckpointStore  # noqa: E402
from packages.application.trace import JsonTraceRecorder  # noqa: E402
from packages.domain.models import AgentSpec, EventType, RunConfig, TaskSpec  # noqa: E402
from packages.runtime.session import SessionState  # noqa: E402

MODEL = "coding-minimax-m2.7-free"


def interrupted_run(directory: Path) -> None:
    """Stop the child only after the first tool result has been saved."""
    original_save = CheckpointStore.save

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
        if state.next_node == "model" and state.budget.tool_call_count == 1:
            os._exit(0)

    CheckpointStore.save = stop_after_first_tool  # type: ignore[method-assign,assignment]
    service = EpisodeService(artifacts_dir=directory, live_model_catalog=True)
    asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(
                provider="aihubmix",
                model=MODEL,
                task_id="order-status-001",
                max_steps=4,
                token_budget=8000,
            )
        )
    )
    raise RuntimeError("The model did not reach a committed first tool")


def main() -> None:
    """Resume in a fresh process and report only nonsecret verification facts."""
    directory = ROOT / "artifacts" / "live-resume-probe"
    directory.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:2] == ["--child"]:
        interrupted_run(directory)
        return
    if list((directory / "checkpoints").glob("*.json")):
        raise RuntimeError("A prior unfinished probe exists; inspect it before rerunning")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Interrupted run exited {result.returncode}: {result.stderr[-500:]}")
    checkpoints = list((directory / "checkpoints").glob("*.json"))
    if len(checkpoints) != 1:
        raise RuntimeError(f"Expected one checkpoint, found {len(checkpoints)}")
    episode_id = UUID(checkpoints[0].stem)
    before = CheckpointStore(checkpoints[0].parent).load(episode_id)
    assert before.session.budget.model_call_count == 1
    assert before.session.budget.tool_call_count == 1
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
    assert len(tool_calls) == len(set(tool_calls)) == artifact.episode.tool_call_count
    assert all(
        current.parent_event_id == previous.event_id
        for previous, current in zip(artifact.events, artifact.events[1:], strict=False)
    )
    assert not checkpoints[0].exists()
    assert (directory / f"{episode_id}.json").is_file()
    tokens = artifact.episode.token_usage
    print(
        f"episode={episode_id} status={artifact.episode.termination_reason.value} "
        f"success={artifact.evaluation.success} model_calls={artifact.episode.model_call_count} "
        f"tool_calls={artifact.episode.tool_call_count} "
        f"tokens={tokens.prompt_tokens + tokens.completion_tokens}"
    )


if __name__ == "__main__":
    main()
