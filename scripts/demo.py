"""CLI demo script executing M0 scenarios using the HandwrittenRuntime pipeline."""

import argparse
import asyncio
import sys
from pathlib import Path

from packages.application.runner import run_episode
from packages.application.trace import write_artifact
from packages.domain.models import AgentSpec, RunConfig, TaskSpec
from packages.environments.tool_lab.environment import (
    ToolLabEnvironment,
    create_tool_lab_registry,
)
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.handwritten.runtime import HandwrittenRuntime
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator

ROOT = Path(__file__).resolve().parents[1]


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments with validation."""
    parser = argparse.ArgumentParser(description="AgentLabyrinth M0 Scenario Runner")
    parser.add_argument(
        "--scenario",
        choices=["success", "wrong-answer", "invalid-arguments", "max-steps"],
        default="success",
        help="Execution scenario to run with FakeModelProvider",
    )
    parser.add_argument(
        "--provider",
        choices=["fake", "aihubmix"],
        default=None,
        help="Execution model provider (defaults to spec model provider)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override model name in AgentSpec (e.g. gemini-3.7-flash-free)",
    )
    parser.add_argument(
        "--agent",
        type=Path,
        default=None,
        help=(
            "Path to AgentSpec JSON file (defaults to baseline-m0 or aihubmix-m1 based on provider)"
        ),
    )
    parser.add_argument(
        "--task",
        type=Path,
        default=ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json",
        help="Path to TaskSpec JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/demo_trace.json",
        help="Output path for trace JSON artifact",
    )
    return parser.parse_args(args)


def main(cli_args: list[str] | None = None) -> int:
    """Main CLI entrypoint outside asyncio.run."""
    try:
        args = parse_args(cli_args)
    except SystemExit:
        return 2

    # Determine agent spec path if not specified
    agent_path = args.agent
    if agent_path is None:
        if args.provider == "aihubmix":
            agent_path = ROOT / "benchmarks/tool_lab_core/agents/aihubmix-m1.json"
        else:
            agent_path = ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json"

    # File IO outside asyncio.run
    try:
        agent_text = agent_path.read_text(encoding="utf-8")
        agent = AgentSpec.model_validate_json(agent_text)
    except Exception as exc:
        print(f"Config error loading agent from {agent_path}: {exc}", file=sys.stderr)
        return 2

    # Override provider or model if explicitly requested in CLI
    provider_type = args.provider or agent.model.provider
    if args.model or args.provider:
        new_provider = args.provider or agent.model.provider
        new_model = args.model or agent.model.model
        agent = agent.model_copy(
            update={
                "model": agent.model.model_copy(
                    update={"provider": new_provider, "model": new_model}
                )
            }
        )

    try:
        task_text = args.task.read_text(encoding="utf-8")
        task = TaskSpec.model_validate_json(task_text)
    except Exception as exc:
        print(f"Config error loading task from {args.task}: {exc}", file=sys.stderr)
        return 2

    run_config = RunConfig(seed=1, environment_version="tool-lab-m0-v1")

    # Wire up concrete implementations
    from packages.domain.ports import ModelProvider

    provider: ModelProvider
    if provider_type == "aihubmix":
        from packages.providers.aihubmix import AIHubMixModelProvider

        provider = AIHubMixModelProvider()
    else:
        provider = FakeModelProvider(scenario=args.scenario)

    registry = create_tool_lab_registry()
    validator = DefaultToolValidator(registry)
    executor = ToolExecutor(registry, validator)
    environment = ToolLabEnvironment(registry=registry, executor=executor, validator=validator)
    runtime = HandwrittenRuntime(provider=provider, validator=validator)
    evaluator = OrderStatusEvaluator()

    # Execute episode inside asyncio.run
    artifact = asyncio.run(
        run_episode(
            agent=agent,
            task=task,
            config=run_config,
            runtime=runtime,
            environment=environment,
            evaluator=evaluator,
        )
    )

    # File IO outside asyncio.run
    try:
        output_path = args.output if args.output.is_absolute() else (ROOT / args.output)
        write_artifact(artifact, output_path)
    except Exception as exc:
        print(f"Error saving artifact to {args.output}: {exc}", file=sys.stderr)
        return 1

    # CLI stdout presentation
    cost = artifact.episode.estimated_cost
    print("=" * 60)
    print(f"Demo Execution Summary (Provider: {provider_type}, Model: {agent.model.model})")
    print("=" * 60)
    print(f"Episode ID:         {artifact.episode.episode_id}")
    print(f"Termination Reason: {artifact.episode.termination_reason}")
    print(f"Detail:             {artifact.episode.detail}")
    print(f"Evaluation Success: {artifact.evaluation.success}")
    print(f"Evaluation Reason:  {artifact.evaluation.reason}")
    print(f"Step Count:         {artifact.episode.step_count}")
    print(f"Model Call Count:   {artifact.episode.model_call_count}")
    print(f"Tool Call Count:    {artifact.episode.tool_call_count}")
    print(
        f"Token Usage:        {artifact.episode.token_usage.prompt_tokens} prompt / "
        f"{artifact.episode.token_usage.completion_tokens} completion "
        f"(simulated={artifact.episode.token_usage.simulated})"
    )
    print(
        f"Estimated Cost:     ${cost.amount} USD "
        f"({cost.price_table_version}, known={cost.is_known})"
    )
    print(f"Trace Saved To:     {output_path}")
    print("=" * 60)

    return 0 if artifact.evaluation.success else 1


if __name__ == "__main__":
    sys.exit(main())
