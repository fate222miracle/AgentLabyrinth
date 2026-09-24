"""The remote adapter preserves ToolLab evidence and failure boundaries."""

from pathlib import Path
from unittest.mock import patch

from packages.domain.models import TaskSpec, ToolCall
from packages.environments.tool_lab.mcp import MCPToolLabEnvironment, read_document

TASK = TaskSpec.model_validate_json(
    (
        Path(__file__).resolve().parents[2] / "benchmarks/tool_lab_core/tasks/order-status-007.json"
    ).read_text(encoding="utf-8")
)


def test_remote_read_only_acquires_evidence_after_success() -> None:
    """A failed network read cannot create evaluator-visible evidence."""
    environment = MCPToolLabEnvironment()
    environment.reset(TASK, 1)
    action = ToolCall(call_id="read-1", name="read_document", arguments={"document_id": "DOC-007"})
    with patch("packages.environments.tool_lab.mcp._call_sync", side_effect=OSError("offline")):
        failed = environment.step(action)
    assert failed.error is not None and failed.error.code == "TOOL_EXECUTION_ERROR"
    assert environment.snapshot()["acquired_evidence"] == []

    with patch(
        "packages.environments.tool_lab.mcp._call_sync",
        return_value=read_document("order-status-007", "DOC-007"),
    ):
        succeeded = environment.step(action)
    assert succeeded.error is None
    assert environment.snapshot()["acquired_evidence"] == ["document:DOC-007"]
