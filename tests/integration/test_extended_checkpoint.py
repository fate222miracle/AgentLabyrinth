"""Saved BFCL and MCP episodes resume through their original environments."""

import asyncio
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import JsonValue

from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    AgentSpec,
    EstimatedCost,
    EventType,
    ModelResponse,
    RunConfig,
    TokenUsage,
    ToolCall,
)
from packages.environments.bfcl.environment import BFCLEnvironment
from packages.environments.tool_lab import mcp
from packages.evaluation.bfcl import BFCLEvaluator
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime
from packages.runtime.session import SessionState

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("suite", ["bfcl", "bfcl_java", "mcp"])
def test_extended_resume_across_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suite: str
) -> None:
    """A new process recovers the same ID without repeating committed remote reads."""
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("_checkpoint_worker.py")),
            suite,
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    checkpoint_path = next((tmp_path / "checkpoints").glob("*.json"))
    episode_id = UUID(checkpoint_path.stem)
    CheckpointStore(checkpoint_path.parent).load(episode_id)
    service = EpisodeService(artifacts_dir=tmp_path)
    assert episode_id in service.resumable_episode_ids()
    if suite.startswith("bfcl"):
        adapter = service.bfcl_java if suite == "bfcl_java" else service.bfcl
        case, _ = adapter.case_for_task(
            "bfcl-simple_java_18" if suite == "bfcl_java" else "bfcl-simple_python_1"
        )
        arguments = {
            key: values[0]
            for key, values in case.ground_truth[case.tool_name].items()
            if values[0] != ""
        }
        response = ModelResponse(
            action=ToolCall(call_id="bfcl-call-1", name=case.tool_name, arguments=arguments),
            token_usage=TokenUsage(prompt_tokens=40, completion_tokens=20, simulated=True),
            estimated_cost=EstimatedCost(
                amount=Decimal("0.001"), currency="USD", price_table_version="fake-zero-v1"
            ),
        )
        monkeypatch.setattr(
            "apps.api.service.FakeModelProvider",
            lambda **kwargs: FakeModelProvider(custom_responses=[response], **kwargs),
        )
    else:
        monkeypatch.setattr(
            mcp, "_call_sync", lambda *args: pytest.fail("Committed MCP read was repeated")
        )
    artifact = asyncio.run(service.resume_episode(episode_id))
    assert artifact.evaluation.success
    assert artifact.episode.episode_id == episode_id
    assert sum(e.event_type == EventType.EPISODE_RESUMED for e in artifact.events) == 1
    assert not checkpoint_path.exists()


def fake_agent() -> AgentSpec:
    """Load the versioned Fake agent without changing its stored source."""
    return AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    ("suite", "task_name"),
    [
        ("bfcl", "bfcl-simple_python_1"),
        ("bfcl_java", "bfcl-simple_java_18"),
    ],
)
def test_bfcl_resume_uses_pinned_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suite: str, task_name: str
) -> None:
    """A saved BFCL observation resumes as the same one-call proposal task."""
    service = EpisodeService(artifacts_dir=tmp_path)
    case, task = getattr(service, suite).case_for_task(task_name)
    agent = fake_agent()
    config = RunConfig(environment_version="bfcl-adapted-single-call-v1")
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(tmp_path / "checkpoints")
    args = {
        key: values[0]
        for key, values in case.ground_truth[case.tool_name].items()
        if values[0] != ""
    }
    response = ModelResponse(
        action=ToolCall(call_id="bfcl-call-1", name=case.tool_name, arguments=args),
        token_usage=TokenUsage(prompt_tokens=40, completion_tokens=20, simulated=True),
        estimated_cost=EstimatedCost(
            amount=Decimal("0.001"), currency="USD", price_table_version="fake-zero-v1"
        ),
    )

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.next_node == "model":
            raise SystemExit(0)

    with pytest.raises(SystemExit):
        asyncio.run(
            run_episode(
                agent,
                task,
                config,
                create_runtime(agent, FakeModelProvider()),
                BFCLEnvironment(case),
                BFCLEvaluator(),
                recorder=recorder,
                save_checkpoint=save,
            )
        )
    monkeypatch.setattr(
        "apps.api.service.FakeModelProvider",
        lambda **kwargs: FakeModelProvider(custom_responses=[response], **kwargs),
    )
    artifact = asyncio.run(
        EpisodeService(artifacts_dir=tmp_path).resume_episode(recorder.episode_id)
    )
    assert artifact.evaluation.success
    assert artifact.task == task
    assert sum(e.event_type == EventType.EPISODE_RESUMED for e in artifact.events) == 1


def test_mcp_resume_retains_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A remote read is not repeated after its result and evidence were saved."""
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task("order-status-007")
    agent = fake_agent()
    config = RunConfig(environment_version="tool-lab-mcp-v1")
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(tmp_path / "checkpoints")
    remote_calls: list[str] = []

    def remote(name: str, arguments: dict[str, object], url: str) -> dict[str, JsonValue]:
        remote_calls.append(name)
        if name == "search_documents":
            top_k = arguments["top_k"]
            assert isinstance(top_k, int)
            return mcp.search_documents(str(arguments["task_name"]), str(arguments["query"]), top_k)
        return mcp.read_document(str(arguments["task_name"]), str(arguments["document_id"]))

    monkeypatch.setattr(mcp, "_call_sync", remote)

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.next_node == "model" and state.budget.tool_call_count == 2:
            raise SystemExit(0)

    with pytest.raises(SystemExit):
        asyncio.run(
            run_episode(
                agent,
                task,
                config,
                create_runtime(agent, FakeModelProvider()),
                mcp.MCPToolLabEnvironment(),
                OrderStatusEvaluator(),
                recorder=recorder,
                save_checkpoint=save,
            )
        )
    before = list(remote_calls)
    artifact = asyncio.run(
        EpisodeService(artifacts_dir=tmp_path).resume_episode(recorder.episode_id)
    )
    assert artifact.evaluation.success
    assert remote_calls == before
    assert artifact.episode.tool_call_count == 3
    assert sum(e.event_type == EventType.EPISODE_RESUMED for e in artifact.events) == 1
