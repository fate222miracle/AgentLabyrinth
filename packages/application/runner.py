"""Environment-agnostic orchestration; business correctness belongs to Evaluator."""

from time import perf_counter

from packages.application.trace import JsonTraceRecorder, content_hash
from packages.domain.models import (
    AgentSpec,
    EpisodeArtifact,
    EpisodeResult,
    EvaluationResult,
    EventType,
    RunConfig,
    TaskSpec,
    TerminationReason,
)
from packages.domain.ports import AgentRuntime, Environment, Evaluator


async def run_episode(
    agent: AgentSpec,
    task: TaskSpec,
    config: RunConfig,
    runtime: AgentRuntime,
    environment: Environment,
    evaluator: Evaluator,
) -> EpisodeArtifact:
    """Run once, evaluate isolated copies, then append the sole final event."""
    # Freeze provenance before passing copies to extension implementations.
    agent, task, config = (
        agent.model_copy(deep=True),
        task.model_copy(deep=True),
        config.model_copy(deep=True),
    )
    recorder = JsonTraceRecorder(config)
    started = perf_counter()
    recorder.record(EventType.EPISODE_STARTED, 0, {"seed": config.seed})
    try:
        episode = await runtime.run(
            agent.model_copy(deep=True), task.model_copy(deep=True), environment, recorder
        )
        if episode.episode_id != recorder.episode_id:
            raise ValueError("Runtime returned a foreign episode")
        evaluation = evaluator.evaluate(
            task.model_copy(deep=True), episode.model_copy(deep=True), recorder.events
        )
        if episode.termination_reason == TerminationReason.SUCCESS and not evaluation.success:
            episode = episode.model_copy(update={"termination_reason": TerminationReason.FAILED})
            evaluation = evaluation.model_copy(
                update={
                    "metrics": {
                        **evaluation.metrics,
                        "termination_reason": TerminationReason.FAILED.value,
                    }
                }
            )
        if episode.termination_reason != TerminationReason.SUCCESS and evaluation.success:
            evaluation = evaluation.model_copy(
                update={"success": False, "reason": "runtime_failed"}
            )
    except Exception:
        # Last-resort containment. Runtime must normalize expected failures itself,
        # preserving usage and state. Never copy an unknown exception into Trace.
        events = recorder.events
        episode = EpisodeResult(
            episode_id=recorder.episode_id,
            termination_reason=TerminationReason.RUNTIME_ERROR,
            detail="unhandled_runtime_or_evaluator_error; usage_and_state_incomplete",
            step_count=max((event.step_index for event in events), default=0),
            model_call_count=sum(e.event_type == EventType.MODEL_REQUESTED for e in events),
            tool_call_count=sum(e.event_type == EventType.TOOL_STARTED for e in events),
            duration_ms=int((perf_counter() - started) * 1000),
            final_state={},
        )
        evaluation = EvaluationResult(
            evaluator_version="runner-containment-v1",
            success=False,
            reason="unhandled_runtime_or_evaluator_error",
            metrics={"usage_complete": False},
        )
    recorder.record(
        EventType.EPISODE_FINISHED,
        episode.step_count,
        {
            "termination_reason": episode.termination_reason.value,
            "success": evaluation.success,
            "detail": episode.detail,
        },
        parent_event_id=recorder.events[-1].event_id,
        duration_ms=int((perf_counter() - started) * 1000),
    )
    return EpisodeArtifact(
        agent=agent,
        task=task,
        run_config=config,
        config_hashes={
            "agent": content_hash(agent),
            "task": content_hash(task),
            "run_config": content_hash(config),
        },
        episode=episode,
        evaluation=evaluation,
        events=recorder.events,
    )
