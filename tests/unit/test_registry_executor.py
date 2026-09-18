"""Unit tests for ToolRegistry, DefaultToolValidator, and ToolExecutor."""

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.domain.models import ToolCall
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator, ToolRegistry


class DummyArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    name: str = Field(min_length=1)
    count: int = Field(gt=0)


def test_registry_duplicate_registration_rejected() -> None:
    """Registry rejects duplicate tool registration."""
    registry = ToolRegistry()
    registry.register("dummy", "desc", "READ_ONLY", "1.0.0", DummyArgs, lambda x: "ok")
    with pytest.raises(ValueError, match="already registered"):
        registry.register("dummy", "desc", "READ_ONLY", "1.0.0", DummyArgs, lambda x: "ok")


def test_strict_argument_validation() -> None:
    """Pydantic strict mode rejects coercion, missing fields, and extra fields."""
    # Extra field
    with pytest.raises(ValidationError):
        DummyArgs.model_validate({"name": "test", "count": 5, "unknown": "extra"})

    # Type coercion (string count)
    with pytest.raises(ValidationError):
        DummyArgs.model_validate({"name": "test", "count": "5"})

    # Type coercion (int name)
    with pytest.raises(ValidationError):
        DummyArgs.model_validate({"name": 123, "count": 5})

    # Valid arguments
    args = DummyArgs.model_validate({"name": "test", "count": 5})
    assert args.name == "test"
    assert args.count == 5


def test_validator_inspection_and_validation() -> None:
    """DefaultToolValidator produces accurate status for unknown, forbidden, and invalid tools."""
    registry = ToolRegistry()
    registry.register("dummy", "desc", "READ_ONLY", "1.0.0", DummyArgs, lambda x: "ok")
    validator = DefaultToolValidator(registry)

    # 1. Unknown tool
    unknown_action = ToolCall(call_id="c1", name="unknown_tool", arguments={})
    res_unk = validator.inspect(unknown_action, ("dummy",))
    assert not res_unk.arguments_valid
    assert not res_unk.permitted
    assert res_unk.error_code == "UNKNOWN_TOOL"
    assert validator.validate(unknown_action, ("dummy",)) is not None

    # 2. Forbidden tool
    valid_args_action = ToolCall(call_id="c2", name="dummy", arguments={"name": "x", "count": 1})
    res_forb = validator.inspect(valid_args_action, ("other_tool",))
    assert res_forb.arguments_valid
    assert not res_forb.permitted
    assert res_forb.error_code == "FORBIDDEN_TOOL"

    # 3. Invalid arguments
    invalid_args_action = ToolCall(call_id="c3", name="dummy", arguments={"name": "", "count": 0})
    res_inv = validator.inspect(invalid_args_action, ("dummy",))
    assert not res_inv.arguments_valid
    assert res_inv.permitted
    assert res_inv.error_code == "INVALID_ARGUMENTS"

    # 4. Valid and permitted
    res_ok = validator.inspect(valid_args_action, ("dummy",))
    assert res_ok.arguments_valid
    assert res_ok.permitted
    assert res_ok.error_code is None
    assert validator.validate(valid_args_action, ("dummy",)) is None

    registry.register("blocked", "desc", "FORBIDDEN", "1.0.0", DummyArgs, lambda x: "bad")
    blocked = ToolCall(call_id="c4", name="blocked", arguments={"name": "x", "count": 1})
    assert validator.inspect(blocked, ("blocked",)).error_code == "FORBIDDEN_TOOL"


def test_executor_defensive_execution() -> None:
    """ToolExecutor defensively validates before calling tool handler."""
    registry = ToolRegistry()
    registry.register(
        "dummy", "desc", "READ_ONLY", "1.0.0", DummyArgs, lambda args: f"processed_{args.name}"
    )
    executor = ToolExecutor(registry)

    action = ToolCall(call_id="c1", name="dummy", arguments={"name": "item", "count": 2})
    result = executor.execute(action, ("dummy",))
    assert result == "processed_item"

    # Reject forbidden execution
    with pytest.raises(ValueError, match="rejected"):
        executor.execute(action, ("other",))
