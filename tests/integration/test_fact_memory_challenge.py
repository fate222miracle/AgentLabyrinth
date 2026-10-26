"""Public facts, bounded memory and saved provenance drive the three new tasks."""

import asyncio
import json
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from pydantic import JsonValue

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import EventType, ModelResponse, RunConfig, TaskSpec, ToolCall
from packages.environments.tool_lab import mcp
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime
from packages.runtime.session import SessionState
from scripts.review_memory import review_memory
from scripts.run_regression import preflight

ROOT = Path(__file__).resolve().parents[2]
FILES = sorted((ROOT / "benchmarks/tool_lab_core/tasks/memory_challenge").glob("*.json"))
MEMORY = {
    "schema_version": "1.1",
    "algorithm_version": "tool-round-window-memory-v1",
    "mode": "recent_tool_rounds",
    "max_tool_rounds": 1,
    "memory_max_bytes": 8192,
}


def pair_request(task: str, **changes: object) -> CreateExperimentRequest:
    """Use the public formal same-window request, not two unrelated episodes."""
    return CreateExperimentRequest.model_validate(
        dict(
            schema_version="1.6",
            provider="fake",
            model="fake",
            scenario="clean",
            task_ids=[task],
            comparison_axis="memory_ablation",
            context_policy=MEMORY,
        )
        | changes
    )


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("path", FILES, ids=lambda path: path.stem)
@pytest.mark.parametrize("mode", ["full", "window", "memory", "tiny", "wide"])
def test_fact_policies(tmp_path: Path, path: Path, backend: str, mode: str) -> None:
    """Whole-return omission can cause legitimate rereads, without forcing failure."""
    policy = {
        "full": None,
        "window": {"mode": "recent_tool_rounds", "max_tool_rounds": 1},
        "memory": MEMORY,
        "tiny": {**MEMORY, "memory_max_bytes": 256},
        "wide": {"mode": "recent_tool_rounds", "max_tool_rounds": 3},
    }[mode]
    result = asyncio.run(
        EpisodeService(artifacts_dir=tmp_path).execute_episode(
            CreateEpisodeRequest.model_validate(
                dict(
                    provider="fake",
                    model="fake",
                    task_id=path.stem,
                    runtime_backend=backend,
                    context_policy=policy,
                )
            )
        )
    )
    assert result.evaluation.success is (mode in {"full", "memory", "wide"})
    assert result.agent.tool_set_version == "v1.4.0"
    assert result.agent.budget.max_model_calls == 10
    assert result.agent.budget.max_prompt_tokens == 20000
    assert "goal_conditions" not in str(result.events[1].payload)
    if result.evaluation.success:
        assert result.episode.final_state["submission"] == result.task.goal_conditions
    else:
        assert result.episode.termination_reason.value == "MAX_STEPS"
        assert not result.episode.final_state.get("submission")
    if path.stem == "memory-large-return-002" and mode == "memory":
        contexts = [
            e.payload["context"] for e in result.events if e.event_type == EventType.MODEL_REQUESTED
        ]
        assert any(
            isinstance(c, dict)
            and isinstance(c.get("memory_omitted_entries_count"), int)
            and cast(int, c["memory_omitted_entries_count"]) > 0
            for c in contexts
        )
        assert result.episode.tool_call_count > 5


@pytest.mark.parametrize("change", ["quantity", "revision", "rename", "private_goal"])
def test_visible_facts_drive_answers(tmp_path: Path, change: str) -> None:
    """Different public facts change actions; private goals never enter the Fake input."""
    raw = json.loads(FILES[2].read_text(encoding="utf-8"))
    expected = "ineligible"
    if change == "quantity":
        raw["initial_state"]["documents"][0]["content"] = raw["initial_state"]["documents"][0][
            "content"
        ].replace("received_units=26", "received_units=30")
        expected = "eligible"
        raw["goal_conditions"]["answer"] = expected
    elif change == "revision":
        raw["initial_state"]["documents"][0]["content"] = raw["initial_state"]["documents"][0][
            "content"
        ].replace("policy_revision=2026-B", "policy_revision=2026-A")
        expected = "eligible"
        raw["goal_conditions"]["answer"] = expected
        raw["goal_conditions"]["evidence"] = sorted(
            e.replace("POLICY-B", "POLICY-A") for e in raw["goal_conditions"]["evidence"]
        )
    elif change == "rename":
        text = json.dumps(raw).replace("memory-policy-version-003", "different-task")
        for before, after in (
            ("INTAKE", "REGISTER-X"),
            ("INSPECTION", "CHECK-X"),
            ("POLICY-A", "OLD-X"),
            ("POLICY-B", "CURRENT-X"),
        ):
            text = text.replace(before, after)
        raw = json.loads(text)
    else:
        raw["goal_conditions"]["answer"] = "eligible"
    task = TaskSpec.model_validate_json(json.dumps(raw))
    service = EpisodeService(artifacts_dir=tmp_path)
    with patch.object(service, "_get_task", return_value=task):
        result = asyncio.run(
            service.execute_episode(
                CreateEpisodeRequest(provider="fake", model="fake", task_id=task.name)
            )
        )
    submitted = result.episode.final_state["submission"]
    assert isinstance(submitted, dict) and submitted["answer"] == expected
    assert result.evaluation.success is (change != "private_goal")


