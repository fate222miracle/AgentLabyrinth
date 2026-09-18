"""Unit tests for BudgetTracker and budget limit boundaries."""

from decimal import Decimal
from pathlib import Path

from packages.domain.models import Budget, EstimatedCost, TaskSpec, TerminationReason, TokenUsage
from packages.runtime.handwritten.budget import BudgetTracker

ROOT = Path(__file__).resolve().parents[2]


def load_task() -> TaskSpec:
    """Load sample TaskSpec."""
    return TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )


def test_budget_step_and_call_limits() -> None:
    """BudgetTracker correctly identifies step and model call limits."""
    task = load_task().model_copy(update={"max_steps": 2})
    agent_budget = Budget(max_steps=5, max_model_calls=3)
    tracker = BudgetTracker(agent_budget, task)

    assert tracker.max_steps == 2  # min(5, 2)
    can_call, _, _ = tracker.can_call_model()
    assert can_call

    tracker.step_count = 2
    can_call, reason, detail = tracker.can_call_model()
    assert not can_call
    assert reason == TerminationReason.MAX_STEPS


def test_budget_token_and_cost_accrual() -> None:
    """BudgetTracker accurately tracks token and Decimal cost boundaries."""
    task = load_task().model_copy(update={"token_budget": 100})
    agent_budget = Budget(
        max_prompt_tokens=50,
        max_completion_tokens=50,
        max_estimated_cost=Decimal("0.01"),
    )
    tracker = BudgetTracker(agent_budget, task)

    # Within limits
    usage = TokenUsage(prompt_tokens=30, completion_tokens=20)
    cost = EstimatedCost(amount=Decimal("0.005"))
    ok, _, _ = tracker.accrue_usage(usage, cost)
    assert ok

    # Exceed prompt tokens limit (30 + 30 = 60 > 50)
    usage_exceed = TokenUsage(prompt_tokens=30, completion_tokens=10)
    ok_exceed, reason, detail = tracker.accrue_usage(usage_exceed, cost)
    assert not ok_exceed
    assert reason == TerminationReason.TOKEN_BUDGET_EXCEEDED


def test_budget_decimal_cost_precision() -> None:
    """Decimal cost stays exact without floating point rounding errors."""
    task = load_task()
    agent_budget = Budget(max_estimated_cost=Decimal("0.003"))
    tracker = BudgetTracker(agent_budget, task)

    usage = TokenUsage(prompt_tokens=10, completion_tokens=10)
    c1 = EstimatedCost(amount=Decimal("0.001"))
    c2 = EstimatedCost(amount=Decimal("0.002"))
    c3 = EstimatedCost(amount=Decimal("0.0001"))

    tracker.accrue_usage(usage, c1)
    tracker.accrue_usage(usage, c2)
    assert tracker.estimated_cost == Decimal("0.003")

    ok, reason, _ = tracker.accrue_usage(usage, c3)
    assert not ok
    assert reason == TerminationReason.COST_BUDGET_EXCEEDED


def test_budget_real_provider_initial_state() -> None:
    """Real provider BudgetTracker reports simulated=False and is_known=False on zero usage."""
    task = load_task()
    agent_budget = Budget()
    tracker = BudgetTracker(
        agent_budget,
        task,
        is_simulated=False,
        price_table_version="aihubmix-free-unverified",
    )

    # Initial state before any model responses
    token_usage = tracker.total_token_usage()
    assert token_usage.simulated is False
    assert token_usage.prompt_tokens == 0
    assert token_usage.completion_tokens == 0

    cost = tracker.total_estimated_cost()
    assert cost.is_known is False
    assert cost.price_table_version == "aihubmix-free-unverified"
    assert cost.amount == Decimal("0")


def test_budget_unknown_cost_handling() -> None:
    """Unknown cost does not accumulate as verified $0 and marks outcome is_known=False."""
    task = load_task()
    agent_budget = Budget(max_estimated_cost=Decimal("1.00"))
    tracker = BudgetTracker(agent_budget, task, is_simulated=False)

    usage = TokenUsage(prompt_tokens=20, completion_tokens=10, simulated=False)
    unknown_cost = EstimatedCost(
        amount=Decimal("0"),
        currency="USD",
        price_table_version="aihubmix-free-unverified",
        is_known=False,
    )

    ok, reason, detail = tracker.accrue_usage(usage, unknown_cost)
    assert ok
    assert tracker.estimated_cost == Decimal("0")

    final_cost = tracker.total_estimated_cost()
    assert final_cost.is_known is False
    assert final_cost.price_table_version == "aihubmix-free-unverified"
