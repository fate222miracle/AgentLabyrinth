"""Deterministic evaluator for the fixed key-door GridWorld task."""

from pydantic import JsonValue

from packages.domain.models import (
    EpisodeResult,
    EvaluationResult,
    EventType,
    TaskSpec,
    TerminationReason,
    TraceEvent,
)
from packages.domain.ports import Evaluator
from packages.environments.gridworld.environment import (
    GridWorldEnvironment,
)


class GridWorldKeyDoorEvaluator(Evaluator):
    """Score only authoritative state received inside the trusted Runner."""

    def evaluate(
        self, task: TaskSpec, episode: EpisodeResult, events: tuple[TraceEvent, ...]
    ) -> EvaluationResult:
        """Check the key-door-goal state transition and report bounded counters."""
        layout = GridWorldEnvironment._validate_task(task)
        if episode.episode_id is None:
            raise ValueError("GridWorld evaluator received an unrelated task or episode")
        state = episode.final_state
        if state.get("environment_version") != "gridworld-key-door-v1":
            raise ValueError("GridWorld evaluator received an incompatible state")
        action_count = _integer_field(state, "action_count")
        illegal_count = _integer_field(state, "illegal_action_count")
        position = (_integer_field(state, "x"), _integer_field(state, "y"))
        has_key = state.get("has_key")
        key_available = state.get("key_available")
        door_open = state.get("door_open")
        done = state.get("done")
        if (
            not isinstance(has_key, bool)
            or not isinstance(key_available, bool)
            or not isinstance(door_open, bool)
            or not isinstance(done, bool)
        ):
            raise ValueError("GridWorld evaluator received invalid state flags")
        if action_count > task.max_steps or illegal_count > action_count:
            raise ValueError("GridWorld evaluator received invalid action counters")

        started_actions = {
            str(event.payload.get("call_id")): str(event.payload.get("name"))
            for event in events
            if event.event_type == EventType.TOOL_STARTED
        }
        succeeded_calls = {
            str(event.payload.get("call_id"))
            for event in events
            if event.event_type == EventType.TOOL_SUCCEEDED
        }
        successful_action_events = sum(
            name in task.expected_tools
            for call_id, name in started_actions.items()
            if call_id in succeeded_calls
        )
        key_picked_up = not key_available
        goal_reached = position == layout.goal and done
        success = (
            episode.termination_reason == TerminationReason.SUCCESS
            and key_picked_up
            and not has_key
            and door_open
            and goal_reached
        )
        reason = "key_door_goal_reached" if success else "goal_conditions_not_met"
        metrics: dict[str, JsonValue] = {
            "environment_action_count": action_count,
            "illegal_action_count": illegal_count,
            "key_picked_up": key_picked_up,
            "key_consumed": not has_key and not key_available,
            "door_opened": door_open,
            "goal_reached": goal_reached,
            "successful_action_events": successful_action_events,
        }
        return EvaluationResult(
            evaluator_version="gridworld-key-door-v1",
            success=success,
            reason=reason,
            metrics=metrics,
        )


def _integer_field(state: dict[str, JsonValue], field: str) -> int:
    """Read an integer state counter or coordinate without accepting booleans."""
    value = state.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("GridWorld evaluator received incomplete state")
    return value
