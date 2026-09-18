"""Contract tests for multi-turn tool call message representation and call ID preservation."""

import asyncio
from datetime import UTC
from pathlib import Path
from uuid import uuid4

from packages.domain.models import (
    AgentSpec,
    Message,
    ModelConfig,
    ModelResponse,
    Observation,
    RunConfig,
    StepResult,
    TaskSpec,
    TerminationReason,
    TokenUsage,
    ToolCall,
    ToolSchema,
)
from packages.domain.ports import ModelProvider, ToolValidator
from packages.runtime.handwritten.runtime import HandwrittenRuntime

ROOT = Path(__file__).resolve().parents[2]


class MultiTurnTrackingProvider(ModelProvider):
    """Provider that captures the received messages across multiple rounds."""

    def __init__(self) -> None:
        self.history_records: list[list[Message]] = []
        self.call_count = 0

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        self.call_count += 1
        # Record a snapshot of messages received at each turn
        self.history_records.append([m.model_copy(deep=True) for m in messages])

        if self.call_count == 1:
            return ModelResponse(
                action=ToolCall(
                    call_id="call_test_step1",
                    name="query_records",
                    arguments={"table": "orders", "filters": {"order_id": "ORD-001"}},
                ),
                token_usage=TokenUsage(prompt_tokens=20, completion_tokens=10, simulated=False),
            )
        else:
            return ModelResponse(
                action=ToolCall(
                    call_id="call_test_step2",
                    name="submit_answer",
                    arguments={"answer": "delivered", "evidence": ["order:ORD-001"]},
                ),
                token_usage=TokenUsage(prompt_tokens=40, completion_tokens=15, simulated=False),
            )


class DummyMockEnvironment:
    """Minimal environment providing query_records and submit_answer."""

    def __init__(self) -> None:
        self.done = False

    def reset(self, task: TaskSpec, seed: int) -> Observation:
        return Observation(content={"target_order_id": "ORD-001"})

    def available_tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="query_records",
                description="Query records",
                parameters={
                    "type": "object",
                    "properties": {"table": {"type": "string"}},
                    "required": ["table"],
                },
                version="1.0.0",
                risk_level="READ_ONLY",
            ),
            ToolSchema(
                name="submit_answer",
                description="Submit answer",
                parameters={
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                },
                version="1.0.0",
                risk_level="LOW_RISK_WRITE",
            ),
        ]

    def step(self, action: ToolCall) -> StepResult:
        if action.name == "query_records":
            return StepResult(
                observation=Observation(content={"result": {"status": "delivered"}}),
                done=False,
            )
        elif action.name == "submit_answer":
            self.done = True
            return StepResult(
                observation=Observation(content={"status": "submitted"}),
                done=True,
            )
        return StepResult(observation=Observation(content={}), done=False)

    def snapshot(self) -> dict[str, object]:
        return {"done": self.done}

    def restore(self, snapshot: dict[str, object]) -> None:
        pass


class PassthroughValidator(ToolValidator):
    def validate(self, action: ToolCall, allowed_tools: tuple[str, ...]) -> None:
        return None


class MinimalTraceRecorder:
    def __init__(self) -> None:
        self.episode_id = uuid4()
        self.run_config = RunConfig()
        self.events: list[object] = []

    def record(
        self, event_type: object, step_index: int, payload: object, **kwargs: object
    ) -> object:
        from datetime import datetime
        from uuid import uuid4

        from packages.domain.models import TraceEvent

        ev = TraceEvent(
            event_id=uuid4(),
            episode_id=self.episode_id,
            step_index=step_index,
            event_type=event_type,  # type: ignore[arg-type]
            timestamp=datetime.now(UTC),
            payload=payload,  # type: ignore[arg-type]
        )
        self.events.append(ev)
        return ev


def test_runtime_multi_turn_message_contract() -> None:
    """Verify that in turn 2, the messages sent to provider contain assistant tool_calls
    and tool feedback."""
    provider = MultiTurnTrackingProvider()
    validator = PassthroughValidator()
    runtime = HandwrittenRuntime(provider=provider, validator=validator)
    env = DummyMockEnvironment()
    recorder = MinimalTraceRecorder()

    agent = AgentSpec(
        id=uuid4(),
        name="test-agent",
        version="1.0.0",
        description="multi-turn test",
        prompt_version="v1",
        tool_set_version="v1",
    )
    task = TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )

    result = asyncio.run(runtime.run(agent, task, env, recorder))  # type: ignore[arg-type]

    assert result.termination_reason == TerminationReason.SUCCESS
    assert provider.call_count == 2

    # Verify messages in Turn 1: [system, user]
    turn1_msgs = provider.history_records[0]
    assert len(turn1_msgs) == 2
    assert turn1_msgs[0].role == "system"
    assert turn1_msgs[1].role == "user"

    # Verify messages in Turn 2:
    # [system, user, assistant (with tool_calls), tool (with tool_call_id)]
    turn2_msgs = provider.history_records[1]
    assert len(turn2_msgs) == 4
    assert turn2_msgs[0].role == "system"
    assert turn2_msgs[1].role == "user"

    # Assistant message from Turn 1 action
    assert turn2_msgs[2].role == "assistant"
    assert turn2_msgs[2].tool_calls is not None
    assert len(turn2_msgs[2].tool_calls) == 1
    assert turn2_msgs[2].tool_calls[0].call_id == "call_test_step1"
    assert turn2_msgs[2].tool_calls[0].name == "query_records"

    # Tool message from Turn 1 execution
    assert turn2_msgs[3].role == "tool"
    assert turn2_msgs[3].tool_call_id == "call_test_step1"
    assert isinstance(turn2_msgs[3].content, dict)
    assert turn2_msgs[3].content.get("result") == {"status": "delivered"}

    # Total token usage should report simulated=False because provider used simulated=False
    assert result.token_usage.simulated is False
    assert result.token_usage.prompt_tokens == 60
    assert result.token_usage.completion_tokens == 25
