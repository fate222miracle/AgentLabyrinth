"""Composition boundary for the two concrete runtime implementations."""

from importlib.metadata import version

from packages.domain.models import AgentSpec, RuntimeBackend
from packages.domain.ports import AgentRuntime, ModelProvider, ToolValidator
from packages.runtime.handwritten.runtime import HandwrittenRuntime


def create_runtime(
    agent: AgentSpec, provider: ModelProvider, validator: ToolValidator | None = None
) -> AgentRuntime:
    """Select the backend independently of the agent's recovery policy."""
    if agent.runtime_backend == "langgraph":
        from packages.runtime.langgraph import LangGraphRuntimeAdapter

        return LangGraphRuntimeAdapter(provider, validator)
    return HandwrittenRuntime(provider, validator)


def runtime_version(backend: RuntimeBackend) -> str:
    """Return exact installed graph version or the versioned reference implementation."""
    return version("langgraph") if backend == "langgraph" else "reference-v2"
