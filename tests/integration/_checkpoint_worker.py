"""Stop a BFCL or MCP Fake episode after a durable safe point."""

import asyncio
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
    if suite == "experiment":
        request = CreateExperimentRequest(
            provider="fake", model="fake-model", scenario="success", task_ids=["order-status-001"]
        )
        service.reserve_experiment_job(request.request_id)
        service.update_experiment_job(request.request_id, status="running")
        original = FakeModelProvider.generate
        calls = 0

        async def interrupt(
            provider: FakeModelProvider,
            messages: list[Message],
            tools: list[ToolSchema],
            config: ModelConfig,
        ) -> ModelResponse:
            nonlocal calls
            calls += 1
            if calls == 3:
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
