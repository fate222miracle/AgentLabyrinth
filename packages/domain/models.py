"""M0 boundary schema. No ToolLab or provider-specific implementation belongs here."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
RuntimeBackend = Literal["handwritten", "langgraph", "pydantic_ai"]
RuntimeStrategy = Literal["handwritten", "handwritten_recovery"]
ToolCallMode = Literal["single", "serial"]


class Contract(BaseModel):
    """Forbid coercion and unknown fields; owners must copy nested mutable values."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"


class Budget(Contract):
    """Episode hard limits; optional time limits preserve legacy configurations."""

    schema_version: Literal["1.0", "1.1"] = "1.0"  # type: ignore[assignment]
    max_execution_time_ms: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_time_revision(self) -> Self:
        """Require the additive revision when a total execution limit is supplied."""
        if self.max_execution_time_ms is not None and self.schema_version != "1.1":
            raise ValueError("Execution time limit requires Budget schema 1.1")
        return self

    @model_serializer(mode="wrap")
    def serialize_budget(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        """Keep legacy serialized configurations and provenance hashes unchanged."""
        result: dict[str, object] = handler(self)
        if self.max_execution_time_ms is None:
            result.pop("max_execution_time_ms", None)
        return result

    max_steps: PositiveInt = 6
    max_model_calls: PositiveInt = 6
    max_tool_calls: PositiveInt = 5
    max_prompt_tokens: PositiveInt = 1000
    max_completion_tokens: PositiveInt = 1000
    max_estimated_cost: Decimal = Field(default=Decimal("1"), gt=0, allow_inf_nan=False)


class ModelConfig(Contract):
    """Model provider configuration supporting simulated and real gateways."""

    schema_version: Literal["1.0", "1.1"] = "1.0"  # type: ignore[assignment]
    tool_call_mode: ToolCallMode | None = None
    provider: Literal["fake", "aihubmix"] = "fake"
    model: str = "fake-orders-v1"
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_tokens: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_call_mode(self) -> Self:
        """Bind explicit execution semantics to a model configuration revision."""
        if (self.tool_call_mode is not None) != (self.schema_version == "1.1"):
            raise ValueError("Tool call mode requires ModelConfig schema 1.1")
        return self

    @model_serializer(mode="wrap")
    def serialize_model(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        """Keep legacy serialized model configurations byte compatible."""
        result: dict[str, object] = handler(self)
        if self.tool_call_mode is None:
            result.pop("tool_call_mode", None)
        return result


class ContextPolicy(Contract):
    """Select a versioned model-input projection, never a storage retention policy."""

    schema_version: Literal["1.0", "1.1"] = "1.0"  # type: ignore[assignment]
    algorithm_version: Literal["tool-round-window-v1", "tool-round-window-memory-v1"] = (
        "tool-round-window-v1"
    )
    mode: Literal["full", "recent_tool_rounds"] = "full"
    max_tool_rounds: Annotated[int, Field(ge=1, le=100)] | None = None
    memory_max_bytes: Annotated[int, Field(ge=256, le=32768)] | None = None

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        """Reject missing windows and meaningless parameters on full history."""
        if (self.mode == "recent_tool_rounds") != (self.max_tool_rounds is not None):
            raise ValueError("Only recent_tool_rounds requires max_tool_rounds")
        memory = self.memory_max_bytes is not None
        if memory != (self.schema_version == "1.1") or memory != (
            self.algorithm_version == "tool-round-window-memory-v1"
        ):
            raise ValueError("Tool memory requires ContextPolicy schema 1.1 and memory algorithm")
        if memory and self.mode != "recent_tool_rounds":
            raise ValueError("Tool memory requires recent_tool_rounds")
        return self

    @model_serializer(mode="wrap")
    def serialize_policy(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        """Keep old policy bytes and configuration hashes unchanged."""
        result: dict[str, object] = handler(self)
        if self.memory_max_bytes is None:
            result.pop("memory_max_bytes", None)
        return result


class PlanItem(Contract):
    """One bounded model-declared subgoal; never a private reasoning trace."""

    id: str = Field(min_length=1, max_length=32)
    goal: str = Field(min_length=1, max_length=200)
    status: Literal["pending", "active", "done", "cancelled"] = "pending"
    depends_on: tuple[str, ...] = Field(default=(), max_length=8)

    @field_validator("id", "goal")
    @classmethod
    def non_blank_plan_text(cls, value: str) -> str:
        """Reject invisible identifiers and goals instead of recording empty work."""
        if not value.strip():
            raise ValueError("Plan text cannot be blank")
        return value

    @field_validator("depends_on", mode="before")
    @classmethod
    def coerce_dependencies(cls, value: object) -> object:
        """Accept a JSON array for an immutable, strictly validated dependency tuple."""
        if isinstance(value, list):
            return tuple(value)
        return value


def validate_plan(items: tuple[PlanItem, ...]) -> tuple[PlanItem, ...]:
    """Validate the same bounded dependency graph at tool and persistence boundaries."""
    if not 1 <= len(items) <= 8:
        raise ValueError("Plan requires 1 to 8 items")
    edges = {item.id: item.depends_on for item in items}
    if len(edges) != len(items):
        raise ValueError("Plan item ids must be unique")
    for deps in edges.values():
        if len(set(deps)) != len(deps) or any(dep not in edges for dep in deps):
            raise ValueError("Plan dependencies must be unique known ids")
    visited: set[str] = set()
    active: set[str] = set()

    def visit(item_id: str) -> None:
        if item_id in active:
            raise ValueError("Plan dependencies must be acyclic")
        if item_id in visited:
            return
        active.add(item_id)
        for dep in edges[item_id]:
            visit(dep)
        active.remove(item_id)
        visited.add(item_id)

    for item in items:
        visit(item.id)
    return items


class PlanningConfig(Contract):
    """Versioned planning component: enables bounded declarative plan updates only."""

    algorithm_version: Literal["plan-update-v1"] = "plan-update-v1"


class AgentSpec(Contract):
    """Versioned, validated agent configuration."""

    schema_version: Literal["1.0", "1.1", "1.2", "1.3", "1.4"] = "1.1"  # type: ignore[assignment]
    id: UUID
    name: str
    version: str
    description: str
    model: ModelConfig = Field(default_factory=ModelConfig)
    prompt_version: str
    tool_set_version: str
    runtime_backend: RuntimeBackend = "handwritten"
    runtime_strategy: RuntimeStrategy = "handwritten"
    budget: Budget = Field(default_factory=Budget)
    context_policy: ContextPolicy | None = None
    planning: PlanningConfig | None = None

    @model_validator(mode="after")
    def validate_context_revision(self) -> Self:
        """An explicit projection or planning component requires the additive Agent revision."""
        if self.context_policy is not None and self.schema_version not in ("1.2", "1.3", "1.4"):
            raise ValueError("Context policy requires AgentSpec schema 1.2")
        if self.planning is not None and self.schema_version not in ("1.3", "1.4"):
            raise ValueError("Planning requires AgentSpec schema 1.3")
        if self.runtime_backend == "pydantic_ai" and self.schema_version != "1.4":
            raise ValueError("PydanticAI backend requires AgentSpec schema 1.4")
        return self

    @model_serializer(mode="wrap")
    def serialize_agent(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        """Preserve existing configuration hashes when no policy or plan was specified."""
        result: dict[str, object] = handler(self)
        if self.context_policy is None:
            result.pop("context_policy", None)
        if self.planning is None:
            result.pop("planning", None)
        return result

    @property
    def recovery_policy(self) -> Literal["none", "invalid_arguments_once"]:
        """Interpret the legacy strategy field independently of the runtime backend."""
        return (
            "invalid_arguments_once" if self.runtime_strategy == "handwritten_recovery" else "none"
        )


class TaskSpec(Contract):
    """Generic task definition; private goals are never sent to the provider."""

    id: UUID
    name: str
    version: str
    category: str
    description: str
    initial_state: dict[str, JsonValue]
    goal_conditions: dict[str, JsonValue]
    constraints: tuple[str, ...] = ()
    expected_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...] = ()
    max_steps: PositiveInt
    token_budget: PositiveInt
    evaluator_config: dict[str, JsonValue]


class RunConfig(Contract):
    """Configuration shared with Runtime via TraceRecorder."""

    schema_version: Literal["1.0", "1.1"] = "1.1"  # type: ignore[assignment]
    seed: int = 1
    environment_version: str = "tool-lab-m0-v1"
    runtime_version: str | None = None


class TokenUsage(Contract):
    """Counts reported by the provider, explicitly simulated for Fake."""

    prompt_tokens: NonNegativeInt = 0
    completion_tokens: NonNegativeInt = 0
    simulated: bool = True


class EstimatedCost(Contract):
    """Decimal amount with explicit estimate, price provenance, and known status."""

    amount: Decimal = Field(default=Decimal("0"), ge=0, allow_inf_nan=False)
    currency: Literal["USD"] = "USD"
    price_table_version: str = "fake-zero-v1"
    estimated: Literal[True] = True
    is_known: bool = True


class ToolSchema(Contract):
    """Public tool definition; executable handlers stay outside Domain."""

    name: str
    description: str
    parameters: dict[str, JsonValue]
    version: str
    risk_level: Literal["READ_ONLY", "LOW_RISK_WRITE", "FORBIDDEN"]


class ToolCall(Contract):
    """One model proposal, not permission to execute it."""

    kind: Literal["tool_call"] = "tool_call"
    call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: dict[str, JsonValue]


class FinalAnswer(Contract):
    """Public model text; does not itself satisfy a submission task."""

    kind: Literal["final_answer"] = "final_answer"
    text: str


class ToolCallBatch(Contract):
    """One model response containing bounded proposals; execution requires preflight."""

    kind: Literal["tool_call_batch"] = "tool_call_batch"
    calls: tuple[ToolCall, ...] = Field(min_length=2, max_length=8)


class ModelResponse(Contract):
    """One final answer, single proposal, or explicitly versioned batch."""

    schema_version: Literal["1.0", "1.1"] = "1.0"  # type: ignore[assignment]
    action: Annotated[ToolCall | FinalAnswer | ToolCallBatch, Field(discriminator="kind")]
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: EstimatedCost = Field(default_factory=EstimatedCost)

    @model_validator(mode="after")
    def validate_batch_revision(self) -> Self:
        """Do not reinterpret a legacy response as a batch."""
        if isinstance(self.action, ToolCallBatch) and self.schema_version != "1.1":
            raise ValueError("Tool batch requires ModelResponse schema 1.1")
        return self


class Message(Contract):
    """Only public observation and structured feedback, never hidden reasoning."""

    role: Literal["system", "user", "assistant", "tool"]
    content: JsonValue = None
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] | None = None


class Observation(Contract):
    """Agent-visible projection, separate from private environment snapshot."""

    content: dict[str, JsonValue]


class ErrorInfo(Contract):
    """Sanitized error code and safe message; no raw exception strings."""

    code: str
    message: str
    retryable: bool = False


class StepResult(Contract):
    """Environment feedback; done indicates submission, not answer correctness."""

    observation: Observation
    done: bool = False
    error: ErrorInfo | None = None


class TerminationReason(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    MAX_STEPS = "MAX_STEPS"
    TOKEN_BUDGET_EXCEEDED = "TOKEN_BUDGET_EXCEEDED"
    COST_BUDGET_EXCEEDED = "COST_BUDGET_EXCEEDED"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIME_BUDGET_EXCEEDED = "TIME_BUDGET_EXCEEDED"


class EventType(StrEnum):
    EPISODE_STARTED = "EPISODE_STARTED"
    EPISODE_RESUMED = "EPISODE_RESUMED"
    OBSERVATION_CREATED = "OBSERVATION_CREATED"
    MODEL_REQUESTED = "MODEL_REQUESTED"
    MODEL_RESPONDED = "MODEL_RESPONDED"
    TOOL_CALL_PROPOSED = "TOOL_CALL_PROPOSED"
    TOOL_CALL_VALIDATED = "TOOL_CALL_VALIDATED"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_SUCCEEDED = "TOOL_SUCCEEDED"
    TOOL_FAILED = "TOOL_FAILED"
    PLAN_UPDATED = "PLAN_UPDATED"
    ENVIRONMENT_UPDATED = "ENVIRONMENT_UPDATED"
    EPISODE_FINISHED = "EPISODE_FINISHED"


class TraceEvent(Contract):
    """Append-only observable event schema, per requirement 26.3."""

    event_id: UUID
    episode_id: UUID
    step_index: NonNegativeInt
    event_type: EventType
    timestamp: datetime
    duration_ms: NonNegativeInt = 0
    payload: dict[str, JsonValue]
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: EstimatedCost = Field(default_factory=EstimatedCost)
    parent_event_id: UUID | None = None

    @field_validator("timestamp")
    @classmethod
    def utc_only(cls, value: datetime) -> datetime:
        """Reject naive or non-UTC event timestamps."""
        offset = value.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("timestamp must be UTC")
        return value


class EpisodeResult(Contract):
    """Runtime outcome, later finalized by Runner using independent evaluation."""

    episode_id: UUID
    termination_reason: TerminationReason
    detail: str
    step_count: NonNegativeInt
    model_call_count: NonNegativeInt
    tool_call_count: NonNegativeInt
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: EstimatedCost = Field(default_factory=EstimatedCost)
    duration_ms: NonNegativeInt
    final_state: dict[str, JsonValue]


class EvaluationResult(Contract):
    """Deterministic evaluator verdict, with explicit version and metric names."""

    evaluator_version: str
    success: bool
    reason: str
    metrics: dict[str, JsonValue]


class EpisodeArtifact(Contract):
    """Self-contained JSON artifact for M0 inspection, not a Replay product."""

    schema_version: Literal["1.0", "1.1"] = "1.1"  # type: ignore[assignment]
    agent: AgentSpec
    task: TaskSpec
    run_config: RunConfig
    config_hashes: dict[str, str]
    episode: EpisodeResult
    evaluation: EvaluationResult
    events: tuple[TraceEvent, ...]
    reference_cost: EstimatedCost | None = None
