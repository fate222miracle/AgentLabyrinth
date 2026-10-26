"""API DTO schemas for AgentLabyrinth M1 Slice B Web Demo."""

from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.application.experiment import ComparisonAxis, ExperimentArtifact
from packages.application.review import (
    EpisodeReviewArtifact,
    ReviewRating,
    ReviewVerdict,
)
from packages.domain.models import (
    ContextPolicy,
    EpisodeArtifact,
    PlanningConfig,
    RuntimeBackend,
    RuntimeStrategy,
    ToolCallMode,
)

ALLOWED_AIHUBMIX_MODELS: set[str] = {
    "coding-minimax-m2.7-free",
    "xiaomi-mimo-v2.5-pro-free",
}

ALLOWED_FAKE_SCENARIOS: set[str] = {
    "clean",
    "success",
    "wrong-answer",
    "invalid-arguments",
    "invalid-then-success",
    "max-steps",
}

FaultProfile = Literal["none", "tool_timeout", "empty_result", "mcp_disconnect"]


def is_model_permitted(model_id: str, extra_allowed: set[str] | None = None) -> bool:
    """Validate that model is in the explicit allowed whitelist."""
    if model_id in ALLOWED_AIHUBMIX_MODELS:
        return True
    if extra_allowed and model_id in extra_allowed:
        return True
    return False


class ModelOption(BaseModel):
    """Metadata describing an available model option in the API."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    provider: Literal["fake", "aihubmix"]
    is_default: bool = False
    is_experimental: bool = False
    notes: str = ""
    scenarios: list[str] = Field(default_factory=list)


class TaskOption(BaseModel):
    """Metadata describing an available evaluation task."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    category: str
    description: str
    max_steps: int
    token_budget: int
    suite: Literal["tool_lab_core", "bfcl_adapted", "bfcl_java_adapted"] = "tool_lab_core"
    split: str = "development"
    supports_mcp: bool = False
    supports_planning: bool = False


class MetaResponse(BaseModel):
    """Configuration metadata response for frontend discovery."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID = Field(default_factory=uuid4)
    models: list[ModelOption]
    tasks: list[TaskOption]
    default_model: str
    default_task: str
    model_catalog_status: Literal["live", "unavailable", "static"] = "static"


class CreateEpisodeRequest(BaseModel):
    """Request payload to execute a new single ToolLab episode."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"] = "1.3"
    tool_call_mode: ToolCallMode | None = None
    request_id: UUID = Field(default_factory=uuid4)
    provider: Literal["fake", "aihubmix"]
    model: str
    scenario: (
        Literal["success", "wrong-answer", "invalid-arguments", "invalid-then-success", "max-steps"]
        | None
    ) = None
    task_id: str = "order-status-001"
    suite: Literal["tool_lab_core", "bfcl_adapted", "bfcl_java_adapted"] = "tool_lab_core"
    max_steps: int | None = Field(default=None, ge=1, le=20)
    max_execution_time_ms: int | None = Field(default=None, ge=1, le=3600000, strict=True)
    token_budget: int | None = Field(default=None, ge=100, le=20000)
    runtime_backend: RuntimeBackend = "handwritten"
    runtime_strategy: RuntimeStrategy = "handwritten"
    tool_transport: Literal["local", "mcp"] = "local"
    fault_profile: FaultProfile = "none"
    context_policy: ContextPolicy | None = None
    planning: PlanningConfig | None = None

    @model_validator(mode="after")
    def context_revision(self) -> "CreateEpisodeRequest":
        """Keep explicit context and planning configuration out of legacy requests."""
        if self.schema_version in ("1.4", "1.5"):
            if self.tool_call_mode is None:
                raise ValueError("Tool call mode requires Episode request revision 1.4")
        elif self.tool_call_mode is not None and self.schema_version not in ("1.6", "1.7"):
            raise ValueError("Tool call mode requires Episode request revision 1.4")
        if self.context_policy is not None and self.schema_version not in (
            "1.3",
            "1.4",
            "1.5",
            "1.6",
            "1.7",
        ):
            raise ValueError("Context policy requires Episode request revision 1.3")
        if self.planning is not None and self.schema_version not in ("1.6", "1.7"):
            raise ValueError("Planning requires Episode request revision 1.6")
        if self.runtime_backend == "pydantic_ai" and self.schema_version != "1.7":
            raise ValueError("PydanticAI backend requires Episode request revision 1.7")
        return self


