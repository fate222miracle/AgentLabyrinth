"""Stop a BFCL or MCP Fake episode after a durable safe point."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import JsonValue

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from apps.api.schemas import CreateExperimentRequest  # noqa: E402
from apps.api.service import EpisodeService  # noqa: E402
from packages.application.checkpoint import CheckpointStore  # noqa: E402
from packages.application.runner import run_episode  # noqa: E402
from packages.application.trace import JsonTraceRecorder  # noqa: E402
from packages.domain.models import (  # noqa: E402
    AgentSpec,
    Message,
    ModelConfig,
    ModelResponse,
    RunConfig,
    TaskSpec,
    ToolSchema,
)
from packages.domain.ports import Environment, Evaluator  # noqa: E402
from packages.environments.bfcl.environment import BFCLEnvironment  # noqa: E402
from packages.environments.tool_lab import mcp  # noqa: E402
from packages.evaluation.bfcl import BFCLEvaluator  # noqa: E402
from packages.evaluation.order_status import OrderStatusEvaluator  # noqa: E402
from packages.providers.fake import FakeModelProvider  # noqa: E402
from packages.runtime.factory import create_runtime  # noqa: E402
from packages.runtime.session import SessionState  # noqa: E402


def main() -> None:
    """Persist state and terminate without running the normal cleanup path."""
    suite, directory = sys.argv[1], Path(sys.argv[2])
    service = EpisodeService(artifacts_dir=directory)
    if suite == "queued":
        import httpx

        from apps.api.main import app, get_episode_service

        two_started = asyncio.Event()
        calls = 0

        async def blocked(
            provider: FakeModelProvider,
            messages: list[Message],
            tools: list[ToolSchema],
            config: ModelConfig,
        ) -> ModelResponse:
            nonlocal calls
            calls += 1
            if calls == 2:
                two_started.set()
            await asyncio.Event().wait()
            raise AssertionError("Blocked provider unexpectedly returned")

        async def queue_and_exit() -> None:
            app.dependency_overrides[get_episode_service] = lambda: service
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                ids = []
                for seed in (1, 2, 3):
                    response = await client.post(
                        "/api/v1/experiments/jobs",
                        json={
                            "provider": "fake",
                            "model": "fake-model",
                            "scenario": "success",
                            "task_ids": ["order-status-001"],
                            "seeds": [seed],
                            "repeat_count": 2,
                        },
                    )
                    assert response.status_code == 202, response.text
                    ids.append(response.json()["experiment_id"])
                await asyncio.wait_for(two_started.wait(), 3)
                state = (await client.get(f"/api/v1/experiments/jobs/{ids[2]}")).json()
                assert state["status"] == "queued"
                (directory / "queued_ids.json").write_text(json.dumps(ids), encoding="utf-8")
                os._exit(0)

        with patch.object(FakeModelProvider, "generate", blocked):
            asyncio.run(queue_and_exit())
        raise AssertionError("Queued worker did not exit")
    if suite in {"experiment", "experiment-tokens", "experiment-tokens-end"}:
        request = CreateExperimentRequest(
            provider="fake",
            model="fake-model",
            scenario="success",
            task_ids=["order-status-001"],
            max_total_tokens=int(sys.argv[3]) if suite.startswith("experiment-tokens") else None,
            repeat_count=2 if suite.startswith("experiment-tokens") else 1,
        )
        service.reserve_experiment_job(request.request_id)
        service.update_experiment_job(request.request_id, status="running")
        original = FakeModelProvider.generate
        calls = 0

        if suite == "experiment-tokens-end":
            original_save = CheckpointStore.save

            def end_save(
                self: CheckpointStore,
                state: SessionState,
                agent: AgentSpec,
                task: TaskSpec,
                config: RunConfig,
                recorder: JsonTraceRecorder,
                fake_scenario: str | None = None,
            ) -> None:
                original_save(self, state, agent, task, config, recorder, fake_scenario)
                if state.next_node == "end":
                    os._exit(0)

            with patch.object(CheckpointStore, "save", end_save):
                asyncio.run(service.execute_experiment(request, job_id=request.request_id))
            raise AssertionError("Experiment did not stop after a terminal safe point")

        async def interrupt(
            provider: FakeModelProvider,
            messages: list[Message],
            tools: list[ToolSchema],
            config: ModelConfig,
        ) -> ModelResponse:
            nonlocal calls
            calls += 1
            if calls == (4 if suite == "experiment-tokens" else 3):
                os._exit(0)
            return await original(provider, messages, tools, config)

        with patch.object(FakeModelProvider, "generate", interrupt):
            asyncio.run(service.execute_experiment(request, job_id=request.request_id))
        raise AssertionError("Experiment worker did not interrupt the second arm")
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    )
    environment: Environment
    evaluator: Evaluator
    if suite.startswith("bfcl"):
        adapter = service.bfcl_java if suite == "bfcl_java" else service.bfcl
        case, task = adapter.case_for_task(
            "bfcl-simple_java_18" if suite == "bfcl_java" else "bfcl-simple_python_1"
        )
        environment = BFCLEnvironment(case)
        evaluator = BFCLEvaluator()
        config = RunConfig(environment_version="bfcl-adapted-single-call-v1")
        stop_after_tools = 0
    else:
        task = service._get_task("order-status-007")
        environment = mcp.MCPToolLabEnvironment()
        evaluator = OrderStatusEvaluator()
        config = RunConfig(environment_version="tool-lab-mcp-v1")
        stop_after_tools = 2

        def remote(name: str, arguments: dict[str, Any], url: str) -> dict[str, JsonValue]:
            if name == "search_documents":
                return mcp.search_documents(
                    str(arguments["task_name"]), str(arguments["query"]), int(arguments["top_k"])
                )
            return mcp.read_document(str(arguments["task_name"]), str(arguments["document_id"]))

        mcp._call_sync = remote

    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(directory / "checkpoints")

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.next_node == "model" and state.budget.tool_call_count == stop_after_tools:
            os._exit(0)

    asyncio.run(
        run_episode(
            agent,
            task,
            config,
            create_runtime(agent, FakeModelProvider()),
            environment,
            evaluator,
            recorder=recorder,
            save_checkpoint=save,
        )
    )
    raise AssertionError("Worker did not reach the intended safe point")


if __name__ == "__main__":
    main()
