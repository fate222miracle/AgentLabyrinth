"""Public M0 ports. Concrete implementations must not change these silently."""

from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from packages.domain.models import (
    AgentSpec,
    EpisodeResult,
    ErrorInfo,
    EstimatedCost,
    EvaluationResult,
    EventType,
    Message,
    ModelConfig,
    ModelResponse,
    Observation,
    RunConfig,
    StepResult,
    TaskSpec,
    TokenUsage,
    ToolCall,
    ToolSchema,
    TraceEvent,
)


class ModelProvider(Protocol):
    """Translate public model context to one portable response."""

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        """Return a validated action; never execute tools here."""
        ...


class Environment(Protocol):
    """Local controlled state and actions, isolated from model and evaluator."""

    def reset(self, task: TaskSpec, seed: int) -> Observation:
        """Rebuild deterministic state and return its public projection."""
        ...

    def available_tools(self) -> list[ToolSchema]:
        """Describe registered tools without exposing handlers."""
        ...

    def step(self, action: ToolCall) -> StepResult:
        """Execute through the shared Executor, with no hidden model calls."""
        ...

    def snapshot(self) -> dict[str, JsonValue]:
        """Return an independent JSON-compatible state copy."""
        ...

    def restore(self, snapshot: dict[str, JsonValue]) -> None:
        """Validate and restore a snapshot; this is not Runtime resume."""
        ...


class ToolValidator(Protocol):
    """Shared registry validation used by Runtime and Environment's Executor."""

    def validate(self, action: ToolCall, allowed_tools: tuple[str, ...]) -> ErrorInfo | None:
        """Check registration, strict arguments and permissions without side effects."""
        ...


class TraceRecorder(Protocol):
    """Single-episode append-only recorder, owned by Runner."""

    @property
    def episode_id(self) -> UUID:
        """Identify this episode."""
        ...

    @property
    def run_config(self) -> RunConfig:
        """Expose the seed and environment version to Runtime."""
        ...

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        """Return deep copies in append order."""
        ...

    def record(
        self,
        event_type: EventType,
        step_index: int,
        payload: dict[str, JsonValue],
        *,
        parent_event_id: UUID | None = None,
        duration_ms: int = 0,
        token_usage: TokenUsage | None = None,
        estimated_cost: EstimatedCost | None = None,
    ) -> TraceEvent:
        """Append a sanitized event and return an independent copy."""
        ...


class AgentRuntime(Protocol):
    """Framework-independent episode control loop (requirement 8.1)."""

    async def run(
        self, agent: AgentSpec, task: TaskSpec, environment: Environment, recorder: TraceRecorder
    ) -> EpisodeResult:
        """Reset environment, run loop, return outcome; Runner writes final event."""
        ...


class Evaluator(Protocol):
    """Independent read-only deterministic scoring."""

    def evaluate(
        self, task: TaskSpec, episode: EpisodeResult, events: tuple[TraceEvent, ...]
    ) -> EvaluationResult:
        """Judge state and trace without mutating either."""
        ...
