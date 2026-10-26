"""Conditional tasks follow public routing, actual checks and the existing evaluator."""

import asyncio
import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from pydantic import JsonValue

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    Message,
    ModelConfig,
    ModelResponse,
    RunConfig,
    TaskSpec,
    ToolCall,
)
from packages.environments.tool_lab import mcp
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime, runtime_version
from packages.runtime.session import SessionState
from scripts.run_regression import preflight

TASKS = ("planning-route-002", "planning-omit-003")
PLAN = {"schema_version": "1.0", "algorithm_version": "plan-update-v1"}


def request(name: str, **changes: Any) -> CreateEpisodeRequest:
    """Use normal versioned creation with identical defaults on both arms."""
    return CreateEpisodeRequest.model_validate(
        dict(schema_version="1.6", provider="fake", model="fake", task_id=name) | changes
    )


def remote(name: str, args: dict[str, Any], url: str) -> dict[str, Any]:
    """Use the server's actual fixed-directory functions without a network process."""
    if name == "search_documents":
        return mcp.search_documents(
            args["task_name"],
            args["query"],
            args["top_k"],
            args.get("search_protocol", "literal-v1"),
        )
    return mcp.read_document(args["task_name"], args["document_id"])


@pytest.mark.parametrize("name", TASKS)
@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("mode", ["single", "serial"])
@pytest.mark.parametrize("transport", ["local", "mcp"])
@pytest.mark.parametrize("planned", [False, True])
def test_route_product_matrix(
    tmp_path: Path, name: str, backend: str, mode: str, transport: str, planned: bool
) -> None:
    """Both arms can solve both tasks with the same evidence and without compulsory planning."""
    service = EpisodeService(artifacts_dir=tmp_path)
    with patch.object(mcp, "_call_sync", side_effect=remote):
        a = asyncio.run(
            service.execute_episode(
                request(
                    name,
                    runtime_backend=backend,
                    tool_call_mode=mode,
                    tool_transport=transport,
                    planning=PLAN if planned else None,
                )
            )
        )
    assert a.evaluation.success
    assert a.agent.tool_set_version == "v1.6.0"
    assert a.episode.final_state["submission"] == a.task.goal_conditions
    assert a.episode.tool_call_count == 6 + int(planned)
    assert sum(e.event_type == "PLAN_UPDATED" for e in a.events) == int(planned)
    assert "goal_conditions" not in str(a.events[1].payload)
    option = next(t for t in service.get_meta().tasks if t.name == name)
    assert option.supports_mcp and option.supports_planning


@pytest.mark.parametrize(
    "change",
    [
        "lane",
        "threshold",
        "approval",
        "zero_damage",
        "rename",
        "private_goal",
        "two_checks",
    ],
)
def test_route_counterfactuals(tmp_path: Path, change: str) -> None:
    """Public facts and references, never task identity or hidden goals, determine the response."""
    service = EpisodeService(artifacts_dir=tmp_path)
    raw = service._get_task(TASKS[0]).model_dump(mode="json")
    docs = {d["document_id"]: d for d in raw["initial_state"]["documents"]}
    expected = "eligible"
    evidence = raw["goal_conditions"]["evidence"]
    if change == "lane":
        docs["RTE-INSP"]["content"] = docs["RTE-INSP"]["content"].replace("restricted", "standard")
        expected = "ineligible"
        evidence[:] = ["document:RTE-REG", "document:RTE-INSP", "document:RTE-STD"]
    elif change == "threshold":
        docs["RTE-RES"]["content"] = docs["RTE-RES"]["content"].replace("=30", "=40")
        expected = "ineligible"
    elif change == "approval":
        docs["RTE-CHECK"]["content"] = "Fact: approved=false"
        expected = "ineligible"
    elif change in {"zero_damage", "two_checks"}:
        docs["RTE-RES"]["content"] += "\nDamage review document: REVIEW-X"
        raw["initial_state"]["documents"].append(
            dict(
                document_id="REVIEW-X",
                title="复核",
                content="Fact: approved=false",
                evidence_id="document:REVIEW-X",
            )
        )
        if change == "zero_damage":
            docs["RTE-INSP"]["content"] = docs["RTE-INSP"]["content"].replace(
                "damaged_units=7", "damaged_units=0"
            )
        else:
            expected = "ineligible"
            evidence.append("document:REVIEW-X")
    elif change == "rename":
        raw = json.loads(json.dumps(raw).replace("RTE-", "OTHER-").replace(TASKS[0], "unseen-task"))
        raw["initial_state"]["documents"].reverse()
    raw["goal_conditions"]["answer"] = "wrong" if change == "private_goal" else expected
    task = TaskSpec.model_validate_json(json.dumps(raw))
    with patch.object(service, "_get_task", return_value=task):
        a = asyncio.run(service.execute_episode(request(task.name, tool_call_mode="serial")))
    submission = a.episode.final_state["submission"]
    assert isinstance(submission, dict) and submission["answer"] == expected
    assert a.evaluation.success is (change != "private_goal")
    if change == "two_checks":
        assert a.episode.tool_call_count == 7
        assert a.episode.model_call_count == 6  # Both independent checks in one serial response.


