"""Fixed key-door GridWorld with separate recovery and agent-visible state."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from packages.domain.models import (
    GRIDWORLD_ENVIRONMENT_VERSION,
    ErrorInfo,
    Observation,
    StepResult,
    TaskSpec,
    ToolCall,
    ToolSchema,
)
from packages.domain.ports import Environment
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator, ToolRegistry

TASK_ID = UUID("a70c6633-c787-4ae3-9e99-85055d519b5f")
TASK_NAME = "key-door-001-v1"
TASK_VERSION = "1.0.0"
MAP_ID = "key-door-001-v1"
ENVIRONMENT_VERSION = GRIDWORLD_ENVIRONMENT_VERSION
MAX_ACTIONS = 16
GALLERY_TASK_NAME = "key-door-002-v1"
GALLERY_TASK_ID = UUID("2d70465a-2b9e-4c8f-8f2f-7f07d5ad4f9c")
GALLERY_MAX_ACTIONS = 20
GALLERY_REAL_MAX_ACTIONS = 24
GALLERY_REAL_MAX_TIME_MS = 330_000
GALLERY_REAL_PROFILE = "temporary-real-gallery-v3"
GALLERY_REAL_ROUTE_HINTS = (
    "Every move refreshes your local view. Read the latest world before acting.",
    "For pickup, first move to the key's exact cell.",
    "Prefer short routes through known walkable cells to a known target. While exploring, "
    "prefer routes that reveal unknown cells before retracing known ground.",
)
REAL_BUDGET_PROFILE = "temporary-real-160k-v2"
REAL_TOKEN_BUDGET = 160_000
REAL_MAX_OUTPUT_TOKENS = 2_048
SOURCE_TOKEN_BUDGET = 16_000
START = (1, 2)
KEY_POSITION = (2, 1)
DOOR_POSITION = (3, 2)
GOAL_POSITION = (5, 2)
KEY_ID = "key-amber"
DOOR_ID = "door-amber"
GOAL_RULE = "collect-key-open-matching-door-enter-goal-v1"

_WALLS = frozenset(
    {(x, y) for x in range(7) for y in (0, 4)}
    | {(x, y) for y in range(5) for x in (0, 6)}
    | {(3, 1), (3, 3)}
)
_GALLERY_ROWS = (
    "#########",
    "#..K#...#",
    "#.#.#.#.#",
    "#S..D.#G#",
    "#.#.#...#",
    "#...#.#.#",
    "#########",
)


@dataclass(frozen=True)
class GridLayout:
    task_id: UUID
    size: tuple[int, int]
    start: tuple[int, int]
    key: tuple[int, int]
    door: tuple[int, int]
    goal: tuple[int, int]
    walls: frozenset[tuple[int, int]]
    max_actions: int
    milestones: tuple[int, int, int]
    description: str


_FIRST_LAYOUT = GridLayout(
    TASK_ID,
    (7, 5),
    START,
    KEY_POSITION,
    DOOR_POSITION,
    GOAL_POSITION,
    _WALLS,
    MAX_ACTIONS,
    (3, 5, 8),
    "Explore the local map, collect the matching key, open its door, and enter the goal.",
)
GRID_LAYOUTS = {
    TASK_NAME: _FIRST_LAYOUT,
    GALLERY_TASK_NAME: GridLayout(
        GALLERY_TASK_ID,
        (9, 7),
        (1, 3),
        (3, 1),
        (4, 3),
        (7, 3),
        frozenset(
            (x, y)
            for y, row in enumerate(_GALLERY_ROWS)
            for x, tile in enumerate(row)
            if tile == "#"
        ),
        GALLERY_MAX_ACTIONS,
        (5, 8, 14),
        "Explore the archive corridors, retrieve the matching key, return to the main door, "
        "and find a route to the exit.",
    ),
}
_DELTAS: dict[str, tuple[int, int]] = {
    "move_up": (0, -1),
    "move_down": (0, 1),
    "move_left": (-1, 0),
    "move_right": (1, 0),
}
_TASK_CONSTRAINTS = (
    "Use one environment action per model response.",
    "Only act on targets identified by your observations.",
)
_TASK_TOOLS = (
    "move_up",
    "move_down",
    "move_left",
    "move_right",
    "inspect",
    "pickup",
    "use",
)
_CELL_KINDS = Literal["wall", "floor", "key", "closed_door", "open_door", "goal"]
_ACTION_NAMES = Literal[
    "move_up", "move_down", "move_left", "move_right", "inspect", "pickup", "use"
]
_ACTION_CODES = Literal[
    "action_completed",
    "movement_blocked",
    "local_view_refreshed",
    "key_unavailable",
    "key_picked_up",
    "target_unavailable",
    "matching_key_required",
    "door_opened",
    "goal_reached",
]


class _EmptyArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class _UseArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    target_id: str = Field(min_length=1)


class _KnownCell(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    x: int = Field(ge=0, le=8)
    y: int = Field(ge=0, le=6)
    kind: _CELL_KINDS
    observed_at_action: int = Field(ge=0, le=GALLERY_REAL_MAX_ACTIONS)


class _Coordinate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    x: int = Field(ge=0, le=8)
    y: int = Field(ge=0, le=6)


class _LastAction(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    action: _ACTION_NAMES
    accepted: bool
    code: _ACTION_CODES
    feedback: str


class _GridWorldSnapshot(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: Literal["1.0"]
    environment_version: Literal["gridworld-key-door-v1"]
    task_id: str
    seed: int
    x: int = Field(ge=1, le=7)
    y: int = Field(ge=1, le=5)
    key_available: bool
    has_key: bool
    door_open: bool
    action_count: int = Field(ge=0, le=GALLERY_REAL_MAX_ACTIONS)
    illegal_action_count: int = Field(ge=0, le=GALLERY_REAL_MAX_ACTIONS)
    done: bool
    known_cells: list[_KnownCell]
    visible_cells: list[_Coordinate]
    last_action: _LastAction | None


class GridWorldEnvironment(Environment):
    """Run the immutable key-door map with strict local actions and partial views."""

    def __init__(self) -> None:
        self._registry = ToolRegistry()
        self._validator = DefaultToolValidator(self._registry)
        self._executor = ToolExecutor(self._registry, self._validator)
        self._layout = _FIRST_LAYOUT
        self._max_actions = self._layout.max_actions
        self._task_id: UUID | None = None
        self._seed = 0
        self._position = START
        self._key_available = True
        self._has_key = False
        self._door_open = False
        self._action_count = 0
        self._illegal_action_count = 0
        self._done = False
        self._known_cells: dict[tuple[int, int], _KnownCell] = {}
        self._visible_cells: set[tuple[int, int]] = set()
        self._last_action: dict[str, JsonValue] | None = None
        self._register_tools()

    def _register_tools(self) -> None:
        """Register one strict single-action tool for each approved game command."""
        descriptions = {
            "move_up": "Move one cell up.",
            "move_down": "Move one cell down.",
            "move_left": "Move one cell left.",
            "move_right": "Move one cell right.",
            "inspect": "Refresh the local observation without moving.",
            "pickup": "Pick up the key at the current cell.",
            "use": "Use a carried key on a visible adjacent target.",
        }
        for name, description in descriptions.items():
            arguments = _UseArgs if name == "use" else _EmptyArgs

            def handler(args: BaseModel, action_name: str = name) -> JsonValue:
                return self._apply_action(action_name, args)

            self._registry.register(
                name=name,
                description=description,
                risk_level="LOW_RISK_WRITE",
                version="gridworld-key-door-v1",
                param_model=arguments,
                handler=handler,
            )

    def reset(self, task: TaskSpec, seed: int) -> Observation:
        """Validate the public task descriptor and return the initial local view."""
        self._layout = self._validate_task(task)
        self._max_actions = task.max_steps
        self._task_id = task.id
        self._seed = seed
        self._position = self._layout.start
        self._key_available = True
        self._has_key = False
        self._door_open = False
        self._action_count = 0
        self._illegal_action_count = 0
        self._done = False
        self._known_cells = {}
        self._visible_cells = set()
        self._last_action = None
        self._refresh_visible_cells()
        return Observation(content=self._observed_world())

    @staticmethod
    def _validate_task(task: TaskSpec) -> GridLayout:
        """Reject task metadata that could smuggle private map facts into artifacts."""
        layout = GRID_LAYOUTS.get(task.name)
        if layout is None:
            raise ValueError("Unsupported or non-public GridWorld task specification")
        base_evaluator_config = {
            "name": "gridworld_key_door_v1",
            "split": "development",
            "origin": "native",
        }
        is_fake_budget = (
            task.version == TASK_VERSION
            and task.token_budget == SOURCE_TOKEN_BUDGET
            and task.evaluator_config == base_evaluator_config
        )
        is_gallery_real_v3 = (
            task.name == GALLERY_TASK_NAME
            and task.version == f"{TASK_VERSION}+{GALLERY_REAL_PROFILE}"
        )
        real_profiles: tuple[tuple[str, int], ...] = (
            ("temporary-real-100k-v1", 100_000),
            (REAL_BUDGET_PROFILE, REAL_TOKEN_BUDGET),
        )
        if is_gallery_real_v3:
            real_profiles += ((GALLERY_REAL_PROFILE, REAL_TOKEN_BUDGET),)
        is_temporary_real_budget = any(
            task.version == f"{TASK_VERSION}+{profile}"
            and task.token_budget == token_budget
            and task.evaluator_config
            == {
                **base_evaluator_config,
                "budget_profile": profile,
                "source_token_budget": SOURCE_TOKEN_BUDGET,
            }
            for profile, token_budget in real_profiles
        )
        constraints = (
            (*_TASK_CONSTRAINTS, *GALLERY_REAL_ROUTE_HINTS)
            if is_gallery_real_v3
            else _TASK_CONSTRAINTS
        )
        max_actions = GALLERY_REAL_MAX_ACTIONS if is_gallery_real_v3 else layout.max_actions
        if (
            task.schema_version != "1.0"
            or task.id != layout.task_id
            or not (is_fake_budget or is_temporary_real_budget)
            or task.category != "gridworld"
            or task.description != layout.description
            or task.initial_state != {"map_id": task.name, "start": list(layout.start)}
            or task.goal_conditions != {"rule_id": GOAL_RULE}
            or task.constraints != constraints
            or task.expected_tools != _TASK_TOOLS
            or task.forbidden_tools
            or task.max_steps != max_actions
        ):
            raise ValueError("Unsupported or non-public GridWorld task specification")
        return layout

    def available_tools(self) -> list[ToolSchema]:
        """Return the seven strict GridWorld action schemas."""
        return self._registry.list_schemas()

    def step(self, action: ToolCall) -> StepResult:
        """Execute one action and return either rule feedback or a safe tool error."""
        if self._task_id is None:
            raise RuntimeError("Environment must be reset before step")
        if self._done:
            raise RuntimeError("GridWorld episode is already complete")
        if self._action_count >= self._max_actions:
            raise RuntimeError("GridWorld action budget is exhausted")
        try:
            result = self._executor.execute(action, tuple(_DELTAS) + ("inspect", "pickup", "use"))
        except ValueError:
            return StepResult(
                observation=Observation(content={"error": "INVALID_ACTION"}),
                error=ErrorInfo(
                    code="TOOL_EXECUTION_ERROR",
                    message="GridWorld action could not be executed.",
                ),
            )
        self._refresh_visible_cells()
        return StepResult(
            observation=Observation(
                content={
                    "action_result": result,
                    "world": self._observed_world(),
                }
            ),
            done=self._done,
        )

    def snapshot(self) -> dict[str, JsonValue]:
        """Return the private, versioned state needed to resume this environment."""
        return cast(
            dict[str, JsonValue],
            _GridWorldSnapshot(
                schema_version="1.0",
                environment_version=ENVIRONMENT_VERSION,
                task_id=str(self._task_id) if self._task_id else "",
                seed=self._seed,
                x=self._position[0],
                y=self._position[1],
                key_available=self._key_available,
                has_key=self._has_key,
                door_open=self._door_open,
                action_count=self._action_count,
                illegal_action_count=self._illegal_action_count,
                done=self._done,
                known_cells=[
                    self._known_cells[coordinate]
                    for coordinate in sorted(self._known_cells, key=lambda cell: (cell[1], cell[0]))
                ],
                visible_cells=[
                    _Coordinate(x=x, y=y)
                    for x, y in sorted(self._visible_cells, key=lambda cell: (cell[1], cell[0]))
                ],
                last_action=(
                    _LastAction.model_validate(self._last_action, strict=True)
                    if self._last_action is not None
                    else None
                ),
            ).model_dump(mode="json"),
        )

    def _observed_world(self) -> dict[str, JsonValue]:
        """Expose usable target IDs only when the target is currently visible."""
        state = self.public_state()
        door = self._layout.door
        if door in self._visible_cells and not self._door_open:
            state["visible_targets"] = [{"target_id": DOOR_ID, "position": [door[0], door[1]]}]
        return state

    def public_state(self) -> dict[str, JsonValue]:
        """Return only the current position and the agent's accumulated known map."""
        if self._task_id is None:
            raise RuntimeError("Environment must be reset before reading public state")
        known_cells: list[JsonValue] = [
            {
                **cell.model_dump(mode="json"),
                "visible": (cell.x, cell.y) in self._visible_cells,
            }
            for cell in sorted(self._known_cells.values(), key=lambda item: (item.y, item.x))
        ]
        return {
            "schema_version": "1.0",
            "environment_version": ENVIRONMENT_VERSION,
            "task_id": str(self._task_id),
            "position": [self._position[0], self._position[1]],
            "inventory": [KEY_ID] if self._has_key else [],
            "action_count": self._action_count,
            "illegal_action_count": self._illegal_action_count,
            "known_cells": known_cells,
            "last_action": deepcopy(self._last_action),
        }

    def restore(self, snapshot: dict[str, JsonValue]) -> None:
        """Validate and restore private state and last-known facts atomically."""
        if self._task_id is None:
            raise ValueError("Environment must be reset before restoring a snapshot")
        state = _GridWorldSnapshot.model_validate(snapshot, strict=True)
        if state.task_id != str(self._task_id) or state.seed != self._seed:
            raise ValueError("Snapshot belongs to another task or seed")
        width, height = self._layout.size
        pickup_at, open_at, finish_at = self._layout.milestones
        if (
            not (0 < state.x < width - 1 and 0 < state.y < height - 1)
            or state.action_count > self._max_actions
        ):
            raise ValueError("GridWorld snapshot exceeds its map or action bounds")
        if state.door_open and (state.key_available or state.has_key):
            raise ValueError("Invalid key and door state in GridWorld snapshot")
        if state.has_key and state.key_available:
            raise ValueError("Invalid duplicate key state in GridWorld snapshot")
        if sum((state.key_available, state.has_key, state.door_open)) != 1:
            raise ValueError("Invalid key lifecycle in GridWorld snapshot")
        if (state.has_key or state.door_open) and state.action_count < pickup_at:
            raise ValueError("Key cannot be collected before its required action sequence")
        if state.done != ((state.x, state.y) == self._layout.goal):
            raise ValueError("Invalid terminal position in GridWorld snapshot")
        if state.done and (
            not state.door_open
            or state.action_count < finish_at
            or state.last_action is None
            or state.last_action.code != "goal_reached"
        ):
            raise ValueError("Invalid completed state in GridWorld snapshot")
        if state.door_open and state.action_count < open_at:
            raise ValueError("Door cannot be open before its required action sequence")
        if state.illegal_action_count > state.action_count:
            raise ValueError("Invalid action counters in GridWorld snapshot")
        if (state.action_count == 0) != (state.last_action is None):
            raise ValueError("Last action does not match the action counter")
        if state.last_action is not None:
            self._validate_last_action(state.last_action)
            if state.last_action.code == "key_picked_up" and not state.has_key:
                raise ValueError("Picked-up key is missing from GridWorld snapshot state")
            if state.last_action.code == "door_opened" and not state.door_open:
                raise ValueError("Opened door is missing from GridWorld snapshot state")
            if (state.last_action.code == "goal_reached") != state.done:
                raise ValueError("Goal action does not match terminal GridWorld state")
            if not state.last_action.accepted and state.illegal_action_count == 0:
                raise ValueError("Rejected action is missing from GridWorld action counters")
        if (state.x, state.y) in self._layout.walls or (
            (state.x, state.y) == self._layout.door and not state.door_open
        ):
            raise ValueError("Player position is blocked in GridWorld snapshot")
        if (state.x, state.y) == self._layout.goal and not state.door_open:
            raise ValueError("Goal position is unreachable while its door is closed")

        known_cells: dict[tuple[int, int], _KnownCell] = {}
        for cell in state.known_cells:
            coordinate = (cell.x, cell.y)
            if (
                cell.x >= width
                or cell.y >= height
                or coordinate in known_cells
                or cell.observed_at_action > state.action_count
            ):
                raise ValueError("Invalid known-cell history in GridWorld snapshot")
            if cell.kind not in self._possible_cell_kinds(coordinate):
                raise ValueError("Known cell kind does not match the fixed map")
            known_cells[coordinate] = cell
        visible_cells = {(cell.x, cell.y) for cell in state.visible_cells}
        if len(visible_cells) != len(state.visible_cells) or not visible_cells.issubset(
            known_cells
        ):
            raise ValueError("Invalid visible-cell set in GridWorld snapshot")
        expected_visible = self._visible_cells_at((state.x, state.y), door_open=state.door_open)
        if visible_cells != expected_visible:
            raise ValueError("Visible-cell set does not match the current position")
        for coordinate in visible_cells:
            cell = known_cells[coordinate]
            if cell.observed_at_action != state.action_count or cell.kind != self._cell_at_state(
                coordinate,
                key_available=state.key_available,
                door_open=state.door_open,
            ):
                raise ValueError("Visible cell does not match the current observation")
        for coordinate, cell in known_cells.items():
            if coordinate == self._layout.key and cell.kind != (
                "key" if state.key_available else "floor"
            ):
                raise ValueError("Known key state is inconsistent with the snapshot")
            if coordinate == self._layout.door and cell.kind != (
                "open_door" if state.door_open else "closed_door"
            ):
                raise ValueError("Known door state is inconsistent with the snapshot")

        self._position = (state.x, state.y)
        self._key_available = state.key_available
        self._has_key = state.has_key
        self._door_open = state.door_open
        self._action_count = state.action_count
        self._illegal_action_count = state.illegal_action_count
        self._done = state.done
        self._known_cells = known_cells
        self._visible_cells = visible_cells
        self._last_action = (
            state.last_action.model_dump(mode="json") if state.last_action is not None else None
        )

    def _possible_cell_kinds(self, coordinate: tuple[int, int]) -> tuple[str, ...]:
        """Return terrain values a known cell may have on this immutable map."""
        if coordinate in self._layout.walls:
            return ("wall",)
        if coordinate == self._layout.key:
            return ("key", "floor")
        if coordinate == self._layout.door:
            return ("closed_door", "open_door")
        if coordinate == self._layout.goal:
            return ("goal",)
        return ("floor",)

    @staticmethod
    def _validate_last_action(action: _LastAction) -> None:
        """Reject impossible action feedback in a private checkpoint."""
        feedback_by_code = {
            "action_completed": "Action completed.",
            "movement_blocked": "Movement blocked.",
            "local_view_refreshed": "Local view refreshed.",
            "key_unavailable": "No available key is at the current cell.",
            "key_picked_up": "Key picked up.",
            "target_unavailable": "Target unavailable.",
            "matching_key_required": "A matching key is required.",
            "door_opened": "Door opened; the matching key was consumed.",
            "goal_reached": "Goal reached.",
        }
        valid_actions = {
            "action_completed": _TASK_TOOLS[:4],
            "movement_blocked": _TASK_TOOLS[:4],
            "local_view_refreshed": ("inspect",),
            "key_unavailable": ("pickup",),
            "key_picked_up": ("pickup",),
            "target_unavailable": ("use",),
            "matching_key_required": ("use",),
            "door_opened": ("use",),
            "goal_reached": _TASK_TOOLS[:4],
        }
        if (
            action.feedback != feedback_by_code[action.code]
            or action.action not in valid_actions[action.code]
            or action.accepted
            != (
                action.code
                in (
                    "action_completed",
                    "local_view_refreshed",
                    "key_picked_up",
                    "door_opened",
                    "goal_reached",
                )
            )
        ):
            raise ValueError("Invalid last action in GridWorld snapshot")

    def _apply_action(self, name: str, args: BaseModel) -> JsonValue:
        """Apply one validated game action; rule violations remain normal feedback."""
        if self._done or self._action_count >= self._max_actions:
            raise RuntimeError("GridWorld action budget is exhausted")
        self._action_count += 1
        accepted = True
        code = "action_completed"
        feedback = "Action completed."

        if name in _DELTAS:
            dx, dy = _DELTAS[name]
            destination = (self._position[0] + dx, self._position[1] + dy)
            if self._cell_at(destination) in ("wall", "closed_door"):
                accepted = False
                code = "movement_blocked"
                feedback = "Movement blocked."
            else:
                self._position = destination
                if destination == self._layout.goal:
                    self._done = True
                    code = "goal_reached"
                    feedback = "Goal reached."
        elif name == "inspect":
            code = "local_view_refreshed"
            feedback = "Local view refreshed."
        elif name == "pickup":
            if self._position != self._layout.key or not self._key_available:
                accepted = False
                code = "key_unavailable"
                feedback = "No available key is at the current cell."
            else:
                self._key_available = False
                self._has_key = True
                code = "key_picked_up"
                feedback = "Key picked up."
        elif name == "use":
            target_id = cast(_UseArgs, args).target_id
            door = self._layout.door
            adjacent = abs(self._position[0] - door[0]) + abs(self._position[1] - door[1]) == 1
            target_visible = door in self._visible_cells
            if target_id != DOOR_ID or not adjacent or not target_visible or self._door_open:
                accepted = False
                code = "target_unavailable"
                feedback = "Target unavailable."
            elif not self._has_key:
                accepted = False
                code = "matching_key_required"
                feedback = "A matching key is required."
            else:
                self._has_key = False
                self._door_open = True
                code = "door_opened"
                feedback = "Door opened; the matching key was consumed."
        else:
            raise RuntimeError("Unregistered GridWorld action reached handler")

        if not accepted:
            self._illegal_action_count += 1
        self._last_action = {
            "action": name,
            "accepted": accepted,
            "code": code,
            "feedback": feedback,
        }
        self._refresh_visible_cells()
        return cast(JsonValue, deepcopy(self._last_action))

    def _cell_at(self, coordinate: tuple[int, int]) -> _CELL_KINDS:
        """Resolve current authoritative terrain without exposing it directly."""
        return self._cell_at_state(
            coordinate, key_available=self._key_available, door_open=self._door_open
        )

    def _refresh_visible_cells(self) -> None:
        """Update only facts reached by the current four cardinal rays."""
        visible = self._visible_cells_at(self._position, door_open=self._door_open)
        self._visible_cells = visible
        for x, y in visible:
            self._known_cells[(x, y)] = _KnownCell(
                x=x,
                y=y,
                kind=self._cell_at((x, y)),
                observed_at_action=self._action_count,
            )

    def _visible_cells_at(
        self, position: tuple[int, int], *, door_open: bool
    ) -> set[tuple[int, int]]:
        """Compute the current four-ray view without changing remembered facts."""
        visible: set[tuple[int, int]] = {position}
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            for distance in (1, 2):
                coordinate = (
                    position[0] + dx * distance,
                    position[1] + dy * distance,
                )
                kind = self._cell_at_state(coordinate, key_available=True, door_open=door_open)
                visible.add(coordinate)
                if kind in ("wall", "closed_door"):
                    break
        return visible

    def _cell_at_state(
        self, coordinate: tuple[int, int], *, key_available: bool, door_open: bool
    ) -> _CELL_KINDS:
        """Resolve terrain from an explicit state without mutating the environment."""
        if coordinate in self._layout.walls:
            return "wall"
        if coordinate == self._layout.key and key_available:
            return "key"
        if coordinate == self._layout.door:
            return "open_door" if door_open else "closed_door"
        if coordinate == self._layout.goal:
            return "goal"
        return "floor"
