"""Deterministic Fake actions for the approved fixed GridWorld task."""

from decimal import Decimal

from pydantic import JsonValue

from packages.domain.models import (
    EstimatedCost,
    Message,
    ModelConfig,
    ModelResponse,
    TokenUsage,
    ToolCall,
    ToolSchema,
)
from packages.domain.ports import ModelProvider
from packages.environments.gridworld.environment import GALLERY_TASK_NAME, GRID_LAYOUTS, TASK_NAME

_SUCCESS_ACTIONS: tuple[tuple[str, dict[str, JsonValue]], ...] = (
    ("move_up", {}),
    ("move_right", {}),
    ("pickup", {}),
    ("move_down", {}),
    ("use", {"target_id": "door-amber"}),
    ("move_right", {}),
    ("move_right", {}),
    ("move_right", {}),
)
_GALLERY_SUCCESS_ACTIONS: tuple[tuple[str, dict[str, JsonValue]], ...] = (
    ("move_right", {}),
    ("move_right", {}),
    ("move_up", {}),
    ("move_up", {}),
    ("pickup", {}),
    ("move_down", {}),
    ("move_down", {}),
    ("use", {"target_id": "door-amber"}),
    ("move_right", {}),
    ("move_right", {}),
    ("move_down", {}),
    ("move_right", {}),
    ("move_right", {}),
    ("move_up", {}),
)


class GridWorldFakeProvider(ModelProvider):
    """Provide deterministic success, rule-rejection, or max-step traces."""

    def __init__(
        self, scenario: str = "success", initial_call_count: int = 0, *, task_name: str = TASK_NAME
    ) -> None:
        if scenario not in {"success", "illegal-action", "max-steps"}:
            raise ValueError("Unsupported GridWorld Fake scenario")
        if initial_call_count < 0:
            raise ValueError("Initial call count must be non-negative")
        if task_name not in GRID_LAYOUTS:
            raise ValueError("Unsupported GridWorld Fake task")
        route = _GALLERY_SUCCESS_ACTIONS if task_name == GALLERY_TASK_NAME else _SUCCESS_ACTIONS
        self._actions = (("move_left", {}), *route) if scenario == "illegal-action" else route
        self.scenario = scenario
        self._call_count = initial_call_count

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        """Return the next fixed action without consulting hidden environment state."""
        del messages, tools, config
        self._call_count += 1
        name: str
        arguments: dict[str, JsonValue]
        if self.scenario == "max-steps":
            name, arguments = "inspect", {}
        else:
            index = self._call_count - 1
            name, arguments = (
                self._actions[index] if index < len(self._actions) else ("inspect", {})
            )
        return ModelResponse(
            action=ToolCall(
                call_id=f"gridworld-fake-{self._call_count}",
                name=name,
                arguments=arguments,
            ),
            token_usage=TokenUsage(prompt_tokens=40, completion_tokens=20, simulated=True),
            estimated_cost=EstimatedCost(
                amount=Decimal("0.001"),
                currency="USD",
                price_table_version="fake-zero-v1",
                estimated=True,
            ),
        )
