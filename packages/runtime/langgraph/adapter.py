"""Independent LangGraph scheduler for the shared portable episode operations."""

from collections.abc import Callable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from packages.domain.models import AgentSpec, EpisodeResult, TaskSpec, TerminationReason
from packages.domain.ports import Environment, ModelProvider, ToolValidator, TraceRecorder
from packages.runtime.session import CheckpointFailure, EpisodeSession, NextNode, SessionState


class _GraphState(TypedDict):
    next_node: NextNode


class LangGraphRuntimeAdapter:
    """Use graph edges to schedule model, validation, execution and recovery."""

    def __init__(self, provider: ModelProvider, validator: ToolValidator | None = None) -> None:
        self._provider, self._validator = provider, validator

    async def run(
        self, agent: AgentSpec, task: TaskSpec, environment: Environment, recorder: TraceRecorder
    ) -> EpisodeResult:
        """Run an isolated state graph; shared checks govern every action and retry."""
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
        """Continue the graph from a portable safe point, independent of its scheduler."""
        session = EpisodeSession(
            agent, task, environment, recorder, self._provider, self._validator
        )
        initial_node: NextNode = "model"
        if resume_state is not None:
            initial_node = session.restore(resume_state)
            if initial_node == "end":
                return session.result()

        async def observe(state: _GraphState) -> _GraphState:
            next_node = session.observe()
            session.checkpoint(next_node, save_checkpoint)
            return {"next_node": next_node}

        async def model(state: _GraphState) -> _GraphState:
            next_node = await session.call_model()
            session.checkpoint(next_node, save_checkpoint)
            return {"next_node": next_node}

        async def validate(state: _GraphState) -> _GraphState:
            next_node = session.validate()
            session.checkpoint(next_node, save_checkpoint)
            return {"next_node": next_node}

        async def execute(state: _GraphState) -> _GraphState:
            next_node = await session.execute()
            session.checkpoint(next_node, save_checkpoint)
            return {"next_node": next_node}

        def route(state: _GraphState) -> NextNode:
            return state["next_node"]

        graph = StateGraph(_GraphState)
        for name, node in (
            ("observe", observe),
            ("model", model),
            ("validate", validate),
            ("execute", execute),
        ):
            graph.add_node(name, node)
        graph.add_edge(START, "observe" if resume_state is None else initial_node)
        graph.add_edge("observe", "model")
        graph.add_conditional_edges("model", route, {"validate": "validate", "end": END})
        graph.add_conditional_edges(
            "validate", route, {"execute": "execute", "model": "model", "end": END}
        )
        graph.add_conditional_edges("execute", route, {"model": "model", "end": END})
        try:
            # One model step uses up to three graph nodes, plus observe and the stop check.
            await graph.compile().ainvoke(
                {"next_node": "model"},
                config={"recursion_limit": 3 * session.budget.max_steps + 3},
            )
        except CheckpointFailure:
            raise
        except Exception:
            session.stop(TerminationReason.RUNTIME_ERROR, "unhandled_runtime_error")
        return session.result()
