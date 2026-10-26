"""Framework-independent episode operations shared by both runtime schedulers."""

import asyncio
import json
from collections.abc import Callable
from time import perf_counter
from typing import Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from packages.domain.models import (
    AgentSpec,
    ContextPolicy,
    EpisodeResult,
    EstimatedCost,
    EventType,
    FinalAnswer,
    Message,
    PlanItem,
    TaskSpec,
    TerminationReason,
    TokenUsage,
    ToolCall,
    ToolCallBatch,
    ToolSchema,
    validate_plan,
)
from packages.domain.ports import (
    Environment,
    ModelProvider,
    ModelProviderError,
    ToolValidator,
    TraceRecorder,
)
from packages.runtime.context import ContextHistoryError, _json_bytes, project_context
from packages.runtime.handwritten.budget import BudgetState, BudgetTracker
from packages.tools.registry import DefaultToolValidator, ToolRegistry, ValidationResult

NextNode = Literal["model", "validate", "execute", "end"]

PLANNING_TOOL = "update_plan"


class SessionState(BaseModel):
    """Portable state saved only at a model boundary or after termination."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: Literal["1.0", "1.1", "1.2"] = "1.0"
    next_node: Literal["model", "execute", "end"]
    pending_calls: tuple[ToolCall, ...] = ()
    messages: tuple[Message, ...]
    seen_call_ids: tuple[str, ...]
    retried: bool
    budget: BudgetState
    last_state: dict[str, JsonValue]
    termination_reason: TerminationReason
    detail: str
    elapsed_ms: int = Field(ge=0)
    plan: tuple[PlanItem, ...] = ()

    @model_validator(mode="after")
    def validate_pending(self) -> "SessionState":
        """Bind batch and plan revisions to their additive safe points."""
        if (self.pending_calls or self.next_node == "execute") and self.schema_version not in (
            "1.1",
            "1.2",
        ):
            raise ValueError("Pending batch requires SessionState schema 1.1")
        if self.plan and self.schema_version != "1.2":
            raise ValueError("Saved plan requires SessionState schema 1.2")
        if self.plan:
            validate_plan(self.plan)
        if self.next_node == "execute" and not self.pending_calls:
            raise ValueError("Execute checkpoint requires pending calls")
        if self.next_node == "model" and self.pending_calls:
            raise ValueError("Incomplete batch cannot call model")
        return self

    @model_serializer(mode="wrap")
    def serialize_state(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        """Keep original single-action and batch safe points unchanged."""
        result: dict[str, object] = handler(self)
        if self.schema_version == "1.0":
            result.pop("pending_calls", None)
        if not self.plan:
            result.pop("plan", None)
        return result


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
        self.plan: tuple[PlanItem, ...] = ()
        self.planning_enabled = agent.planning is not None
        self.action: ToolCall | None = None
        self.batch_calls: tuple[ToolCall, ...] = ()
        self.pending_calls: list[ToolCall] = []
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
        if save is None or (
            next_node not in ("model", "end")
            and not (next_node == "execute" and self.pending_calls)
        ):
            return
        state = SessionState(
            schema_version="1.2" if self.plan else "1.1" if self.pending_calls else "1.0",
            next_node=next_node,
            pending_calls=tuple(self.pending_calls),
            messages=tuple(self.messages),
            seen_call_ids=tuple(sorted(self.seen_call_ids)),
            retried=self.retried,
            budget=self.budget.snapshot(),
            last_state=self.last_state,
            termination_reason=self.termination_reason,
            detail=self.detail,
            elapsed_ms=int((perf_counter() - self.started) * 1000),
            plan=self.plan,
        )
        try:
            save(state)
        except Exception as exc:
            raise CheckpointFailure("Could not persist episode checkpoint") from exc

    def restore(self, state: SessionState) -> NextNode:
        """Restore the environment and counters before scheduling any new action."""
        if state.plan and not self.planning_enabled:
            raise ValueError("Saved plan requires a planning agent")
        self._restore_plan(state)
        self.environment.reset(self.task, self.recorder.run_config.seed)
        self.environment.restore(state.last_state)
        if self.environment.snapshot() != state.last_state:
            raise ValueError("Environment checkpoint mismatch")
        self.budget.restore(state.budget)
        self.messages = list(state.messages)
        self.plan = tuple(state.plan)
        self.seen_call_ids = set(state.seen_call_ids)
        if len(self.seen_call_ids) != len(state.seen_call_ids):
            raise ValueError("Duplicate tool call ID in checkpoint")
        self.retried = state.retried
        self.pending_calls = list(state.pending_calls)
        if self.pending_calls and state.next_node == "execute":
            self._restore_batch(state)
        self.last_state = state.last_state
        self.termination_reason = state.termination_reason
        self.detail = state.detail
        self.started = perf_counter() - state.elapsed_ms / 1000
        events = self.recorder.events
        self.parent_event_id = events[-1].event_id if events else None
        return state.next_node

    def _restore_plan(self, state: SessionState) -> None:
        """Bind persisted declarations to earlier validated, successful tool feedback."""
        latest: tuple[PlanItem, ...] = ()
        proposals: dict[str, ToolCall] = {}
        started: set[str] = set()
        succeeded: dict[str, tuple[PlanItem, ...]] = {}
        applied: set[str] = set()
        for event in self.recorder.events:
            call_id = str(event.payload.get("call_id", ""))
            if event.event_type == EventType.TOOL_CALL_PROPOSED:
                if event.payload.get("name") == PLANNING_TOOL:
                    arguments = event.payload.get("arguments")
                    if not isinstance(arguments, dict):
                        raise ValueError("Saved plan arguments are malformed")
                    proposals[call_id] = ToolCall(
                        call_id=call_id,
                        name=PLANNING_TOOL,
                        arguments=arguments,
                    )
            elif event.event_type == EventType.TOOL_STARTED and call_id in proposals:
                started.add(call_id)
            elif event.event_type == EventType.TOOL_SUCCEEDED and call_id in proposals:
                call = proposals[call_id]
                if (
                    not self.planning_enabled
                    or call_id not in started
                    or self._inspect(call).error_code
                ):
                    raise ValueError("Saved plan lacks a permitted source")
                raw = call.arguments.get("plan")
                if not isinstance(raw, list):
                    raise ValueError("Saved plan source is malformed")
                items = validate_plan(tuple(PlanItem.model_validate(entry) for entry in raw))
                observation = event.payload.get("observation")
                result = observation.get("result") if isinstance(observation, dict) else None
                if not isinstance(result, dict) or result.get("items") != [
                    i.model_dump(mode="json") for i in items
                ]:
                    raise ValueError("Saved plan feedback mismatch")
                if not any(
                    m.role == "tool" and m.tool_call_id == call_id and m.content == observation
                    for m in state.messages
                ):
                    raise ValueError("Saved plan conversation mismatch")
                if not any(
                    call in (m.tool_calls or ()) for m in state.messages if m.role == "assistant"
                ):
                    raise ValueError("Saved plan proposal mismatch")
                succeeded[call_id] = items
            elif event.event_type == EventType.PLAN_UPDATED:
                if call_id not in succeeded or call_id in applied:
                    raise ValueError("Saved plan update lacks a successful source")
                latest = succeeded[call_id]
                if event.payload.get("items") != [i.model_dump(mode="json") for i in latest]:
                    raise ValueError("Saved plan event mismatch")
                applied.add(call_id)
        if applied != set(succeeded) or state.plan != latest:
            raise ValueError("Saved plan does not match recorded declarations")

    def _restore_batch(self, state: SessionState) -> None:
        """Bind pending work to the unmatched saved round before any tool can run."""
        if self.agent.model.tool_call_mode != "serial":
            raise ValueError("Pending batch requires saved serial mode")
        start = max((i for i, m in enumerate(self.messages) if m.role == "assistant"), default=-1)
        if start < 0:
            raise ValueError("Missing pending batch source")
        project_context(self.messages[:start], self.agent.context_policy or ContextPolicy())
        source = self.messages[start]
        feedback = self.messages[start + 1 :]
        calls = source.tool_calls or ()
        if (
            not 2 <= len(calls) <= 8
            or tuple(c.call_id for c in calls[: len(feedback)])
            != tuple(m.tool_call_id for m in feedback)
            or any(m.role != "tool" for m in feedback)
            or tuple(self.pending_calls) != calls[len(feedback) :]
            or any(c.call_id not in self.seen_call_ids for c in calls)
            or len({c.call_id for c in calls}) != len(calls)
        ):
            raise ValueError("Pending batch conversation mismatch")
        executed = {
            e.payload.get("call_id")
            for e in self.recorder.events
            if e.event_type == EventType.TOOL_STARTED
        }
        proposals = {
            e.payload.get("call_id"): e.payload
            for e in self.recorder.events
            if e.event_type == EventType.TOOL_CALL_PROPOSED
        }
        returns = {
            e.payload.get("call_id"): e.payload.get("observation")
            for e in self.recorder.events
            if e.event_type == EventType.TOOL_SUCCEEDED
        }
        if (
            sum(e.event_type == EventType.TOOL_STARTED for e in self.recorder.events)
            != state.budget.tool_call_count
            or any(
                proposals.get(call.call_id, {}).get("name") != call.name
                or proposals.get(call.call_id, {}).get("arguments") != call.arguments
                for call in calls
            )
            or any(returns.get(m.tool_call_id) != m.content for m in feedback)
        ):
            raise ValueError("Pending batch Trace mismatch")
        schemas = {t.name: t for t in self._available_tools()}
        for call in self.pending_calls:
            if (
                call.call_id in executed
                or self._inspect(call).error_code is not None
                or call.name not in schemas
                or schemas[call.name].risk_level != "READ_ONLY"
            ):
                raise ValueError("Unsafe pending batch")
        self.batch_calls = calls
        self.action = self.pending_calls[0]

    def stop(self, reason: TerminationReason, detail: str) -> NextNode:
        """Retain usage and the last valid environment state on every stop."""
        self.termination_reason, self.detail = reason, detail
        return "end"

    def remaining_seconds(self) -> float | None:
        """Return remaining active time, including time inherited from a safe point."""
        limit = self.agent.budget.max_execution_time_ms
        return None if limit is None else limit / 1000 - (perf_counter() - self.started)

    def time_exceeded(self) -> bool:
        """Check total time without altering counters or the environment."""
        remaining = self.remaining_seconds()
        return remaining is not None and remaining <= 0

    def stop_for_time(self, *, usage_unknown: bool = False) -> NextNode:
        """Identify a deadline stop and distinguish an unaccounted upstream request."""
        detail = "max_execution_time_exceeded"
        if usage_unknown:
            detail += ": upstream_usage_unknown"
            # Preserve reported tokens, but never imply a known total invoice.
            self.budget.mark_unknown_cost()
        return self.stop(TerminationReason.TIME_BUDGET_EXCEEDED, detail)

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
        if self.time_exceeded():
            return self.stop_for_time()
        allowed, reason, detail = self.budget.can_call_model()
        if not allowed:
            return self.stop(reason or TerminationReason.MAX_STEPS, detail or "max_steps_exceeded")
        payload: dict[str, JsonValue] = {"messages_count": len(self.messages)}
        if self.agent.context_policy is not None:
            try:
                projection = project_context(self.messages, self.agent.context_policy)
            except ContextHistoryError:
                return self.stop(TerminationReason.RUNTIME_ERROR, "invalid_context_history")
            model_messages = projection.messages
            payload = {"messages_count": len(model_messages), "context": projection.diagnostics}
        else:
            model_messages = [message.model_copy(deep=True) for message in self.messages]
        if self.planning_enabled and self.plan:
            # A declared plan is a claim; only real tool results count toward completion.
            overlay: dict[str, JsonValue] = {
                "_agentlabyrinth_plan": {
                    "schema_version": "1.0",
                    "notice": "Your declared plan; a claim, not verified execution.",
                    "items": [item.model_dump(mode="json") for item in self.plan],
                }
            }
            model_messages = [*model_messages, Message(role="user", content=overlay)]
        if self.planning_enabled:
            source = next(
                (
                    e
                    for e in reversed(self.recorder.events)
                    if e.event_type == EventType.PLAN_UPDATED
                ),
                None,
            )
            payload["messages_count"] = len(model_messages)
            payload["planning"] = {
                "schema_version": "1.0",
                "algorithm_version": "plan-update-v1",
                "declaration_event_id": str(source.event_id) if source else None,
                "items_count": len(self.plan),
                "overlay_bytes": len(json.dumps(overlay, ensure_ascii=False).encode("utf-8"))
                if self.plan
                else 0,
            }
            diagnostics = payload.get("context")
            if isinstance(diagnostics, dict):
                diagnostics["planning_overlay_messages_count"] = int(bool(self.plan))
                diagnostics["visible_messages_count"] = len(model_messages)
                diagnostics["input_messages_bytes"] = _json_bytes(
                    [m.model_dump(mode="json") for m in model_messages]
                )
        if self.time_exceeded():
            return self.stop_for_time()
        self.budget.model_call_count += 1
        self.budget.step_count += 1
        self.record(EventType.MODEL_REQUESTED, payload)
        deadline = asyncio.timeout(self.remaining_seconds())
        try:
            async with deadline:
                response = await self.provider.generate(
                    model_messages, self._available_tools(), self.agent.model
                )
        except TimeoutError:
            if not deadline.expired():
                return self.stop(TerminationReason.RUNTIME_ERROR, "provider_error")
            return self.stop_for_time(usage_unknown=True)
        except ModelProviderError as exc:
            if exc.token_usage is not None:
                cost = EstimatedCost(is_known=False, price_table_version="aihubmix-free-unverified")
                self.budget.accrue_usage(exc.token_usage, cost)
                self.record(
                    EventType.MODEL_RESPONDED,
                    {"action_kind": "rejected", "error_code": exc.code},
                    token_usage=exc.token_usage,
                    estimated_cost=cost,
                )
            if self.time_exceeded():
                return self.stop_for_time(usage_unknown=True)
            return self.stop(TerminationReason.RUNTIME_ERROR, f"provider_error: {exc.code}")
        except Exception:
            return self.stop(TerminationReason.RUNTIME_ERROR, "provider_error")

        allowed, reason, detail = self.budget.accrue_usage(
            response.token_usage, response.estimated_cost
        )
        self.record(
            EventType.MODEL_RESPONDED,
            {
                "action_kind": response.action.kind,
                **(
                    {"tool_calls_count": len(response.action.calls), "execution": "serial"}
                    if isinstance(response.action, ToolCallBatch)
                    else {}
                ),
            },
            token_usage=response.token_usage,
            estimated_cost=response.estimated_cost,
        )
        if self.time_exceeded():
            return self.stop_for_time()
        if not allowed:
            return self.stop(
                reason or TerminationReason.TOKEN_BUDGET_EXCEEDED, detail or "token_budget_exceeded"
            )
        if isinstance(response.action, FinalAnswer):
            return self.stop(TerminationReason.FAILED, "missing_submission")
        if isinstance(response.action, ToolCallBatch):
            if self.agent.model.tool_call_mode != "serial":
                return self.stop(
                    TerminationReason.RUNTIME_ERROR, "provider_error: MULTIPLE_TOOL_CALLS"
                )
            self.batch_calls = response.action.calls
            return "validate"
        self.action = response.action
        return "validate"

    def _available_tools(self) -> list[ToolSchema]:
        """Expose the plan-declaration tool only to planning agents."""
        tools = self.environment.available_tools()
        if self.planning_enabled:
            return tools
        return [tool for tool in tools if tool.name != PLANNING_TOOL]

    def available_tools(self) -> list[ToolSchema]:
        """Expose the tools a model step may call so adapters mirror, never filter, this set."""
        return self._available_tools()

    def _allowed_tools(self) -> tuple[str, ...]:
        """Mirror the exposed set; the plan tool is a component, never a task requirement."""
        allowed = tuple(t for t in self.task.expected_tools if t not in self.task.forbidden_tools)
        if PLANNING_TOOL in self.task.forbidden_tools or not self.planning_enabled:
            return tuple(name for name in allowed if name != PLANNING_TOOL)
        return allowed if PLANNING_TOOL in allowed else (*allowed, PLANNING_TOOL)

    def _inspect(self, action: ToolCall) -> ValidationResult:
        allowed = self._allowed_tools()
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
        if self.time_exceeded():
            return self.stop_for_time()
        if self.batch_calls:
            return self._validate_batch()
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
                schema = next((t for t in self._available_tools() if t.name == action.name), None)
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

    def _validate_batch(self) -> NextNode:
        """Inspect the complete read batch before any tool starts."""
        schemas = {tool.name: tool for tool in self._available_tools()}
        ids: set[str] = set()
        invalid: list[ToolCall] = []
        fatal: str | None = None
        for index, call in enumerate(self.batch_calls):
            self.record(
                EventType.TOOL_CALL_PROPOSED,
                {
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments": call.arguments,
                    "batch_id": self.batch_calls[0].call_id,
                    "batch_index": index + 1,
                    "batch_size": len(self.batch_calls),
                },
            )
            check = self._inspect(call)
            duplicate = call.call_id in ids or call.call_id in self.seen_call_ids
            ids.add(call.call_id)
            schema = schemas.get(call.name)
            code = "DUPLICATE_CALL_ID" if duplicate else check.error_code
            if code is None and (not check.arguments_valid or not check.permitted):
                code = "TOOL_VALIDATION_FAILED"
            if (
                code in (None, "INVALID_ARGUMENTS")
                and schema is not None
                and schema.risk_level != "READ_ONLY"
            ):
                code = "BATCH_REQUIRES_READ_ONLY"
            self.record(
                EventType.TOOL_CALL_VALIDATED,
                {
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments_valid": check.arguments_valid,
                    "permitted": check.permitted,
                    "error_code": code,
                },
            )
            if code == "INVALID_ARGUMENTS":
                invalid.append(call)
            elif code is not None:
                fatal = fatal or code
        self.seen_call_ids.update(ids)
        if fatal:
            return self.stop(TerminationReason.FAILED, f"batch_rejected: {fatal}")
        if invalid:
            if self.agent.recovery_policy != "invalid_arguments_once" or self.retried:
                return self.stop(TerminationReason.FAILED, "invalid_arguments: INVALID_ARGUMENTS")
            self.retried = True
            self.messages.append(Message(role="assistant", tool_calls=self.batch_calls))
            for call in self.batch_calls:
                self.messages.append(
                    Message(
                        role="tool",
                        tool_call_id=call.call_id,
                        content={
                            "error": "INVALID_ARGUMENTS" if call in invalid else "BATCH_CANCELLED",
                            "message": "No tools executed. Correct calls and use new call IDs.",
                            "parameters_schema": schemas[call.name].parameters,
                        },
                    )
                )
            self.batch_calls = ()
            return "model"
        if self.budget.tool_call_count + len(self.batch_calls) > self.budget.max_tool_calls:
            return self.stop(TerminationReason.MAX_STEPS, "max_tool_calls_reached")
        self.pending_calls = list(self.batch_calls)
        self.action = self.pending_calls[0]
        self.messages.append(Message(role="assistant", tool_calls=self.batch_calls))
        return "execute"

    async def execute(self) -> NextNode:
        """Run one validated tool through Environment/Executor, then append its feedback."""
        if self.time_exceeded():
            return self.stop_for_time()
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
        if self.planning_enabled and action.name == PLANNING_TOOL:
            started_payload["transport"] = "local"
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
            if self.time_exceeded():
                return self.stop_for_time()
            return self.stop(TerminationReason.RUNTIME_ERROR, "environment_error")
        if step.error is not None:
            self.record(
                EventType.TOOL_FAILED,
                {"call_id": action.call_id, "error": step.error.model_dump()},
            )
            if self.time_exceeded():
                return self.stop_for_time()
            return self.stop(TerminationReason.FAILED, f"tool_failed: {step.error.code}")
        self.record(
            EventType.TOOL_SUCCEEDED,
            {"call_id": action.call_id, "observation": step.observation.content},
        )
        self.record(
            EventType.ENVIRONMENT_UPDATED,
            {
                "done": step.done,
                "state": self.last_state,
                **({"call_id": action.call_id} if self.pending_calls else {}),
            },
        )
        if self.planning_enabled and action.name == PLANNING_TOOL:
            raw = action.arguments.get("plan")
            items = (
                tuple(PlanItem.model_validate(entry) for entry in raw)
                if isinstance(raw, list)
                else ()
            )
            self.plan = items
            self.record(
                EventType.PLAN_UPDATED,
                {"call_id": action.call_id, "items": [i.model_dump(mode="json") for i in items]},
            )
        if not self.pending_calls:
            self.messages.append(Message(role="assistant", content=None, tool_calls=(action,)))
        self.messages.append(
            Message(role="tool", content=step.observation.content, tool_call_id=action.call_id)
        )
        if self.pending_calls:
            self.pending_calls.pop(0)
            self.action = self.pending_calls[0] if self.pending_calls else None
            if not self.pending_calls:
                self.batch_calls = ()
        if self.time_exceeded():
            return self.stop_for_time()
        if step.done:
            return self.stop(TerminationReason.SUCCESS, "submitted")
        return "execute" if self.pending_calls else "model"

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
