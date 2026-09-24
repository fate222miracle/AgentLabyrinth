"""Reference runtime: explicit Python scheduling of shared episode operations."""

from collections.abc import Callable

from packages.domain.models import AgentSpec, EpisodeResult, TaskSpec, TerminationReason
from packages.domain.ports import Environment, ModelProvider, ToolValidator, TraceRecorder
from packages.runtime.session import CheckpointFailure, EpisodeSession, SessionState


class HandwrittenRuntime:
    """Execute the portable tool-calling lifecycle with a handwritten loop."""

    def __init__(self, provider: ModelProvider, validator: ToolValidator | None = None) -> None:
        self._provider, self._validator = provider, validator

    async def run(
        self, agent: AgentSpec, task: TaskSpec, environment: Environment, recorder: TraceRecorder
    ) -> EpisodeResult:
        """Schedule operations until a business stop condition is reached."""
        return await self.run_resumable(agent, task, environment, recorder)

    async def run_resumable(
        self,
        agent: AgentSpec,
        task: TaskSpec,
        environment: Environment,
        recorder: TraceRecorder,
        *,
        resume_state: SessionState | None = None,
        save_checkpoint: Callable[[SessionState], None] | None = None,
    ) -> EpisodeResult:
        """Schedule from a validated safe point with optional durable checkpoints."""
        session = EpisodeSession(
            agent, task, environment, recorder, self._provider, self._validator
        )
        if resume_state is not None:
            next_node = session.restore(resume_state)
        else:
            try:
                next_node = session.observe()
            except Exception:
                next_node = session.stop(TerminationReason.RUNTIME_ERROR, "unhandled_runtime_error")
            session.checkpoint(next_node, save_checkpoint)
        try:
            while next_node != "end":
                if next_node == "model":
                    next_node = await session.call_model()
                elif next_node == "validate":
                    next_node = session.validate()
                else:
                    next_node = await session.execute()
                session.checkpoint(next_node, save_checkpoint)
        except CheckpointFailure:
            raise
        except Exception:
            session.stop(TerminationReason.RUNTIME_ERROR, "unhandled_runtime_error")
        return session.result()
