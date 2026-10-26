"""Batched proposals retain per-call safety, accounting and resumable progress."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import JsonValue, ValidationError

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    AgentSpec,
    ContextPolicy,
    EventType,
    ModelConfig,
    ModelResponse,
    RunConfig,
    StepResult,
    TaskSpec,
    TokenUsage,
    ToolCall,
    ToolCallBatch,
)
from packages.domain.ports import ModelProviderError
from packages.environments.tool_lab import mcp
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.aihubmix import AIHubMixModelProvider
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime, runtime_version
from packages.runtime.session import SessionState
from scripts.review_memory import review_memory
from scripts.run_regression import preflight

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ContextPolicy(
    schema_version="1.1",
    algorithm_version="tool-round-window-memory-v1",
    mode="recent_tool_rounds",
    max_tool_rounds=1,
    memory_max_bytes=8192,
)


def request(**changes: object) -> CreateEpisodeRequest:
    """Keep new mode explicit and legacy requests unchanged."""
    merged: dict[str, object] = (
        dict(
            schema_version="1.4",
            tool_call_mode="serial",
            provider="fake",
            model="fake",
            task_id="memory-fact-reuse-001",
        )
        | changes
    )
    if merged.get("runtime_backend") == "pydantic_ai" and "schema_version" not in changes:
        merged["schema_version"] = "1.7"
    return CreateEpisodeRequest.model_validate(merged)


@pytest.mark.parametrize("backend", ["handwritten", "langgraph", "pydantic_ai"])
@pytest.mark.parametrize(
    "task", ["memory-fact-reuse-001", "memory-large-return-002", "memory-policy-version-003"]
)
def test_batches_complete_with_full_window_and_memory(
    tmp_path: Path, backend: str, task: str
) -> None:
    """A model round contains all matched returns, with each execution counted once."""
    for policy in (None, ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=1), MEMORY):
        a = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path).execute_episode(
                request(task_id=task, runtime_backend=backend, context_policy=policy)
            )
        )
        assert a.evaluation.success is (policy is None or policy.memory_max_bytes is not None)
        proposed = [e for e in a.events if e.event_type == EventType.TOOL_CALL_PROPOSED]
        started = [e for e in a.events if e.event_type == EventType.TOOL_STARTED]
        assert len(started) == a.episode.tool_call_count
        assert len({e.payload["call_id"] for e in proposed}) == len(proposed)
        assert any(e.payload.get("batch_size") == 2 for e in proposed)
        assert a.task.version.endswith("+serial-v1")
        assert not any(c.startswith("每轮只提出一个") for c in a.task.constraints)
        assert a.agent.model.tool_call_mode == "serial"


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate",
        "unknown",
        "forbidden",
        "write",
        "invalid_twice",
        "budget",
        "second_failure",
        "timeout",
    ],
)
@pytest.mark.parametrize("backend", ["handwritten", "langgraph", "pydantic_ai"])
def test_batch_failure_boundaries(tmp_path: Path, damage: str, backend: str) -> None:
    """An invalid batch executes nothing; a runtime failure stops remaining calls."""
    calls = [
        ToolCall(
            call_id=f"b{i}",
            name="search_documents",
            arguments={"query": "CASE-710 intake", "top_k": 3},
        )
        for i in range(3)
    ]
    if damage == "duplicate":
        calls[1] = calls[0]
    elif damage == "unknown":
        calls[1] = calls[1].model_copy(update={"name": "invented_tool"})
    elif damage == "write":
        calls[1] = ToolCall(
            call_id="b1", name="submit_answer", arguments={"answer": "ineligible", "evidence": []}
        )
    elif damage == "invalid_twice":
        calls[1] = calls[1].model_copy(update={"arguments": {"query": "x", "top_k": 0}})
    responses = [
        ModelResponse(schema_version="1.1", action=ToolCallBatch(calls=tuple(calls))),
        ModelResponse(
            schema_version="1.1",
            action=ToolCallBatch(
                calls=tuple(c.model_copy(update={"call_id": c.call_id + "retry"}) for c in calls)
            ),
        ),
    ]
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task("memory-fact-reuse-001")
    if damage == "forbidden":
        task = task.model_copy(update={"forbidden_tools": ("search_documents",)})
    capacity = service._agent_with_task_capacity
    step = ToolLabEnvironment.step
    executed: list[str] = []

    def execute(env: ToolLabEnvironment, call: ToolCall) -> StepResult:
        executed.append(call.call_id)
        if damage == "second_failure" and len(executed) == 2:
            raise RuntimeError("controlled failure")
        return step(env, call)

    def limits(agent: AgentSpec, tasks: list[TaskSpec]) -> AgentSpec:
        agent = capacity(agent, tasks)
        if damage == "budget":
            return agent.model_copy(
                update={"budget": agent.budget.model_copy(update={"max_tool_calls": 2})}
            )
        return agent

    with (
        patch.object(service, "_get_task", return_value=task),
        patch.object(service, "_agent_with_task_capacity", side_effect=limits),
        patch(
            "apps.api.service.FakeModelProvider",
            return_value=FakeModelProvider(custom_responses=responses),
        ),
        patch.object(ToolLabEnvironment, "step", execute),
        patch(
            "packages.runtime.session.EpisodeSession.time_exceeded",
            lambda self: damage == "timeout" and len(executed) >= 2,
        ),
    ):
        a = asyncio.run(
            service.execute_episode(
                request(runtime_backend=backend, runtime_strategy="handwritten_recovery")
            )
        )
    assert not a.evaluation.success
    assert len(executed) == (2 if damage in {"second_failure", "timeout"} else 0)
    assert a.episode.tool_call_count == len(executed)
    assert a.episode.model_call_count == (2 if damage == "invalid_twice" else 1)


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
@pytest.mark.parametrize("transport", ["local", "mcp"])
def test_partial_batch_resumes_and_rejects_tampering(
    tmp_path: Path, backend: str, transport: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A persisted first read is never repeated when the second is pending."""
    req = request(runtime_backend=backend, context_policy=MEMORY)
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._with_call_mode(service._get_task(req.task_id), "serial")
    pair = CreateExperimentRequest(
        schema_version="1.7",
        tool_call_mode="serial",
        provider="fake",
        model="fake",
        scenario="clean",
        task_ids=[req.task_id],
        runtime_backend=backend,
        comparison_axis="memory_ablation",
        context_policy=MEMORY,
    )
    plan = asyncio.run(service.prepare_experiment(pair))
    agent = plan.recovery_agent
    config = RunConfig(
        runtime_version=runtime_version(agent.runtime_backend),
        environment_version="tool-lab-mcp-v1" if transport == "mcp" else "tool-lab-m0-v1",
    )
    if transport == "mcp":

        def remote(name: str, args: dict[str, object], url: str) -> dict[str, JsonValue]:
            if name == "search_documents":
                return mcp.search_documents(
                    str(args["task_name"]), str(args["query"]), int(str(args["top_k"]))
                )
            return mcp.read_document(str(args["task_name"]), str(args["document_id"]))

        monkeypatch.setattr(mcp, "_call_sync", remote)
    environment = (
        mcp.MCPToolLabEnvironment(tool_set_version=agent.tool_set_version)
        if transport == "mcp"
        else ToolLabEnvironment(tool_set_version=agent.tool_set_version)
    )
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(tmp_path / "checkpoints")

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.next_node == "execute" and len(state.pending_calls) == 1:
            raise SystemExit(0)

    with pytest.raises(SystemExit):
        asyncio.run(
            run_episode(
                agent,
                task,
                config,
                create_runtime(agent, FakeModelProvider()),
                environment,
                OrderStatusEvaluator(),
                recorder=recorder,
                save_checkpoint=save,
            )
        )
    checkpoint = store.load(recorder.episode_id)
    assert checkpoint.session.schema_version == "1.1"
    assert checkpoint.session.budget.tool_call_count == 3
    original = store.path(recorder.episode_id).read_bytes()
    raw = json.loads(original)
    raw["session"]["pending_calls"][0]["arguments"]["document_id"] = "INTAKE"
    store.path(recorder.episode_id).write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Pending batch"):
        asyncio.run(
            EpisodeService(artifacts_dir=tmp_path)._resume_episode_once(recorder.episode_id)
        )
    store.path(recorder.episode_id).write_bytes(original)
    # A second process loads the original fixed mode and queue, without a new plan.
    if transport == "mcp":
        resumed = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path)._resume_episode_once(recorder.episode_id)
        )
        assert resumed.evaluation.success and resumed.episode.tool_call_count == 5
        return
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import asyncio,sys; from pathlib import Path; from uuid import UUID; "
            "from apps.api.service import EpisodeService; "
            "s=EpisodeService(artifacts_dir=Path(sys.argv[1])); "
            "a=asyncio.run(s.resume_episode(UUID(sys.argv[2]))); "
            "assert a.evaluation.success and a.episode.tool_call_count==5",
            str(tmp_path),
            str(recorder.episode_id),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    a = service.get_episode(recorder.episode_id)
    assert a is not None and a.agent.model.tool_call_mode == "serial"
    reads = [e.payload["observation"] for e in a.events if e.event_type == EventType.TOOL_SUCCEEDED]
    assert len(reads) == 5


