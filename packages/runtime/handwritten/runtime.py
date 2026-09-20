"""Handwritten agent control loop implementation."""

from time import perf_counter
from uuid import UUID

from pydantic import JsonValue

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
    AgentRuntime,
    Environment,
    ModelProvider,
    ModelProviderError,
    ToolValidator,
    TraceRecorder,
)
from packages.runtime.handwritten.budget import BudgetTracker
from packages.tools.registry import DefaultToolValidator, ToolRegistry, ValidationResult


class HandwrittenRuntime(AgentRuntime):
    """Deterministically execute an episode using a Handwritten control loop strategy."""

    def __init__(
        self,
        provider: ModelProvider,
        validator: ToolValidator | None = None,
    ) -> None:
        self._provider = provider
        self._validator = validator

    def _inspect_tool_call(
        self,
        action: ToolCall,
        allowed_tools: tuple[str, ...],
        active_validator: ToolValidator | None,
    ) -> ValidationResult:
        """Inspect tool call using active validator."""
        validator = active_validator or self._validator
        if validator is None:
            raise RuntimeError("Tool validator is required")
        if isinstance(validator, DefaultToolValidator):
            return validator.inspect(action, allowed_tools)

        err = validator.validate(action, allowed_tools)
        if err is None:
            return ValidationResult(
                arguments_valid=True, permitted=True, error_code=None, error_info=None
            )

        args_valid = err.code != "INVALID_ARGUMENTS"
        permitted = err.code != "FORBIDDEN_TOOL"
        return ValidationResult(
            arguments_valid=args_valid, permitted=permitted, error_code=err.code, error_info=err
        )

    async def run(
        self, agent: AgentSpec, task: TaskSpec, environment: Environment, recorder: TraceRecorder
    ) -> EpisodeResult:
        """Reset environment, run loop, return outcome; Runner writes final event."""
        start_time = perf_counter()
        seed = recorder.run_config.seed

        is_simulated = agent.model.provider == "fake"
        default_price_table = "fake-zero-v1" if is_simulated else "aihubmix-free-unverified"
        budget = BudgetTracker(
            agent.budget,
            task,
            is_simulated=is_simulated,
            price_table_version=default_price_table,
        )
        seen_call_ids: set[str] = set()
        retried_invalid_arguments: bool = False
        last_state: dict[str, JsonValue] = {}
        events = recorder.events
        parent_event_id: UUID | None = events[-1].event_id if events else None

        def record(
            event_type: EventType,
            step_index: int,
            payload: dict[str, JsonValue],
            *,
            token_usage: TokenUsage | None = None,
            estimated_cost: EstimatedCost | None = None,
        ) -> None:
            """Link each runtime event to the preceding event in this episode."""
            nonlocal parent_event_id
            event = recorder.record(
                event_type,
                step_index,
                payload,
                parent_event_id=parent_event_id,
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )
            parent_event_id = event.event_id

        # Build default validator from environment if not explicitly injected
        env_validator = getattr(environment, "_validator", None)
        env_registry = getattr(environment, "_registry", None)

        if self._validator is not None:
            active_validator = self._validator
        elif isinstance(env_validator, DefaultToolValidator):
            active_validator = env_validator
        elif isinstance(env_registry, ToolRegistry):
            active_validator = DefaultToolValidator(env_registry)
        else:
            active_validator = None

        termination_reason = TerminationReason.FAILED
        detail = "loop_terminated_without_submission"

        try:
            obs = environment.reset(task, seed)
            last_state = environment.snapshot()
            record(
                EventType.OBSERVATION_CREATED,
                0,
                {"observation": obs.content, "initial_state": last_state},
            )
            messages: list[Message] = [
                Message(
                    role="system",
                    content={
                        "task": task.description,
                        "constraints": list(task.constraints),
                        "instruction": (
                            "Use tools and follow their parameter descriptions exactly."
                        ),
                    },
                ),
                Message(role="user", content=obs.content),
            ]
            while True:
                # 1. Pre-call budget check
                can_call, reason, reas_detail = budget.can_call_model()
                if not can_call:
                    termination_reason = reason or TerminationReason.MAX_STEPS
                    detail = reas_detail or "max_steps_exceeded"
                    break

                # 2. Advance step and model call counts
                budget.model_call_count += 1
                budget.step_count += 1
                step_idx = budget.step_count

                # 3. Record MODEL_REQUESTED
                record(
                    EventType.MODEL_REQUESTED,
                    step_idx,
                    {"messages_count": len(messages)},
                )

                # 4. Invoke Provider
                try:
                    response = await self._provider.generate(
                        messages=messages,
                        tools=environment.available_tools(),
                        config=agent.model,
                    )
                except ModelProviderError as exc:
                    termination_reason = TerminationReason.RUNTIME_ERROR
                    detail = f"provider_error: {exc.code}"
                    break
                except Exception:
                    termination_reason = TerminationReason.RUNTIME_ERROR
                    detail = "provider_error"
                    break

                # 5. Accrue usage and check post-call budget
                ok_usage, usage_reason, usage_detail = budget.accrue_usage(
                    response.token_usage, response.estimated_cost
                )

                record(
                    EventType.MODEL_RESPONDED,
                    step_idx,
                    {"action_kind": response.action.kind},
                    token_usage=response.token_usage,
                    estimated_cost=response.estimated_cost,
                )

                if not ok_usage:
                    termination_reason = usage_reason or TerminationReason.TOKEN_BUDGET_EXCEEDED
                    detail = usage_detail or "token_budget_exceeded"
                    break

                # 6. Process action
                action = response.action
                if isinstance(action, FinalAnswer):
                    termination_reason = TerminationReason.FAILED
                    detail = "missing_submission"
                    break

                if isinstance(action, ToolCall):
                    # Propose tool call
                    record(
                        EventType.TOOL_CALL_PROPOSED,
                        step_idx,
                        {
                            "call_id": action.call_id,
                            "name": action.name,
                            "arguments": action.arguments,
                        },
                    )

                    # Allowed tools for validation
                    allowed_tools = tuple(
                        t for t in task.expected_tools if t not in task.forbidden_tools
                    )
                    inspection = self._inspect_tool_call(action, allowed_tools, active_validator)
                    duplicate = action.call_id in seen_call_ids

                    record(
                        EventType.TOOL_CALL_VALIDATED,
                        step_idx,
                        {
                            "call_id": action.call_id,
                            "name": action.name,
                            "arguments_valid": inspection.arguments_valid,
                            "permitted": inspection.permitted,
                            "error_code": "DUPLICATE_CALL_ID"
                            if duplicate
                            else inspection.error_code,
                        },
                    )

                    # Check duplicate call ID
                    if duplicate:
                        termination_reason = TerminationReason.FAILED
                        detail = "duplicate_call_id"
                        break
                    seen_call_ids.add(action.call_id)

                    # Check unknown or forbidden tool first - must terminate immediately
                    # without retry
                    if inspection.error_code == "UNKNOWN_TOOL":
                        termination_reason = TerminationReason.FAILED
                        detail = "unknown_tool"
                        break

                    if not inspection.permitted or inspection.error_code == "FORBIDDEN_TOOL":
                        termination_reason = TerminationReason.FAILED
                        detail = f"forbidden_tool: {action.name}"
                        break

                    # Check argument validity (only for permitted tools)
                    if not inspection.arguments_valid:
                        # Recovery strategy: allow at most one controlled retry
                        # for INVALID_ARGUMENTS
                        if (
                            agent.runtime_strategy == "handwritten_recovery"
                            and inspection.error_code == "INVALID_ARGUMENTS"
                            and not retried_invalid_arguments
                        ):
                            retried_invalid_arguments = True
                            available = environment.available_tools()
                            tool_schema = next(
                                (t for t in available if t.name == action.name), None
                            )
                            expected_params: dict[str, JsonValue] = (
                                tool_schema.parameters if tool_schema else {}
                            )
                            feedback: dict[str, JsonValue] = {
                                "error": "INVALID_ARGUMENTS",
                                "message": (
                                    f"Parameter validation failed for tool '{action.name}'. "
                                    f"Parameters must conform to schema."
                                ),
                                "tool": action.name,
                                "parameters_schema": expected_params,
                            }
                            messages.append(Message(role="assistant", tool_calls=(action,)))
                            messages.append(
                                Message(role="tool", content=feedback, tool_call_id=action.call_id)
                            )
                            # Re-prompt model; tool call count is not incremented
                            # because tool execution was rejected before start
                            continue

                        termination_reason = TerminationReason.FAILED
                        detail = f"invalid_arguments: {inspection.error_code}"
                        break

                    # Check tool budget
                    can_tool, t_reason, t_detail = budget.can_start_tool()
                    if not can_tool:
                        termination_reason = t_reason or TerminationReason.MAX_STEPS
                        detail = t_detail or "max_tool_calls_exceeded"
                        break

                    # Start tool execution
                    budget.tool_call_count += 1
                    record(
                        EventType.TOOL_STARTED,
                        step_idx,
                        {"call_id": action.call_id, "name": action.name},
                    )

                    try:
                        step_res = environment.step(action)
                    except Exception:
                        record(
                            EventType.TOOL_FAILED,
                            step_idx,
                            {"call_id": action.call_id, "error_code": "ENVIRONMENT_ERROR"},
                        )
                        termination_reason = TerminationReason.RUNTIME_ERROR
                        detail = "environment_error"
                        break
                    last_state = environment.snapshot()

                    if step_res.error is not None:
                        record(
                            EventType.TOOL_FAILED,
                            step_idx,
                            {
                                "call_id": action.call_id,
                                "error": step_res.error.model_dump(),
                            },
                        )
                        termination_reason = TerminationReason.FAILED
                        detail = f"tool_failed: {step_res.error.code}"
                        break
                    else:
                        record(
                            EventType.TOOL_SUCCEEDED,
                            step_idx,
                            {
                                "call_id": action.call_id,
                                "observation": step_res.observation.content,
                            },
                        )
                        record(
                            EventType.ENVIRONMENT_UPDATED,
                            step_idx,
                            {"done": step_res.done},
                        )
                        messages.append(
                            Message(
                                role="assistant",
                                content=None,
                                tool_calls=(action,),
                            )
                        )
                        messages.append(
                            Message(
                                role="tool",
                                content=step_res.observation.content,
                                tool_call_id=action.call_id,
                            )
                        )

                        if step_res.done:
                            termination_reason = TerminationReason.SUCCESS
                            detail = "submitted"
                            break
        except Exception:
            termination_reason = TerminationReason.RUNTIME_ERROR
            detail = "unhandled_runtime_error"

        duration_ms = int((perf_counter() - start_time) * 1000)

        return EpisodeResult(
            episode_id=recorder.episode_id,
            termination_reason=termination_reason,
            detail=detail,
            step_count=budget.step_count,
            model_call_count=budget.model_call_count,
            tool_call_count=budget.tool_call_count,
            token_usage=budget.total_token_usage(),
            estimated_cost=budget.total_estimated_cost(),
            duration_ms=duration_ms,
            final_state=last_state,
        )
