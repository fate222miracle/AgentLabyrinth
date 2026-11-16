"""Saved four-model GridWorld batch manifest and response."""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.schemas import GridWorldComparisonRow

MODELS = (
    "coding-minimax-m2.7-free",
    "coding-minimax-m3-free",
    "coding-glm-5.3-free",
    "coding-glm-5.3-flash-free",
)


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]


class BatchRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model: str
    episode_id: UUID
    state: Literal["queued", "started", "unavailable", "error"] = "queued"


class BatchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    batch_id: UUID
    created_at: datetime
    task: str
    task_version: str
    configuration_key: str
    seed: int
    max_steps: int
    input_threshold: int
    output_per_call: int
    timeout_ms: int
    context_rounds: int
    runs: tuple[BatchRun, BatchRun, BatchRun, BatchRun]

    @model_validator(mode="after")
    def validate_sources(self) -> Self:
        if tuple(run.model for run in self.runs) != MODELS:
            raise ValueError("Batch must preserve the four-model lineup")
        if len({run.episode_id for run in self.runs}) != len(MODELS):
            raise ValueError("Batch episode IDs must be distinct")
        if self.created_at.utcoffset() is None:
            raise ValueError("Batch timestamp must have a timezone")
        return self


class BatchResult(BaseModel):
    model: str
    episode_id: UUID
    status: Literal[
        "queued",
        "running",
        "completed",
        "failed",
        "unavailable",
        "error",
        "interrupted",
        "not_started",
    ]
    row: GridWorldComparisonRow | None = None


class BatchView(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    batch_id: UUID
    created_at: datetime
    task: str
    task_version: str
    seed: int
    max_steps: int
    input_threshold: int
    output_per_call: int
    timeout_ms: int
    context_rounds: int
    running: bool
    runs: list[BatchResult]


class BatchList(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    items: list[BatchView]
    skipped_count: int = Field(ge=0)
