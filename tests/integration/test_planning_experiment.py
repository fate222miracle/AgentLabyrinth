"""Planning challenge uses the formal matrix, a declared plan and recovery boundaries."""

import asyncio
import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.experiment import (
    ExperimentArtifact,
    ExperimentTokenBudgetError,
    compute_config_hash,
    create_experiment_plan,
    read_experiment_checkpoint,
    run_experiment,
)
from packages.application.regression import fixed_config
from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    ContextPolicy,
    FinalAnswer,
    ModelResponse,
    RunConfig,
    ToolCall,
    ToolCallBatch,
)
from packages.environments.tool_lab import mcp
from packages.environments.tool_lab.environment import ToolLabEnvironment, UpdatePlanArgs
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime, runtime_version
from packages.runtime.session import SessionState
from scripts.run_regression import preflight

PLANNING_TASK = "planning-branch-001"
FIXED_VARIABLE_KEYS = ("model", "prompt_version", "tool_set_version", "budget")


@pytest.mark.parametrize("twice", [False, True])
def test_invalid_plan_batch_repairs_once_and_done_is_not_submission(
    tmp_path: Path, twice: bool
) -> None:
    """A malformed declaration cancels its sibling; claiming done never passes scoring."""
    bad = ToolCall(
        call_id="bad",
        name="update_plan",
        arguments={"plan": [{"id": "x", "goal": "x", "depends_on": ["x"]}]},
    )
    sibling = ToolCall(
        call_id="cancelled",
        name="search_documents",
        arguments={"query": "PLN-900 intake", "top_k": 3},
    )
    corrected = ToolCall(
        call_id="repair",
        name="update_plan",
        arguments={"plan": [{"id": "done", "goal": "Declare completion", "status": "done"}]},
    )
    responses = [
        ModelResponse(schema_version="1.1", action=ToolCallBatch(calls=(bad, sibling))),
        ModelResponse(
            action=bad.model_copy(update={"call_id": "bad_again"}) if twice else corrected
        ),
        ModelResponse(action=FinalAnswer(text="Finished")),
    ]
    with patch(
        "apps.api.service.FakeModelProvider",
        return_value=FakeModelProvider(custom_responses=responses),
    ):
        a = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path).execute_episode(
                CreateEpisodeRequest(
                    schema_version="1.6",
                    provider="fake",
                    model="fake",
                    task_id=PLANNING_TASK,
                    planning={"schema_version": "1.0", "algorithm_version": "plan-update-v1"},
                    tool_call_mode="serial",
                    runtime_strategy="handwritten_recovery",
                )
            )
        )
    assert not a.evaluation.success and not a.episode.final_state.get("submission")
    assert a.episode.tool_call_count == (0 if twice else 1)
    assert a.episode.model_call_count == (2 if twice else 3)
    assert not any(
        e.payload.get("call_id") == "cancelled" for e in a.events if e.event_type == "TOOL_STARTED"
    )
    assert sum(e.event_type == "PLAN_UPDATED" for e in a.events) == (0 if twice else 1)


def test_plan_graph_and_saved_result_reject_invalid_claims(tmp_path: Path) -> None:
    """Malformed plans and rehashed results cannot invent the planning component."""
    for items in (
        [],
        [{"id": " ", "goal": "x"}],
        [{"id": "a", "goal": " "}],
        [{"id": "a", "goal": "x", "depends_on": ["unknown"]}],
        [{"id": "a", "goal": "x", "depends_on": ["a"]}],
        [{"id": "a", "goal": "x"}] * 2,
        [
            {"id": "a", "goal": "x", "depends_on": ["b"]},
            {"id": "b", "goal": "y", "depends_on": ["a"]},
        ],
        [{"id": str(i), "goal": "x"} for i in range(9)],
    ):
        with pytest.raises(ValidationError):
            UpdatePlanArgs.model_validate({"plan": items})
    result = asyncio.run(EpisodeService(artifacts_dir=tmp_path).execute_experiment(request()))
    for damage in ("missing", "wrong_algorithm", "left_enabled", "unknown_runtime"):
        data = result.model_dump(mode="json")
        if damage == "missing":
            data["config"]["recovery_agent"].pop("planning")
        elif damage == "wrong_algorithm":
            data["config"]["recovery_agent"]["planning"]["algorithm_version"] = "invented"
        elif damage == "left_enabled":
            data["config"]["baseline_agent"]["planning"] = data["config"]["recovery_agent"][
                "planning"
            ]
        else:
            for arm in ("baseline_agent", "recovery_agent"):
                data["config"][arm]["runtime_version"] = ""
        data["config_hash"] = compute_config_hash(data["config"])
        with pytest.raises(ValidationError):
            ExperimentArtifact.model_validate(data)


