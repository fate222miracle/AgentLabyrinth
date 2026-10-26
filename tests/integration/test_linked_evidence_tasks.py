"""Linked evidence tasks test real dependencies without changing legacy grading."""

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from pydantic import JsonValue

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.domain.models import ContextPolicy, ModelResponse, TaskSpec, ToolCall
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.environments.tool_lab.mcp import _documents
from packages.providers.fake import FakeModelProvider

ROOT = Path(__file__).resolve().parents[2]
TASKS = sorted((ROOT / "benchmarks/tool_lab_core/tasks/long_chain").glob("*.json"))


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("path", TASKS, ids=lambda p: p.stem)
def test_chain_full_window_and_short_window(tmp_path: Path, backend: str, path: Path) -> None:
    """Full/large windows preserve evidence; a short window cannot fake it."""
    task = TaskSpec.model_validate_json(path.read_text(encoding="utf-8"))
    service = EpisodeService(artifacts_dir=tmp_path)
    for window, expected in ((None, True), (1, False), (5, True), (-1, True)):
        artifact = asyncio.run(
            service.execute_episode(
                CreateEpisodeRequest.model_validate(
                    {
                        "provider": "fake",
                        "model": "fake",
                        "task_id": task.name,
                        "runtime_backend": backend,
                        "context_policy": None
                        if window is None
                        else {
                            "schema_version": "1.1",
                            "algorithm_version": "tool-round-window-memory-v1",
                            "mode": "recent_tool_rounds",
                            "max_tool_rounds": 1,
                            "memory_max_bytes": 8192,
                        }
                        if window == -1
                        else {"mode": "recent_tool_rounds", "max_tool_rounds": window},
                    }
                )
            )
        )
        assert artifact.evaluation.success is expected
        assert artifact.agent.budget.max_model_calls == task.max_steps
        assert artifact.agent.budget.max_prompt_tokens == task.token_budget
        evidence = cast(list[str], task.goal_conditions["evidence"])
        assert artifact.episode.model_call_count == len(evidence) + 2
        assert service.get_episode(artifact.episode.episode_id) == artifact
        if not expected:
            assert artifact.evaluation.reason == "evidence_mismatch"
        assert "goal_conditions" not in str(artifact.events[1].payload)
    env = ToolLabEnvironment(tool_set_version="v1.1.0")
    env.reset(task, 1)
    documents = cast(list[dict[str, str]], task.initial_state["documents"])
    first = documents[0]["document_id"]
    env.step(ToolCall(call_id="first", name="read_document", arguments={"document_id": first}))
    snapshot = env.snapshot()
    restored = ToolLabEnvironment(tool_set_version="v1.1.0")
    restored.reset(task, 1)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
    assert _documents(task.name) == task.initial_state["documents"]


def test_private_goal_cannot_drive_fake_and_forged_evidence_is_rejected(tmp_path: Path) -> None:
    """No hidden goal lookup, and listing unread evidence cannot pass grading."""
    task = TaskSpec.model_validate_json(TASKS[0].read_text(encoding="utf-8"))
    service = EpisodeService(artifacts_dir=tmp_path)
    req = CreateEpisodeRequest(provider="fake", model="fake", task_id=task.name)
    with patch.object(
        service,
        "_get_task",
        return_value=task.model_copy(
            update={"goal_conditions": {**task.goal_conditions, "answer": "hidden-answer"}}
        ),
    ):
        result = asyncio.run(service.execute_episode(req))
    assert not result.evaluation.success
    submission = result.episode.final_state["submission"]
    assert isinstance(submission, dict)
    assert submission["answer"] == task.goal_conditions["answer"]
    documents = cast(list[dict[str, str]], task.initial_state["documents"])
    evidence = cast(list[str], task.goal_conditions["evidence"])
    terminal = next(
        d for d in documents if "Status:" in d["content"] and d["evidence_id"] in evidence
    )
    actions: list[tuple[str, dict[str, JsonValue]]] = [
        ("search_documents", {"query": task.initial_state["document_query"], "top_k": 3}),
        ("read_document", {"document_id": terminal["document_id"]}),
        ("submit_answer", task.goal_conditions),
    ]
    fake = FakeModelProvider(
        custom_responses=[
            ModelResponse(action=ToolCall(call_id=f"forge-{i}", name=name, arguments=args))
            for i, (name, args) in enumerate(actions)
        ]
    )
    with patch("apps.api.service.FakeModelProvider", return_value=fake):
        result = asyncio.run(service.execute_episode(req))
    assert not result.evaluation.success
    assert result.evaluation.reason.startswith("unqueried_or_forged_evidence")
    limited = asyncio.run(service.execute_episode(req.model_copy(update={"max_steps": 2})))
    assert not limited.evaluation.success and limited.episode.step_count == 2


def test_context_plan_and_legacy_catalog_boundary(tmp_path: Path) -> None:
    """Pin equal capacities on both arms; retain the twelve original tasks."""
    service = EpisodeService(artifacts_dir=tmp_path)
    assert len(service._load_all_tasks()) == 21
    assert len(list((ROOT / "benchmarks/tool_lab_core/tasks").glob("*.json"))) == 12
    with pytest.raises(ValueError, match="not found"):
        service._get_task("../long_chain/return-evidence-chain-001.json")
    plan = asyncio.run(
        service.prepare_experiment(
            CreateExperimentRequest(
                provider="fake",
                model="fake",
                scenario="clean",
                task_ids=[TASKS[0].stem],
                comparison_axis="context_policy",
                context_policy=ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=1),
            )
        )
    )
    assert plan.baseline_agent.budget == plan.recovery_agent.budget
    assert plan.baseline_agent.budget.max_model_calls == 10
