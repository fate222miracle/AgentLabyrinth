"""GridWorld environment, visibility, evaluator, and fixed-budget contracts."""

import asyncio
from collections.abc import Callable
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import JsonValue

from packages.application.runner import run_episode
from packages.domain.models import (
    AgentSpec,
    Budget,
    EpisodeResult,
    EstimatedCost,
    EvaluationResult,
    EventType,
    FinalAnswer,
    Message,
    ModelConfig,
    ModelResponse,
    RunConfig,
    StepResult,
    TaskSpec,
    TerminationReason,
    TokenUsage,
    ToolCall,
    ToolSchema,
    TraceEvent,
)
from packages.domain.ports import Evaluator, ModelProvider
from packages.environments.gridworld.environment import (
    DOOR_POSITION,
    ENVIRONMENT_VERSION,
    GOAL_POSITION,
    KEY_POSITION,
    MAX_ACTIONS,
    TASK_NAME,
    GridWorldEnvironment,
)
from packages.environments.gridworld.evaluator import GridWorldKeyDoorEvaluator
from packages.runtime.handwritten.budget import BudgetTracker
from packages.runtime.handwritten.runtime import HandwrittenRuntime
from packages.runtime.session import SessionState

ROOT = Path(__file__).resolve().parents[2]
TASK_PATH = ROOT / "benchmarks/gridworld/tasks/key-door-001-v1.json"
ActionSpec = tuple[str, dict[str, JsonValue]]
SnapshotMutation = Callable[[dict[str, JsonValue]], None]
TaskMutation = Callable[[TaskSpec], TaskSpec]
SOLUTION: tuple[ActionSpec, ...] = (
    ("move_up", {}),
    ("move_right", {}),
    ("pickup", {}),
    ("move_down", {}),
    ("use", {"target_id": "door-amber"}),
    ("move_right", {}),
    ("move_right", {}),
    ("move_right", {}),
)


def json_object(value: JsonValue) -> dict[str, JsonValue]:
    """Narrow one JSON value to an object for explicit test assertions."""
    assert isinstance(value, dict)
    return value


def json_list(value: JsonValue) -> list[JsonValue]:
    """Narrow one JSON value to an array for explicit test assertions."""
    assert isinstance(value, list)
    return value


def cell_coordinates(cell: dict[str, JsonValue]) -> tuple[int, int]:
    """Read a known-cell coordinate without relying on unvalidated JSON types."""
    x = cell.get("x")
    y = cell.get("y")
    assert isinstance(x, int) and not isinstance(x, bool)
    assert isinstance(y, int) and not isinstance(y, bool)
    return x, y


