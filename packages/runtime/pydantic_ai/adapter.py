"""Third scheduler: PydanticAI routes each model step, the Session owns every effect.

Admission scope (ADR-038 §10, accepted "A1 limitation"): the framework produces the
nodes inside one model step (``ModelRequestNode`` -> ``CallToolsNode`` -> ``End``);
the transition *between* steps is still performed by this adapter from the value
``EpisodeSession`` returns. That is a documented scheduling gap, not a claim that
the framework drives the whole episode loop.
"""

from collections.abc import Callable

from pydantic_ai import Agent, DeferredToolRequests, ExternalToolset, ToolDefinition
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage

from packages.domain.models import AgentSpec, EpisodeResult, TaskSpec, TerminationReason
from packages.domain.ports import Environment, ModelProvider, ToolValidator, TraceRecorder
from packages.runtime.session import CheckpointFailure, EpisodeSession, NextNode, SessionState

# Framework messages never reach the provider or the saved state; the Session projects
# its own portable history. This prompt only satisfies the framework's construction.
_FRAMEWORK_PROMPT = "AgentLabyrinth framework driver"


class _SessionBridgeModel(Model):
    """One framework model request equals exactly one ``Session.call_model()``."""

    def __init__(self, session: EpisodeSession) -> None:
        super().__init__()
        self.session = session
        self.requests = 0
        self.last_node: NextNode | None = None

    @property
    def model_name(self) -> str:
        """Identify the bridge; the real provider name stays in the Session config."""
        return "agentlabyrinth-session-bridge"

    @property
    def system(self) -> str:
        """Report a neutral provider family; no provider SDK is involved."""
        return "agentlabyrinth"

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Delegate limits, the single provider call and accounting to the Session."""
        self.requests += 1
        self.last_node = await self.session.call_model()
        if self.last_node != "validate":
            # Stop, retry-once and final-answer outcomes end this framework run.
            return ModelResponse(parts=[TextPart(content=self.session.detail)])
        calls = self.session.batch_calls or (
            (self.session.action,) if self.session.action is not None else ()
        )
        registered = {tool.name for tool in self.session.available_tools()}
        if any(call.name not in registered for call in calls):
            # The framework would silently re-request the model for an unknown name and
            # turn one budgeted call into two. Session must own that rejection instead.
            return ModelResponse(parts=[TextPart(content="pending_validation")])
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=call.name,
                    args=dict(call.arguments),
                    tool_call_id=call.call_id,
                )
                for call in calls
            ],
            # Framework usage is non-authoritative; the Session keeps the real figures.
            usage=RequestUsage(),
        )


def _tool_definitions(session: EpisodeSession) -> list[ToolDefinition]:
    """Publish exactly the exposure set the Session publishes, descriptions unchanged."""
    return [
        ToolDefinition(
            name=schema.name,
            description=schema.description,
            parameters_json_schema=schema.parameters,
        )
        for schema in session.available_tools()
    ]


class PydanticAIRuntimeAdapter:
    """Use PydanticAI nodes for one model step; shared checks own every action."""

    def __init__(self, provider: ModelProvider, validator: ToolValidator | None = None) -> None:
        self._provider, self._validator = provider, validator

    async def run(
        self, agent: AgentSpec, task: TaskSpec, environment: Environment, recorder: TraceRecorder
    ) -> EpisodeResult:
        """Run through the shared Session with the framework contributing each model step."""
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
        """Restore a portable safe point first; the framework never owns saved state."""
        session = EpisodeSession(
            agent, task, environment, recorder, self._provider, self._validator
        )
        if resume_state is not None:
            node = session.restore(resume_state)
            if node == "end":
                return session.result()
        else:
            node = session.observe()
            session.checkpoint(node, save_checkpoint)
        guard = 0
        while node != "end":
            guard += 1
            if guard > 3 * session.budget.max_steps + session.budget.max_tool_calls + 3:
                raise RuntimeError("adapter loop guard exceeded")
            if node != "model":
                # Restored or freshly validated batch: the Session owns the next effect.
                node = session.validate() if node == "validate" else await session.execute()
                session.checkpoint(node, save_checkpoint)
                continue
            bridge = _SessionBridgeModel(session)
            run_error = False
            try:
                await self._framework_step(bridge)
            except CheckpointFailure:
                raise
            except Exception:
                # The framework can preempt the Session (for example on a duplicate
                # ``tool_call_id``); the Session still decides the termination reason.
                run_error = True
            if bridge.last_node is None:
                node = session.stop(TerminationReason.RUNTIME_ERROR, "unhandled_runtime_error")
            else:
                node = bridge.last_node
            if run_error and node == "validate":
                node = session.validate()
                session.checkpoint(node, save_checkpoint)
        return session.result()

    async def _framework_step(self, bridge: _SessionBridgeModel) -> None:
        """Let PydanticAI produce the nodes of one model step, including tool routing."""
        pydantic_agent = Agent(
            bridge,
            output_type=[DeferredToolRequests, str],
            toolsets=[ExternalToolset(_tool_definitions(bridge.session))],
            system_prompt=_FRAMEWORK_PROMPT,
        )
        async with pydantic_agent.iter("start") as run:
            # Deferred output means the framework reports tool calls without running them.
            async for _ in run:
                continue
