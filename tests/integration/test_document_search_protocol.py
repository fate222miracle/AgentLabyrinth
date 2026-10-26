"""Versioned search fixes ID discovery without rewriting evidence or saved runs."""

import asyncio
from pathlib import Path
from typing import Literal, cast
from unittest.mock import patch

import pytest
from pydantic import JsonValue, ValidationError

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import ContextPolicy, ModelResponse, RunConfig, ToolCall
from packages.environments.tool_lab import mcp
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime, runtime_version
from packages.runtime.session import SessionState
from scripts.review_memory import review_memory
from scripts.run_regression import preflight


@pytest.mark.parametrize("version", ["v1.4.0", "v1.5.0"])
def test_search_rules_and_evidence_are_versioned(tmp_path: Path, version: str) -> None:
    """An ID selects itself, not its citations; old literal output remains unchanged."""
    task = EpisodeService(artifacts_dir=tmp_path)._get_task("memory-fact-reuse-001")
    env = ToolLabEnvironment(tool_set_version=version)
    env.reset(task, 1)
    for query in ("INSPECTION", " inspection ", "CASE-710 intake", "receipt", "POLICY"):
        action = ToolCall(
            call_id=query, name="search_documents", arguments={"query": query, "top_k": 1}
        )
        local = env.step(action)
        assert local.error is None
        remote = mcp.search_documents(
            task.name,
            query,
            1,
            "id-first-literal-v1" if version == "v1.5.0" else "literal-v1",
        )
        assert local.observation.content == {"result": remote}
        assert env.snapshot()["acquired_evidence"] == []
        documents = cast(list[dict[str, JsonValue]], remote["documents"])
        assert len(documents) <= 1
        assert "content" not in str(remote) and "evidence_id" not in str(remote)
        if version == "v1.5.0":
            if query.strip().casefold() == "inspection":
                assert remote["search_mode"] == "exact_id"
                assert documents[0]["document_id"] == "INSPECTION"
            elif query == "receipt":
                assert remote["search_mode"] == "none"
                assert documents == [] and "document_query" in str(remote["hint"])
            else:
                assert remote["search_mode"] == "literal_text" and "hint" not in remote
        else:
            assert set(remote) == {"documents"}
            assert remote == mcp.search_documents(task.name, query, 1)
            if query == "INSPECTION":
                assert documents[0]["document_id"] == "INTAKE"
    forged = env.step(
        ToolCall(call_id="forged", name="submit_answer", arguments=task.goal_conditions)
    )
    assert forged.error is None
    assert env.snapshot()["acquired_evidence"] == []
    assert env.snapshot()["submission"] is not None
    # Submission stores a claim; only the evaluator decides whether evidence was acquired.
    with patch(
        "apps.api.service.FakeModelProvider",
        return_value=FakeModelProvider(
            custom_responses=[
                ModelResponse(
                    action=ToolCall(
                        call_id="forged", name="submit_answer", arguments=task.goal_conditions
                    )
                )
            ]
        ),
    ):
        artifact = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path).execute_episode(
                CreateEpisodeRequest(
                    schema_version="1.5",
                    provider="fake",
                    model="fake",
                    task_id=task.name,
                    tool_call_mode="serial",
                )
            )
        )
    assert not artifact.evaluation.success


def test_search_rejects_invalid_requests_and_protocols(tmp_path: Path) -> None:
    """No whitespace query, coerced limit, or model-controlled protocol extension."""
    task = EpisodeService(artifacts_dir=tmp_path)._get_task("memory-fact-reuse-001")
    env = ToolLabEnvironment(tool_set_version="v1.5.0")
    env.reset(task, 1)
    for arguments in (
        {"query": " ", "top_k": 1},
        {"query": "x", "top_k": 0},
        {"query": "x", "top_k": "1"},
        {"query": "x", "top_k": 1, "search_protocol": "literal-v1"},
    ):
        result = env.step(
            ToolCall(
                call_id="invalid",
                name="search_documents",
                arguments=cast(dict[str, JsonValue], arguments),
            )
        )
        assert result.error is not None
    with pytest.raises(ValueError, match="protocol"):
        mcp.search_documents(task.name, "x", 1, "unknown")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        CreateEpisodeRequest(schema_version="1.5", provider="fake", model="fake")
    assert env.snapshot()["acquired_evidence"] == []


@pytest.mark.parametrize("version,toolset", [("1.7", "v1.4.0"), ("1.8", "v1.5.0")])
def test_formal_plan_and_review_preserve_search_source(
    tmp_path: Path, version: Literal["1.7", "1.8"], toolset: str
) -> None:
    """Both arms and preflight use the frozen task variant and matching descriptions."""
    service = EpisodeService(artifacts_dir=tmp_path / "inputs")
    req = CreateExperimentRequest(
        schema_version=version,
        provider="fake",
        model="fake",
        tool_call_mode="serial",
        scenario="clean",
        comparison_axis="memory_ablation",
        task_ids=["memory-fact-reuse-001"],
        context_policy=ContextPolicy(
            schema_version="1.1",
            algorithm_version="tool-round-window-memory-v1",
            mode="recent_tool_rounds",
            max_tool_rounds=1,
            memory_max_bytes=8192,
        ),
    )
    original = service._get_task(req.task_ids[0])
    result = asyncio.run(service.execute_experiment(req))
    preflight(result, req, service)
    for row in result.pairs:
        for id_ in (row.baseline_episode_id, row.recovery_episode_id):
            artifact = service.get_episode(id_)
            assert artifact is not None and artifact.agent.tool_set_version == toolset
            assert ("id-search-v1" in artifact.task.version) is (version == "1.8")
            assert artifact.task.goal_conditions == original.goal_conditions
            assert artifact.task.initial_state == original.initial_state
    assert service._get_task(original.name) == original
    assert (
        review_memory(
            service.artifacts_dir, tmp_path / "review", experiment_id=result.experiment_id
        )["status"]
        == "reviewed"
    )


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("transport", ["local", "mcp"])
def test_search_profile_survives_partial_batch_resume(
    tmp_path: Path, backend: str, transport: str
) -> None:
    """Resume new checkpoints with their ID protocol, without repeating committed reads."""
    service = EpisodeService(artifacts_dir=tmp_path)
    req = CreateExperimentRequest.model_validate(
        dict(
            schema_version="1.8",
            provider="fake",
            model="fake",
            tool_call_mode="serial",
            scenario="clean",
            task_ids=["memory-fact-reuse-001"],
            runtime_backend=backend,
        )
    )
    plan = asyncio.run(service.prepare_experiment(req))
    task, agent = plan.tasks[0], plan.baseline_agent
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

    def remote(name: str, args: dict[str, object], url: str) -> dict[str, JsonValue]:
        if name == "search_documents":
            assert args["search_protocol"] == "id-first-literal-v1"
            return mcp.search_documents(
                str(args["task_name"]),
                str(args["query"]),
                int(str(args["top_k"])),
                "id-first-literal-v1",
            )
        return mcp.read_document(str(args["task_name"]), str(args["document_id"]))

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.next_node == "execute" and len(state.pending_calls) == 1:
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
        checkpoint = store.load(recorder.episode_id)
        assert checkpoint.agent.tool_set_version == "v1.5.0"
        assert checkpoint.task.version == "1.0.0+id-search-v1.serial-v1"
        resumed = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path)._resume_episode_once(recorder.episode_id)
        )
    assert resumed.evaluation.success and resumed.episode.tool_call_count == 5
    assert resumed.agent == agent and resumed.task == task
