"""API DTO schemas for AgentLabyrinth M1 Slice B Web Demo."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from packages.domain.models import EpisodeArtifact

ALLOWED_AIHUBMIX_MODELS: set[str] = {
    "gemini-3.7-flash-free",
    "coding-kimi-k3-free",
    "coding-glm-5.3-flash-free",
    "deepseek-v4-flash-0731-free",
}

ALLOWED_FAKE_SCENARIOS: set[str] = {
    "success",
    "wrong-answer",
    "invalid-arguments",
    "max-steps",
}


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
    scenario: Literal["success", "wrong-answer", "invalid-arguments", "max-steps"] | None = None
    task_id: Literal["order-status-001"] = "order-status-001"
    max_steps: int | None = Field(default=None, ge=1, le=20)


class EpisodeResponse(BaseModel):
    """Standard response envelope carrying the executed or retrieved EpisodeArtifact."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    artifact: EpisodeArtifact


class ErrorResponse(BaseModel):
    """Sanitized standard error response body."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    error_code: str
    message: str
