"""M0 boundary schema. No ToolLab or provider-specific implementation belongs here."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
RuntimeBackend = Literal["handwritten", "langgraph"]
RuntimeStrategy = Literal["handwritten", "handwritten_recovery"]


class Contract(BaseModel):
    """Forbid coercion and unknown fields; owners must copy nested mutable values."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"


class Budget(Contract):
    """M0 hard limits; time limits are deliberately deferred."""

    max_steps: PositiveInt = 6
    max_model_calls: PositiveInt = 6
    max_tool_calls: PositiveInt = 5
    max_prompt_tokens: PositiveInt = 1000
    max_completion_tokens: PositiveInt = 1000
    max_estimated_cost: Decimal = Field(default=Decimal("1"), gt=0, allow_inf_nan=False)


class ModelConfig(Contract):
    """Model provider configuration supporting simulated and real gateways."""

    provider: Literal["fake", "aihubmix"] = "fake"
    model: str = "fake-orders-v1"
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_tokens: PositiveInt | None = None


class AgentSpec(Contract):
    """Versioned, validated agent configuration."""

    # This contract alone accepts the additive v1.1 revision; other contracts stay v1.0.
    schema_version: Literal["1.0", "1.1"] = "1.1"  # type: ignore[assignment]
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


class ModelResponse(Contract):
    """Exactly one action per M0 model request."""

    action: Annotated[ToolCall | FinalAnswer, Field(discriminator="kind")]
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: EstimatedCost = Field(default_factory=EstimatedCost)


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

    agent: AgentSpec
    task: TaskSpec
    run_config: RunConfig
    config_hashes: dict[str, str]
    episode: EpisodeResult
    evaluation: EvaluationResult
    events: tuple[TraceEvent, ...]
