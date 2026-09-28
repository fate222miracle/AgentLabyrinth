"""Fault profiles are explicit, reproducible, and excluded from real-model runs."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.service import EpisodeService


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Isolate every injected run from the user's saved experiments."""
    app.dependency_overrides[get_episode_service] = lambda: EpisodeService(artifacts_dir=tmp_path)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("profile", "task_id", "transport", "expected_code"),
    [
        ("tool_timeout", "order-status-001", "local", "TOOL_TIMEOUT"),
        ("empty_result", "order-status-001", "local", None),
        ("mcp_disconnect", "order-status-007", "mcp", "TOOL_EXECUTION_ERROR"),
    ],
)
def test_fault_episode_trace(
    client: TestClient, profile: str, task_id: str, transport: str, expected_code: str | None
) -> None:
    """An injected failure stays in Task provenance and observable Trace."""
    response = client.post(
        "/api/v1/episodes",
        json={
            "provider": "fake",
            "model": "fake-model",
            "scenario": "success",
            "task_id": task_id,
            "tool_transport": transport,
            "fault_profile": profile,
        },
    )
    assert response.status_code == 201, response.text
    artifact = response.json()["artifact"]
    assert artifact["task"]["evaluator_config"]["fault_profile"] == profile
    assert artifact["evaluation"]["success"] is False
    events = artifact["events"]
    assert events[-1]["event_type"] == "EPISODE_FINISHED"
    if expected_code:
        failures = [e for e in events if e["event_type"] == "TOOL_FAILED"]
        assert len(failures) == 1
        assert failures[0]["payload"]["error"]["code"] == expected_code
    else:
        assert artifact["episode"]["final_state"]["acquired_evidence"] == []


def test_fault_experiment_keeps_both_arms_comparable(client: TestClient) -> None:
    """Both paired arms receive the same injected task variant."""
    response = client.post(
        "/api/v1/experiments",
        json={
            "provider": "fake",
            "model": "fake-model",
            "scenario": "success",
            "task_ids": ["order-status-001"],
            "fault_profile": "tool_timeout",
        },
    )
    assert response.status_code == 201, response.text
    experiment = response.json()["experiment"]
    assert experiment["config"]["fault_profile"] == "tool_timeout"
    assert experiment["metrics"]["baseline_success_count"] == 0
    assert experiment["metrics"]["recovery_success_count"] == 0


def test_fault_rejected_for_real_model(client: TestClient) -> None:
    """Fault runs cannot silently pollute a real-model score."""
    response = client.post(
        "/api/v1/episodes",
        json={
            "provider": "aihubmix",
            "model": "coding-minimax-m2.7-free",
            "fault_profile": "tool_timeout",
        },
    )
    assert response.status_code == 400
