"""Composition boundary for the three concrete runtime implementations."""

from importlib.metadata import PackageNotFoundError, version

from packages.domain.models import AgentSpec, RuntimeBackend
from packages.domain.ports import AgentRuntime, ModelProvider, ToolValidator
from packages.runtime.handwritten.runtime import HandwrittenRuntime


class RuntimeUnavailable(RuntimeError):
    """A declared backend is missing its dependency; fail before any model call."""


def create_runtime(
    agent: AgentSpec, provider: ModelProvider, validator: ToolValidator | None = None
) -> AgentRuntime:
    """Select the backend independently of the agent's recovery policy."""
    if agent.runtime_backend == "langgraph":
        from packages.runtime.langgraph import LangGraphRuntimeAdapter

        return LangGraphRuntimeAdapter(provider, validator)
    if agent.runtime_backend == "pydantic_ai":
        try:
            from packages.runtime.pydantic_ai import PydanticAIRuntimeAdapter
        except ImportError as exc:
            # Never fall back to the reference implementation for a saved backend.
            raise RuntimeUnavailable("PydanticAI runtime dependency is not installed") from exc
        return PydanticAIRuntimeAdapter(provider, validator)
    return HandwrittenRuntime(provider, validator)


def runtime_version(backend: RuntimeBackend) -> str:
    """Return exact installed graph version or the versioned reference implementation."""
    if backend == "langgraph":
        return version("langgraph")
    if backend == "pydantic_ai":
        # Record the slim distribution actually installed, not the absent meta package.
        try:
            return f"pydantic-ai-slim-{version('pydantic-ai-slim')}"
        except PackageNotFoundError as exc:
            # A missing install must not be reported as the reference version.
            raise RuntimeUnavailable("PydanticAI runtime dependency is not installed") from exc
    return "reference-v2"
