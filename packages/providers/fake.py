"""Fake ModelProvider implementation for deterministic testing and M0 execution."""

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
    ) -> None:
        self.scenario = scenario.replace("-", "_")
        self.custom_responses = list(custom_responses) if custom_responses else []
        self._call_count = 0

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        """Return a validated action based on conversation history and scenario."""
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

        if self.scenario == "invalid_arguments":
            return ModelResponse(
                action=ToolCall(
                    call_id="call_inv_1",
                    name="query_records",
                    arguments={"table": "invalid_table", "filters": {}},
                ),
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

        # Inspect messages for observation & tool results
        query_result = self._extract_query_result(messages)

        if self.scenario == "max_steps" or self.scenario == "looping":
            call_id = f"call_loop_{self._call_count}"
            target_order_id = self._extract_target_order_id(messages)
            return ModelResponse(
                action=ToolCall(
                    call_id=call_id,
                    name="query_records",
                    arguments={"table": "orders", "filters": {"order_id": target_order_id}},
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )

        if query_result is None:
            # Turn 1: Propose query_records for target order ID
            target_order_id = self._extract_target_order_id(messages)
            return ModelResponse(
                action=ToolCall(
                    call_id=f"call_query_{self._call_count}",
                    name="query_records",
                    arguments={"table": "orders", "filters": {"order_id": target_order_id}},
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )
        else:
            # Turn 2: Extract status and evidence, propose submit_answer
            if self.scenario == "wrong-answer" or self.scenario == "wrong_answer":
                answer = "processing"
                evidence = query_result["evidence"]
            else:
                answer = query_result["status"]
                evidence = query_result["evidence"]

            return ModelResponse(
                action=ToolCall(
                    call_id=f"call_submit_{self._call_count}",
                    name="submit_answer",
                    arguments={
                        "answer": answer,
                        "evidence": evidence,
                    },
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )

    def _extract_target_order_id(self, messages: list[Message]) -> str:
        """Parse target order ID from public messages."""
        for msg in messages:
            if isinstance(msg.content, dict):
                if "target_order_id" in msg.content and isinstance(
                    msg.content["target_order_id"], str
                ):
                    return msg.content["target_order_id"]
        raise ValueError("Public observation has no target order ID")

    def _extract_query_result(self, messages: list[Message]) -> dict[str, Any] | None:
        """Extract order query result from tool response messages."""
        for msg in reversed(messages):
            if msg.role == "tool" and isinstance(msg.content, dict):
                res = msg.content.get("result")
                if isinstance(res, dict) and "records" in res:
                    records = res.get("records")
                    if (
                        isinstance(records, list)
                        and len(records) > 0
                        and isinstance(records[0], dict)
                    ):
                        rec = records[0]
                        status = rec.get("status")
                        evidence_id = rec.get("evidence_id")
                        if not isinstance(status, str) or not isinstance(evidence_id, str):
                            raise ValueError("Query result has no status or evidence ID")
                        return {"status": status, "evidence": [evidence_id]}
        return None