@pytest.mark.parametrize(
    "backend,transport,mode",
    [
        ("handwritten", "local", "single"),
        ("langgraph", "local", "serial"),
        ("handwritten", "mcp", "serial"),
        ("langgraph", "mcp", "single"),
    ],
)
def test_plan_resume_requires_real_sources_and_preserves_pending_batch(
    tmp_path: Path, backend: str, transport: str, mode: str
) -> None:
    """Reject plan tampering before model calls and resume each committed declaration once."""
    service = EpisodeService(artifacts_dir=tmp_path)
    plan = asyncio.run(
        service.prepare_experiment(request(runtime_backend=backend, tool_call_mode=mode))
    )
    agent, task = plan.recovery_agent, plan.tasks[0]
    config = RunConfig(
        runtime_version=runtime_version(agent.runtime_backend),
        environment_version="tool-lab-mcp-v1" if transport == "mcp" else "tool-lab-m0-v1",
    )
    env = (
        mcp.MCPToolLabEnvironment(tool_set_version=agent.tool_set_version)
        if transport == "mcp"
        else ToolLabEnvironment(tool_set_version=agent.tool_set_version)
    )
    recorder, store = JsonTraceRecorder(config), CheckpointStore(tmp_path / "checkpoints")
    declare = ToolCall(
        call_id="declare",
        name="update_plan",
        arguments={
            "plan": [
                {"id": "facts", "goal": "Collect public facts"},
                {"id": "submit", "goal": "Derive and submit", "depends_on": ["facts"]},
            ]
        },
    )
    search = ToolCall(
        call_id="search", name="search_documents", arguments={"query": "PLN-900 intake", "top_k": 3}
    )
    response = (
        ModelResponse(schema_version="1.1", action=ToolCallBatch(calls=(declare, search)))
        if mode == "serial"
        else ModelResponse(action=declare)
    )

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.plan:
            raise SystemExit(0)

    def remote(name: str, args: dict[str, Any], url: str) -> dict[str, Any]:
        if name == "search_documents":
            return mcp.search_documents(
                args["task_name"],
                args["query"],
                args["top_k"],
                args.get("search_protocol", "literal-v1"),
            )
        return mcp.read_document(args["task_name"], args["document_id"])

    with patch.object(mcp, "_call_sync", side_effect=remote):
        with pytest.raises(SystemExit):
            asyncio.run(
                run_episode(
                    agent,
                    task,
                    config,
                    create_runtime(agent, FakeModelProvider(custom_responses=[response])),
                    env,
                    OrderStatusEvaluator(),
                    recorder=recorder,
                    save_checkpoint=save,
                )
            )
        original = store.path(recorder.episode_id).read_bytes()
        for damage in ("replace", "erase", "event", "feedback", "missing_event"):
            data = json.loads(original)
            if damage == "replace":
                data["session"]["plan"][0]["goal"] = "Unrecorded goal"
            elif damage == "erase":
                data["session"]["plan"] = []
            elif damage == "event":
                next(e for e in data["events"] if e["event_type"] == "PLAN_UPDATED")["payload"][
                    "items"
                ][0]["goal"] = "Future claim"
            elif damage == "feedback":
                next(m for m in data["session"]["messages"] if m["role"] == "tool")["content"] = {}
            else:
                data["events"] = [e for e in data["events"] if e["event_type"] != "PLAN_UPDATED"]
            store.path(recorder.episode_id).write_text(json.dumps(data), encoding="utf-8")
            with patch.object(
                FakeModelProvider,
                "generate",
                side_effect=AssertionError("No model call before validation"),
            ):
                with pytest.raises(ValueError):
                    asyncio.run(
                        EpisodeService(artifacts_dir=tmp_path)._resume_episode_once(
                            recorder.episode_id
                        )
                    )
        store.path(recorder.episode_id).write_bytes(original)
        resumed = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path)._resume_episode_once(recorder.episode_id)
        )
    assert resumed.evaluation.success
    assert sum(e.event_type == "PLAN_UPDATED" for e in resumed.events) == 1
    assert resumed.episode.tool_call_count == 6
    requests = [e for e in resumed.events if e.event_type == "MODEL_REQUESTED"]
    diagnostics = requests[-1].payload["planning"]
    assert isinstance(diagnostics, dict) and diagnostics["items_count"] == 2
    assert diagnostics["declaration_event_id"] is not None


