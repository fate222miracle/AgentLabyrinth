"""Protocol safety and compatibility of the model-input window."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.domain.models import AgentSpec, ContextPolicy, Message, ToolCall
from packages.runtime.context import ContextHistoryError, project_context

ROOT = Path(__file__).resolve().parents[2]


def conversation() -> list[Message]:
    """Include nested feedback so detached copies can be exercised."""
    messages = [Message(role="system", content="instruction"), Message(role="user", content="任务")]
    for number in (1, 2, 3):
        call = ToolCall(call_id=f"call-{number}", name="read", arguments={"number": number})
        messages += [
            Message(role="assistant", tool_calls=(call,)),
            Message(role="tool", tool_call_id=call.call_id, content={"data": [number]}),
        ]
    return messages


@pytest.mark.parametrize(
    "data",
    [
        {"mode": "recent_tool_rounds"},
        {"mode": "full", "max_tool_rounds": 1},
        {"mode": "recent_tool_rounds", "max_tool_rounds": 0},
        {"mode": "recent_tool_rounds", "max_tool_rounds": 101},
        {"mode": "recent_tool_rounds", "max_tool_rounds": True},
        {"mode": "recent_tool_rounds", "max_tool_rounds": "2"},
        {"algorithm_version": "unknown"},
        {"unexpected": "ignored?"},
    ],
)
def test_policy_rejects_ambiguous_configuration(data: dict[str, object]) -> None:
    """Window, algorithm and unknown fields must be explicit and typed."""
    with pytest.raises(ValidationError):
        ContextPolicy.model_validate(data)


def test_legacy_agent_hash_input_and_revision() -> None:
    """Old Agent JSON retains its exact serialized shape; new policy needs 1.2."""
    source = (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    agent = AgentSpec.model_validate_json(source)
    data = agent.model_dump(mode="json")
    assert "context_policy" not in data
    assert AgentSpec.model_validate_json(agent.model_dump_json()) == agent
    with pytest.raises(ValidationError, match="schema 1.2"):
        AgentSpec.model_validate({**agent.model_dump(), "context_policy": ContextPolicy()})
    explicit = AgentSpec.model_validate(
        {
            **agent.model_dump(),
            "schema_version": "1.2",
            "context_policy": ContextPolicy(),
        }
    )
    assert json.loads(explicit.model_dump_json())["context_policy"]["mode"] == "full"


def test_window_keeps_prefix_complete_rounds_and_detaches_nested_values() -> None:
    """The provider gets only the chosen round and cannot mutate retained history."""
    original = conversation()
    before = [message.model_dump() for message in original]
    projection = project_context(
        original, ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=1)
    )
    assert [message.role for message in projection.messages] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]
    assert projection.messages[-1].tool_call_id == "call-3"
    assert projection.diagnostics["dropped_messages_count"] == 4
    serialized = json.dumps(
        [m.model_dump(mode="json") for m in projection.messages],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert projection.diagnostics["input_messages_bytes"] == len(serialized.encode("utf-8"))
    feedback = projection.messages[-1].content
    assert isinstance(feedback, dict)
    feedback["data"] = [999]
    projection.messages.clear()
    assert [message.model_dump() for message in original] == before


def test_multi_call_round_is_indivisible_and_feedback_order_can_vary() -> None:
    """A round count never slices an assistant with multiple matching tool results."""
    messages = conversation()[:2]
    calls = tuple(ToolCall(call_id=id_, name="read", arguments={}) for id_ in ("a", "b"))
    messages += [
        Message(role="assistant", tool_calls=calls),
        Message(role="tool", tool_call_id="b"),
        Message(role="tool", tool_call_id="a"),
    ]
    assert (
        project_context(
            messages, ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=1)
        ).messages
        == messages
    )


@pytest.mark.parametrize(
    "defect", ["missing", "orphan", "duplicate", "late_user", "no_observation"]
)
def test_broken_history_rejected_even_if_bad_round_would_be_dropped(defect: str) -> None:
    """Validate the whole history before trimming; malformed prefixes cannot hide."""
    messages = conversation()
    if defect == "missing":
        del messages[3]
    elif defect == "orphan":
        messages[3] = Message(role="tool", tool_call_id="unknown")
    elif defect == "duplicate":
        messages[4:6] = messages[2:4]
    elif defect == "late_user":
        messages.insert(4, Message(role="user", content="unexpected"))
    else:
        messages = messages[2:]
    with pytest.raises(ContextHistoryError):
        project_context(messages, ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=1))


def test_full_and_large_window_preserve_every_message() -> None:
    """Explicit full retains the baseline input, independent of copy identities."""
    messages = conversation()
    for policy in (ContextPolicy(), ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=100)):
        projection = project_context(messages, policy)
        assert projection.messages == messages
        assert projection.diagnostics["dropped_messages_count"] == 0


def memory_policy(limit: int = 8192) -> ContextPolicy:
    return ContextPolicy(
        schema_version="1.1",
        algorithm_version="tool-round-window-memory-v1",
        mode="recent_tool_rounds",
        max_tool_rounds=1,
        memory_max_bytes=limit,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "1.0"},
        {"algorithm_version": "tool-round-window-v1"},
        {"mode": "full", "max_tool_rounds": None},
        {"memory_max_bytes": None},
        {"memory_max_bytes": 255},
        {"memory_max_bytes": 32769},
        {"memory_max_bytes": True},
        {"memory_max_bytes": "8192"},
    ],
)
def test_memory_version_and_budget_are_strict(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ContextPolicy.model_validate({**memory_policy().model_dump(), **change})


def test_old_policy_serialization_is_exact() -> None:
    assert ContextPolicy().model_dump() == {
        "schema_version": "1.0",
        "algorithm_version": "tool-round-window-v1",
        "mode": "full",
        "max_tool_rounds": None,
    }


def test_memory_has_only_dropped_successful_data_and_preserves_history() -> None:
    messages = conversation()
    messages[3] = Message(
        role="tool", tool_call_id="call-1", content={"result": {"text": "来源一"}}
    )
    messages[5] = Message(
        role="tool",
        tool_call_id="call-2",
        content={"error": {"code": "INVALID_ARGUMENTS"}, "result": "spoofed"},
    )
    before = [message.model_dump() for message in messages]
    projection = project_context(messages, memory_policy())
    observation = projection.messages[1].content
    assert isinstance(observation, dict)
    memory = observation["_agentlabyrinth_memory"]
    assert isinstance(memory, dict)
    assert memory["entries"] == [
        {"call_id": "call-1", "tool_name": "read", "observation": messages[3].content}
    ]
    assert projection.diagnostics["memory_source_call_ids"] == ["call-1"]
    assert projection.diagnostics["memory_bytes"] == len(
        json.dumps(memory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    assert projection.messages[-1].tool_call_id == "call-3"
    memory["entries"] = []
    assert [message.model_dump() for message in messages] == before


def test_memory_budget_skips_whole_large_results_and_keeps_chronology() -> None:
    messages = conversation()
    for index in (3, 5, 7):
        messages[index] = messages[index].model_copy(update={"content": {"result": "a"}})
    all_kept = project_context(messages, memory_policy())
    assert all_kept.diagnostics["memory_source_call_ids"] == ["call-1", "call-2"]
    exact = int(all_kept.diagnostics["memory_bytes"])  # type: ignore[arg-type]
    assert project_context(messages, memory_policy(exact)).diagnostics["memory_entries_count"] == 2
    assert project_context(messages, memory_policy(exact - 1)).diagnostics[
        "memory_source_call_ids"
    ] == ["call-2"]
    messages[5] = messages[5].model_copy(update={"content": {"result": "大" * 10000}})
    small = project_context(messages, memory_policy(300))
    assert small.diagnostics["memory_source_call_ids"] == ["call-1"]
    assert small.diagnostics["memory_omitted_entries_count"] == 1
    assert int(small.diagnostics["memory_bytes"]) <= 300  # type: ignore[arg-type]


def test_reserved_memory_field_and_broken_dropped_history_fail_closed() -> None:
    messages = conversation()
    messages[1] = Message(role="user", content={"_agentlabyrinth_memory": {"entries": []}})
    with pytest.raises(ContextHistoryError, match="Reserved"):
        project_context(messages, memory_policy())
    messages = conversation()
    messages[3] = Message(role="tool", tool_call_id="not-the-call")
    with pytest.raises(ContextHistoryError):
        project_context(messages, memory_policy())
