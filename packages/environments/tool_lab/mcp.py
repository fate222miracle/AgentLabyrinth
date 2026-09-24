"""Fixed, read-only ToolLab documents served and consumed over MCP HTTP."""

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from mcp import Client
from mcp.server import MCPServer
from pydantic import JsonValue

from packages.domain.models import Observation, TaskSpec
from packages.environments.tool_lab.environment import (
    ReadDocumentArgs,
    SearchDocumentsArgs,
    ToolLabEnvironment,
)

MCP_URL = "http://127.0.0.1:8765/mcp"
TASKS_DIR = Path(__file__).resolve().parents[3] / "benchmarks/tool_lab_core/tasks"


def _documents(task_name: str) -> list[dict[str, JsonValue]]:
    """Resolve a catalog task without accepting paths or arbitrary datasets."""
    for path in TASKS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("name") == task_name:
            state = data.get("initial_state", {})
            documents = state.get("documents", [])
            return cast(list[dict[str, JsonValue]], documents)
    raise ValueError("Unknown ToolLab task")


server = MCPServer("AgentLabyrinth ToolLab documents")


@server.tool()
def search_documents(task_name: str, query: str, top_k: int) -> dict[str, JsonValue]:
    """Search a fixed task's documents and return IDs and titles."""
    args = SearchDocumentsArgs(query=query, top_k=top_k)
    needle = args.query.casefold()
    matches = [
        {"document_id": doc["document_id"], "title": doc["title"]}
        for doc in _documents(task_name)
        if needle in str(doc["title"]).casefold() or needle in str(doc["content"]).casefold()
    ][: args.top_k]
    return {"documents": cast(JsonValue, matches)}


@server.tool()
def read_document(task_name: str, document_id: str) -> dict[str, JsonValue]:
    """Read one fixed task document; the client records evidence after success."""
    args = ReadDocumentArgs(document_id=document_id)
    document = next(
        (doc for doc in _documents(task_name) if doc["document_id"] == args.document_id), None
    )
    return {"document": cast(JsonValue, document)}


async def _call_remote(name: str, arguments: dict[str, Any]) -> dict[str, JsonValue]:
    async with Client(MCP_URL, read_timeout_seconds=5) as client:
        result = await client.call_tool(name, arguments)
    if result.is_error or not isinstance(result.structured_content, dict):
        raise ValueError("MCP tool returned an error")
    return cast(dict[str, JsonValue], result.structured_content)


class MCPToolLabEnvironment(ToolLabEnvironment):
    """Use the ordinary ToolLab validator and evaluator with remote document reads."""

    tool_transport = "mcp"
    remote_tools = ("search_documents", "read_document")

    def __init__(self) -> None:
        super().__init__()
        self._remote_task_name = ""

    def reset(self, task: TaskSpec, seed: int) -> Observation:
        """Keep the same isolated state while selecting the server's fixed task."""
        observation = super().reset(task, seed)
        self._remote_task_name = task.name
        return observation

    def _handle_search_documents(self, args: SearchDocumentsArgs) -> JsonValue:
        """Return remote search results through the existing Executor."""
        try:
            return _call_sync(
                "search_documents",
                {"task_name": self._remote_task_name, **args.model_dump()},
            )
        except Exception as exc:
            raise ValueError("MCP document search failed") from exc

    def _handle_read_document(self, args: ReadDocumentArgs) -> JsonValue:
        """Acquire evidence only after a successful remote read."""
        try:
            result = _call_sync(
                "read_document",
                {"task_name": self._remote_task_name, **args.model_dump()},
            )
        except Exception as exc:
            raise ValueError("MCP document read failed") from exc
        document = result.get("document")
        if isinstance(document, dict):
            evidence_id = document.get("evidence_id")
            if isinstance(evidence_id, str):
                self._acquired_evidence.add(evidence_id)
        return {
            "document": document,
            "acquired_evidence": cast(JsonValue, sorted(self._acquired_evidence)),
        }


def _call_sync(name: str, arguments: dict[str, Any]) -> dict[str, JsonValue]:
    """Bridge the synchronous Tool Executor from the runtime's worker thread."""
    return asyncio.run(_call_remote(name, arguments))


if __name__ == "__main__":
    server.run(transport="streamable-http", host="127.0.0.1", port=8765, json_response=True)