def test_planning_disabled_and_mixed_profile_regressions(tmp_path: Path) -> None:
    """No declaration requirement on baseline, no hidden plan completion or safety metrics."""
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task(PLANNING_TASK)
    assert "请先用 update_plan" not in task.description
    task = task.model_copy(update={"forbidden_tools": ("update_plan",)})
    response = ModelResponse(
        action=ToolCall(
            call_id="forbidden",
            name="update_plan",
            arguments={"plan": [{"id": "x", "goal": "Done", "status": "done"}]},
        )
    )
    with (
        patch.object(service, "_get_task", return_value=task),
        patch(
            "apps.api.service.FakeModelProvider",
            return_value=FakeModelProvider(custom_responses=[response]),
        ),
    ):
        artifact = asyncio.run(
            service.execute_episode(
                CreateEpisodeRequest(
                    schema_version="1.6",
                    provider="fake",
                    model="fake",
                    task_id=task.name,
                    planning={"schema_version": "1.0", "algorithm_version": "plan-update-v1"},
                )
            )
        )
    assert not artifact.evaluation.success
    assert artifact.evaluation.metrics["forbidden_tool_call_count"] == 1
    mixed = CreateExperimentRequest.model_validate(
        dict(
            schema_version="1.8",
            provider="fake",
            model="fake",
            scenario="clean",
            tool_call_mode="serial",
            comparison_axis="runtime_backend",
            task_ids=[PLANNING_TASK, "memory-fact-reuse-001"],
        )
    )
    result = asyncio.run(service.execute_experiment(mixed))
    preflight(result, mixed, service)


def request(**changes: object) -> CreateExperimentRequest:
    """Build a small, fixed planning comparison without credentials."""
    return CreateExperimentRequest.model_validate(
        {
            "provider": "fake",
            "model": "fake-model",
            "scenario": "success",
            "task_ids": [PLANNING_TASK],
            "comparison_axis": "planning",
            "schema_version": "1.9",
            **changes,
        }
    )


