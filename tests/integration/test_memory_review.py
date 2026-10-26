"""Saved memory evidence can be inspected without running agents or trusting altered inputs."""

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from apps.api.schemas import CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.trace import content_hash, read_artifact
from packages.domain.models import AgentSpec, EventType
from scripts.review_memory import review_memory, successful_document_reads


def saved_pair(directory: Path, **changes: object) -> tuple[UUID, tuple[UUID, UUID]]:
    """Create real saved Fake evidence through the existing formal service."""
    request = CreateExperimentRequest.model_validate(
        {
            "schema_version": "1.6",
            "provider": "fake",
            "model": "fake-model",
            "scenario": "clean",
            "comparison_axis": "memory_ablation",
            "task_ids": ["order-status-007"],
            "context_policy": {
                "schema_version": "1.1",
                "algorithm_version": "tool-round-window-memory-v1",
                "mode": "recent_tool_rounds",
                "max_tool_rounds": 1,
                "memory_max_bytes": 8192,
            },
            **changes,
        }
    )
    result = asyncio.run(EpisodeService(artifacts_dir=directory).execute_experiment(request))
    pair = result.pairs[0]
    return result.experiment_id, (pair.baseline_episode_id, pair.recovery_episode_id)


def snapshot(directory: Path) -> dict[str, str]:
    """Detect writes to any input rather than only to the selected summary."""
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.rglob("*.json")
    }


def test_formal_review_is_offline_read_only_and_links_each_request(tmp_path: Path) -> None:
    inputs, output = tmp_path / "inputs", tmp_path / "review"
    experiment_id, ids = saved_pair(inputs)
    before = snapshot(inputs)
    with (
        patch("socket.socket.connect", side_effect=AssertionError("network")),
        patch(
            "packages.providers.fake.FakeModelProvider.generate", new_callable=AsyncMock
        ) as model,
        patch("packages.environments.tool_lab.environment.ToolLabEnvironment.step") as tool,
    ):
        report = review_memory(inputs, output, experiment_id=experiment_id)
    assert model.call_count == tool.call_count == 0
    assert report["status"] == "reviewed", report
    assert snapshot(inputs) == before
    left, right = report["pairs"][0]
    assert [row["episode_id"] for row in (left, right)] == list(map(str, ids))
    assert not left["success"] and right["success"]
    assert left["repeated_document_reads"] == 1 and right["repeated_document_reads"] == 0
    assert left["usage_complete"] and right["usage_complete"]
    memory_request = next(row for row in right["requests"] if row["memory_sources"])
    assert memory_request["memory_sources"][0]["call_id"] == "call_search_1"
    artifact = read_artifact(inputs / f"{ids[1]}.json")
    event_ids = [str(event.event_id) for event in artifact.events]
    for source in memory_request["memory_sources"]:
        assert event_ids.index(source["return_event_id"]) < event_ids.index(
            memory_request["event_id"]
        )
    assert json.loads((output / "memory-review.json").read_text(encoding="utf-8")) == report
    markdown = (output / "memory-review.md").read_text(encoding="utf-8")
    assert "正式保存的 Experiment" in markdown and "| Step |" in markdown
    assert "未保存逐条跳过来源" in markdown
    with pytest.raises(FileExistsError):
        review_memory(inputs, output, experiment_id=experiment_id)
    assert snapshot(inputs) == before


@pytest.mark.parametrize(
    "damage",
    [
        "hash",
        "identity",
        "budget",
        "schema",
        "future_source",
        "context_count",
        "foreign_event",
        "duplicate_event",
    ],
)
def test_invalid_episode_evidence_is_rejected_without_echoing_input(
    tmp_path: Path, damage: str
) -> None:
    inputs = tmp_path / "inputs"
    _, ids = saved_pair(inputs)
    path = inputs / f"{ids[1]}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if damage == "hash":
        data["config_hashes"]["agent"] = "0" * 64
    elif damage == "identity":
        data["episode"]["episode_id"] = str(uuid4())
    elif damage == "budget":
        data["agent"]["budget"]["max_steps"] += 1
        data["config_hashes"]["agent"] = content_hash(
            AgentSpec.model_validate_json(json.dumps(data["agent"]))
        )
    elif damage == "schema":
        data["agent"]["model"]["temperature"] = "SENSITIVE_TEST_SENTINEL"
    elif damage in ("future_source", "context_count"):
        context = next(
            e["payload"]["context"] for e in data["events"] if e["event_type"] == "MODEL_REQUESTED"
        )
        if damage == "future_source":
            context.update(
                memory_source_call_ids=["call_search_1"], memory_entries_count=1, memory_bytes=100
            )
        else:
            context["visible_messages_count"] = True
    elif damage == "foreign_event":
        data["events"][1]["episode_id"] = str(uuid4())
    else:
        data["events"][1]["event_id"] = data["events"][0]["event_id"]
    data["episode"]["final_state"]["DO_NOT_ECHO"] = "SENSITIVE_TEST_SENTINEL"
    path.write_text(json.dumps(data), encoding="utf-8")
    before = snapshot(inputs)
    report = review_memory(inputs, tmp_path / "review", episode_ids=ids)
    assert report["status"] == "rejected" and report["pairs"] == []
    assert snapshot(inputs) == before
    assert "SENSITIVE_TEST_SENTINEL" not in json.dumps(report)


