"""Application service for running and retrieving ToolLab episodes."""

from pathlib import Path
from uuid import UUID

from apps.api.schemas import (
    ALLOWED_AIHUBMIX_MODELS,
    ALLOWED_FAKE_SCENARIOS,
    CreateEpisodeRequest,
    MetaResponse,
    ModelOption,
    TaskOption,
)
from packages.application.runner import run_episode
from packages.application.trace import read_artifact, write_artifact
from packages.domain.models import AgentSpec, EpisodeArtifact, RunConfig, TaskSpec
from packages.domain.ports import ModelProvider
from packages.environments.tool_lab.environment import (
    ToolLabEnvironment,
    create_tool_lab_registry,
)
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.aihubmix import AIHubMixModelProvider
from packages.providers.fake import FakeModelProvider
from packages.runtime.handwritten.runtime import HandwrittenRuntime
from packages.tools.executor import ToolExecutor
from packages.tools.registry import DefaultToolValidator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS_DIR = ROOT / "artifacts"
DEFAULT_TASK_PATH = ROOT / "benchmarks/tool_lab_core/tasks/order-status-001.json"
DEFAULT_AIHUBMIX_AGENT = ROOT / "benchmarks/tool_lab_core/agents/aihubmix-m1.json"
DEFAULT_FAKE_AGENT = ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json"


class EpisodeService:
    """Coordinates execution, persistence, and retrieval of episodes."""

    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self.artifacts_dir = artifacts_dir or DEFAULT_ARTIFACTS_DIR

    def get_meta(self) -> MetaResponse:
        """Return available models, tasks, and system defaults."""
        models: list[ModelOption] = [
            ModelOption(
                id="gemini-3.7-flash-free",
                name="Gemini 3.7 Flash Free",
                provider="aihubmix",
                is_default=True,
                is_experimental=False,
                notes="已实测推荐，双向工具调用完整通过 (639 prompt / 166 completion tokens)",
            ),
            ModelOption(
                id="fake",
                name="Fake / Mock Engine (离线测试)",
                provider="fake",
                is_default=False,
                is_experimental=False,
                notes="确定性离线模拟场景，无需 API Key 与网络连接",
                scenarios=sorted(ALLOWED_FAKE_SCENARIOS),
            ),
            ModelOption(
                id="coding-kimi-k3-free",
                name="Coding Kimi K3 Free",
                provider="aihubmix",
                is_default=False,
                is_experimental=True,
                notes="实验性：上游网关通道偶发离线 (UPSTREAM_CHANNEL_UNAVAILABLE)",
            ),
            ModelOption(
                id="coding-glm-5.3-flash-free",
                name="Coding GLM 5.3 Flash Free",
                provider="aihubmix",
                is_default=False,
                is_experimental=True,
                notes="实验性：复杂参数输出嵌套字符串 JSON，触发严格校验拦截",
            ),
            ModelOption(
                id="deepseek-v4-flash-0731-free",
                name="DeepSeek V4 Flash 0731 Free",
                provider="aihubmix",
                is_default=False,
                is_experimental=True,
                notes="实验性：Prompt 消耗偏大 (>1500 tokens)，触发 1000 Token 预算熔断",
            ),
        ]

        tasks: list[TaskOption] = [
            TaskOption(
                id="order-status-001",
                name="查询模拟订单 ORD-001",
                category="tool_selection",
                description="查询模拟订单 ORD-001 的状态，并提交状态及该订单记录的证据 ID。",
                max_steps=6,
                token_budget=1000,
            )
        ]

        return MetaResponse(
            models=models,
            tasks=tasks,
            default_model="gemini-3.7-flash-free",
            default_task="order-status-001",
        )

    async def execute_episode(self, req: CreateEpisodeRequest) -> EpisodeArtifact:
        """Assemble dependencies, run episode via HandwrittenRuntime, and persist artifact."""
        # 1. Validate requested model/scenario against whitelist
        if req.provider == "aihubmix":
            if req.model not in ALLOWED_AIHUBMIX_MODELS:
                raise ValueError(f"Model '{req.model}' is not in the allowed free model whitelist")
            provider: ModelProvider = AIHubMixModelProvider()
            agent_text = DEFAULT_AIHUBMIX_AGENT.read_text(encoding="utf-8")
            agent = AgentSpec.model_validate_json(agent_text)
            agent = agent.model_copy(
                update={
                    "model": agent.model.model_copy(
                        update={"provider": "aihubmix", "model": req.model}
                    )
                }
            )
        elif req.provider == "fake":
            scenario = req.scenario or "success"
            if scenario not in ALLOWED_FAKE_SCENARIOS:
                raise ValueError(f"Scenario '{scenario}' is not in allowed fake scenarios")
            provider = FakeModelProvider(scenario=scenario)
            agent_text = DEFAULT_FAKE_AGENT.read_text(encoding="utf-8")
            agent = AgentSpec.model_validate_json(agent_text)
        else:
            raise ValueError(f"Unsupported provider: {req.provider}")

        # Override budget steps if specified
        if req.max_steps is not None:
            agent = agent.model_copy(
                update={"budget": agent.budget.model_copy(update={"max_steps": req.max_steps})}
            )

        # 2. Load Task
        task_text = DEFAULT_TASK_PATH.read_text(encoding="utf-8")
        task = TaskSpec.model_validate_json(task_text)

        # 3. Assemble components
        registry = create_tool_lab_registry()
        validator = DefaultToolValidator(registry)
        executor = ToolExecutor(registry, validator)
        environment = ToolLabEnvironment(registry=registry, executor=executor, validator=validator)
        runtime = HandwrittenRuntime(provider=provider, validator=validator)
        evaluator = OrderStatusEvaluator()
        run_config = RunConfig(seed=1, environment_version="tool-lab-m0-v1")

        # 4. Execute episode
        artifact = await run_episode(
            agent=agent,
            task=task,
            config=run_config,
            runtime=runtime,
            environment=environment,
            evaluator=evaluator,
        )

        # 5. Persist independent JSON artifact
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = self.artifacts_dir / f"{artifact.episode.episode_id}.json"
        write_artifact(artifact, artifact_path)

        return artifact

    def get_episode(self, episode_id: UUID) -> EpisodeArtifact | None:
        """Strictly read previously saved artifact from disk without invoking any model."""
        target_file = self.artifacts_dir / f"{episode_id}.json"
        if not target_file.is_file():
            return None
        return read_artifact(target_file)