def plan_events(service: EpisodeService, episode_id: UUID) -> int:
    """Count recorded plan declarations in a saved episode."""
    artifact = service.get_episode(episode_id)
    assert artifact is not None
    return sum(event.event_type == "PLAN_UPDATED" for event in artifact.events)


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_planning_matrix_outcome_and_saved_provenance(tmp_path: Path, backend: str) -> None:
    """Only the plan component changes; both fixed arms still reach the recorded answer."""
    service = EpisodeService(artifacts_dir=tmp_path)
    req = request(runtime_backend=backend)
    result = asyncio.run(service.execute_experiment(req))
    assert result.schema_version == "1.6"
    assert result.config["comparison_axis"] == "planning"
    assert result.config["arm_labels"] == {
        "baseline": "No Planning",
        "recovery": "Declared Plan",
    }
    pair = result.pairs[0]
    assert pair.baseline_success and pair.recovery_success
    assert pair.baseline_termination_reason == "SUCCESS"
    assert pair.recovery_termination_reason == "SUCCESS"
    assert pair.retry_eligible is None and pair.recovered is False
    # The component plan call must not inflate the arm's tool metrics beyond a rate of one.
    assert pair.baseline_tool_selection_accuracy == 1.0
    assert pair.recovery_tool_selection_accuracy == 1.0
    assert pair.baseline_tool_argument_validity_rate == 1.0
    assert pair.recovery_tool_argument_validity_rate == 1.0
    assert result.metrics.retry_eligible_count is None
    assert result.metrics.retry_recovery_count is None
    assert result.metrics.retry_recovery_rate is None
    preflight(result, req, service)
    fingerprint = fixed_config(result)
    assert fingerprint["baseline_agent"]["context_policy"] == ContextPolicy(mode="full").model_dump(
        mode="json"
    )
    assert (
        fingerprint["recovery_agent"]["context_policy"]
        == (fingerprint["baseline_agent"]["context_policy"])
    )
    assert "planning" not in fingerprint["baseline_agent"]
    # The planning component is the axis variable, so it is recorded but not a fairness field.
    assert "planning" not in fingerprint["recovery_agent"]
    assert "planning" not in result.config["baseline_agent"]
    assert result.config["recovery_agent"]["planning"]["algorithm_version"] == "plan-update-v1"
    left = service.get_episode(pair.baseline_episode_id)
    right = service.get_episode(pair.recovery_episode_id)
    assert left is not None and right is not None
    assert left.agent.runtime_backend == right.agent.runtime_backend == backend
    assert left.agent.budget == right.agent.budget
    assert left.agent.runtime_strategy == right.agent.runtime_strategy
    assert left.agent.recovery_policy == right.agent.recovery_policy
    assert left.agent.context_policy == right.agent.context_policy == ContextPolicy(mode="full")
    assert left.agent.planning is None and right.agent.planning is not None
    for key in FIXED_VARIABLE_KEYS:
        assert getattr(left.agent, key) == getattr(right.agent, key)
    assert left.task == right.task and left.run_config == right.run_config
    stripped_left = left.agent.model_dump(exclude={"id", "name", "planning"})
    stripped_right = right.agent.model_dump(exclude={"id", "name", "planning"})
    assert stripped_left == stripped_right
    # The declaration tool is exposed only to the planning arm.
    assert plan_events(service, pair.recovery_episode_id) >= 1
    assert plan_events(service, pair.baseline_episode_id) == 0
    assert any(event.event_type == "PLAN_UPDATED" for event in right.events)
    assert all(event.event_type != "PLAN_UPDATED" for event in left.events)
    assert any(
        event.payload.get("name") == "update_plan"
        for event in right.events
        if event.event_type == "TOOL_SUCCEEDED"
    ) or any(
        event.payload.get("name") == "update_plan"
        for event in right.events
        if event.event_type == "TOOL_STARTED"
    )


def test_planning_recorded_plan_is_injected_without_being_executed(tmp_path: Path) -> None:
    """The saved plan is a declaration; completion is decided by real submission only."""
    service = EpisodeService(artifacts_dir=tmp_path)
    result = asyncio.run(service.execute_experiment(request()))
    right = service.get_episode(result.pairs[0].recovery_episode_id)
    left = service.get_episode(result.pairs[0].baseline_episode_id)
    assert right is not None and left is not None
    updated = [event for event in right.events if event.event_type == "PLAN_UPDATED"][0]
    raw_items = updated.payload["items"]
    assert isinstance(raw_items, list) and len(raw_items) == 2
    items = [cast(dict[str, object], item) for item in raw_items]
    assert {item["id"] for item in items} == {"facts", "decide"}
    assert items[1]["depends_on"] == ["facts"]
    # The extra planning round is charged to the planning arm itself.
    right_requests = sum(e.event_type == "MODEL_REQUESTED" for e in right.events)
    left_requests = sum(e.event_type == "MODEL_REQUESTED" for e in left.events)
    assert right_requests == left_requests + 1
    assert any(
        event.payload.get("name") == "update_plan"
        for event in right.events
        if event.event_type == "TOOL_STARTED"
    )
    assert not any(
        event.payload.get("name") == "update_plan"
        for event in left.events
        if event.event_type == "TOOL_STARTED"
    )
    assert any(
        event.payload.get("name") == "submit_answer"
        for event in right.events
        if event.event_type == "TOOL_STARTED"
    )


