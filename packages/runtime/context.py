"""Pure model-input projection; durable conversation history stays untouched."""

import json
from dataclasses import dataclass

from pydantic import JsonValue

from packages.domain.models import ContextPolicy, Message


class ContextHistoryError(ValueError):
    """A broken tool conversation must not be sent to a provider."""


@dataclass(frozen=True)
class ContextProjection:
    """Detached visible messages and non-content diagnostics for one request."""

    messages: list[Message]
    diagnostics: dict[str, JsonValue]


def project_context(messages: list[Message], policy: ContextPolicy) -> ContextProjection:
    """Keep the initial instructions and whole, matched tool rounds or fail closed."""
    prefix: list[Message] = []
    rounds: list[list[Message]] = []
    seen: set[str] = set()
    index = 0
    while index < len(messages) and messages[index].role in ("system", "user"):
        message = messages[index]
        if message.tool_calls is not None or message.tool_call_id is not None:
            raise ContextHistoryError("Invalid initial message")
        prefix.append(message)
        index += 1
    if not prefix or not any(message.role == "user" for message in prefix):
        raise ContextHistoryError("Missing initial observation")
    while index < len(messages):
        assistant = messages[index]
        if (
            assistant.role != "assistant"
            or not assistant.tool_calls
            or assistant.tool_call_id is not None
        ):
            raise ContextHistoryError("Expected a complete tool round")
        pending = {call.call_id for call in assistant.tool_calls}
        if len(pending) != len(assistant.tool_calls) or pending & seen:
            raise ContextHistoryError("Duplicate tool call ID")
        seen.update(pending)
        round_messages = [assistant]
        index += 1
        while pending:
            if index >= len(messages):
                raise ContextHistoryError("Incomplete tool round")
            feedback = messages[index]
            if (
                feedback.role != "tool"
                or feedback.tool_call_id not in pending
                or feedback.tool_calls is not None
            ):
                raise ContextHistoryError("Orphan or mismatched tool feedback")
            pending.remove(feedback.tool_call_id)
            round_messages.append(feedback)
            index += 1
        rounds.append(round_messages)
    kept = rounds if policy.max_tool_rounds is None else rounds[-policy.max_tool_rounds :]
    visible = prefix + [message for round_messages in kept for message in round_messages]
    detached = [message.model_copy(deep=True) for message in visible]
    # This measures our serialized messages, not provider envelopes or tokenizer output.
    serialized = json.dumps(
        [message.model_dump(mode="json") for message in detached],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ContextProjection(
        messages=detached,
        diagnostics={
            "algorithm_version": policy.algorithm_version,
            "mode": policy.mode,
            "max_tool_rounds": policy.max_tool_rounds,
            "history_messages_count": len(messages),
            "visible_messages_count": len(detached),
            "dropped_messages_count": len(messages) - len(detached),
            "input_messages_bytes": len(serialized.encode("utf-8")),
        },
    )
