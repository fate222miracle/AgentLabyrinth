"""Append-only in-memory trace, with copy isolation and safe JSON output."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import JsonValue

from packages.domain.models import (
    Contract,
    EpisodeArtifact,
    EstimatedCost,
    EventType,
    RunConfig,
    TokenUsage,
    TraceEvent,
)

SENSITIVE_KEYS = {
    "authorization",
    "token",
    "access_token",
    "api_key",
    "password",
    "secret",
    "chain_of_thought",
    "hidden_reasoning",
}


def sanitize(value: JsonValue) -> JsonValue:
    """Filter known sensitive keys recursively; free text must already be safe."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def content_hash(value: Contract) -> str:
    """Hash canonical JSON, independent of whitespace and dictionary key order."""
    canonical = json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class JsonTraceRecorder:
    """Own one event stream; never return mutable references to stored events."""

    def __init__(
        self,
        run_config: RunConfig,
        episode_id: UUID | None = None,
        events: tuple[TraceEvent, ...] = (),
    ) -> None:
        self._episode_id = episode_id or uuid4()
        self._run_config = run_config.model_copy(deep=True)
        if any(event.episode_id != self._episode_id for event in events):
            raise ValueError("Foreign episode event in checkpoint")
        if any(
            current.parent_event_id != previous.event_id or current.step_index < previous.step_index
            for previous, current in zip(events, events[1:], strict=False)
        ):
            raise ValueError("Invalid checkpoint Trace chain")
        if events and (
            events[0].event_type != EventType.EPISODE_STARTED
            or events[0].parent_event_id is not None
            or any(event.event_type == EventType.EPISODE_FINISHED for event in events)
        ):
            raise ValueError("Checkpoint must contain an unfinished episode")
        self._events: list[TraceEvent] = [event.model_copy(deep=True) for event in events]

    @property
    def episode_id(self) -> UUID:
        """Identify the owned episode."""
        return self._episode_id

    @property
    def run_config(self) -> RunConfig:
        """Expose an independent configuration."""
        return self._run_config.model_copy(deep=True)

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        """Return independent event snapshots in insertion order."""
        return tuple(event.model_copy(deep=True) for event in self._events)

    def record(
        self,
        event_type: EventType,
        step_index: int,
        payload: dict[str, JsonValue],
        *,
        parent_event_id: UUID | None = None,
        duration_ms: int = 0,
        token_usage: TokenUsage | None = None,
        estimated_cost: EstimatedCost | None = None,
    ) -> TraceEvent:
        """Validate causal ordering and append a sanitized independent event."""
        if self._events and self._events[-1].event_type == EventType.EPISODE_FINISHED:
            raise ValueError("episode already finished")
        if parent_event_id is not None and not any(
            event.event_id == parent_event_id for event in self._events
        ):
            raise ValueError("parent event must already exist in this episode")
        if self._events and step_index < self._events[-1].step_index:
            raise ValueError("step index cannot move backwards")
        safe_payload = {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else sanitize(value)
            for key, value in payload.items()
        }
        event = TraceEvent(
            event_id=uuid4(),
            episode_id=self.episode_id,
            step_index=step_index,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            duration_ms=duration_ms,
            payload=safe_payload,
            parent_event_id=parent_event_id,
            token_usage=token_usage or TokenUsage(),
            estimated_cost=estimated_cost or EstimatedCost(),
        ).model_copy(deep=True)
        self._events.append(event)
        return event.model_copy(deep=True)


def write_artifact(artifact: EpisodeArtifact, path: Path) -> None:
    """Write validated JSON at the synchronous CLI boundary, never inside async code."""
    safe = sanitize(artifact.model_dump(mode="json"))
    serialized = json.dumps(safe, ensure_ascii=False, indent=2)
    EpisodeArtifact.model_validate_json(serialized)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized + "\n", encoding="utf-8")


def read_artifact(path: Path) -> EpisodeArtifact:
    """Strictly load a previously saved artifact without invoking a model."""
    return EpisodeArtifact.model_validate_json(path.read_text(encoding="utf-8"))