def known_cells(state: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """Return known cells after validating the public JSON shape."""
    return [json_object(value) for value in json_list(state["known_cells"])]


def load_task() -> TaskSpec:
    """Load the approved public GridWorld task fixture."""
    return TaskSpec.model_validate_json(TASK_PATH.read_text(encoding="utf-8"))


def make_call(name: str, arguments: dict[str, JsonValue] | None = None) -> ToolCall:
    """Create one unique GridWorld action proposal."""
    return ToolCall(
        call_id=str(uuid4()),
        name=name,
        arguments=arguments or {},
    )


def run_action(
    environment: GridWorldEnvironment,
    name: str,
    arguments: dict[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    """Run a schema-valid game action and return its public observation."""
    result = environment.step(make_call(name, arguments))
    assert result.error is None
    return result.observation.content


class SequenceProvider(ModelProvider):
    """Return a fixed action sequence while retaining every model-visible message."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.calls = 0
        self.message_batches: list[list[Message]] = []

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        assert config.max_tokens == 800
        assert len(tools) == 7
        self.message_batches.append([message.model_copy(deep=True) for message in messages])
        response = self.responses[self.calls]
        self.calls += 1
        return response


class FailingEvaluator(Evaluator):
    """Raise after execution to verify Runner never serializes a private snapshot."""

    def evaluate(
        self, task: TaskSpec, episode: EpisodeResult, events: tuple[TraceEvent, ...]
    ) -> EvaluationResult:
        raise RuntimeError("test evaluator failure")


class FailingProjectionEnvironment(GridWorldEnvironment):
    """Always fail the explicit public projection without exposing snapshot data."""

    def public_state(self) -> dict[str, JsonValue]:
        raise RuntimeError("test public projection failure")


def response(
    name: str,
    arguments: dict[str, JsonValue] | None = None,
    *,
    prompt_tokens: int = 1,
    completion_tokens: int = 1,
) -> ModelResponse:
    """Build one simulated response with explicitly reported use."""
    return ModelResponse(
        action=make_call(name, arguments),
        token_usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            simulated=True,
        ),
    )


def make_agent(budget: Budget | None = None) -> AgentSpec:
    """Create an agent using the fixed per-response output cap."""
    return AgentSpec(
        id=uuid4(),
        name="gridworld-contract-agent",
        version="1.0.0",
        description="Fake test agent",
        prompt_version="gridworld-test-v1",
        tool_set_version="gridworld-key-door-v1",
        model=ModelConfig(max_tokens=800),
        budget=budget
        or Budget(
            max_steps=16,
            max_model_calls=16,
            max_tool_calls=16,
            max_prompt_tokens=16_000,
            max_completion_tokens=12_800,
        ),
    )


def make_run_config(seed: int = 1) -> RunConfig:
    """Bind the fixed map to its immutable environment version."""
    return RunConfig(seed=seed, environment_version=ENVIRONMENT_VERSION)


def state_has_private_fields(value: object) -> bool:
    """Recursively detect private checkpoint fields in public JSON objects."""
    if isinstance(value, dict):
        private_keys = {"key_available", "has_key", "door_open", "visible_cells", "last_state"}
        return bool(private_keys.intersection(value)) or any(
            state_has_private_fields(item) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(state_has_private_fields(item) for item in value)
    return False


def test_fixed_route_is_eight_actions_and_evaluator_uses_private_terminal_state() -> None:
    task = load_task()
    environment = GridWorldEnvironment()
    environment.reset(task, seed=7)
    observations = [run_action(environment, name, arguments) for name, arguments in SOLUTION]

    snapshot = environment.snapshot()
    result = GridWorldKeyDoorEvaluator().evaluate(
        task,
        EpisodeResult(
            episode_id=uuid4(),
            termination_reason=TerminationReason.SUCCESS,
            detail="goal_reached",
            step_count=8,
            model_call_count=8,
            tool_call_count=8,
            duration_ms=0,
            final_state=snapshot,
        ),
        (),
    )

    assert snapshot["action_count"] == 8
    assert snapshot["has_key"] is False
    assert snapshot["key_available"] is False
    assert snapshot["door_open"] is True
    assert snapshot["done"] is True
    assert result.success is True
    assert result.metrics == {
        "environment_action_count": 8,
        "illegal_action_count": 0,
        "key_picked_up": True,
        "key_consumed": True,
        "door_opened": True,
        "goal_reached": True,
        "successful_action_events": 0,
    }
    assert observations[4]["action_result"] == {
        "action": "use",
        "accepted": True,
        "code": "door_opened",
        "feedback": "Door opened; the matching key was consumed.",
    }


def test_public_observation_hides_unexplored_goal_and_private_snapshot_fields() -> None:
    environment = GridWorldEnvironment()
    observation = environment.reset(load_task(), seed=1)
    public = environment.public_state()
    private = environment.snapshot()

    assert {
        key: value for key, value in observation.content.items() if key != "visible_targets"
    } == public
    assert not state_has_private_fields(public)
    assert not state_has_private_fields(observation.content)
    cells = known_cells(public)
    assert len(cells) < 35
    assert (5, 2) not in {cell_coordinates(cell) for cell in cells}
    assert private != public
    assert {"key_available", "has_key", "door_open", "visible_cells"} <= set(private)
    assert public["position"] == [1, 2]
    assert public["inventory"] == []


def test_visible_door_exposes_the_target_id_needed_by_use() -> None:
    environment = GridWorldEnvironment()
    initial = environment.reset(load_task(), seed=1).content
    assert initial.get("visible_targets") == [{"target_id": "door-amber", "position": [3, 2]}]
    hidden = run_action(environment, "move_up")
    assert "visible_targets" not in json_object(hidden["world"])

    for action, arguments in SOLUTION[1:4]:
        observed = run_action(environment, action, arguments)
    target = json_object(json_list(json_object(observed["world"])["visible_targets"])[0])
    target_id = target["target_id"]
    assert isinstance(target_id, str)
    opened = run_action(environment, "use", {"target_id": target_id})
    assert json_object(opened["action_result"])["accepted"] is True
    assert "visible_targets" not in json_object(opened["world"])


def test_observation_rays_stop_at_walls_and_closed_doors_then_reveal_open_door() -> None:
    environment = GridWorldEnvironment()
    environment.reset(load_task(), seed=1)
    initial = environment.public_state()
    initial_coordinates = {cell_coordinates(cell) for cell in known_cells(initial)}
    assert (3, 2) in initial_coordinates
    assert (4, 2) not in initial_coordinates

    for name, arguments in SOLUTION[:5]:
        run_action(environment, name, arguments)
    after_open = environment.public_state()
    known = {cell_coordinates(cell): cell for cell in known_cells(after_open)}
    assert known[(3, 2)]["kind"] == "open_door"
    assert known[(4, 2)]["kind"] == "floor"
    assert (5, 2) not in known

    run_action(environment, "move_left")
    run_action(environment, "move_up")
    moved_away = environment.public_state()
    remembered_door = next(
        cell for cell in known_cells(moved_away) if cell_coordinates(cell) == DOOR_POSITION
    )
    assert remembered_door["kind"] == "open_door"
    assert remembered_door["visible"] is False


@pytest.mark.parametrize(
    ("name", "arguments", "expected_code"),
    [
        ("move_left", {}, "movement_blocked"),
        ("pickup", {}, "key_unavailable"),
    ],
)
def test_rule_rejections_are_counted_actions_not_tool_errors(
    name: str, arguments: dict[str, JsonValue], expected_code: str
) -> None:
    environment = GridWorldEnvironment()
    environment.reset(load_task(), seed=1)

    feedback = run_action(environment, name, arguments)

    action_result = json_object(feedback["action_result"])
    assert action_result["accepted"] is False
    assert action_result["code"] == expected_code
    assert environment.snapshot()["action_count"] == 1
    assert environment.snapshot()["illegal_action_count"] == 1


def test_wrong_or_invisible_target_does_not_probe_hidden_map() -> None:
    environment = GridWorldEnvironment()
    environment.reset(load_task(), seed=1)

    result = environment.step(make_call("use", {"target_id": "hidden-target"}))

    assert result.error is None
    assert json_object(result.observation.content["action_result"])["code"] == (
        "target_unavailable"
    )
    assert environment.snapshot()["action_count"] == 1
    assert environment.snapshot()["illegal_action_count"] == 1


def test_invalid_tool_proposal_is_an_execution_error_not_a_game_action() -> None:
    environment = GridWorldEnvironment()
    environment.reset(load_task(), seed=1)

    result = environment.step(make_call("unknown_action"))

    assert result.error is not None
    assert result.error.code == "TOOL_EXECUTION_ERROR"
    assert result.observation.content == {"error": "INVALID_ACTION"}
    assert environment.snapshot()["action_count"] == 0
    assert environment.snapshot()["illegal_action_count"] == 0


def test_snapshot_order_and_same_seed_are_deterministic() -> None:
    snapshots = []
    public_states = []
    for seed in (1, 7, 99):
        environment = GridWorldEnvironment()
        environment.reset(load_task(), seed=seed)
        snapshots.append(environment.snapshot())
        public_states.append(environment.public_state())
    assert public_states[0] == public_states[1] == public_states[2]
    comparable_snapshots = [
        {key: value for key, value in snapshot.items() if key != "seed"} for snapshot in snapshots
    ]
    assert comparable_snapshots[0] == comparable_snapshots[1] == comparable_snapshots[2]

    environment = GridWorldEnvironment()
    environment.reset(load_task(), seed=7)
    same_seed_snapshot = environment.snapshot()
    same_seed_public = environment.public_state()
    repeated = GridWorldEnvironment()
    repeated.reset(load_task(), seed=7)
    assert repeated.snapshot() == same_seed_snapshot
    assert repeated.public_state() == same_seed_public

    for name, arguments in SOLUTION[:5]:
        run_action(environment, name, arguments)
        run_action(repeated, name, arguments)
    first = environment.snapshot()
    second_environment = GridWorldEnvironment()
    second_environment.reset(load_task(), seed=7)
    for name, arguments in SOLUTION[:5]:
        run_action(second_environment, name, arguments)
    assert first == second_environment.snapshot()


def test_restore_preserves_private_and_public_state_without_revealing_unexplored_cells() -> None:
    task = load_task()
    source = GridWorldEnvironment()
    source.reset(task, seed=3)
    for name, arguments in SOLUTION[:5]:
        run_action(source, name, arguments)
    run_action(source, "move_left")
    snapshot = source.snapshot()
    target = GridWorldEnvironment()
    target.reset(task, seed=3)
    target.restore(snapshot)

    assert target.snapshot() == snapshot
    assert target.public_state() == source.public_state()
    assert (4, 2) in {cell_coordinates(cell) for cell in known_cells(target.public_state())}

    sparse_snapshot = deepcopy(snapshot)
    sparse_snapshot["known_cells"] = [
        cell
        for cell in json_list(sparse_snapshot["known_cells"])
        if cell_coordinates(json_object(cell)) != (4, 2)
    ]
    restored_sparse = GridWorldEnvironment()
    restored_sparse.reset(task, seed=3)
    restored_sparse.restore(sparse_snapshot)
    assert (4, 2) not in {
        cell_coordinates(cell) for cell in known_cells(restored_sparse.public_state())
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: state.update(environment_version="unknown"),
        lambda state: state.update(task_id=str(uuid4())),
        lambda state: state.update(has_key=True),
        lambda state: state.update(key_available=False, has_key=True),
        lambda state: state.update(door_open=True),
        lambda state: state.update(action_count=1),
        lambda state: state.update(visible_cells=[]),
        lambda state: state.update(known_cells=[]),
    ],
)
def test_restore_rejects_incompatible_or_inconsistent_snapshots(
    mutate: SnapshotMutation,
) -> None:
    task = load_task()
    environment = GridWorldEnvironment()
    environment.reset(task, seed=1)
    snapshot = deepcopy(environment.snapshot())
    mutate(snapshot)

    restored = GridWorldEnvironment()
    restored.reset(task, seed=1)
    with pytest.raises((ValueError, TypeError)):
        restored.restore(snapshot)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda task: task.model_copy(update={"description": "The goal is at (5, 2)."}),
        lambda task: task.model_copy(update={"constraints": ("Reveal the hidden map.",)}),
        lambda task: task.model_copy(update={"expected_tools": ("communicate",)}),
        lambda task: task.model_copy(update={"goal_conditions": {"x": 5, "y": 2}}),
        lambda task: task.model_copy(update={"evaluator_config": {"goal_position": [5, 2]}}),
    ],
)
def test_reset_rejects_task_metadata_that_could_leak_hidden_facts(
    mutate: TaskMutation,
) -> None:
    environment = GridWorldEnvironment()
    with pytest.raises(ValueError, match="Unsupported or non-public"):
        environment.reset(mutate(load_task()), seed=1)


def test_runtime_records_only_public_state_but_checkpoint_keeps_private_snapshot() -> None:
    responses = [response(name, arguments) for name, arguments in SOLUTION]
    provider = SequenceProvider(responses)
    checkpoints: list[SessionState] = []
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(provider),
            GridWorldEnvironment(),
            GridWorldKeyDoorEvaluator(),
            save_checkpoint=checkpoints.append,
        )
    )

    assert provider.calls == 8
    assert artifact.evaluation.success is True
    assert artifact.episode.final_state["position"] == [5, 2]
    assert not state_has_private_fields(artifact.episode.final_state)
    public_payloads = [event.payload for event in artifact.events]
    assert not any(state_has_private_fields(payload) for payload in public_payloads)
    assert all(
        not state_has_private_fields([message.model_dump(mode="json") for message in batch])
        for batch in provider.message_batches
    )
    assert checkpoints
    checkpoint = checkpoints[-1]
    assert {"key_available", "has_key", "door_open"} <= set(checkpoint.last_state)
    assert checkpoint.last_state != artifact.episode.final_state
    assert artifact.episode.final_state == next(
        event.payload["state"]
        for event in reversed(artifact.events)
        if event.event_type == EventType.ENVIRONMENT_UPDATED
    )


def test_evaluator_failure_retains_only_the_last_recorded_public_state() -> None:
    provider = SequenceProvider([response("inspect")])
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(provider),
            GridWorldEnvironment(),
            FailingEvaluator(),
        )
    )

    assert artifact.episode.termination_reason == TerminationReason.RUNTIME_ERROR
    assert artifact.episode.final_state == next(
        event.payload["state"]
        for event in reversed(artifact.events)
        if event.event_type == EventType.ENVIRONMENT_UPDATED
    )
    assert not state_has_private_fields(artifact.episode.final_state)
    assert not any(state_has_private_fields(event.payload) for event in artifact.events)


def test_gridworld_failed_move_does_not_publish_unrecorded_goal() -> None:
    class FailingMove(GridWorldEnvironment):
        def step(self, action: ToolCall) -> StepResult:
            result = super().step(action)
            if self.public_state()["action_count"] == 6:
                raise RuntimeError("failure after entering the open door")
            return result

    provider = SequenceProvider([response(name, args) for name, args in SOLUTION[:6]])
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(provider),
            FailingMove(),
            GridWorldKeyDoorEvaluator(),
        )
    )

    last = next(
        json_object(event.payload["state"])
        for event in reversed(artifact.events)
        if event.event_type == EventType.ENVIRONMENT_UPDATED
    )
    assert artifact.episode.termination_reason == TerminationReason.RUNTIME_ERROR
    assert last["action_count"] == 5
    assert all(cell["kind"] != "goal" for cell in known_cells(last))
    assert artifact.episode.final_state == last


def test_legacy_budget_still_allows_another_request_at_exact_limit() -> None:
    task = TaskSpec.model_validate_json(
        next((ROOT / "benchmarks/tool_lab_core/tasks").rglob("order-status-001.json")).read_text(
            encoding="utf-8"
        )
    )
    tracker = BudgetTracker(Budget(max_prompt_tokens=16_000, max_completion_tokens=12_800), task)
    assert tracker.accrue_usage(TokenUsage(prompt_tokens=task.token_budget), EstimatedCost())[0]
    assert tracker.can_call_model() == (True, None, None)


def test_public_projection_failure_fails_closed_in_artifact_and_trace() -> None:
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(SequenceProvider([])),
            FailingProjectionEnvironment(),
            GridWorldKeyDoorEvaluator(),
        )
    )

    assert artifact.episode.termination_reason == TerminationReason.RUNTIME_ERROR
    assert artifact.episode.final_state == {}
    assert not any(state_has_private_fields(event.payload) for event in artifact.events)


@pytest.mark.parametrize("prompt_tokens", [1, 16_000])
def test_per_response_801_tokens_are_recorded_and_action_is_rejected(prompt_tokens: int) -> None:
    oversized = response("inspect", prompt_tokens=prompt_tokens, completion_tokens=801).model_copy(
        update={
            "estimated_cost": EstimatedCost(
                amount=Decimal("0.12"),
                price_table_version="gridworld-test-v1",
            )
        }
    )
    provider = SequenceProvider([oversized])
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(provider),
            GridWorldEnvironment(),
            GridWorldKeyDoorEvaluator(),
        )
    )

    assert provider.calls == 1
    assert artifact.episode.termination_reason == TerminationReason.TOKEN_BUDGET_EXCEEDED
    assert artifact.episode.detail == "model_completion_tokens_exceeded"
    assert artifact.episode.token_usage.prompt_tokens == prompt_tokens
    assert artifact.episode.token_usage.completion_tokens == 801
    assert artifact.episode.estimated_cost.amount == Decimal("0.12")
    assert artifact.episode.final_state["action_count"] == 0
    assert not any(event.event_type == EventType.TOOL_STARTED for event in artifact.events)
    assert not any(event.event_type == EventType.ENVIRONMENT_UPDATED for event in artifact.events)


def test_per_response_800_tokens_execute_current_action() -> None:
    provider = SequenceProvider(
        [
            response("inspect", prompt_tokens=1, completion_tokens=800),
            ModelResponse(
                action=FinalAnswer(text="No submission."),
                token_usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
            ),
        ]
    )
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(provider),
            GridWorldEnvironment(),
            GridWorldKeyDoorEvaluator(),
        )
    )
    assert artifact.episode.final_state["action_count"] == 1
    assert artifact.episode.token_usage.completion_tokens == 801


@pytest.mark.parametrize(
    ("prompt_tokens", "completion_tokens", "expected_detail", "expected_actions"),
    [
        (15_999, 1, "task_token_budget_reached", 1),
        (15_999, 2, "task_token_budget_exceeded", 0),
        (16_000, 0, "agent_max_prompt_tokens_reached", 1),
        (16_001, 0, "agent_max_prompt_tokens_exceeded", 0),
    ],
)
def test_cumulative_token_boundary_accounts_response_and_blocks_followup(
    prompt_tokens: int,
    completion_tokens: int,
    expected_detail: str,
    expected_actions: int,
) -> None:
    provider = SequenceProvider(
        [
            response(
                "inspect",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
            response("inspect"),
        ]
    )
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(provider),
            GridWorldEnvironment(),
            GridWorldKeyDoorEvaluator(),
        )
    )

    assert provider.calls == 1
    assert artifact.episode.detail == expected_detail
    assert artifact.episode.token_usage.prompt_tokens == prompt_tokens
    assert artifact.episode.token_usage.completion_tokens == completion_tokens
    assert artifact.episode.final_state["action_count"] == expected_actions
    assert sum(event.event_type == EventType.TOOL_STARTED for event in artifact.events) == (
        expected_actions
    )


def test_exact_token_boundary_executes_rule_rejection_then_stops() -> None:
    provider = SequenceProvider(
        [
            response("move_left", prompt_tokens=15_999, completion_tokens=1),
            response("inspect"),
        ]
    )
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(provider),
            GridWorldEnvironment(),
            GridWorldKeyDoorEvaluator(),
        )
    )

    assert provider.calls == 1
    assert artifact.episode.detail == "task_token_budget_reached"
    assert artifact.episode.final_state["action_count"] == 1
    assert artifact.episode.final_state["illegal_action_count"] == 1
    assert sum(event.event_type == EventType.TOOL_SUCCEEDED for event in artifact.events) == 1
    assert not any(event.event_type == EventType.TOOL_FAILED for event in artifact.events)
    assert sum(event.event_type == EventType.MODEL_REQUESTED for event in artifact.events) == 1


def test_sixteenth_action_can_succeed_and_unsolved_action_stops_without_request_17() -> None:
    complete_responses = [response("inspect") for _ in range(8)] + [
        response(name, arguments) for name, arguments in SOLUTION
    ]
    complete_provider = SequenceProvider(complete_responses)
    complete = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(complete_provider),
            GridWorldEnvironment(),
            GridWorldKeyDoorEvaluator(),
        )
    )
    assert complete_provider.calls == 16
    assert complete.episode.termination_reason == TerminationReason.SUCCESS
    assert complete.episode.final_state["action_count"] == 16

    unfinished_provider = SequenceProvider([response("inspect") for _ in range(16)])
    unfinished = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(unfinished_provider),
            GridWorldEnvironment(),
            GridWorldKeyDoorEvaluator(),
        )
    )
    assert unfinished_provider.calls == 16
    assert unfinished.episode.termination_reason == TerminationReason.MAX_STEPS
    assert unfinished.episode.detail == "max_steps_reached"
    assert unfinished.episode.final_state["action_count"] == 16
    assert sum(event.event_type == EventType.MODEL_REQUESTED for event in unfinished.events) == 16
    assert sum(event.event_type == EventType.TOOL_STARTED for event in unfinished.events) == 16


def test_completion_token_budget_at_12800_allows_sixteenth_action_without_request_17() -> None:
    provider = SequenceProvider(
        [response("inspect", prompt_tokens=0, completion_tokens=800) for _ in range(16)]
    )
    artifact = asyncio.run(
        run_episode(
            make_agent(),
            load_task(),
            make_run_config(),
            HandwrittenRuntime(provider),
            GridWorldEnvironment(),
            GridWorldKeyDoorEvaluator(),
        )
    )

    assert provider.calls == 16
    assert artifact.episode.termination_reason == TerminationReason.MAX_STEPS
    assert artifact.episode.token_usage.completion_tokens == 12_800
    assert artifact.episode.final_state["action_count"] == 16
    assert sum(event.event_type == EventType.MODEL_REQUESTED for event in artifact.events) == 16


def test_budget_tracker_accepts_exact_completion_and_cost_limits_then_rejects_excess() -> None:
    task = load_task().model_copy(update={"max_steps": 32, "token_budget": 32_000})
    budget = Budget(
        max_steps=32,
        max_model_calls=32,
        max_tool_calls=32,
        max_prompt_tokens=32_000,
        max_completion_tokens=12_800,
        max_estimated_cost=Decimal("1.00"),
    )
    tracker = BudgetTracker(budget, task)

    for _ in range(16):
        allowed, _, _ = tracker.accrue_usage(
            TokenUsage(prompt_tokens=0, completion_tokens=800),
            EstimatedCost(amount=Decimal("0.0625"), price_table_version="gridworld-test-v1"),
        )
        assert allowed
    assert tracker.completion_tokens == 12_800
    allowed, reason, detail = tracker.accrue_usage(
        TokenUsage(prompt_tokens=0, completion_tokens=1),
        EstimatedCost(amount=Decimal("0"), price_table_version="gridworld-test-v1"),
    )
    assert not allowed
    assert reason == TerminationReason.TOKEN_BUDGET_EXCEEDED
    assert detail == "agent_max_completion_tokens_exceeded"
    assert tracker.completion_tokens == 12_801
    assert tracker.estimated_cost == 1

    exact_cost = BudgetTracker(
        Budget(
            max_estimated_cost=Decimal("1.00"),
            max_prompt_tokens=32_000,
            max_completion_tokens=32_000,
        ),
        task,
    )
    allowed, _, _ = exact_cost.accrue_usage(
        TokenUsage(prompt_tokens=0, completion_tokens=0),
        EstimatedCost(amount=Decimal("1.00"), price_table_version="gridworld-test-v1"),
    )
    assert allowed
    allowed, reason, detail = exact_cost.accrue_usage(
        TokenUsage(prompt_tokens=0, completion_tokens=0),
        EstimatedCost(amount=Decimal("0.01"), price_table_version="gridworld-test-v1"),
    )
    assert not allowed
    assert reason == TerminationReason.COST_BUDGET_EXCEEDED
    assert detail == "agent_max_estimated_cost_exceeded"


def test_gridworld_budget_schema_allows_fixed_execution_deadline() -> None:
    budget = Budget(
        schema_version="1.1",
        max_execution_time_ms=300_000,
        max_steps=16,
        max_model_calls=16,
        max_tool_calls=16,
        max_prompt_tokens=16_000,
        max_completion_tokens=12_800,
        max_estimated_cost=Decimal("1.00"),
    )
    agent = make_agent(budget)
    assert agent.budget.max_execution_time_ms == 300_000
    assert agent.budget.schema_version == "1.1"


def test_fixed_task_and_map_constants_match_task_fixture() -> None:
    task = load_task()
    environment = GridWorldEnvironment()
    environment.reset(task, seed=1)
    assert task.name == TASK_NAME
    assert MAX_ACTIONS == 16
    assert KEY_POSITION == (2, 1)
    assert DOOR_POSITION == (3, 2)
    assert GOAL_POSITION == (5, 2)
