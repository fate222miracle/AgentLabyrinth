"""Run deterministic fake and exploratory real experiments for M1 Slice C."""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.application.experiment import run_experiment  # noqa: E402
from packages.domain.models import AgentSpec, TaskSpec  # noqa: E402
from packages.domain.ports import ModelProvider  # noqa: E402
from packages.providers.aihubmix import AIHubMixModelProvider, get_aihubmix_api_key  # noqa: E402
from packages.providers.fake import FakeModelProvider  # noqa: E402

ARTIFACTS_DIR = ROOT / "artifacts"
TASKS_DIR = ROOT / "benchmarks/tool_lab_core/tasks"
AGENTS_DIR = ROOT / "benchmarks/tool_lab_core/agents"


def load_task(filename: str) -> TaskSpec:
    return TaskSpec.model_validate_json((TASKS_DIR / filename).read_text(encoding="utf-8"))


async def main() -> None:
    task_files = [
        "order-status-001.json",
        "order-status-002.json",
        "order-status-003.json",
        "order-status-004.json",
    ]
    tasks = [load_task(f) for f in task_files]

    # ==========================================
    # 1. Deterministic Fake Experiment
    # ==========================================
    print("\n==========================================")
    print(" Running Deterministic Fake Experiment")
    print(" Scenario: invalid_then_success (4 tasks)")
    print("==========================================")

    fake_base_agent = AgentSpec.model_validate_json(
        (AGENTS_DIR / "baseline-m0.json").read_text(encoding="utf-8")
    )
    fake_rec_agent = AgentSpec.model_validate_json(
        (AGENTS_DIR / "recovery-m1.json").read_text(encoding="utf-8")
    )

    def fake_factory() -> ModelProvider:
        return FakeModelProvider(scenario="invalid_then_success")

    fake_exp = await run_experiment(
        baseline_agent=fake_base_agent,
        recovery_agent=fake_rec_agent,
        tasks=tasks,
        provider_factory=fake_factory,
        seed=1,
        artifacts_dir=ARTIFACTS_DIR,
        config_metadata={
            "experiment_type": "deterministic_fake_invalid_then_success",
            "provider": "fake",
            "model": "fake-orders-v1",
            "scenario": "invalid-then-success",
            "task_ids": [t.name for t in tasks],
            "seed": 1,
        },
    )

    print(f"Fake Experiment ID: {fake_exp.experiment_id}")
    print(f"Total Pairs: {fake_exp.metrics.total_pairs}")
    b_succ = fake_exp.metrics.baseline_success_count
    r_succ = fake_exp.metrics.recovery_success_count
    tot = fake_exp.metrics.total_pairs
    print(f"Baseline Success: {b_succ} / {tot}")
    print(f"Recovery Success: {r_succ} / {tot}")
    print(f"Retry Recovery Count: {fake_exp.metrics.retry_recovery_count}")
    print(f"Retry Recovery Rate: {fake_exp.metrics.retry_recovery_rate:.1%}")
    print(f"Baseline Total Tokens: {fake_exp.metrics.baseline_total_tokens}")
    print(f"Recovery Total Tokens: {fake_exp.metrics.recovery_total_tokens}")
    delta = fake_exp.metrics.recovery_total_tokens - fake_exp.metrics.baseline_total_tokens
    print(f"Token Delta: +{delta}")

    for p in fake_exp.pairs:
        print(
            f"  - {p.task_id}: Base={p.baseline_success} ({p.baseline_termination_reason}), "
            f"Rec={p.recovery_success} ({p.recovery_termination_reason}), "
            f"Recovered={p.recovered}, Tokens: {p.baseline_tokens} -> {p.recovery_tokens}"
        )

    # ==========================================
    # 2. Real Model Exploratory Experiment (Coding GLM 5.3 Free)
    # ==========================================
    target_real_model = "coding-glm-5.3-free"
    print("\n==========================================")
    print(f" Running Real Model Experiment ({target_real_model})")
    print("==========================================")
    try:
        get_aihubmix_api_key()
        has_key = True
    except Exception:
        has_key = False
        print("No AIHubMix API key configured, skipping real model run.")

    if has_key:
        real_base_text = (AGENTS_DIR / "aihubmix-m1.json").read_text(encoding="utf-8")
        real_base_agent = AgentSpec.model_validate_json(real_base_text)
        real_base_agent = real_base_agent.model_copy(
            update={
                "model": real_base_agent.model.model_copy(
                    update={"provider": "aihubmix", "model": target_real_model}
                ),
                "runtime_strategy": "handwritten",
            }
        )
        real_rec_agent = real_base_agent.model_copy(
            update={
                "id": uuid4(),
                "name": f"{real_base_agent.name}-recovery",
                "runtime_strategy": "handwritten_recovery",
            }
        )

        def real_factory() -> ModelProvider:
            return AIHubMixModelProvider()

        # Run 2 representative tasks (ORD-001 shipped, ORD-002 delivered)
        real_tasks = tasks[:2]
        real_exp = await run_experiment(
            baseline_agent=real_base_agent,
            recovery_agent=real_rec_agent,
            tasks=real_tasks,
            provider_factory=real_factory,
            seed=1,
            artifacts_dir=ARTIFACTS_DIR,
            config_metadata={
                "experiment_type": "real_model_exploratory",
                "provider": "aihubmix",
                "model": target_real_model,
                "task_ids": [t.name for t in real_tasks],
                "seed": 1,
            },
        )

        print(f"Real Experiment ID: {real_exp.experiment_id}")
        print(f"Total Pairs: {real_exp.metrics.total_pairs}")
        rb_succ = real_exp.metrics.baseline_success_count
        rr_succ = real_exp.metrics.recovery_success_count
        rtot = real_exp.metrics.total_pairs
        print(f"Baseline Success: {rb_succ} / {rtot}")
        print(f"Recovery Success: {rr_succ} / {rtot}")
        print(f"Retry Recovery Count: {real_exp.metrics.retry_recovery_count}")
        print(f"Retry Recovery Rate: {real_exp.metrics.retry_recovery_rate:.1%}")
        print(f"Baseline Total Tokens: {real_exp.metrics.baseline_total_tokens}")
        print(f"Recovery Total Tokens: {real_exp.metrics.recovery_total_tokens}")
        print(f"Is Cost Known: {real_exp.metrics.is_cost_known}")

        for p in real_exp.pairs:
            print(
                f"  - {p.task_id}: Base={p.baseline_success} ({p.baseline_termination_reason}), "
                f"Rec={p.recovery_success} ({p.recovery_termination_reason}), "
                f"Recovered={p.recovered}, Tokens: {p.baseline_tokens} -> {p.recovery_tokens}"
            )


if __name__ == "__main__":
    asyncio.run(main())