@pytest.mark.parametrize("missing", ["events", "diagnostics", "response"])
def test_absent_trace_diagnostics_and_unreported_usage_remain_unknown(
    tmp_path: Path, missing: str
) -> None:
    inputs = tmp_path / "inputs"
    _, ids = saved_pair(inputs)
    path = inputs / f"{ids[1]}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if missing == "events":
        data["events"] = []
    elif missing == "diagnostics":
        for event in data["events"]:
            event["payload"].pop("context", None)
    else:
        # A timed-out request legitimately has no response and only previously reported usage.
        events = data["events"]
        response = next(e for e in reversed(events) if e["event_type"] == "MODEL_RESPONDED")
        request_index = max(i for i, e in enumerate(events) if e["event_type"] == "MODEL_REQUESTED")
        data["events"] = events[: request_index + 1] + [events[-1]]
        finish = data["events"][-1]
        finish["parent_event_id"] = events[request_index]["event_id"]
        finish["payload"].update(termination_reason="RUNTIME_ERROR", success=False)
        data["episode"]["termination_reason"] = "RUNTIME_ERROR"
        data["episode"]["tool_call_count"] = 2
        data["evaluation"]["success"] = False
        for key in ("prompt_tokens", "completion_tokens"):
            data["episode"]["token_usage"][key] -= response["token_usage"][key]
        data["episode"]["detail"] = "upstream_usage_unknown"
    path.write_text(json.dumps(data), encoding="utf-8")
    report = review_memory(inputs, tmp_path / "review", episode_ids=ids)
    assert report["status"] == "reviewed", report
    right = report["pairs"][0][1]
    if missing == "events":
        assert right["successful_document_reads"] is None
        assert right["repeated_document_reads"] is None and right["requests"] == []
        assert not right["usage_complete"]
    elif missing == "diagnostics":
        assert all(
            row["context"] is None and row["memory_sources"] is None for row in right["requests"]
        )
    else:
        assert not right["usage_complete"]


@pytest.mark.parametrize("damage", ["pair", "hash", "matrix", "arm"])
def test_formal_summary_cannot_override_its_episode_sources(tmp_path: Path, damage: str) -> None:
    inputs = tmp_path / "inputs"
    experiment_id, _ = saved_pair(inputs)
    path = inputs / "experiments" / f"{experiment_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if damage == "pair":
        data["pairs"][0]["recovery_tokens"] += 1
    elif damage == "hash":
        data["config_hash"] = "0" * 64
    elif damage == "matrix":
        data["pairs"][0]["repeat_index"] += 1
    else:
        data["config"]["baseline_agent"]["version"] = "changed"
        from packages.application.experiment import compute_config_hash

        data["config_hash"] = compute_config_hash(data["config"])
    path.write_text(json.dumps(data), encoding="utf-8")
    report = review_memory(inputs, tmp_path / "review", experiment_id=experiment_id)
    assert report["status"] == "rejected" and report["pairs"] == []


def test_cli_handles_missing_inputs_and_keeps_a_failure_report(tmp_path: Path) -> None:
    output = tmp_path / "review"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.review_memory",
            "--artifacts-dir",
            str(tmp_path / "missing"),
            "--episodes",
            str(uuid4()),
            str(uuid4()),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert (
        json.loads((output / "memory-review.json").read_text(encoding="utf-8"))["status"]
        == "rejected"
    )
    assert (output / "memory-review.md").is_file()


def test_read_counter_never_pairs_a_result_with_a_later_proposal(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    _, ids = saved_pair(inputs)
    artifact = read_artifact(inputs / f"{ids[1]}.json")
    proposed = next(
        e
        for e in artifact.events
        if e.event_type == EventType.TOOL_CALL_PROPOSED and e.payload["name"] == "read_document"
    )
    returned = next(
        e
        for e in artifact.events
        if e.event_type == EventType.TOOL_SUCCEEDED
        and e.payload["call_id"] == proposed.payload["call_id"]
    )
    assert successful_document_reads((returned, proposed)) == []
    empty = returned.model_copy(
        update={
            "payload": {
                "call_id": proposed.payload["call_id"],
                "observation": {"result": {"document": None}},
            }
        }
    )
    assert successful_document_reads((proposed, empty)) == []


def test_old_context_axis_and_capacity_failure_keep_their_actual_outcomes(tmp_path: Path) -> None:
    for label, changes in (
        (
            "context",
            {
                "schema_version": "1.5",
                "comparison_axis": "context_policy",
                "context_policy": {"mode": "recent_tool_rounds", "max_tool_rounds": 1},
            },
        ),
        (
            "tiny",
            {
                "context_policy": {
                    "schema_version": "1.1",
                    "algorithm_version": "tool-round-window-memory-v1",
                    "mode": "recent_tool_rounds",
                    "max_tool_rounds": 1,
                    "memory_max_bytes": 256,
                }
            },
        ),
    ):
        inputs = tmp_path / label
        experiment_id, _ = saved_pair(inputs, **changes)
        report = review_memory(inputs, tmp_path / f"{label}-report", experiment_id=experiment_id)
        assert report["status"] == "reviewed", report
        left, right = report["pairs"][0]
        if label == "context":
            assert left["success"] and not right["success"]
            assert all(r["memory_sources"] is None for r in left["requests"])
        else:
            assert not left["success"] and not right["success"]
            assert any(r["context"]["memory_omitted_entries_count"] > 0 for r in right["requests"])
