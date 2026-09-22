"""LangGraph bootstrap adapter for the framework-independent Runtime Port."""

from typing import TypedDict, cast

from langgraph.graph import END, START, StateGraph

from packages.domain.models import AgentSpec, EpisodeResult, TaskSpec
from packages.domain.ports import AgentRuntime, Environment, TraceRecorder


class _AdapterState(TypedDict):
    result: EpisodeResult | None


class LangGraphRuntimeAdapter:
    """Run an existing AgentRuntime inside a LangGraph state graph.

    This bootstrap proves the adapter boundary and canonical Trace contract. It is
    not yet an independent control loop and must not be used for runtime comparisons.
    """

    def __init__(self, delegate: AgentRuntime) -> None:
        self._delegate = delegate

    async def run(
        self, agent: AgentSpec, task: TaskSpec, environment: Environment, recorder: TraceRecorder
    ) -> EpisodeResult:
        """Execute one episode through a compiled LangGraph."""

        async def execute(_: _AdapterState) -> _AdapterState:
            return {"result": await self._delegate.run(agent, task, environment, recorder)}

        # ponytail: compile per episode until the independent graph proves reuse safe
        # and profiling shows graph construction matters.
        graph = StateGraph(_AdapterState)
        graph.add_node("execute", execute)  # type: ignore[call-overload]
        graph.add_edge(START, "execute")
        graph.add_edge("execute", END)
        output = cast(_AdapterState, await graph.compile().ainvoke({"result": None}))
        result = output["result"]
        if result is None:
            raise RuntimeError("LangGraph adapter completed without an episode result")
        return result
