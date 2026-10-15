"""Fake ModelProvider implementation for deterministic testing and M0 execution."""

import re
from decimal import Decimal
from typing import Any

from packages.domain.models import (
    EstimatedCost,
    FinalAnswer,
    Message,
    ModelConfig,
    ModelResponse,
    TokenUsage,
    ToolCall,
    ToolSchema,
)
from packages.domain.ports import ModelProvider


class FakeModelProvider(ModelProvider):
    """Fake model provider translating public observation to portable responses."""

    def __init__(
        self,
        scenario: str = "normal",
        custom_responses: list[ModelResponse] | None = None,
        initial_call_count: int = 0,
    ) -> None:
        self.scenario = scenario.replace("-", "_")
        self.custom_responses = list(custom_responses) if custom_responses else []
        if initial_call_count < 0:
            raise ValueError("initial_call_count must be non-negative")
        self._call_count = initial_call_count

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        """Return a validated action based on public messages and scenario."""
        messages = self._visible_memory(messages)
        self._call_count += 1

        if self.custom_responses:
            index = min(self._call_count - 1, len(self.custom_responses) - 1)
            return self.custom_responses[index].model_copy(deep=True)

        token_usage = TokenUsage(prompt_tokens=40, completion_tokens=20, simulated=True)
        estimated_cost = EstimatedCost(
            amount=Decimal("0.001"),
            currency="USD",
            price_table_version="fake-zero-v1",
            estimated=True,
        )

        if self.scenario == "unparseable":
            raise ValueError("FakeModelProvider simulated unparseable model response")
        if self.scenario == "final_answer_only":
            return ModelResponse(
                action=FinalAnswer(text="Task solved without tool submission."),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )
        if self.scenario == "forbidden_tool":
            return ModelResponse(
                action=ToolCall(
                    call_id="call_forb_1",
                    name="unregistered_or_forbidden",
                    arguments={"key": "val"},
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )
        if self.scenario == "duplicate_call_id":
            return ModelResponse(
                action=ToolCall(
                    call_id="duplicate_id_001",
                    name="query_records",
                    arguments={"table": "orders", "filters": {"order_id": "ORD-001"}},
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )

        if self._extract_task_kind(messages) == "document_chain":
            return self._chain_response(messages, token_usage, estimated_cost)
        if self._extract_task_kind(messages) == "document":
            return self._document_response(messages, token_usage, estimated_cost)

        if self.scenario == "invalid_arguments":
            return self._invalid_order_response(token_usage, estimated_cost)
        if self.scenario == "invalid_then_success" and self._call_count == 1:
            return self._invalid_order_response(token_usage, estimated_cost)

        query_result = self._extract_query_result(messages)
        if self.scenario in {"max_steps", "looping"}:
            target_order_id = self._extract_target_order_id(messages)
            return ModelResponse(
                action=ToolCall(
                    call_id=f"call_loop_{self._call_count}",
                    name="query_records",
                    arguments={
                        "table": "orders",
                        "filters": {"order_id": target_order_id},
                    },
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )

        if query_result is None:
            target_order_id = self._extract_target_order_id(messages)
            action = ToolCall(
                call_id=f"call_query_{self._call_count}",
                name="query_records",
                arguments={
                    "table": "orders",
                    "filters": {"order_id": target_order_id},
                },
            )
        else:
            answer = (
                "processing"
                if self.scenario in {"wrong-answer", "wrong_answer"}
                else query_result["status"]
            )
            action = ToolCall(
                call_id=f"call_submit_{self._call_count}",
                name="submit_answer",
                arguments={"answer": answer, "evidence": query_result["evidence"]},
            )
        return ModelResponse(
            action=action,
            token_usage=token_usage,
            estimated_cost=estimated_cost,
        )

    @staticmethod
    def _visible_memory(messages: list[Message]) -> list[Message]:
        """Interpret only the explicit public memory envelope, like visible tool feedback."""
        expanded: list[Message] = []
        for message in messages:
            expanded.append(message)
            if message.role != "user" or not isinstance(message.content, dict):
                continue
            memory = message.content.get("_agentlabyrinth_memory")
            if not isinstance(memory, dict) or memory.get("schema_version") != "1.0":
                continue
            entries = memory.get("entries")
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                observation, call_id = entry.get("observation"), entry.get("call_id")
                if (
                    isinstance(observation, dict)
                    and "result" in observation
                    and "error" not in observation
                    and isinstance(call_id, str)
                ):
                    expanded.append(Message(role="tool", content=observation, tool_call_id=call_id))
        return expanded

    def _invalid_order_response(
        self, token_usage: TokenUsage, estimated_cost: EstimatedCost
    ) -> ModelResponse:
        """Return the deterministic malformed order query used by recovery tests."""
        return ModelResponse(
            action=ToolCall(
                call_id=f"call_inv_{self._call_count}",
                name="query_records",
                arguments={"table": "invalid_table", "filters": {}},
            ),
            token_usage=token_usage,
            estimated_cost=estimated_cost,
        )

    def _extract_task_kind(self, messages: list[Message]) -> str:
        """Read public task mode without inspecting private goal conditions."""
        for msg in messages:
            if isinstance(msg.content, dict) and msg.content.get("task_kind") in (
                "document",
                "document_chain",
            ):
                return str(msg.content["task_kind"])
        return "order"

    def _chain_response(
        self, messages: list[Message], usage: TokenUsage, cost: EstimatedCost
    ) -> ModelResponse:
        """Follow public document references; retain only evidence visible in the request."""
        document = self._extract_document_result(messages)
        if document is None:
            first = self._extract_document_search_result(messages)
            name = "read_document" if first else "search_documents"
            arguments: dict[str, Any] = (
                {"document_id": first}
                if first
                else {"query": self._extract_document_query(messages), "top_k": 3}
            )
        else:
            link = re.search(r"Next document:\s*([A-Za-z0-9_-]+)", document["content"])
            if link or self.scenario in {"max_steps", "looping"}:
                name = "read_document"
                arguments = {"document_id": link.group(1) if link else "missing-document"}
            else:
                status = re.search(r"Status:\s*([A-Za-z0-9_-]+)", document["content"])
                if status is None:
                    raise ValueError("Document chain has neither a reference nor a status")
                evidence: set[str] = set()
                for message in messages:
                    if message.role == "tool" and isinstance(message.content, dict):
                        result = message.content.get("result")
                        read = result.get("document") if isinstance(result, dict) else None
                        if isinstance(read, dict):
                            identifier = read.get("evidence_id")
                            if isinstance(identifier, str):
                                evidence.add(identifier)
                name = "submit_answer"
                arguments = {
                    "answer": "wrong" if self.scenario == "wrong_answer" else status.group(1),
                    "evidence": sorted(evidence),
                }
        return ModelResponse(
            action=ToolCall(
                call_id=f"call_chain_{self._call_count}", name=name, arguments=arguments
            ),
            token_usage=usage,
            estimated_cost=cost,
        )

    def _document_response(
        self,
        messages: list[Message],
        token_usage: TokenUsage,
        estimated_cost: EstimatedCost,
    ) -> ModelResponse:
        """Complete a document search, read, and evidence submission chain."""
        search_result = self._extract_document_search_result(messages)
        document_result = self._extract_document_result(messages)
        if search_result is None:
            query = self._extract_document_query(messages)
            action = ToolCall(
                call_id=f"call_search_{self._call_count}",
                name="search_documents",
                arguments={"query": query, "top_k": 3},
            )
        elif document_result is None:
            action = ToolCall(
                call_id=f"call_read_{self._call_count}",
                name="read_document",
                arguments={"document_id": search_result},
            )
        else:
            content = document_result["content"]
            answer_match = re.search(
                r"(?:status|answer)\s*:\s*([a-zA-Z0-9_-]+)", content, flags=re.IGNORECASE
            )
            answer = answer_match.group(1) if answer_match else content.strip()
            action = ToolCall(
                call_id=f"call_submit_{self._call_count}",
                name="submit_answer",
                arguments={
                    "answer": answer,
                    "evidence": [document_result["evidence_id"]],
                },
            )
        return ModelResponse(
            action=action,
            token_usage=token_usage,
            estimated_cost=estimated_cost,
        )

    def _extract_target_order_id(self, messages: list[Message]) -> str:
        """Parse target order ID from public messages."""
        for msg in messages:
            if isinstance(msg.content, dict):
                target = msg.content.get("target_order_id")
                if isinstance(target, str):
                    return target
        raise ValueError("Public observation has no target order ID")

    def _extract_document_query(self, messages: list[Message]) -> str:
        """Read the public document search hint."""
        for msg in messages:
            if isinstance(msg.content, dict):
                query = msg.content.get("document_query")
                if isinstance(query, str) and query.strip():
                    return query
        return "status"

    def _extract_query_result(self, messages: list[Message]) -> dict[str, Any] | None:
        """Extract order query result from tool response messages."""
        for msg in reversed(messages):
            if msg.role == "tool" and isinstance(msg.content, dict):
                result = msg.content.get("result")
                if isinstance(result, dict) and "records" in result:
                    records = result.get("records")
                    if isinstance(records, list) and records:
                        record = records[0]
                        if isinstance(record, dict):
                            status = record.get("status")
                            evidence_id = record.get("evidence_id")
                            if isinstance(status, str) and isinstance(evidence_id, str):
                                return {"status": status, "evidence": [evidence_id]}
        return None

    def _extract_document_search_result(self, messages: list[Message]) -> str | None:
        """Return the first document ID from a successful search response."""
        for msg in reversed(messages):
            if msg.role == "tool" and isinstance(msg.content, dict):
                result = msg.content.get("result")
                if isinstance(result, dict):
                    documents = result.get("documents")
                    if isinstance(documents, list) and documents:
                        first = documents[0]
                        if isinstance(first, dict):
                            document_id = first.get("document_id")
                            if isinstance(document_id, str):
                                return document_id
        return None

    def _extract_document_result(self, messages: list[Message]) -> dict[str, str] | None:
        """Return document content and evidence from a successful read."""
        for msg in reversed(messages):
            if msg.role == "tool" and isinstance(msg.content, dict):
                result = msg.content.get("result")
                if isinstance(result, dict):
                    document = result.get("document")
                    if isinstance(document, dict):
                        content = document.get("content")
                        evidence_id = document.get("evidence_id")
                        if isinstance(content, str) and isinstance(evidence_id, str):
                            return {"content": content, "evidence_id": evidence_id}
        return None
