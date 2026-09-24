"""Resource budget tracking and hard-limit enforcement."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.domain.models import Budget, EstimatedCost, TaskSpec, TerminationReason, TokenUsage


class BudgetState(BaseModel):
    """Versioned counters needed to continue the same resource budget."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    step_count: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    estimated_cost: Decimal = Field(ge=0)
    is_simulated: bool
    any_simulated: bool
    has_usage: bool
    has_unknown_cost: bool
    price_table_version: str


class BudgetTracker:
    """Track resource consumption and enforce step, call, token, and cost limits."""

    def __init__(
        self,
        agent_budget: Budget,
        task: TaskSpec,
        is_simulated: bool = True,
        price_table_version: str = "fake-zero-v1",
    ) -> None:
        self.max_steps = min(agent_budget.max_steps, task.max_steps)
        self.max_model_calls = agent_budget.max_model_calls
        self.max_tool_calls = agent_budget.max_tool_calls
        self.max_prompt_tokens = agent_budget.max_prompt_tokens
        self.max_completion_tokens = agent_budget.max_completion_tokens
        self.task_token_budget = task.token_budget
        self.max_estimated_cost = agent_budget.max_estimated_cost

        self.step_count = 0
        self.model_call_count = 0
        self.tool_call_count = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.estimated_cost = Decimal("0")
        self._is_simulated = is_simulated
        self._any_simulated = False
        self._has_usage = False
        self._has_unknown_cost = not is_simulated
        self._price_table_version = price_table_version

    def snapshot(self) -> BudgetState:
        """Freeze consumption without persisting limits already bound to Agent/Task."""
        return BudgetState(
            step_count=self.step_count,
            model_call_count=self.model_call_count,
            tool_call_count=self.tool_call_count,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            estimated_cost=self.estimated_cost,
            is_simulated=self._is_simulated,
            any_simulated=self._any_simulated,
            has_usage=self._has_usage,
            has_unknown_cost=self._has_unknown_cost,
            price_table_version=self._price_table_version,
        )

    def restore(self, state: BudgetState) -> None:
        """Restore counters only when their provenance matches this agent and task."""
        if state.schema_version != "1.0" or state.is_simulated != self._is_simulated:
            raise ValueError("Incompatible budget checkpoint")
        if state.model_call_count > state.step_count or state.tool_call_count > self.max_tool_calls:
            raise ValueError("Invalid budget counters in checkpoint")
        self.step_count = state.step_count
        self.model_call_count = state.model_call_count
        self.tool_call_count = state.tool_call_count
        self.prompt_tokens = state.prompt_tokens
        self.completion_tokens = state.completion_tokens
        self.estimated_cost = state.estimated_cost
        self._any_simulated = state.any_simulated
        self._has_usage = state.has_usage
        self._has_unknown_cost = state.has_unknown_cost
        self._price_table_version = state.price_table_version

    def can_call_model(self) -> tuple[bool, TerminationReason | None, str | None]:
        """Check pre-model-call limits for step and model call counts."""
        if self.step_count >= self.max_steps:
            return False, TerminationReason.MAX_STEPS, "max_steps_reached"
        if self.model_call_count >= self.max_model_calls:
            return False, TerminationReason.MAX_STEPS, "max_model_calls_reached"
        return True, None, None

    def accrue_usage(
        self, usage: TokenUsage, cost: EstimatedCost
    ) -> tuple[bool, TerminationReason | None, str | None]:
        """Accrue tokens and cost, checking post-model-call budget boundaries."""
        self._has_usage = True
        if usage.simulated:
            self._any_simulated = True
        self._price_table_version = cost.price_table_version

        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens

        # Check token boundaries first
        if self.prompt_tokens > self.max_prompt_tokens:
            return (
                False,
                TerminationReason.TOKEN_BUDGET_EXCEEDED,
                "agent_max_prompt_tokens_exceeded",
            )
        if self.completion_tokens > self.max_completion_tokens:
            return (
                False,
                TerminationReason.TOKEN_BUDGET_EXCEEDED,
                "agent_max_completion_tokens_exceeded",
            )
        if (self.prompt_tokens + self.completion_tokens) > self.task_token_budget:
            return (
                False,
                TerminationReason.TOKEN_BUDGET_EXCEEDED,
                "task_token_budget_exceeded",
            )

        # Cost tracking and boundary check:
        # Unknown fees are explicitly not treated as verified $0
        if cost.is_known:
            self.estimated_cost += cost.amount
            if self.estimated_cost > self.max_estimated_cost:
                return (
                    False,
                    TerminationReason.COST_BUDGET_EXCEEDED,
                    "agent_max_estimated_cost_exceeded",
                )
        else:
            self._has_unknown_cost = True

        return True, None, None

    def can_start_tool(self) -> tuple[bool, TerminationReason | None, str | None]:
        """Check pre-tool-execution call limits."""
        if self.tool_call_count >= self.max_tool_calls:
            return False, TerminationReason.MAX_STEPS, "max_tool_calls_reached"
        return True, None, None

    def total_token_usage(self) -> TokenUsage:
        """Return total aggregated token usage model."""
        simulated = self._any_simulated if self._has_usage else self._is_simulated
        return TokenUsage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            simulated=simulated,
        )

    def total_estimated_cost(self) -> EstimatedCost:
        """Return total aggregated cost model."""
        return EstimatedCost(
            amount=self.estimated_cost,
            currency="USD",
            price_table_version=self._price_table_version,
            estimated=True,
            is_known=not self._has_unknown_cost,
        )
