"""Local, atomic ToolLab episode checkpoints at runtime safe points."""

import json
import os
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from packages.application.runner import run_episode
from packages.application.trace import (
    JsonTraceRecorder,
    content_hash,
    read_artifact,
    sanitize,
    write_artifact,
)
from packages.domain.models import AgentSpec, EpisodeArtifact, RunConfig, TaskSpec, TraceEvent
from packages.domain.ports import AgentRuntime, Environment, Evaluator
from packages.runtime.session import SessionState


class EpisodeCheckpoint(BaseModel):
    """Complete portable state needed to continue one unfinished Episode."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    episode_id: UUID
    agent: AgentSpec
    task: TaskSpec
    run_config: RunConfig
    config_hashes: dict[str, str]
    fake_scenario: str | None = None
    events: tuple[TraceEvent, ...]
    session: SessionState

    def validated_recorder(self) -> JsonTraceRecorder:
        """Reject modified provenance or a broken Trace before restoring tools."""
        if self.run_config.environment_version != "tool-lab-m0-v1":
            raise ValueError("Checkpoint is not for ToolLab")
        expected = {
            "agent": content_hash(self.agent),
            "task": content_hash(self.task),
            "run_config": content_hash(self.run_config),
        }
        if self.config_hashes != expected:
            raise ValueError("Checkpoint provenance mismatch")
        if not self.events or self.events[-1].step_index != self.session.budget.step_count:
            raise ValueError("Checkpoint Trace and budget mismatch")
        return JsonTraceRecorder(self.run_config, self.episode_id, self.events)


class CheckpointStore:
    """Write each complete state by replacing one local JSON file atomically."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path(self, episode_id: UUID) -> Path:
        """Resolve a validated UUID below the checkpoint directory."""
        return self.directory / f"{episode_id}.json"

    def save(
        self,
        state: SessionState,
        agent: AgentSpec,
        task: TaskSpec,
        config: RunConfig,
        recorder: JsonTraceRecorder,
        fake_scenario: str | None = None,
    ) -> None:
        """Persist the runtime and matching Trace as one versioned JSON document."""
        checkpoint = EpisodeCheckpoint(
            episode_id=recorder.episode_id,
            agent=agent,
            task=task,
            run_config=config,
            config_hashes={
                "agent": content_hash(agent),
                "task": content_hash(task),
                "run_config": content_hash(config),
            },
            fake_scenario=fake_scenario,
            events=recorder.events,
            session=state,
        )
        checkpoint.validated_recorder()
        safe = sanitize(checkpoint.model_dump(mode="json"))
        serialized = json.dumps(safe, ensure_ascii=False, indent=2) + "\n"
        EpisodeCheckpoint.model_validate_json(serialized)
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.path(recorder.episode_id)
        temporary = self.directory / f".{recorder.episode_id}.{uuid4().hex}.tmp"
        try:
            with temporary.open("w", encoding="utf-8") as output:
                output.write(serialized)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, episode_id: UUID) -> EpisodeCheckpoint:
        """Fail closed on corrupt or foreign checkpoints."""
        checkpoint = EpisodeCheckpoint.model_validate_json(
            self.path(episode_id).read_text(encoding="utf-8")
        )
        if checkpoint.episode_id != episode_id:
            raise ValueError("Foreign episode checkpoint")
        checkpoint.validated_recorder()
        return checkpoint


async def run_checkpointed_episode(
    agent: AgentSpec,
    task: TaskSpec,
    config: RunConfig,
    runtime: AgentRuntime,
    environment: Environment,
    evaluator: Evaluator,
    artifacts_dir: Path,
    fake_scenario: str | None = None,
) -> EpisodeArtifact:
    """Run one ToolLab episode with durable safe points and a final artifact."""
    if config.environment_version != "tool-lab-m0-v1":
        raise ValueError("Checkpointing currently supports ToolLab only")
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(artifacts_dir / "checkpoints")
    artifact = await run_episode(
        agent,
        task,
        config,
        runtime,
        environment,
        evaluator,
        recorder=recorder,
        save_checkpoint=lambda state: store.save(
            state, agent, task, config, recorder, fake_scenario
        ),
    )
    write_artifact(artifact, artifacts_dir / f"{recorder.episode_id}.json")
    store.path(recorder.episode_id).unlink(missing_ok=True)
    return artifact


async def resume_checkpointed_episode(
    episode_id: UUID,
    runtime: AgentRuntime,
    environment: Environment,
    evaluator: Evaluator,
    artifacts_dir: Path,
) -> EpisodeArtifact:
    """Continue one unfinished ToolLab run, or return its existing final artifact."""
    artifact_path = artifacts_dir / f"{episode_id}.json"
    if artifact_path.is_file():
        return read_artifact(artifact_path)
    store = CheckpointStore(artifacts_dir / "checkpoints")
    checkpoint = store.load(episode_id)
    recorder = checkpoint.validated_recorder()
    artifact = await run_episode(
        checkpoint.agent,
        checkpoint.task,
        checkpoint.run_config,
        runtime,
        environment,
        evaluator,
        recorder=recorder,
        resume_state=checkpoint.session,
        save_checkpoint=lambda state: store.save(
            state,
            checkpoint.agent,
            checkpoint.task,
            checkpoint.run_config,
            recorder,
            checkpoint.fake_scenario,
        ),
    )
    write_artifact(artifact, artifact_path)
    store.path(episode_id).unlink(missing_ok=True)
    return artifact