class EpisodeResponse(BaseModel):
    """Standard response envelope carrying the executed or retrieved EpisodeArtifact."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    artifact: EpisodeArtifact


class HumanReviewInput(BaseModel):
    """Explicit local annotation using the same rubric as the Judge."""

    model_config = ConfigDict(extra="forbid")
    reviewer_label: str = Field(min_length=1, max_length=80)
    verdict: ReviewVerdict
    answer_correctness: ReviewRating
    evidence_support: ReviewRating
    process_safety: ReviewRating
    rationale: str = Field(min_length=1, max_length=2000)
    event_ids: tuple[UUID, ...] = ()


class CreateEpisodeReviewRequest(BaseModel):
    """Create one post-hoc review without changing the source Episode."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0", "1.1"] = "1.0"
    request_id: UUID = Field(default_factory=uuid4)
    episode_id: UUID
    method: Literal["human", "llm_judge"]
    judge_provider: Literal["aihubmix"] | None = None
    judge_model: str | None = Field(default=None, min_length=1, max_length=200)
    human: HumanReviewInput | None = None
    judge_scenario: Literal["success", "invalid_json", "bad_reference", "provider_error"] | None = (
        None
    )

    @model_validator(mode="after")
    def validate_method(self) -> "CreateEpisodeReviewRequest":
        """Keep manual labels and model execution inputs mutually exclusive."""
        if self.schema_version == "1.0":
            if {"judge_provider", "judge_model"} & self.model_fields_set:
                raise ValueError("Real Judge requires review request revision 1.1")
        elif (
            self.method != "llm_judge"
            or "human" in self.model_fields_set
            or "judge_scenario" in self.model_fields_set
            or self.judge_provider != "aihubmix"
            or self.judge_model is None
            or not self.judge_model.strip()
        ):
            raise ValueError("Review revision 1.1 requires only an explicit real Judge model")
        if self.method == "human" and (self.human is None or self.judge_scenario is not None):
            raise ValueError("Human review requires only human input")
        if self.method == "llm_judge" and self.human is not None:
            raise ValueError("Judge review cannot include human input")
        return self