@pytest.mark.parametrize("mode,count", [(None, 2), ("single", 2), ("serial", 2), ("serial", 9)])
def test_provider_preserves_or_rejects_complete_batch(mode: str | None, count: int) -> None:
    """No first-call truncation, with known usage retained on new-mode rejection."""
    provider = AIHubMixModelProvider(api_key="test")
    response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": f"t{i}",
                            "function": {"name": "search_documents", "arguments": '{"query":"x"}'},
                        }
                        for i in range(count)
                    ]
                }
            }
        ],
        "usage": {"prompt_tokens": 80, "completion_tokens": 20},
    }
    config = ModelConfig.model_validate(
        dict(provider="aihubmix", model="test")
        | ({"schema_version": "1.1", "tool_call_mode": mode} if mode else {})
    )
    with patch.object(provider, "_send_http_request", return_value=response):
        if mode == "serial" and count == 2:
            result = asyncio.run(provider.generate([], [], config))
            assert isinstance(result.action, ToolCallBatch) and len(result.action.calls) == 2
        else:
            with pytest.raises(ModelProviderError) as error:
                asyncio.run(provider.generate([], [], config))
            assert (error.value.token_usage is not None) is (mode is not None)


def test_legacy_hashes_and_new_request_versions(tmp_path: Path) -> None:
    """New children are explicit; a missing field never silently enables batching."""
    assert "tool_call_mode" not in ModelConfig().model_dump()
    for factory, data in (
        (CreateEpisodeRequest, {"schema_version": "1.3"}),
        (CreateExperimentRequest, {"schema_version": "1.6"}),
    ):
        with pytest.raises(ValidationError):
            factory.model_validate(
                dict(provider="fake", model="fake", tool_call_mode="serial") | data
            )
    with pytest.raises(ValueError, match="BFCL"):
        asyncio.run(
            EpisodeService(artifacts_dir=tmp_path).execute_episode(
                request(suite="bfcl_adapted", task_id="bfcl-simple_python_1")
            )
        )


