"""Unit tests for ToolLabEnvironment."""

from pathlib import Path

from packages.domain.models import TaskSpec, ToolCall
from packages.environments.tool_lab.environment import (
    ToolLabEnvironment,
)

ROOT = Path(__file__).resolve().parents[2]


def load_task() -> TaskSpec:
    """Load sample TaskSpec."""
    return TaskSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json").read_text(encoding="utf-8")
    )


def test_tool_lab_reset_and_observation_privacy() -> None:
    """Reset initializes state; public observation hides private goal
    conditions and unqueried records."""
    task = load_task()
    env = ToolLabEnvironment()
    obs = env.reset(task, seed=42)

    assert "description" in obs.content
    assert obs.content["target_order_id"] == "ORD-001"
    # Private goals & unqueried orders not exposed in observation
    assert "goal_conditions" not in obs.content
    assert "orders" not in obs.content


def test_query_records_and_evidence_tracking() -> None:
    """Query records tool returns records and tracks acquired evidence without marking done."""
    task = load_task()
    env = ToolLabEnvironment()
    env.reset(task, seed=1)

    call = ToolCall(
        call_id="c1",
        name="query_records",
        arguments={"table": "orders", "filters": {"order_id": "ORD-001"}},
    )
    step_res = env.step(call)
    assert not step_res.done
    assert step_res.error is None
    res = step_res.observation.content["result"]
    assert isinstance(res, dict)
    records = res["records"]
    assert isinstance(records, list)
    assert len(records) == 1
    first_record = records[0]
    assert isinstance(first_record, dict)
    assert first_record["status"] == "shipped"
    assert res["acquired_evidence"] == ["order:ORD-001"]


def test_submit_answer_marks_done() -> None:
    """Submit answer tool records submission and sets step done to True."""
    task = load_task()
    env = ToolLabEnvironment()
    env.reset(task, seed=1)

    call = ToolCall(
        call_id="c2",
        name="submit_answer",
        arguments={"answer": "shipped", "evidence": ["order:ORD-001"]},
    )
    step_res = env.step(call)
    assert step_res.done
    assert step_res.error is None
    snap = env.snapshot()
    assert snap["submission"] == {"answer": "shipped", "evidence": ["order:ORD-001"]}


def test_snapshot_and_restore_deep_copy_isolation() -> None:
    """Snapshot and restore maintain deep copy isolation."""
    task = load_task()
    env = ToolLabEnvironment()
    env.reset(task, seed=1)

    # Perform query
    env.step(
        ToolCall(
            call_id="c1",
            name="query_records",
            arguments={"table": "orders", "filters": {"order_id": "ORD-001"}},
        )
    )
    snap = env.snapshot()

    # Mutate environment with submission
    env.step(
        ToolCall(
            call_id="c2",
            name="submit_answer",
            arguments={"answer": "shipped", "evidence": ["order:ORD-001"]},
        )
    )
    assert env.snapshot()["done"] is True

    # Restore snapshot
    env.restore(snap)
    restored_snap = env.snapshot()
    assert restored_snap["done"] is False
    assert restored_snap["acquired_evidence"] == ["order:ORD-001"]
