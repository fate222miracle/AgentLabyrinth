"""ToolLab environment implementation for order query and submission tasks."""

from copy import deepcopy
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from packages.domain.models import (
    ErrorInfo,
    Observation,
    StepResult,
    TaskSpec,
    ToolCall,
    ToolSchema,
)
from packages.domain.ports import Environment
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator, ToolRegistry


class QueryFilters(BaseModel):
    """The only supported query filter."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    order_id: str = Field(min_length=1)

    @field_validator("order_id")
    @classmethod
    def non_blank(cls, value: str) -> str:
        """Reject whitespace-only identifiers."""
        if not value.strip():
            raise ValueError("order_id cannot be blank")
        return value


class QueryRecordsArgs(BaseModel):
    """Strict schema for querying database records."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    table: Literal["orders"]
    filters: QueryFilters


class SubmitAnswerArgs(BaseModel):
    """Strict schema for submitting task answer and evidence."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    answer: str = Field(min_length=1)
    evidence: list[str]

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        """Reject blank submissions."""
        if not value.strip():
            raise ValueError("answer cannot be blank")
        return value

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, v: list[str]) -> list[str]:
        """Ensure evidence list is non-empty and contains non-empty strings."""
        if not v:
            raise ValueError("evidence list cannot be empty")
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("evidence items must be non-empty strings")
        return v


class _Order(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    order_id: str
    status: str
    evidence_id: str


class _Submission(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    answer: str
    evidence: list[str]


class _Snapshot(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    schema_version: Literal["1.0"]
    task_id: str | None
    seed: int | None
    orders: list[_Order]
    acquired_evidence: list[str]
    submission: _Submission | None
    done: bool
    description: str
    target_order_id: str


def create_tool_lab_registry() -> ToolRegistry:
    """Create a registry pre-populated with ToolLab tool schemas."""
    registry = ToolRegistry()
    return registry


class ToolLabEnvironment(Environment):
    """Controlled environment managing order database state and tool execution."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        executor: ToolExecutor | None = None,
        validator: DefaultToolValidator | None = None,
    ) -> None:
        self._registry = registry or create_tool_lab_registry()
        self._validator = validator or DefaultToolValidator(self._registry)
        self._executor = executor or ToolExecutor(self._registry, self._validator)

        # State fields
        self._task_id: UUID | None = None
        self._seed: int | None = None
        self._orders: list[dict[str, JsonValue]] = []
        self._acquired_evidence: set[str] = set()
        self._submission: dict[str, JsonValue] | None = None
        self._done: bool = False
        self._allowed_tools: tuple[str, ...] = ()
        self._description: str = ""
        self._target_order_id: str = ""

        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register environment-bound tool handlers if not already registered."""
        if not self._registry.has_tool("query_records"):
            self._registry.register(
                name="query_records",
                description="Query records from database table.",
                risk_level="READ_ONLY",
                version="1.0.0",
                param_model=QueryRecordsArgs,
                handler=self._handle_query_records,
            )

        if not self._registry.has_tool("submit_answer"):
            self._registry.register(
                name="submit_answer",
                description="Submit answer and evidence for task evaluation.",
                risk_level="LOW_RISK_WRITE",
                version="1.0.0",
                param_model=SubmitAnswerArgs,
                handler=self._handle_submit_answer,
            )

    def _handle_query_records(self, args: QueryRecordsArgs) -> JsonValue:
        """Execute query against isolated orders state and record acquired evidence."""
        order_id = args.filters.order_id
        matched = [deepcopy(r) for r in self._orders if r.get("order_id") == order_id]
        for record in matched:
            evidence_id = record.get("evidence_id")
            if isinstance(evidence_id, str):
                self._acquired_evidence.add(evidence_id)
        return {
            "records": cast(JsonValue, matched),
            "acquired_evidence": cast(JsonValue, sorted(list(self._acquired_evidence))),
        }

    def _handle_submit_answer(self, args: SubmitAnswerArgs) -> JsonValue:
        """Record task submission and set episode done state."""
        self._submission = {
            "answer": args.answer,
            "evidence": cast(JsonValue, deepcopy(args.evidence)),
        }
        self._done = True
        return {
            "feedback": "Answer submitted.",
            "submission": cast(JsonValue, deepcopy(self._submission)),
        }

    def reset(self, task: TaskSpec, seed: int) -> Observation:
        """Rebuild deterministic state and return its public projection."""
        raw_orders = task.initial_state.get("orders")
        if not isinstance(raw_orders, list):
            raise ValueError("Task initial_state missing 'orders' list")

        orders = cast(
            list[dict[str, JsonValue]],
            [_Order.model_validate(item).model_dump() for item in raw_orders],
        )
        if not orders:
            raise ValueError("Task requires at least one order")
        self._task_id = task.id
        self._seed = seed
        self._orders = orders
        self._allowed_tools = tuple(
            name for name in task.expected_tools if name not in task.forbidden_tools
        )
        self._acquired_evidence = set()
        self._submission = None
        self._done = False
        self._description = task.description

        target_id_override = task.initial_state.get("target_order_id")
        if isinstance(target_id_override, str) and target_id_override:
            self._target_order_id = target_id_override
        else:
            self._target_order_id = cast(str, self._orders[0]["order_id"])

        return Observation(
            content={
                "description": self._description,
                "target_order_id": self._target_order_id,
            }
        )

    def available_tools(self) -> list[ToolSchema]:
        """Describe registered tools without exposing handlers."""
        return self._registry.list_schemas()

    def step(self, action: ToolCall) -> StepResult:
        """Execute action defensively through the shared Executor."""
        if self._task_id is None:
            raise RuntimeError("Environment must be reset before step")
        try:
            result = self._executor.execute(action, self._allowed_tools)
            return StepResult(
                observation=Observation(content={"result": result}),
                done=self._done,
                error=None,
            )
        except ValueError:
            err = ErrorInfo(
                code="TOOL_EXECUTION_ERROR",
                message="Tool execution failed.",
                retryable=False,
            )
            return StepResult(
                observation=Observation(content={}),
                done=self._done,
                error=err,
            )

    def snapshot(self) -> dict[str, JsonValue]:
        """Return an independent JSON-compatible state copy."""
        return {
            "schema_version": "1.0",
            "task_id": str(self._task_id) if self._task_id else None,
            "seed": self._seed,
            "orders": cast(JsonValue, deepcopy(self._orders)),
            "acquired_evidence": cast(JsonValue, sorted(list(self._acquired_evidence))),
            "submission": cast(JsonValue, deepcopy(self._submission)),
            "done": self._done,
            "description": self._description,
            "target_order_id": self._target_order_id,
        }

    def restore(self, snapshot: dict[str, JsonValue]) -> None:
        """Validate and restore a snapshot; this is not Runtime resume."""
        state = _Snapshot.model_validate(snapshot)
        task_id = UUID(state.task_id) if state.task_id is not None else None
        if task_id != self._task_id:
            raise ValueError("Snapshot belongs to another task")
        self._task_id = task_id
        self._seed = state.seed
        self._orders = cast(list[dict[str, JsonValue]], [o.model_dump() for o in state.orders])
        self._acquired_evidence = set(state.acquired_evidence)
        self._submission = cast(
            dict[str, JsonValue] | None,
            state.submission.model_dump() if state.submission else None,
        )
        self._done = state.done
        self._description = state.description
        self._target_order_id = state.target_order_id
