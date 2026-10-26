"""Run offline memory checks or one explicit real-model, same-window pair."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from apps.api.schemas import CreateEpisodeRequest
from apps.api.service import EpisodeService
from packages.application.runner import run_episode
from packages.application.trace import content_hash, write_artifact, write_text_atomically
from packages.domain.models import AgentSpec, ContextPolicy, EventType, RuntimeBackend
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime
from scripts.context_ablation import load_inputs
from scripts.review_memory import successful_document_reads


async def run_ablation(directory: Path) -> list[dict[str, object]]:
    """Keep model/task/budget/window fixed when comparing window with memory."""
    directory.mkdir(parents=True, exist_ok=False)
    policies = (
        ("full", ContextPolicy()),
        ("window", ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=1)),
        (
            "memory",
            ContextPolicy(
                schema_version="1.1",
                algorithm_version="tool-round-window-memory-v1",
                mode="recent_tool_rounds",
                max_tool_rounds=1,
                memory_max_bytes=8192,
            ),
        ),
    )
    rows: list[dict[str, object]] = []
    backends: tuple[RuntimeBackend, ...] = ("handwritten", "langgraph")
    for backend in backends:
        base, tasks, config = load_inputs(backend)
        for label, policy in policies:
            agent = AgentSpec.model_validate({**base.model_dump(), "context_policy": policy})
            artifact = await run_episode(
                agent,
                tasks[1],
                config,
                create_runtime(agent, FakeModelProvider()),
                ToolLabEnvironment(),
                OrderStatusEvaluator(),
            )
            await asyncio.to_thread(
                write_artifact, artifact, directory / f"{artifact.episode.episode_id}.json"
            )
            contexts = [
                event.payload["context"]
                for event in artifact.events
                if event.event_type == EventType.MODEL_REQUESTED
            ]
            rows.append(
                {
                    "runtime": backend,
                    "strategy": label,
                    "episode_id": str(artifact.episode.episode_id),
                    "success": artifact.evaluation.success,
                    "termination": artifact.episode.termination_reason.value,
                    "model_calls": artifact.episode.model_call_count,
                    "tool_calls": artifact.episode.tool_call_count,
                    "simulated_tokens": artifact.episode.token_usage.prompt_tokens
                    + artifact.episode.token_usage.completion_tokens,
                    "config_hashes": artifact.config_hashes,
                    "contexts": contexts,
                }
            )
    await asyncio.to_thread(
        write_text_atomically,
        directory / "memory-ablation.json",
        json.dumps(
            {
                "schema_version": "1.0",
                "simulated": True,
                "cases": rows,
                "note": "Fake mechanism verification, not real model capability or token savings.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    return rows


async def run_window_pair(
    directory: Path, service: EpisodeService, model: str, *, provider: str = "aihubmix"
) -> list[dict[str, object]]:
    """Run just two fixed episodes; persist each row before starting the next arm."""
    directory.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, object]] = []
    fixed: tuple[dict[str, object], str, str] | None = None
    for label, policy in (
        ("window", ContextPolicy(mode="recent_tool_rounds", max_tool_rounds=1)),
        (
            "memory",
            ContextPolicy(
                schema_version="1.1",
                algorithm_version="tool-round-window-memory-v1",
                mode="recent_tool_rounds",
                max_tool_rounds=1,
                memory_max_bytes=8192,
            ),
        ),
    ):
        print(f"Starting {label}: {model}, return-evidence-chain-001", flush=True)
        artifact = await service.execute_episode(
            CreateEpisodeRequest.model_validate(
                dict(
                    provider=provider,
                    model=model,
                    task_id="return-evidence-chain-001",
                    runtime_backend="langgraph",
                    max_steps=10,
                    token_budget=20000,
                    max_execution_time_ms=300000,
                    context_policy=policy,
                )
            )
        )
        episode = artifact.episode
        saved = await asyncio.to_thread(service.get_episode, episode.episode_id)
        if saved != artifact or artifact.config_hashes != {
            "agent": content_hash(artifact.agent),
            "task": content_hash(artifact.task),
            "run_config": content_hash(artifact.run_config),
        }:
            raise ValueError("Memory pair artifact provenance mismatch")
        current = (
            artifact.agent.model_dump(exclude={"context_policy"}),
            artifact.config_hashes["task"],
            artifact.config_hashes["run_config"],
        )
        if fixed is not None and current != fixed:
            raise ValueError("Memory comparison changed a fixed variable")
        fixed = current
        reads = [row["document_id"] for row in successful_document_reads(artifact.events)]
        row: dict[str, object] = {
            "strategy": label,
            "episode_id": str(episode.episode_id),
            "model": artifact.agent.model.model,
            "provider": artifact.agent.model.provider,
            "task": artifact.task.name,
            "task_version": artifact.task.version,
            "success": artifact.evaluation.success,
            "evaluation_reason": artifact.evaluation.reason,
            "termination": episode.termination_reason.value,
            "detail": episode.detail,
            "model_calls": episode.model_call_count,
            "tool_calls": episode.tool_call_count,
            "usage": episode.token_usage.model_dump(mode="json"),
            "duration_ms": episode.duration_ms,
            "successful_document_reads": reads,
            "repeated_document_reads": len(reads) - len(set(reads)),
            "submission": episode.final_state.get("submission"),
            "config_hashes": artifact.config_hashes,
            "contexts": [
                event.payload["context"]
                for event in artifact.events
                if event.event_type == EventType.MODEL_REQUESTED
            ],
        }
        rows.append(row)
        await asyncio.to_thread(
            write_text_atomically,
            directory / "memory-pair.json",
            json.dumps(
                {
                    "schema_version": "1.0",
                    "simulated": provider == "fake",
                    "paired": len(rows) == 2,
                    "cases": rows,
                    "note": "One ordered exploratory pair, not a success rate or causal proof. "
                    "Repeated reads count successful reads of an already read document ID; "
                    "a zero count does not establish task completion or efficient reasoning.",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        print(json.dumps({k: v for k, v in row.items() if k != "contexts"}), flush=True)
        # No automatic retries or model substitution when the provider cannot respond.
        if episode.detail.startswith("provider_error"):
            break
    return rows


def main() -> None:
    """Print actual outcomes and fail when the controlled expectations are violated."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/episodic-memory") / str(uuid4())
    )
    parser.add_argument("--model", help="Explicitly run ONE AIHubMix model on a fixed two-arm task")
    args = parser.parse_args()
    if args.model:
        rows = asyncio.run(
            run_window_pair(args.output, EpisodeService(live_model_catalog=True), args.model)
        )
        if len(rows) != 2:
            raise SystemExit("Provider failed; partial evidence saved, no automatic retry")
        return
    rows = asyncio.run(run_ablation(args.output))
    print(
        json.dumps(
            {
                "directory": str(args.output),
                "cases": [{k: v for k, v in row.items() if k != "contexts"} for row in rows],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if any(row["success"] != (row["strategy"] != "window") for row in rows):
        raise SystemExit("Controlled memory ablation did not match expectations")


if __name__ == "__main__":
    main()
