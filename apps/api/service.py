"""Application service for running and retrieving ToolLab episodes and experiments."""

import json
from pathlib import Path
from uuid import UUID, uuid4

from apps.api.schemas import (
    ALLOWED_FAKE_SCENARIOS,
    CreateEpisodeRequest,
    CreateExperimentRequest,
    MetaResponse,
    ModelOption,
    TaskOption,
    is_model_permitted,
)
from packages.application.experiment import (
    ExperimentArtifact,
    read_experiment,
    run_experiment,
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
DEFAULT_TASKS_DIR = ROOT / "benchmarks/tool_lab_core/tasks"
DEFAULT_MODELS_PATH = ROOT / "benchmarks/tool_lab_core/models.json"
DEFAULT_AIHUBMIX_AGENT = ROOT / "benchmarks/tool_lab_core/agents/aihubmix-m1.json"
DEFAULT_FAKE_AGENT = ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json"
DEFAULT_RECOVERY_AGENT = ROOT / "benchmarks/tool_lab_core/agents/recovery-m1.json"


class EpisodeService:
    """Coordinates execution, persistence, and retrieval of episodes and experiments."""

    def __init__(
        self,
        artifacts_dir: Path | None = None,
        tasks_dir: Path | None = None,
        models_path: Path | None = None,
    ) -> None:
        self.artifacts_dir = artifacts_dir or DEFAULT_ARTIFACTS_DIR
        self.tasks_dir = tasks_dir or DEFAULT_TASKS_DIR
        self.models_path = models_path or DEFAULT_MODELS_PATH

    def _get_task(self, task_id: str) -> TaskSpec:
        """Load TaskSpec by ID from tasks directory."""
        task_path = self.tasks_dir / f"{task_id}.json"
        if not task_path.is_file():
            for p in self.tasks_dir.glob("*.json"):
                t = TaskSpec.model_validate_json(p.read_text(encoding="utf-8"))
                if t.name == task_id or str(t.id) == task_id:
                    return t
            raise ValueError(f"Task '{task_id}' not found")
        return TaskSpec.model_validate_json(task_path.read_text(encoding="utf-8"))

    def _load_all_tasks(self) -> list[TaskSpec]:
        """Load all TaskSpecs from tasks directory in sorted order."""
        tasks: list[TaskSpec] = []
        if self.tasks_dir.is_dir():
            for p in sorted(self.tasks_dir.glob("*.json")):
                tasks.append(TaskSpec.model_validate_json(p.read_text(encoding="utf-8")))
        return tasks

    def _load_configured_models(self) -> tuple[list[ModelOption], str]:
        """Load models from catalog JSON with fallback and dynamic upstream discovery."""
        default_model = "coding-glm-5.3-free"
        models: list[ModelOption] = []
        if self.models_path.is_file():
            try:
                data = json.loads(self.models_path.read_text(encoding="utf-8"))
                default_model = data.get("default_model", default_model)
                for item in data.get("models", []):
                    models.append(ModelOption.model_validate(item))
            except Exception:
                pass

        if not models:
            models = [
                ModelOption(
                    id="coding-glm-5.3-free",
                    name="Coding GLM 5.3 Free",
                    provider="aihubmix",
                    is_default=True,
                    is_experimental=False,
                    notes="智谱 GLM 5.3 免费模型，原生工具调用与真实用量报告正常",
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
            ]

        return models, default_model

    def get_meta(self) -> MetaResponse:
        """Return available models, tasks, and system defaults."""
        models, default_model = self._load_configured_models()

        task_specs = self._load_all_tasks()
        tasks: list[TaskOption] = [
            TaskOption(
                id=t.name,
                name=t.name,
                category=t.category,
                description=t.description,
                max_steps=t.max_steps,
                token_budget=t.token_budget,
            )
            for t in task_specs
        ]

        return MetaResponse(
            models=models,
            tasks=tasks,
            default_model=default_model,
            default_task="order-status-001",
        )

    async def execute_episode(self, req: CreateEpisodeRequest) -> EpisodeArtifact:
        """Assemble dependencies, run episode via HandwrittenRuntime, and persist artifact."""
        # 1. Validate requested model/scenario against permissive free model catalog
        if req.provider == "aihubmix":
            if not is_model_permitted(req.model):
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
        task = self._get_task(req.task_id)

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

    async def execute_experiment(self, req: CreateExperimentRequest) -> ExperimentArtifact:
        """Run paired Baseline vs Recovery experiment serially and persist aggregate artifact."""
        if not req.task_ids:
            raise ValueError("Experiment requires at least one task ID")

        # 1. Load tasks
        tasks = [self._get_task(tid) for tid in req.task_ids]

        # 2. Validate requested model/scenario and configure agents & provider factory
        if req.provider == "aihubmix":
            if not is_model_permitted(req.model):
                raise ValueError(f"Model '{req.model}' is not in the allowed free model whitelist")
            base_text = DEFAULT_AIHUBMIX_AGENT.read_text(encoding="utf-8")
            baseline_agent = AgentSpec.model_validate_json(base_text)
            baseline_agent = baseline_agent.model_copy(
                update={
                    "model": baseline_agent.model.model_copy(
                        update={"provider": "aihubmix", "model": req.model}
                    ),
                    "runtime_strategy": "handwritten",
                }
            )
            recovery_agent = baseline_agent.model_copy(
                update={
                    "id": uuid4(),
                    "name": f"{baseline_agent.name}-recovery",
                    "runtime_strategy": "handwritten_recovery",
                }
            )

            def provider_factory() -> ModelProvider:
                return AIHubMixModelProvider()

        elif req.provider == "fake":
            scenario = req.scenario or "invalid-then-success"
            if scenario == "clean":
                scenario = "success"
            if scenario not in ALLOWED_FAKE_SCENARIOS:
                raise ValueError(f"Scenario '{scenario}' is not in allowed fake scenarios")
            base_text = DEFAULT_FAKE_AGENT.read_text(encoding="utf-8")
            baseline_agent = AgentSpec.model_validate_json(base_text)
            rec_text = DEFAULT_RECOVERY_AGENT.read_text(encoding="utf-8")
            recovery_agent = AgentSpec.model_validate_json(rec_text)

            def provider_factory() -> ModelProvider:
                return FakeModelProvider(scenario=scenario)

        else:
            raise ValueError(f"Unsupported provider: {req.provider}")

        # 3. Run paired experiment
        config_metadata = {
            "provider": req.provider,
            "model": req.model,
            "scenario": req.scenario,
            "task_ids": req.task_ids,
            "seed": req.seed,
            "baseline_strategy": baseline_agent.runtime_strategy,
            "recovery_strategy": recovery_agent.runtime_strategy,
        }

        return await run_experiment(
            baseline_agent=baseline_agent,
            recovery_agent=recovery_agent,
            tasks=tasks,
            provider_factory=provider_factory,
            seed=req.seed,
            artifacts_dir=self.artifacts_dir,
            config_metadata=config_metadata,
        )

    def get_experiment(self, experiment_id: UUID) -> ExperimentArtifact | None:
        """Strictly read previously saved ExperimentArtifact from disk without invoking models."""
        target_file = self.artifacts_dir / "experiments" / f"{experiment_id}.json"
        if not target_file.is_file():
            return None
        return read_experiment(target_file)