@pytest.mark.parametrize(
    "override",
    [
        {"schema_version": "1.8"},
        {"schema_version": "1.9", "comparison_axis": "memory_ablation"},
        {
            "schema_version": "1.9",
            "context_policy": {"mode": "recent_tool_rounds", "max_tool_rounds": 1},
        },
    ],
)
def test_planning_rejects_invalid_requests(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        request(**override)


def test_planning_rejects_non_planning_tasks(tmp_path: Path) -> None:
    """A planning comparison cannot silently run tasks that never declare a plan."""
    service = EpisodeService(artifacts_dir=tmp_path)
    with pytest.raises(ValueError, match="planning tasks"):
        asyncio.run(
            service.execute_experiment(request(task_ids=["order-status-007"], schema_version="1.9"))
        )


def test_planning_plan_rejects_mixed_variables(tmp_path: Path) -> None:
    """Creation, freezing and recovery all refuse a changed variable."""
    plan = asyncio.run(EpisodeService(artifacts_dir=tmp_path).prepare_experiment(request()))
    assert plan.schema_version == "1.4"
    left = plan.baseline_agent
    right = plan.recovery_agent
    tampered = [
        (left.model_copy(update={"planning": right.planning}), right),
        (left, right.model_copy(update={"planning": None})),
        (
            left.model_copy(
                update={
                    "context_policy": ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=2)
                }
            ),
            right,
        ),
        (left, right.model_copy(update={"runtime_backend": "langgraph"})),
        (left, right.model_copy(update={"runtime_strategy": "handwritten_recovery"})),
    ]
    for baseline, candidate in tampered:
        with pytest.raises(ValueError):
            create_experiment_plan(
                baseline,
                candidate,
                plan.tasks,
                plan.seeds,
                plan.repeat_count,
                "planning",
                plan.config_metadata,
            )


def test_planning_plan_verify_rejects_rehashed_mixed_inputs(tmp_path: Path) -> None:
    """A fresh hash cannot make a changed fixed variable a valid planning comparison."""
    plan = asyncio.run(EpisodeService(artifacts_dir=tmp_path).prepare_experiment(request()))
    right = plan.recovery_agent
    for field, value in (
        ("model", right.model.model_copy(update={"temperature": 0.5})),
        ("prompt_version", "changed"),
        ("tool_set_version", "changed"),
        ("budget", right.budget.model_copy(update={"max_steps": 99})),
    ):
        changed = plan.model_copy(
            update={"recovery_agent": right.model_copy(update={field: value})}
        ).model_copy(update={"plan_hash": "x"})
        changed = changed.model_copy(
            update={
                "plan_hash": compute_config_hash(
                    changed.model_dump(mode="json", exclude={"plan_hash"})
                )
            }
        )
        with pytest.raises(ValueError):
            changed.verify()
    changed = plan.model_copy(update={"comparison_axis": "recovery_policy"}).model_copy(
        update={"plan_hash": "x"}
    )
    changed = changed.model_copy(
        update={
            "plan_hash": compute_config_hash(changed.model_dump(mode="json", exclude={"plan_hash"}))
        }
    )
    with pytest.raises(ValueError):
        changed.verify()


def test_planning_result_rejects_revision_axis_and_context_mismatches(tmp_path: Path) -> None:
    """Saved revision 1.6 is exclusive to planning comparisons with full context."""

    def rehashed(source: ExperimentArtifact) -> dict[str, Any]:
        data: dict[str, Any] = source.model_dump(mode="json")
        data["config_hash"] = compute_config_hash(data["config"])
        return data

    result = asyncio.run(EpisodeService(artifacts_dir=tmp_path).execute_experiment(request()))
    tampered: list[dict[str, Any]] = []

    data = rehashed(result)
    data["config"]["comparison_axis"] = "memory_ablation"
    tampered.append(data)

    data = rehashed(result)
    data["config"]["baseline_agent"] = None
    tampered.append(data)

    data = rehashed(result)
    data["config"]["recovery_agent"] = []
    tampered.append(data)

    for field in ("runtime_version", "recovery_policy", "runtime_strategy", "runtime_backend"):
        data = rehashed(result)
        data["config"]["recovery_agent"][field] = "changed"
        tampered.append(data)

    data = rehashed(result)
    data["config"]["recovery_agent"].pop("runtime_version")
    tampered.append(data)

    for arm in ("baseline_agent", "recovery_agent"):
        data = rehashed(result)
        data["config"][arm]["context_policy"]["mode"] = "recent_tool_rounds"
        tampered.append(data)

    for candidate in tampered:
        candidate["config_hash"] = compute_config_hash(candidate["config"])
        with pytest.raises(ValidationError):
            ExperimentArtifact.model_validate(candidate)


