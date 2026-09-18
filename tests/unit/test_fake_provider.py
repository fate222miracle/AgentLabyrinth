"""Unit tests for FakeModelProvider."""

import asyncio

import pytest

from packages.domain.models import (
    FinalAnswer,
    Message,
    ModelConfig,
    ToolCall,
)
from packages.providers.fake import FakeModelProvider


def test_fake_provider_normal_multi_turn() -> None:
    """Normal mode produces query_records turn 1, submit_answer turn 2 based on message history."""
    provider = FakeModelProvider(scenario="normal")

    # Turn 1: initial message
    messages = [
        Message(role="system", content="task description"),
        Message(role="user", content={"target_order_id": "ORD-001"}),
    ]
    resp1 = asyncio.run(provider.generate(messages, [], ModelConfig()))
    assert isinstance(resp1.action, ToolCall)
    assert resp1.action.name == "query_records"
    assert resp1.action.arguments == {"table": "orders", "filters": {"order_id": "ORD-001"}}

    # Turn 2: tool response added
    messages.append(
        Message(
            role="tool",
            content={
                "result": {
                    "records": [
                        {"order_id": "ORD-001", "status": "shipped", "evidence_id": "order:ORD-001"}
                    ]
                }
            },
            tool_call_id=resp1.action.call_id,
        )
    )
    resp2 = asyncio.run(provider.generate(messages, [], ModelConfig()))
    assert isinstance(resp2.action, ToolCall)
    assert resp2.action.name == "submit_answer"
    assert resp2.action.arguments == {"answer": "shipped", "evidence": ["order:ORD-001"]}


def test_fake_provider_negative_scenarios() -> None:
    """Fake provider correctly simulates wrong-answer, invalid-arguments, and
    unparseable scenarios."""
    # Unparseable
    p_unparseable = FakeModelProvider(scenario="unparseable")
    with pytest.raises(ValueError, match="unparseable"):
        asyncio.run(p_unparseable.generate([], [], ModelConfig()))

    # Invalid arguments
    p_inv = FakeModelProvider(scenario="invalid_arguments")
    resp_inv = asyncio.run(p_inv.generate([], [], ModelConfig()))
    assert isinstance(resp_inv.action, ToolCall)
    assert resp_inv.action.arguments["table"] == "invalid_table"

    # Final answer only
    p_final = FakeModelProvider(scenario="final_answer_only")
    resp_final = asyncio.run(p_final.generate([], [], ModelConfig()))
    assert isinstance(resp_final.action, FinalAnswer)
