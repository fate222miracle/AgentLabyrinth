"""Tool execution component enforcing strict validation and permission checks."""

from pydantic import JsonValue

from packages.domain.models import ToolCall
from packages.tools.registry import DefaultToolValidator, ToolRegistry


class ToolExecutor:
    """Execute tools safely after defensive validation."""

    def __init__(
        self, registry: ToolRegistry, validator: DefaultToolValidator | None = None
    ) -> None:
        self._registry = registry
        self._validator = validator or DefaultToolValidator(registry)

    def execute(self, action: ToolCall, allowed_tools: tuple[str, ...]) -> JsonValue:
        """Defensively validate action and execute registered handler."""
        error = self._validator.validate(action, allowed_tools)
        if error is not None:
            raise ValueError(f"Tool execution rejected [{error.code}]: {error.message}")

        reg = self._registry.get_registration(action.name)
        if reg is None:
            raise ValueError(f"Unregistered tool: {action.name}")

        parsed_args = reg.param_model.model_validate(action.arguments)
        return reg.handler(parsed_args)