def test_formal_pair_keeps_call_mode_and_offline_sources(tmp_path: Path) -> None:
    """Both arms share the mode, while complete batch returns enter memory separately."""
    service = EpisodeService(artifacts_dir=tmp_path / "inputs")
    req = CreateExperimentRequest(
        schema_version="1.7",
        tool_call_mode="serial",
        provider="fake",
        model="fake",
        scenario="clean",
        comparison_axis="memory_ablation",
        context_policy=MEMORY,
        task_ids=["memory-fact-reuse-001"],
    )
    result = asyncio.run(service.execute_experiment(req))
    preflight(result, req, service)
    report = review_memory(
        service.artifacts_dir, tmp_path / "review", experiment_id=result.experiment_id
    )
    assert report["status"] == "reviewed"
    assert result.metrics.baseline_success_count == 0
    assert result.metrics.recovery_success_count == 1
    assert result.config["model"]["tool_call_mode"] == "serial"


@pytest.mark.parametrize("known", [True, False])
def test_rejected_response_usage_is_recorded_only_if_reported(tmp_path: Path, known: bool) -> None:
    """A protocol error cannot erase trustworthy usage or fabricate a zero response."""

    async def rejected(*args: object, **kwargs: object) -> ModelResponse:
        raise ModelProviderError(
            "TOOL_BATCH_TOO_LARGE",
            token_usage=(TokenUsage(prompt_tokens=80, completion_tokens=20) if known else None),
        )

    with patch("packages.providers.fake.FakeModelProvider.generate", side_effect=rejected):
        a = asyncio.run(EpisodeService(artifacts_dir=tmp_path).execute_episode(request()))
    returned = [e for e in a.events if e.event_type == EventType.MODEL_RESPONDED]
    assert len(returned) == int(known)
    assert a.episode.tool_call_count == 0
    assert a.episode.token_usage.prompt_tokens == (80 if known else 0)
    if known:
        assert returned[0].payload["action_kind"] == "rejected"


@pytest.mark.parametrize("backend", ["handwritten", "langgraph", "pydantic_ai"])
def test_one_batch_argument_repair_keeps_complete_feedback(tmp_path: Path, backend: str) -> None:
    """A cancelled batch can be corrected once, without executing its valid sibling."""

    def call(id_: str, name: str, **arguments: JsonValue) -> ToolCall:
        return ToolCall(call_id=id_, name=name, arguments=arguments)

    actions: list[ToolCall | ToolCallBatch] = [
        ToolCallBatch(
            calls=(
                call("bad", "search_documents", query="x", top_k=0),
                call("cancelled", "search_documents", query="CASE-710 intake", top_k=3),
            )
        ),
        call("search", "search_documents", query="CASE-710 intake", top_k=3),
        call("intake", "read_document", document_id="INTAKE"),
        ToolCallBatch(
            calls=(
                call("inspection", "read_document", document_id="INSPECTION"),
                call("policy", "read_document", document_id="POLICY-B"),
            )
        ),
        call(
            "submit",
            "submit_answer",
            answer="ineligible",
            evidence=["document:INSPECTION", "document:INTAKE", "document:POLICY-B"],
        ),
    ]
    fake = FakeModelProvider(
        custom_responses=[
            ModelResponse(schema_version="1.1" if isinstance(a, ToolCallBatch) else "1.0", action=a)
            for a in actions
        ]
    )
    with patch("apps.api.service.FakeModelProvider", return_value=fake):
        a = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path).execute_episode(
                request(
                    runtime_backend=backend,
                    runtime_strategy="handwritten_recovery",
                    context_policy=MEMORY,
                )
            )
        )
    assert a.evaluation.success
    assert a.episode.model_call_count == 5 and a.episode.tool_call_count == 5
    assert not any(
        e.payload.get("call_id") in {"bad", "cancelled"}
        for e in a.events
        if e.event_type == EventType.TOOL_STARTED
    )