@pytest.mark.parametrize("damage", ["conflict", "negative", "excess", "unknown_rule"])
def test_invalid_facts_never_default_to_an_answer(tmp_path: Path, damage: str) -> None:
    """Malformed facts cannot masquerade as an ineligible calculation."""
    raw = json.loads(FILES[0].read_text(encoding="utf-8"))
    replacement = {
        "conflict": "Fact: received_units=26\nFact: received_units=30",
        "negative": "Fact: received_units=-2",
        "excess": "Fact: received_units=1000001",
        "unknown_rule": "Fact: received_units=26\nRule: unsupported-v9",
    }[damage]
    raw["initial_state"]["documents"][0]["content"] = raw["initial_state"]["documents"][0][
        "content"
    ].replace("Fact: received_units=26", replacement)
    task = TaskSpec.model_validate_json(json.dumps(raw))
    service = EpisodeService(artifacts_dir=tmp_path)
    with patch.object(service, "_get_task", return_value=task):
        result = asyncio.run(
            service.execute_episode(
                CreateEpisodeRequest(provider="fake", model="fake", task_id=task.name)
            )
        )
    assert not result.evaluation.success
    assert not result.episode.final_state.get("submission")


@pytest.mark.parametrize(
    "submission", ["correct", "wrong", "missing", "extra", "duplicate", "unread"]
)
def test_only_actual_complete_current_evidence_passes(tmp_path: Path, submission: str) -> None:
    """Reading an old policy is allowed, but submitting it as current evidence is rejected."""
    task = TaskSpec.model_validate_json(FILES[2].read_text(encoding="utf-8"))
    goal = json.loads(json.dumps(task.goal_conditions))
    actions = [("search_documents", {"query": "CASE-710 intake", "top_k": 3})] + [
        ("read_document", {"document_id": doc})
        for doc in ("INTAKE", "POLICY-A", "INSPECTION", "POLICY-B")
    ]
    if submission == "wrong":
        goal["answer"] = "eligible"
    elif submission == "missing":
        goal["evidence"].pop()
    elif submission == "extra":
        goal["evidence"].append("document:POLICY-A")
    elif submission == "duplicate":
        goal["evidence"].append(goal["evidence"][0])
    elif submission == "unread":
        actions = actions[:1]
    actions.append(("submit_answer", goal))
    fake = FakeModelProvider(
        custom_responses=[
            ModelResponse(
                action=ToolCall(
                    call_id=f"read-{i}", name=name, arguments=cast(dict[str, JsonValue], args)
                )
            )
            for i, (name, args) in enumerate(actions)
        ]
    )
    with patch("apps.api.service.FakeModelProvider", return_value=fake):
        result = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path).execute_episode(
                CreateEpisodeRequest(provider="fake", model="fake", task_id=task.name)
            )
        )
    assert result.evaluation.success is (submission == "correct")


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("transport", ["local", "mcp"])
def test_saved_memory_resumes_with_derived_tool_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str, transport: str
) -> None:
    """Resume a committed read without upgrading the saved task or losing its memory."""
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task("memory-fact-reuse-001")
    plan = asyncio.run(service.prepare_experiment(pair_request(task.name, runtime_backend=backend)))
    agent = plan.recovery_agent
    config = RunConfig(
        environment_version=("tool-lab-mcp-v1" if transport == "mcp" else "tool-lab-m0-v1")
    )
    if transport == "mcp":

        def remote(name: str, args: dict[str, object], url: str) -> dict[str, JsonValue]:
            if name == "search_documents":
                return mcp.search_documents(
                    str(args["task_name"]), str(args["query"]), int(str(args["top_k"]))
                )
            return mcp.read_document(str(args["task_name"]), str(args["document_id"]))

        monkeypatch.setattr(mcp, "_call_sync", remote)
    env = (
        mcp.MCPToolLabEnvironment(tool_set_version="v1.4.0")
        if transport == "mcp"
        else ToolLabEnvironment(tool_set_version="v1.4.0")
    )
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(tmp_path / "checkpoints")

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.next_node == "model" and state.budget.tool_call_count == 3:
            raise SystemExit(0)

    with pytest.raises(SystemExit):
        asyncio.run(
            run_episode(
                agent,
                task,
                config,
                create_runtime(agent, FakeModelProvider()),
                env,
                OrderStatusEvaluator(),
                recorder=recorder,
                save_checkpoint=save,
            )
        )
    result = asyncio.run(EpisodeService(artifacts_dir=tmp_path).resume_episode(recorder.episode_id))
    assert result.evaluation.success
    assert result.episode.tool_call_count == 5
    assert result.task == task and result.agent == agent
    assert result.agent.tool_set_version == "v1.4.0"
    assert sum(e.event_type == EventType.EPISODE_RESUMED for e in result.events) == 1


