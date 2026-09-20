"""Tool registry and validator implementations."""

from collections.abc import Callable
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, JsonValue, ValidationError

from packages.domain.models import ErrorInfo, ToolCall, ToolSchema
from packages.domain.ports import ToolValidator


class ToolRegistration(NamedTuple):
    """Metadata, parameter model, and handler for a registered tool."""

    schema: ToolSchema
    param_model: type[BaseModel]
    handler: Callable[[Any], JsonValue]


class ValidationResult(NamedTuple):
    """Detailed validation status for Runtime trace payload generation."""

    arguments_valid: bool
    permitted: bool
    error_code: str | None
    error_info: ErrorInfo | None


class ToolRegistry:
    """Registry mapping tool names to schemas, parameter models, and handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}

    def register(
        self,
        name: str,
        description: str,
        risk_level: Literal["READ_ONLY", "LOW_RISK_WRITE", "FORBIDDEN"],
        version: str,
        param_model: type[BaseModel],
        handler: Callable[[Any], JsonValue],
        parameters: dict[str, JsonValue] | None = None,
    ) -> ToolSchema:
        """Register a tool with strict parameter validation and unique name constraint."""
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        schema = ToolSchema(
            name=name,
            description=description,
            parameters=parameters or param_model.model_json_schema(),
            version=version,
            risk_level=risk_level,
        )
        self._tools[name] = ToolRegistration(
            schema=schema, param_model=param_model, handler=handler
        )
        return schema

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get_schema(self, name: str) -> ToolSchema | None:
        """Get public schema for a registered tool."""
        reg = self._tools.get(name)
        return reg.schema if reg else None

    def get_registration(self, name: str) -> ToolRegistration | None:
        """Get internal registration tuple for execution."""
        return self._tools.get(name)

    def list_schemas(self) -> list[ToolSchema]:
        """Return list of all registered tool schemas."""
        return [reg.schema for reg in self._tools.values()]


class DefaultToolValidator(ToolValidator):
    """Side-effect free validator implementing the ToolValidator protocol."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def inspect(self, action: ToolCall, allowed_tools: tuple[str, ...]) -> ValidationResult:
        """Perform side-effect free inspection of registration, schema, and permissions."""
        reg = self._registry.get_registration(action.name)
        if reg is None:
            unk_err = ErrorInfo(
                code="UNKNOWN_TOOL",
                message=f"Tool '{action.name}' is not registered.",
                retryable=False,
            )
            return ValidationResult(
                arguments_valid=False,
                permitted=False,
                error_code="UNKNOWN_TOOL",
                error_info=unk_err,
            )

        arguments_valid = True
        try:
            reg.param_model.model_validate(action.arguments)
        except ValidationError:
            arguments_valid = False

        permitted = action.name in allowed_tools and reg.schema.risk_level != "FORBIDDEN"

        error_code: str | None = None
        err: ErrorInfo | None = None

        if not permitted:
            error_code = "FORBIDDEN_TOOL"
            err = ErrorInfo(
                code="FORBIDDEN_TOOL",
                message=f"Tool '{action.name}' is forbidden for this task.",
                retryable=False,
            )
        elif not arguments_valid:
            error_code = "INVALID_ARGUMENTS"
            err = ErrorInfo(
                code="INVALID_ARGUMENTS",
                message=f"Arguments for tool '{action.name}' failed schema validation.",
                retryable=False,
            )

        return ValidationResult(
            arguments_valid=arguments_valid,
            permitted=permitted,
            error_code=error_code,
            error_info=err,
        )

    def validate(self, action: ToolCall, allowed_tools: tuple[str, ...]) -> ErrorInfo | None:
        """Check registration, strict arguments and permissions without side effects."""
        return self.inspect(action, allowed_tools).error_info
