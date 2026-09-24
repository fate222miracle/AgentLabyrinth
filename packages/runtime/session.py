"""Framework-independent episode operations shared by both runtime schedulers."""

import asyncio
from collections.abc import Callable
from time import perf_counter
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from packages.domain.models import (
    AgentSpec,
    EpisodeResult,
    EstimatedCost,
    EventType,
    FinalAnswer,
    Message,
    TaskSpec,
    TerminationReason,
    TokenUsage,
    ToolCall,
)
from packages.domain.ports import (
    Environment,
    ModelProvider,
    ModelProviderError,
    ToolValidator,
    TraceRecorder,
)
from packages.runtime.handwritten.budget import BudgetState, BudgetTracker
from packages.tools.registry import DefaultToolValidator, ToolRegistry, ValidationResult

NextNode = Literal["model", "validate", "execute", "end"]


class SessionState(BaseModel):
    """Portable state saved only at a model boundary or after termination."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    next_node: Literal["model", "end"]
    messages: tuple[Message, ...]
    seen_call_ids: tuple[str, ...]
    retried: bool
    budget: BudgetState
    last_state: dict[str, JsonValue]
    termination_reason: TerminationReason
    detail: str
    elapsed_ms: int = Field(ge=0)


class CheckpointFailure(RuntimeError):
    """A failed durable write must abort instead of yielding a false completed run."""


class ResumableRuntime(Protocol):
    """Opt-in continuation surface; the original Runtime Port stays compatible."""

    async def run_resumable(
        self,
        agent: AgentSpec,
        task: TaskSpec,
        environment: Environment,
        recorder: TraceRecorder,
        *,
        resume_state: SessionState | None = None,
        save_checkpoint: Callable[[SessionState], None] | None = None,
    ) -> EpisodeResult: ...


class EpisodeSession:
    """Own one episode's mutable state; operations never schedule their next call."""

    def __init__(
        self,
        agent: AgentSpec,
        task: TaskSpec,
        environment: Environment,
        recorder: TraceRecorder,
        provider: ModelProvider,
        validator: ToolValidator | None,
    ) -> None:
        self.started = perf_counter()
        self.agent, self.task = agent, task
        self.environment, self.recorder, self.provider = environment, recorder, provider
        simulated = agent.model.provider == "fake"
        self.budget = BudgetTracker(
            agent.budget,
            task,
            is_simulated=simulated,
            price_table_version="fake-zero-v1" if simulated else "aihubmix-free-unverified",
        )
        self.messages: list[Message] = []
        self.action: ToolCall | None = None
        self.seen_call_ids: set[str] = set()
        self.retried = False
        self.last_state: dict[str, JsonValue] = {}
        self.termination_reason = TerminationReason.FAILED
        self.detail = "loop_terminated_without_submission"
        events = recorder.events
        self.parent_event_id = events[-1].event_id if events else None

        env_validator = getattr(environment, "_validator", None)
        env_registry = getattr(environment, "_registry", None)
        self.validator = validator
        if self.validator is None:
            if isinstance(env_validator, DefaultToolValidator):
                self.validator = env_validator
            elif isinstance(env_registry, ToolRegistry):
                self.validator = DefaultToolValidator(env_registry)

    def record(
        self,
        event_type: EventType,
        payload: dict[str, JsonValue],
        *,
        token_usage: TokenUsage | None = None,
        estimated_cost: EstimatedCost | None = None,
    ) -> None:
        """Append one canonical event linked to the preceding event."""
        event = self.recorder.record(
            event_type,
            self.budget.step_count,
            payload,
            parent_event_id=self.parent_event_id,
            token_usage=token_usage,
            estimated_cost=estimated_cost,
        )
        self.parent_event_id = event.event_id

    def checkpoint(self, next_node: NextNode, save: Callable[[SessionState], None] | None) -> None:
        """Persist only after a complete observation or tool/model outcome."""
        if save is None or next_node not in ("model", "end"):
            return
        state = SessionState(
            next_node=next_node,
            messages=tuple(self.messages),
            seen_call_ids=tuple(sorted(self.seen_call_ids)),
            retried=self.retried,
            budget=self.budget.snapshot(),
            last_state=self.last_state,
            termination_reason=self.termination_reason,
            detail=self.detail,
            elapsed_ms=int((perf_counter() - self.started) * 1000),
        )
        try:
            save(state)
        except Exception as exc:
            raise CheckpointFailure("Could not persist episode checkpoint") from exc

    def restore(self, state: SessionState) -> NextNode:
        """Restore the environment and counters before scheduling any new action."""
        self.environment.reset(self.task, self.recorder.run_config.seed)
        self.environment.restore(state.last_state)
        if self.environment.snapshot() != state.last_state:
            raise ValueError("Environment checkpoint mismatch")
        self.budget.restore(state.budget)
        self.messages = list(state.messages)
        self.seen_call_ids = set(state.seen_call_ids)
        if len(self.seen_call_ids) != len(state.seen_call_ids):
            raise ValueError("Duplicate tool call ID in checkpoint")
        self.retried = state.retried
        self.last_state = state.last_state
        self.termination_reason = state.termination_reason
        self.detail = state.detail
        self.started = perf_counter() - state.elapsed_ms / 1000
        events = self.recorder.events
        self.parent_event_id = events[-1].event_id if events else None
        return state.next_node

    def stop(self, reason: TerminationReason, detail: str) -> NextNode:
        """Retain usage and the last valid environment state on every stop."""
        self.termination_reason, self.detail = reason, detail
        return "end"

    def observe(self) -> NextNode:
        """Reset the environment and build only the public model context."""
        obs = self.environment.reset(self.task, self.recorder.run_config.seed)
        self.last_state = self.environment.snapshot()
        self.record(
            EventType.OBSERVATION_CREATED,
            {"observation": obs.content, "initial_state": self.last_state},
        )
        self.messages = [
            Message(
                role="system",
                content={
                    "task": self.task.description,
                    "constraints": list(self.task.constraints),
                    "instruction": "Use tools and follow their parameter descriptions exactly.",
                },
            ),
            Message(role="user", content=obs.content),
        ]
        return "model"

    async def call_model(self) -> NextNode:
        """Check limits, call the provider once, and account for its full response."""
        allowed, reason, detail = self.budget.can_call_model()
        if not allowed:
            return self.stop(reason or TerminationReason.MAX_STEPS, detail or "max_steps_exceeded")
        self.budget.model_call_count += 1
        self.budget.step_count += 1
        self.record(EventType.MODEL_REQUESTED, {"messages_count": len(self.messages)})
        try:
            response = await self.provider.generate(
                self.messages, self.environment.available_tools(), self.agent.model
            )
        except ModelProviderError as exc:
            return self.stop(TerminationReason.RUNTIME_ERROR, f"provider_error: {exc.code}")
        except Exception:
            return self.stop(TerminationReason.RUNTIME_ERROR, "provider_error")

        allowed, reason, detail = self.budget.accrue_usage(
            response.token_usage, response.estimated_cost
        )
        self.record(
            EventType.MODEL_RESPONDED,
            {"action_kind": response.action.kind},
            token_usage=response.token_usage,
            estimated_cost=response.estimated_cost,
        )
        if not allowed:
            return self.stop(
                reason or TerminationReason.TOKEN_BUDGET_EXCEEDED, detail or "token_budget_exceeded"
            )
        if isinstance(response.action, FinalAnswer):
            return self.stop(TerminationReason.FAILED, "missing_submission")
        self.action = response.action
        return "validate"

    def _inspect(self, action: ToolCall) -> ValidationResult:
        allowed = tuple(t for t in self.task.expected_tools if t not in self.task.forbidden_tools)
        if self.validator is None:
            raise RuntimeError("Tool validator is required")
        if isinstance(self.validator, DefaultToolValidator):
            return self.validator.inspect(action, allowed)
        err = self.validator.validate(action, allowed)
        return ValidationResult(
            arguments_valid=err is None or err.code != "INVALID_ARGUMENTS",
            permitted=err is None or err.code != "FORBIDDEN_TOOL",
            error_code=err.code if err else None,
            error_info=err,
        )

    def validate(self) -> NextNode:
        """Reject unsafe actions; only one permitted argument error can re-enter model."""
        action = self.action
        if action is None:
            raise RuntimeError("No tool action to validate")
        self.record(
            EventType.TOOL_CALL_PROPOSED,
            {"call_id": action.call_id, "name": action.name, "arguments": action.arguments},
        )
        inspection = self._inspect(action)
        duplicate = action.call_id in self.seen_call_ids
        self.record(
            EventType.TOOL_CALL_VALIDATED,
            {
                "call_id": action.call_id,
                "name": action.name,
                "arguments_valid": inspection.arguments_valid,
                "permitted": inspection.permitted,
                "error_code": "DUPLICATE_CALL_ID" if duplicate else inspection.error_code,
            },
        )
        if duplicate:
            return self.stop(TerminationReason.FAILED, "duplicate_call_id")
        self.seen_call_ids.add(action.call_id)
        if inspection.error_code == "UNKNOWN_TOOL":
            return self.stop(TerminationReason.FAILED, "unknown_tool")
        if not inspection.permitted or inspection.error_code == "FORBIDDEN_TOOL":
            return self.stop(TerminationReason.FAILED, f"forbidden_tool: {action.name}")
        if not inspection.arguments_valid:
            if (
                self.agent.recovery_policy == "invalid_arguments_once"
                and inspection.error_code == "INVALID_ARGUMENTS"
                and not self.retried
            ):
                self.retried = True
                schema = next(
                    (t for t in self.environment.available_tools() if t.name == action.name), None
                )
                feedback: dict[str, JsonValue] = {
                    "error": "INVALID_ARGUMENTS",
                    "message": (
                        f"Parameter validation failed for tool '{action.name}'. "
                        "Parameters must conform to schema."
                    ),
                    "tool": action.name,
                    "parameters_schema": schema.parameters if schema else {},
                }
                self.messages.append(Message(role="assistant", tool_calls=(action,)))
                self.messages.append(
                    Message(role="tool", content=feedback, tool_call_id=action.call_id)
                )
                return "model"
            return self.stop(
                TerminationReason.FAILED, f"invalid_arguments: {inspection.error_code}"
            )
        # Unrecognized validator failures must fail closed, including custom validators.
        if inspection.error_code is not None:
            return self.stop(TerminationReason.FAILED, "tool_validation_failed")
        return "execute"

    async def execute(self) -> NextNode:
        """Run one validated tool through Environment/Executor, then append its feedback."""
        action = self.action
        if action is None:
            raise RuntimeError("No tool action to execute")
        allowed, reason, detail = self.budget.can_start_tool()
        if not allowed:
            return self.stop(
                reason or TerminationReason.MAX_STEPS, detail or "max_tool_calls_exceeded"
            )
        self.budget.tool_call_count += 1
        started_payload: dict[str, JsonValue] = {"call_id": action.call_id, "name": action.name}
        transport = getattr(self.environment, "tool_transport", None)
        if isinstance(transport, str) and action.name in getattr(
            self.environment, "remote_tools", ()
        ):
            started_payload["transport"] = transport
        self.record(EventType.TOOL_STARTED, started_payload)
        try:
            # ToolLab may cross a real network boundary; keep the event loop responsive.
            step = await asyncio.to_thread(self.environment.step, action)
            self.last_state = self.environment.snapshot()
        except Exception:
            self.record(
                EventType.TOOL_FAILED,
                {"call_id": action.call_id, "error_code": "ENVIRONMENT_ERROR"},
            )
            return self.stop(TerminationReason.RUNTIME_ERROR, "environment_error")
        if step.error is not None:
            self.record(
                EventType.TOOL_FAILED,
                {"call_id": action.call_id, "error": step.error.model_dump()},
            )
            return self.stop(TerminationReason.FAILED, f"tool_failed: {step.error.code}")
        self.record(
            EventType.TOOL_SUCCEEDED,
            {"call_id": action.call_id, "observation": step.observation.content},
        )
        self.record(EventType.ENVIRONMENT_UPDATED, {"done": step.done, "state": self.last_state})
        self.messages.append(Message(role="assistant", content=None, tool_calls=(action,)))
        self.messages.append(
            Message(role="tool", content=step.observation.content, tool_call_id=action.call_id)
        )
        if step.done:
            return self.stop(TerminationReason.SUCCESS, "submitted")
        return "model"

    def result(self) -> EpisodeResult:
        """Build the portable outcome; Runner remains the sole final-event owner."""
        return EpisodeResult(
            episode_id=self.recorder.episode_id,
            termination_reason=self.termination_reason,
            detail=self.detail,
            step_count=self.budget.step_count,
            model_call_count=self.budget.model_call_count,
            tool_call_count=self.budget.tool_call_count,
            token_usage=self.budget.total_token_usage(),
            estimated_cost=self.budget.total_estimated_cost(),
            duration_ms=int((perf_counter() - self.started) * 1000),
            final_state=self.last_state,
        )