class EpisodeReviewResponse(BaseModel):
    """Standard envelope for one immutable review artifact."""

    model_config = ConfigDict(frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    review: EpisodeReviewArtifact


class EpisodeReviewListResponse(BaseModel):
    """All saved reviews for one Episode; reading never invokes a Judge."""

    model_config = ConfigDict(frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    episode_id: UUID
    reviews: tuple[EpisodeReviewArtifact, ...]


class CreateExperimentRequest(BaseModel):
    """Request payload to execute a paired comparison experiment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10"
    ] = "1.5"
    tool_call_mode: ToolCallMode | None = None
    request_id: UUID = Field(default_factory=uuid4)
    provider: Literal["fake", "aihubmix"]
    model: str
    scenario: (
        Literal[
            "clean",
            "success",
            "invalid-then-success",
            "wrong-answer",
            "invalid-arguments",
            "max-steps",
        ]
        | None
    ) = None
    task_ids: list[str] = Field(
        default_factory=lambda: [
            "order-status-001",
            "order-status-002",
            "order-status-003",
            "order-status-004",
        ]
    )
    seed: int = 1
    seeds: list[int] | None = Field(default=None, min_length=1, max_length=10)
    repeat_count: int = Field(default=1, ge=1, le=10)
    max_execution_time_ms: int | None = Field(default=None, ge=1, le=3600000, strict=True)
    token_budget: int | None = Field(default=None, ge=100, le=20000)
    max_reference_cost_usd: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    max_total_tokens: int | None = Field(default=None, ge=1, le=1_000_000_000, strict=True)
    comparison_axis: ComparisonAxis = "recovery_policy"
    runtime_backend: RuntimeBackend = "handwritten"
    runtime_target: RuntimeBackend | None = None
    runtime_strategy: RuntimeStrategy = "handwritten"
    fault_profile: FaultProfile = "none"

    context_policy: ContextPolicy | None = None

    @model_validator(mode="after")
    def global_token_revision(self) -> "CreateExperimentRequest":
        """Keep global budget semantics out of legacy request revisions."""
        if self.schema_version in ("1.7", "1.8"):
            if self.tool_call_mode is None:
                raise ValueError("Tool call mode requires Experiment request revision 1.7")
        elif self.tool_call_mode is not None and self.schema_version not in ("1.9", "1.10"):
            raise ValueError("Tool call mode requires Experiment request revision 1.7")
        if self.max_total_tokens is not None and self.schema_version not in (
            "1.4",
            "1.5",
            "1.6",
            "1.7",
            "1.8",
            "1.9",
            "1.10",
        ):
            raise ValueError("Global Token budget requires request revision 1.4")
        if self.schema_version == "1.6" and self.comparison_axis != "memory_ablation":
            raise ValueError("Request revision 1.6 supports only the memory ablation axis")
        if self.comparison_axis == "memory_ablation" and self.schema_version not in (
            "1.6",
            "1.7",
            "1.8",
            "1.9",
        ):
            raise ValueError("Memory ablation requires Experiment request revision 1.6")
        if self.schema_version == "1.9" and self.comparison_axis != "planning":
            raise ValueError("Request revision 1.9 supports only the planning axis")
        if self.comparison_axis == "planning" and self.schema_version != "1.9":
            raise ValueError("Planning challenge requires Experiment request revision 1.9")
        if self.comparison_axis == "planning" and (
            self.context_policy is not None and self.context_policy.mode != "full"
        ):
            raise ValueError("Planning challenge requires full context")
        if (
            self.context_policy is not None or self.comparison_axis == "context_policy"
        ) and self.schema_version not in ("1.5", "1.6", "1.7", "1.8", "1.9", "1.10"):
            raise ValueError("Context policy requires Experiment request revision 1.5")
        if self.comparison_axis == "context_policy" and (
            self.context_policy is None or self.context_policy.mode != "recent_tool_rounds"
        ):
            raise ValueError("Context comparison requires a recent_tool_rounds policy")
        if self.comparison_axis == "memory_ablation" and (
            self.context_policy is None
            or self.context_policy.mode != "recent_tool_rounds"
            or self.context_policy.memory_max_bytes is None
        ):
            raise ValueError("Memory ablation requires a recent_tool_rounds memory policy")
        if self.runtime_target is not None and self.schema_version != "1.10":
            raise ValueError("Explicit Runtime target requires Experiment request revision 1.10")
        if self.schema_version == "1.10" and self.comparison_axis != "runtime_backend":
            raise ValueError("Request revision 1.10 supports only the runtime comparison axis")
        if self.runtime_target == "handwritten":
            raise ValueError("Runtime comparison target must be langgraph or pydantic_ai")
        if (
            self.comparison_axis == "runtime_backend"
            and self.runtime_target == "pydantic_ai"
            and self.schema_version != "1.10"
        ):
            raise ValueError("PydanticAI Runtime comparison requires request revision 1.10")
        if self.runtime_backend == "pydantic_ai":
            raise ValueError("PydanticAI is selected only as an explicit Runtime comparison target")
        return self


class ExperimentResponse(BaseModel):
    """Standard response envelope carrying an ExperimentArtifact."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    experiment: ExperimentArtifact


class ExperimentJobState(BaseModel):
    """Durable local execution status, separate from the immutable experiment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    experiment_id: UUID
    status: Literal[
        "queued", "running", "paused", "cancelled", "completed", "failed", "interrupted"
    ]
    requested_action: Literal["pause", "cancel"] | None = None
    updated_at: str
    error_code: str | None = None


class ExperimentDashboardItem(BaseModel):
    """Read-only metrics from one completed and persisted experiment."""

    model_config = ConfigDict(frozen=True)
    experiment_id: UUID
    created_at: str
    config_hash: str
    environment_version: str
    comparison_axis: str
    total_pairs: int
    baseline_success_rate: float
    recovery_success_rate: float
    baseline_total_tokens: int
    recovery_total_tokens: int
    baseline_avg_duration_ms: float
    recovery_avg_duration_ms: float
    baseline_total_cost: Decimal | None
    recovery_total_cost: Decimal | None
    model_id: str | None = None
    provider: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    seeds: list[int] = Field(default_factory=list)
    repeat_count: int | None = None
    scenario: str | None = None
    fault_profile: str | None = None
    comparison_key: str | None = None
    baseline_reference_cost: Decimal | None = None
    recovery_reference_cost: Decimal | None = None
    reference_price_version: str | None = None
    recovery_backend: RuntimeBackend | None = None


class ExperimentDashboardResponse(BaseModel):
    """Completed experiments only; invalid files are counted, never invented."""

    model_config = ConfigDict(frozen=True)
    schema_version: Literal["1.0", "1.1"] = "1.1"
    items: list[ExperimentDashboardItem]
    skipped_count: int = 0


class ErrorResponse(BaseModel):
    """Sanitized standard error response body."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    error_code: str
    message: str