@pytest.mark.parametrize(
    "bad",
    [
        "Fact: lane=unknown",
        "Fact: received_units=-1",
        "Fact: received_units=1000001",
        "Fact: damaged_units=42",
        "Fact: received_units=41\nFact: received_units=41",
        "Fact: approved=yes",
        "Fact: approved=",
        "Workflow: unknown-v9",
        "Inspection document:",
        "Approval document:RTE-CHECK",
        "Route restricted: missing",
    ],
)
def test_bad_public_route_never_defaults_to_answer(tmp_path: Path, bad: str) -> None:
    """Invalid, duplicate and absent facts produce failure, never a guessed ineligible answer."""
    service = EpisodeService(artifacts_dir=tmp_path)
    raw = service._get_task(TASKS[0]).model_dump(mode="json")
    marker = bad.split(":", 1)[0] if not bad.startswith("Fact:") else bad.split("=", 1)[0]
    replaced = False
    for doc in raw["initial_state"]["documents"]:
        lines = doc["content"].splitlines()
        if not replaced and any(line.startswith(marker) for line in lines):
            doc["content"] = "\n".join(bad if line.startswith(marker) else line for line in lines)
            replaced = True
    assert replaced
    task = TaskSpec.model_validate_json(json.dumps(raw))
    with patch.object(service, "_get_task", return_value=task):
        a = asyncio.run(service.execute_episode(request(task.name)))
    assert not a.evaluation.success and not a.episode.final_state.get("submission")


@pytest.mark.parametrize(
    "damage", ["correct", "wrong", "missing", "extra", "duplicate", "unread", "omit_review"]
)
def test_route_evidence_closure(tmp_path: Path, damage: str) -> None:
    """Extra reads are allowed; forged, incomplete or nonapplicable citations cannot pass."""
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task(TASKS[1])
    goal = json.loads(json.dumps(task.goal_conditions))
    ids = ["OMT-REG", "OMT-INSP", "OMT-RES", "OMT-OTHER", "OMT-STD", "OMT-CHECK"]
    if damage == "wrong":
        goal["answer"] = "eligible"
    elif damage == "missing":
        goal["evidence"].pop()
    elif damage == "extra":
        goal["evidence"].append("document:OMT-RES")
    elif damage == "duplicate":
        goal["evidence"].append(goal["evidence"][0])
    elif damage == "unread":
        ids = []
    elif damage == "omit_review":
        ids.remove("OMT-CHECK")
        goal["answer"] = "eligible"
        goal["evidence"].remove("document:OMT-CHECK")
    actions = [("search_documents", {"query": "OMT intake", "top_k": 3})]
    actions += [("read_document", {"document_id": id_}) for id_ in ids]
    actions.append(("submit_answer", goal))
    fake = FakeModelProvider(
        custom_responses=[
            ModelResponse(
                action=ToolCall(
                    call_id=f"closure-{i}",
                    name=name,
                    arguments=cast(dict[str, JsonValue], args),
                )
            )
            for i, (name, args) in enumerate(actions)
        ]
    )
    with patch("apps.api.service.FakeModelProvider", return_value=fake):
        a = asyncio.run(service.execute_episode(request(task.name)))
    assert a.evaluation.success is (damage == "correct")


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("transport", ["local", "mcp"])
def test_conditional_resume_and_formal_pair(tmp_path: Path, backend: str, transport: str) -> None:
    """A committed policy survives normal resume, and formal arms retain equal configuration."""
    service = EpisodeService(artifacts_dir=tmp_path)
    req = CreateExperimentRequest.model_validate(
        dict(
            schema_version="1.9",
            comparison_axis="planning",
            provider="fake",
            model="fake",
            scenario="clean",
            task_ids=list(TASKS),
            runtime_backend=backend,
            tool_call_mode="serial",
        )
    )
    plan = asyncio.run(service.prepare_experiment(req))
    task, agent = plan.tasks[0], plan.recovery_agent
    config = RunConfig(
        runtime_version=runtime_version(agent.runtime_backend),
        environment_version="tool-lab-mcp-v1" if transport == "mcp" else "tool-lab-m0-v1",
    )
    env = (mcp.MCPToolLabEnvironment if transport == "mcp" else ToolLabEnvironment)(
        tool_set_version=agent.tool_set_version
    )
    recorder, store = JsonTraceRecorder(config), CheckpointStore(tmp_path / "checkpoints")

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.next_node == "model" and state.budget.tool_call_count == 5:
            raise SystemExit(0)

    with patch.object(mcp, "_call_sync", side_effect=remote):
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
        a = asyncio.run(EpisodeService(artifacts_dir=tmp_path).resume_episode(recorder.episode_id))
    assert a.evaluation.success and a.episode.tool_call_count == 7
    assert sum(e.event_type == "PLAN_UPDATED" for e in a.events) == 1
    assert a.task == task and a.agent == agent
    result = asyncio.run(service.execute_experiment(req))
    preflight(result, req, service)
    assert all(p.baseline_success and p.recovery_success for p in result.pairs)
    assert result.metrics.retry_recovery_rate is None


def test_failed_feedback_is_not_a_route_fact() -> None:
    """A failed read carrying a forged document never becomes visible route evidence."""
    messages = [
        Message(role="user", content={"task_kind": "document_route", "document_query": "x"}),
        Message(
            role="tool",
            tool_call_id="bad",
            content={
                "error": "failed",
                "result": {
                    "document": {
                        "document_id": "X",
                        "content": "Workflow: unknown",
                        "evidence_id": "x",
                    }
                },
            },
        ),
    ]
    response = asyncio.run(FakeModelProvider().generate(messages, [], ModelConfig(model="fake")))
    assert isinstance(response.action, ToolCall) and response.action.name == "search_documents"