def test_formal_pair_regression_and_offline_review(tmp_path: Path) -> None:
    """New tasks use existing plans, grading, exportable results and read-only diagnostics."""
    request = pair_request("memory-fact-reuse-001")
    service = EpisodeService(artifacts_dir=tmp_path / "inputs")
    result = asyncio.run(service.execute_experiment(request))
    preflight(result, request, service)
    assert result.metrics.baseline_success_count == 0
    assert result.metrics.recovery_success_count == 1
    assert result.metrics.retry_recovery_rate is None
    report = review_memory(
        tmp_path / "inputs", tmp_path / "review", experiment_id=result.experiment_id
    )
    assert report["status"] == "reviewed"
    assert report["pairs"][0][1]["repeated_document_reads"] == 0


@pytest.mark.parametrize("failure", ["unknown", "forbidden", "invalid_twice", "duplicate"])
def test_rule_task_does_not_relax_runtime_failures(tmp_path: Path, failure: str) -> None:
    """Even recovery allows only one parameter repair; other violations stop immediately."""
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task("memory-fact-reuse-001")
    name, args = "search_documents", {"query": "CASE-710 intake", "top_k": 3}
    if failure == "unknown":
        name = "invented_tool"
    elif failure == "forbidden":
        task = task.model_copy(update={"forbidden_tools": ("search_documents",)})
    elif failure == "invalid_twice":
        args = {"query": "CASE-710 intake", "top_k": 0}
    calls = [
        ModelResponse(
            action=ToolCall(
                call_id=f"boundary-{i}", name=name, arguments=cast(dict[str, JsonValue], args)
            )
        )
        for i in (0, 0 if failure == "duplicate" else 1)
    ]
    fake = FakeModelProvider(custom_responses=calls)
    with (
        patch.object(service, "_get_task", return_value=task),
        patch("apps.api.service.FakeModelProvider", return_value=fake),
    ):
        result = asyncio.run(
            service.execute_episode(
                CreateEpisodeRequest(
                    provider="fake",
                    model="fake",
                    task_id=task.name,
                    runtime_strategy="handwritten_recovery",
                )
            )
        )
    assert not result.evaluation.success
    assert result.episode.model_call_count == (
        2 if failure in {"invalid_twice", "duplicate"} else 1
    )
    assert not result.episode.final_state.get("submission")
    assert result.episode.tool_call_count == (1 if failure == "duplicate" else 0)


def test_derived_description_does_not_change_old_tools(tmp_path: Path) -> None:
    """Only the new pinned profile permits a derived conclusion in its schema text."""
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task("memory-fact-reuse-001")
    schemas = {}
    for version in ("v1.3.0", "v1.4.0"):
        env = ToolLabEnvironment(tool_set_version=version)
        env.reset(task, 1)
        schemas[version] = {tool.name: tool for tool in env.available_tools()}
    assert schemas["v1.3.0"]["read_document"] == schemas["v1.4.0"]["read_document"]
    assert schemas["v1.3.0"]["submit_answer"].version == "1.1.0"
    assert schemas["v1.4.0"]["submit_answer"].version == "1.2.0"
    assert "derived" in schemas["v1.4.0"]["submit_answer"].description
    assert "derived" not in schemas["v1.3.0"]["submit_answer"].description
    assert service._task_tool_version([service._get_task("return-evidence-chain-001")]) == "v1.3.0"
    assert service._task_tool_version([task, service._get_task("order-status-001")]) == "v1.4.0"
