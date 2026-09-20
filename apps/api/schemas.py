"""API DTO schemas for AgentLabyrinth M1 Slice B Web Demo."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from packages.application.experiment import ExperimentArtifact
from packages.domain.models import EpisodeArtifact

ALLOWED_AIHUBMIX_MODELS: set[str] = {
    "coding-glm-5.3-free",
    "coding-glm-5.2-free",
    "gemini-3.8-flash-free",
    "gemini-3.7-flash-free",
    "coding-kimi-k3-free",
    "coding-glm-5.3-flash-free",
    "deepseek-v4-flash-0731-free",
    "qwen3.8-27b-free",
    "xiaomi-mimo-v2.5-pro-free",
    "coding-minimax-m2.7-free",
}

ALLOWED_FAKE_SCENARIOS: set[str] = {
    "clean",
    "success",
    "wrong-answer",
    "invalid-arguments",
    "invalid-then-success",
    "max-steps",
}


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
    suite: Literal["tool_lab_core", "bfcl_adapted"] = "tool_lab_core"
    split: str = "development"


class MetaResponse(BaseModel):
    """Configuration metadata response for frontend discovery."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID = Field(default_factory=uuid4)
    models: list[ModelOption]
    tasks: list[TaskOption]
    default_model: str
    default_task: str


class CreateEpisodeRequest(BaseModel):
    """Request payload to execute a new single ToolLab episode."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID = Field(default_factory=uuid4)
    provider: Literal["fake", "aihubmix"]
    model: str
    scenario: (
        Literal["success", "wrong-answer", "invalid-arguments", "invalid-then-success", "max-steps"]
        | None
    ) = None
    task_id: str = "order-status-001"
    suite: Literal["tool_lab_core", "bfcl_adapted"] = "tool_lab_core"
    max_steps: int | None = Field(default=None, ge=1, le=20)
    token_budget: int | None = Field(default=None, ge=100, le=20000)


class EpisodeResponse(BaseModel):
    """Standard response envelope carrying the executed or retrieved EpisodeArtifact."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    artifact: EpisodeArtifact


class CreateExperimentRequest(BaseModel):
    """Request payload to execute a paired comparison experiment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
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
    token_budget: int | None = Field(default=None, ge=100, le=20000)


class ExperimentResponse(BaseModel):
    """Standard response envelope carrying an ExperimentArtifact."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    experiment: ExperimentArtifact


class ErrorResponse(BaseModel):
    """Sanitized standard error response body."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    error_code: str
    message: str