def test_saved_planning_plan_resumes_without_rerunning_completed_arm(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    calls = 0

    def stop_after_left() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("controlled interruption")

    plan = asyncio.run(service.prepare_experiment(request()))
    with pytest.raises(RuntimeError, match="controlled interruption"):
        asyncio.run(
            run_experiment(
                plan.baseline_agent,
                plan.recovery_agent,
                plan.tasks,
                lambda: FakeModelProvider(scenario="success"),
                artifacts_dir=tmp_path,
                comparison_axis=plan.comparison_axis,
                config_metadata=plan.config_metadata,
                experiment_id=plan.experiment_id,
                before_arm=stop_after_left,
            )
        )
    path = tmp_path / "experiments" / "checkpoints" / f"{plan.experiment_id}.json"
    saved = read_experiment_checkpoint(path)
    assert saved.baseline_agent == plan.baseline_agent
    assert saved.schema_version == "1.4"
    completed = next(tmp_path.glob("*.json"))
    original = completed.read_bytes()
    reused_episode_id = json.loads(completed.read_text(encoding="utf-8"))["episode"]["episode_id"]
    result = asyncio.run(
        EpisodeService(artifacts_dir=tmp_path).resume_experiment(plan.experiment_id)
    )
    assert completed.read_bytes() == original
    assert result.metrics.baseline_success_count == 1
    assert result.metrics.recovery_success_count == 1
    # The completed arm is reused, not re-run: a re-run would mint a new Episode id.
    assert str(result.pairs[0].baseline_episode_id) == reused_episode_id
    assert not path.exists()


def test_planning_axis_obeys_global_token_admission(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)
    with pytest.raises(ExperimentTokenBudgetError, match="EXPERIMENT_TOKEN_BUDGET_EXCEEDED"):
        asyncio.run(service.execute_experiment(request(max_total_tokens=1)))
    assert len(list(tmp_path.glob("*.json"))) == 1
    with patch.object(
        EpisodeService, "_require_live_model", side_effect=AssertionError("no live requests")
    ):
        saved = read_experiment_checkpoint(
            next((tmp_path / "experiments" / "checkpoints").glob("*.json"))
        )
        assert saved.schema_version == "1.4" and saved.config_metadata["max_total_tokens"] == 1
        with pytest.raises(ExperimentTokenBudgetError):
            asyncio.run(
                EpisodeService(artifacts_dir=tmp_path).resume_experiment(saved.experiment_id)
            )


def test_planning_api_accepts_new_axis_and_rejects_mismatch(tmp_path: Path) -> None:
    service = EpisodeService(artifacts_dir=tmp_path)

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = {
                    "provider": "fake",
                    "model": "fake-model",
                    "scenario": "success",
                    "task_ids": [PLANNING_TASK],
                    "comparison_axis": "planning",
                    "schema_version": "1.9",
                }
                response = await client.post("/api/v1/experiments", json=payload)
                assert response.status_code == 201
                saved = response.json()["experiment"]
                assert saved["schema_version"] == "1.6"
                reply = await client.get(f"/api/v1/experiments/{saved['experiment_id']}")
                assert reply.json()["experiment"] == saved
                payload["schema_version"] = "1.8"
                assert (await client.post("/api/v1/experiments", json=payload)).status_code == 422
                payload["schema_version"] = "1.9"
                payload["task_ids"] = ["order-status-007"]
                assert (await client.post("/api/v1/experiments", json=payload)).status_code == 400
        finally:
            app.dependency_overrides.clear()

    asyncio.run(exercise())
