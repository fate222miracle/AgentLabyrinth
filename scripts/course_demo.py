"""Generate isolated Fake course cases, or serve their saved artifacts locally."""

import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from mcp import Client

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest, MetaResponse
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.trace import JsonTraceRecorder
from packages.domain.models import (
    AgentSpec,
    EpisodeArtifact,
    EventType,
    Message,
    ModelConfig,
    ModelResponse,
    RunConfig,
    TaskSpec,
    TerminationReason,
    ToolSchema,
)
from packages.providers.fake import FakeModelProvider
from packages.runtime.session import SessionState

ROOT = Path(__file__).resolve().parents[1]


def port_in_use(port: int) -> bool:
    """Detect existing localhost listeners without taking over their processes."""
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def preview(directory: Path) -> None:
    """Start the isolated API and Vite together; stop only these owned processes."""
    if any(port_in_use(port) for port in (8000, 5173)):
        raise RuntimeError("Port 8000 or 5173 is occupied; stop your own preview first")
    node = shutil.which("node")
    vite = ROOT / "apps/web/node_modules/vite/bin/vite.js"
    if node is None or not vite.is_file():
        raise RuntimeError("Install Node.js and run npm.cmd --prefix apps/web ci first")
    processes: list[subprocess.Popen[bytes]] = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (
        (directory / "preview-api.log").open("ab") as api_log,
        (directory / "preview-web.log").open("ab") as web_log,
    ):
        try:
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "scripts.course_demo",
                        "--serve",
                        "--artifacts-dir",
                        str(directory),
                    ],
                    cwd=ROOT,
                    stdout=api_log,
                    stderr=api_log,
                    creationflags=flags,
                )
            )
            processes.append(
                subprocess.Popen(
                    [node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
                    cwd=ROOT / "apps/web",
                    stdout=web_log,
                    stderr=web_log,
                    creationflags=flags,
                )
            )
            print(
                "Preview: http://127.0.0.1:5173/ ; links in demo-index.json ; Ctrl+C to stop",
                flush=True,
            )
            while all(process.poll() is None for process in processes):
                time.sleep(0.2)
            raise RuntimeError("Preview exited; inspect preview-api.log and preview-web.log")
        except KeyboardInterrupt:
            pass
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


class DemoService(EpisodeService):
    """Keep the isolated course preview offline with respect to model providers."""

    def get_meta(self) -> MetaResponse:
        """Show Fake as the only selectable model for this temporary preview."""
        meta = super().get_meta()
        models = [model for model in meta.models if model.provider == "fake"]
        return meta.model_copy(update={"models": models, "default_model": models[0].id})

    def _require_live_model(self, model_id: str) -> None:
        raise ValueError("This isolated course preview supports Fake models only")


def request(**overrides: object) -> CreateEpisodeRequest:
    """Use only the fixed Fake provider and public API request validation."""
    return CreateEpisodeRequest.model_validate(
        {"provider": "fake", "model": "fake-orders-v1", "scenario": "success", **overrides}
    )


def verify(artifact: EpisodeArtifact, reason: TerminationReason, success: bool) -> None:
    """Check independent evaluation and the one final-event invariant."""
    if (
        artifact.episode.termination_reason != reason
        or artifact.evaluation.success != success
        or sum(e.event_type == EventType.EPISODE_FINISHED for e in artifact.events) != 1
    ):
        raise RuntimeError(f"Unexpected outcome for {artifact.episode.episode_id}")


def interrupted_child(directory: Path) -> None:
    """Exit the child after the first tool result is durably checkpointed."""
    original = CheckpointStore.save

    def save(
        store: CheckpointStore,
        state: SessionState,
        agent: AgentSpec,
        task: TaskSpec,
        config: RunConfig,
        recorder: JsonTraceRecorder,
        fake_scenario: str | None = None,
    ) -> None:
        original(store, state, agent, task, config, recorder, fake_scenario)
        if state.next_node == "model" and state.budget.tool_call_count == 1:
            os._exit(75)

    with patch.object(CheckpointStore, "save", save):
        asyncio.run(EpisodeService(artifacts_dir=directory).execute_episode(request()))
    raise RuntimeError("The child did not reach its safe point")


async def local_cases(service: EpisodeService) -> dict[str, str]:
    """Create success, recovery comparison and an unanswered timed-out request."""
    clean = await service.execute_episode(request())
    verify(clean, TerminationReason.SUCCESS, True)
    comparison = await service.execute_experiment(
        CreateExperimentRequest(
            provider="fake",
            model="fake-orders-v1",
            scenario="invalid-then-success",
            task_ids=["order-status-001"],
            seeds=[1],
            repeat_count=1,
        )
    )
    baseline, recovery = [service.get_episode(id_) for id_ in comparison.episode_ids]
    if baseline is None or recovery is None:
        raise RuntimeError("Comparison artifacts were not saved")
    verify(baseline, TerminationReason.FAILED, False)
    verify(recovery, TerminationReason.SUCCESS, True)
    original = FakeModelProvider.generate

    async def slow(
        provider: FakeModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        await asyncio.sleep(0.25)
        return await original(provider, messages, tools, config)

    with patch.object(FakeModelProvider, "generate", slow):
        timeout = await service.execute_episode(request(max_execution_time_ms=40))
    verify(timeout, TerminationReason.TIME_BUDGET_EXCEEDED, False)
    if timeout.episode.tool_call_count or timeout.episode.estimated_cost.is_known:
        raise RuntimeError("Timeout must retain unknown usage and execute no tools")
    return {
        "success": str(clean.episode.episode_id),
        "argument_baseline": str(baseline.episode.episode_id),
        "argument_recovery": str(recovery.episode.episode_id),
        "comparison": str(comparison.experiment_id),
        "time_limit": str(timeout.episode.episode_id),
    }


def resume_case(directory: Path) -> str:
    """Resume in this process after a separate process actually exited."""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.course_demo", "--child", "--artifacts-dir", str(directory)],
        cwd=ROOT,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 75:
        raise RuntimeError(f"Child did not interrupt at a safe point (exit {result.returncode})")
    checkpoints = list((directory / "checkpoints").glob("*.json"))
    if len(checkpoints) != 1:
        raise RuntimeError("Expected exactly one interrupted checkpoint")
    episode_id = UUID(checkpoints[0].stem)
    saved = CheckpointStore(directory / "checkpoints").load(episode_id)
    committed = [event for event in saved.events if event.event_type == EventType.TOOL_STARTED]
    service = EpisodeService(artifacts_dir=directory)
    artifact = asyncio.run(service.resume_episode(episode_id))
    verify(artifact, TerminationReason.SUCCESS, True)
    started = [event for event in artifact.events if event.event_type == EventType.TOOL_STARTED]
    if (
        artifact.episode.episode_id != episode_id
        or started[: len(committed)] != committed
        or len(started) != 2
        or checkpoints[0].exists()
        or sum(e.event_type == EventType.EPISODE_RESUMED for e in artifact.events) != 1
    ):
        raise RuntimeError("Resume changed identity or repeated a committed tool")
    return str(episode_id)


async def network_cases(service: EpisodeService) -> dict[str, str]:
    """Exercise real SDK HTTP calls and compare against the same local task."""
    local = await service.execute_episode(request(task_id="order-status-007"))
    remote = await service.execute_episode(
        request(task_id="order-status-007", tool_transport="mcp")
    )
    for artifact in (local, remote):
        verify(artifact, TerminationReason.SUCCESS, True)
    if (
        local.episode.final_state != remote.episode.final_state
        or local.episode.token_usage != remote.episode.token_usage
        or local.episode.tool_call_count != remote.episode.tool_call_count
    ):
        raise RuntimeError("Local and MCP outcomes differ")
    transports = [
        event.payload.get("transport")
        for event in remote.events
        if event.event_type == EventType.TOOL_STARTED
    ]
    # Local submit has no transport field in the existing Trace contract.
    if transports != ["mcp", "mcp", None]:
        raise RuntimeError("MCP reads and local submission are mislabeled")
    disconnect = await service.execute_episode(
        request(task_id="order-status-007", tool_transport="mcp", fault_profile="mcp_disconnect")
    )
    verify(disconnect, TerminationReason.FAILED, False)
    if not any(event.event_type == EventType.TOOL_FAILED for event in disconnect.events):
        raise RuntimeError("Disconnect must have a recorded tool failure")
    return {
        "documents_local": str(local.episode.episode_id),
        "mcp_success": str(remote.episode.episode_id),
        "mcp_disconnect": str(disconnect.episode.episode_id),
    }


async def ready() -> None:
    """Wait for the owned server using actual MCP tools/list, not only an open port."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            async with Client("http://127.0.0.1:8765/mcp", read_timeout_seconds=1) as client:
                tools = await client.list_tools()
                if {tool.name for tool in tools.tools} == {"search_documents", "read_document"}:
                    return
        except Exception:
            await asyncio.sleep(0.1)
    raise RuntimeError("MCP startup failed; inspect mcp-server.log")


def generate(directory: Path, skip_mcp: bool) -> None:
    """Produce new artifacts without overwriting any earlier demonstration."""
    directory.mkdir(parents=True, exist_ok=False)
    service = EpisodeService(artifacts_dir=directory)
    cases = asyncio.run(local_cases(service))
    cases["resumed"] = resume_case(directory)
    if not skip_mcp:
        # Refuse to take over an existing listener, even if it looks like our MCP service.
        if port_in_use(8765):
            raise RuntimeError(
                "Port 8765 is occupied; keep this partial run and use a new directory"
            )
        with (directory / "mcp-server.log").open("wb") as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "packages.environments.tool_lab.mcp"],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                asyncio.run(ready())
                cases.update(asyncio.run(network_cases(service)))
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    report = {
        "schema_version": "1.0",
        "provider": "fake",
        "mcp_http_verified": not skip_mcp,
        "cases": cases,
        "links": {
            name: "http://127.0.0.1:5173/?"
            + f"{'experiment' if name == 'comparison' else 'episode'}_id={id_}"
            for name, id_ in cases.items()
        },
    }
    (directory / "demo-index.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'Preview: uv run python -m scripts.course_demo --preview --artifacts-dir "{directory}"')


def validate_preview_directory(directory: Path) -> None:
    """Accept generated course cases or a validated, completed Fake context report."""
    if (directory / "demo-index.json").is_file():
        return
    context_report = directory / "context-ablation.json"
    if context_report.is_file():
        from scripts.context_ablation import ContextReport

        report = ContextReport.model_validate_json(context_report.read_text(encoding="utf-8"))
        report.validate_artifacts(directory)
        return
    raise ValueError("Preview needs generated demo-index.json or context-ablation.json")


def main() -> None:
    """Generate cases or expose the explicit isolated folder on localhost only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument(
        "--skip-mcp", action="store_true", help="Local-only, explicitly incomplete demo"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--serve", action="store_true", help="Serve only the isolated API")
    mode.add_argument("--preview", action="store_true", help="Start isolated API and Web together")
    mode.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    directory = (args.artifacts_dir or ROOT / "artifacts/course-demo" / str(uuid4())).resolve()
    if args.serve or args.preview:
        if args.artifacts_dir is None:
            parser.error("Preview needs an explicit generated directory")
        try:
            validate_preview_directory(directory)
        except ValueError:
            parser.error("Preview needs a valid generated course or Fake context directory")
        if args.preview:
            preview(directory)
            return
        import uvicorn

        from apps.api.main import app, get_episode_service

        service = DemoService(artifacts_dir=directory)
        app.dependency_overrides[get_episode_service] = lambda: service
        uvicorn.run(app, host="127.0.0.1", port=8000)
    elif args.child:
        interrupted_child(directory)
    else:
        generate(directory, args.skip_mcp)


if __name__ == "__main__":
    main()
