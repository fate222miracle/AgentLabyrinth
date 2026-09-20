"""Non-executable, one-call BFCL environment using the shared registry and executor."""

from typing import cast
from uuid import UUID

from pydantic import JsonValue

from packages.domain.models import (
    ErrorInfo,
    Observation,
    StepResult,
    TaskSpec,
    ToolCall,
    ToolSchema,
)
from packages.environments.bfcl.adapter import BFCLCase
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator, ToolRegistry


class BFCLEnvironment:
    """Capture one validated proposal without running upstream Python or APIs."""

    def __init__(self, case: BFCLCase) -> None:
        self.case = case
        self._registry = ToolRegistry()
        self._validator = DefaultToolValidator(self._registry)
        self._executor = ToolExecutor(self._registry, self._validator)
        self._task_id: UUID | None = None
        self._seed: int | None = None
        self._call: dict[str, JsonValue] | None = None
        self._registry.register(
            name=case.tool_name,
            description=str(case.tool.get("description", "")),
            risk_level="READ_ONLY",
            version="bfcl-v4-pinned",
            param_model=case.argument_model(),
            parameters=case.tool_parameters,
            handler=lambda args: cast(JsonValue, args.model_dump(exclude_none=True)),
        )

    def reset(self, task: TaskSpec, seed: int) -> Observation:
        self._task_id, self._seed, self._call = task.id, seed, None
        return Observation(content={"question": task.description})

    @property
    def validator(self) -> DefaultToolValidator:
        """Expose the shared validator to Runtime without leaking handlers."""
        return self._validator

    def available_tools(self) -> list[ToolSchema]:
        return self._registry.list_schemas()

    def step(self, action: ToolCall) -> StepResult:
        if self._task_id is None:
            raise RuntimeError("Environment must be reset before step")
        try:
            arguments = self._executor.execute(action, (self.case.tool_name,))
            self._call = {"name": action.name, "arguments": arguments}
            return StepResult(observation=Observation(content={"accepted": True}), done=True)
        except ValueError:
            return StepResult(
                observation=Observation(content={}),
                error=ErrorInfo(code="TOOL_EXECUTION_ERROR", message="Tool proposal rejected."),
            )

    def snapshot(self) -> dict[str, JsonValue]:
        return {
            "schema_version": "1.0",
            "task_id": str(self._task_id) if self._task_id else None,
            "seed": self._seed,
            "proposed_call": cast(JsonValue, self._call),
        }

    def restore(self, snapshot: dict[str, JsonValue]) -> None:
        task_id = snapshot.get("task_id")
        if task_id != (str(self._task_id) if self._task_id else None):
            raise ValueError("Snapshot belongs to another task")
        self._seed = cast(int | None, snapshot.get("seed"))
        self._call = cast(dict[str, JsonValue] | None, snapshot.get("proposed_call"))
