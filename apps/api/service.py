"""Application service for running and retrieving ToolLab episodes and experiments."""

import json
from pathlib import Path
from time import monotonic, time_ns
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
from packages.application.checkpoint import (
    CheckpointStore,
    resume_checkpointed_episode,
    run_checkpointed_episode,
)
from packages.application.experiment import (
    ExperimentArtifact,
    read_experiment,
    run_experiment,
)
from packages.application.runner import run_episode
from packages.application.trace import read_artifact, write_artifact
from packages.domain.models import AgentSpec, EpisodeArtifact, RunConfig, TaskSpec
from packages.domain.ports import Environment, Evaluator, ModelProvider
from packages.environments.bfcl.adapter import BFCLAdapter
from packages.environments.bfcl.environment import BFCLEnvironment
from packages.environments.tool_lab.environment import (
    ToolLabEnvironment,
    create_tool_lab_registry,
)
from packages.environments.tool_lab.mcp import MCPToolLabEnvironment
from packages.evaluation.bfcl import BFCLEvaluator
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.aihubmix import AIHubMixModelProvider, list_available_model_ids
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime, runtime_version
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
        live_model_catalog: bool = False,
    ) -> None:
        self.artifacts_dir = artifacts_dir or DEFAULT_ARTIFACTS_DIR
        self.tasks_dir = tasks_dir or DEFAULT_TASKS_DIR
        self.models_path = models_path or DEFAULT_MODELS_PATH
        self.live_model_catalog = live_model_catalog
        self._live_model_ids: set[str] = set()
        self._model_catalog_expires_at = 0.0
        self._model_catalog_status = "static"
        self.bfcl = BFCLAdapter()
        self._started_ns = time_ns()
        self._resuming: set[UUID] = set()

    def _get_live_model_ids(self) -> set[str]:
        """Cache the API-key-scoped model catalog briefly to keep metadata responsive."""
        if not self.live_model_catalog:
            return set()
        now = monotonic()
        if now < self._model_catalog_expires_at:
            return self._live_model_ids
        try:
            self._live_model_ids = list_available_model_ids()
            self._model_catalog_status = "live"
            self._model_catalog_expires_at = now + 300
        except Exception:
            self._live_model_ids = set()
            self._model_catalog_status = "unavailable"
            self._model_catalog_expires_at = now + 30
        return self._live_model_ids

    def _configured_model_ids(self) -> set[str]:
        """Read the curated free-model shortlist from the single catalog file."""
        try:
            data = json.loads(self.models_path.read_text(encoding="utf-8"))
            return {
                item["id"]
                for item in data.get("models", [])
                if item.get("provider") == "aihubmix" and isinstance(item.get("id"), str)
            }
        except (OSError, ValueError, TypeError):
            return set()

    def _get_task(self, task_id: str) -> TaskSpec:
        """Resolve only catalog entries; user input is never used as a path."""
        for task in self._load_all_tasks():
            if task_id in (task.name, str(task.id)):
                return task
        raise ValueError("Task not found in the selected suite")

    @staticmethod
    def _with_token_budget(task: TaskSpec, token_budget: int | None) -> TaskSpec:
        """Record an explicit run override while keeping source tasks unchanged."""
        if token_budget is None:
            return task
        return task.model_copy(
            update={
                "token_budget": token_budget,
                "evaluator_config": {
                    **task.evaluator_config,
                    "source_token_budget": task.token_budget,
                },
            }
        )

    @staticmethod
    def _agent_with_token_budget(agent: AgentSpec, token_budget: int | None) -> AgentSpec:
        """Keep agent and task limits consistent for an explicit override."""
        if token_budget is None:
            return agent
        return agent.model_copy(
            update={
                "budget": agent.budget.model_copy(
                    update={
                        "max_prompt_tokens": token_budget,
                        "max_completion_tokens": token_budget,
                    }
                )
            }
        )

    def _load_all_tasks(self) -> list[TaskSpec]:
        """Load all TaskSpecs from tasks directory in sorted order."""
        tasks: list[TaskSpec] = []
        if self.tasks_dir.is_dir():
            for p in sorted(self.tasks_dir.glob("*.json")):
                tasks.append(TaskSpec.model_validate_json(p.read_text(encoding="utf-8")))
        return tasks

    def _load_configured_models(self) -> tuple[list[ModelOption], str]:
        """Load models from catalog JSON with fallback and dynamic upstream discovery."""
        default_model = "coding-minimax-m2.7-free"
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
                    id="coding-minimax-m2.7-free",
                    name="Coding MiniMax M2.7 Free",
                    provider="aihubmix",
                    is_default=True,
                    is_experimental=False,
                    notes="当前默认免费模型；可用性以 AIHubMix 当前目录与账号配额为准",
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

        if self.live_model_catalog:
            live_ids = self._get_live_model_ids()
            models = [model for model in models if model.provider == "fake" or model.id in live_ids]
            if default_model not in {model.id for model in models}:
                default_model = next(
                    (model.id for model in models if model.provider == "aihubmix"), "fake"
                )

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
                suite="tool_lab_core",
                split=str(t.evaluator_config.get("split", "development")),
                supports_mcp=bool(t.initial_state.get("documents"))
                and {"search_documents", "read_document"}.issubset(t.expected_tools),
            )
            for t in task_specs
        ]
        try:
            tasks.extend(
                TaskOption(
                    id=t.name,
                    name=t.name,
                    category=t.category,
                    description=t.description,
                    max_steps=t.max_steps,
                    token_budget=t.token_budget,
                    suite="bfcl_adapted",
                    split=str(t.evaluator_config.get("split", "evaluation")),
                )
                for t in self.bfcl.tasks()
            )
        except (FileNotFoundError, ValueError):
            pass

        return MetaResponse(
            models=models,
            tasks=tasks,
            default_model=default_model,
            default_task="order-status-001",
            model_catalog_status=self._model_catalog_status,
        )

    def _require_live_model(self, model_id: str) -> None:
        """Reject real model IDs absent from the current user's live catalog."""
        if self.live_model_catalog and model_id not in self._get_live_model_ids():
            raise ValueError("Model is not currently available in this AIHubMix API key catalog")

    async def execute_episode(self, req: CreateEpisodeRequest) -> EpisodeArtifact:
        """Assemble the selected runtime and suite, execute, and persist the episode."""
        # 1. Validate requested model/scenario against permissive free model catalog
        if req.provider == "aihubmix":
            if not is_model_permitted(req.model, self._configured_model_ids()):
                raise ValueError(f"Model '{req.model}' is not in the allowed free model whitelist")
            self._require_live_model(req.model)
            provider: ModelProvider = AIHubMixModelProvider(min_request_interval=13.0)
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
        bfcl_case = None
        if req.suite == "bfcl_adapted":
            bfcl_case, loaded_task = self.bfcl.case_for_task(req.task_id)
        else:
            loaded_task = self._get_task(req.task_id)
        task = self._with_token_budget(loaded_task, req.token_budget)
        if req.tool_transport == "mcp" and (
            req.suite != "tool_lab_core"
            or not task.initial_state.get("documents")
            or not {"search_documents", "read_document"}.issubset(task.expected_tools)
        ):
            raise ValueError("MCP transport supports only ToolLab document tasks")
        agent = self._agent_with_token_budget(agent, req.token_budget)
        agent = agent.model_copy(
            update={
                "schema_version": "1.1",
                "runtime_backend": req.runtime_backend,
                "runtime_strategy": req.runtime_strategy,
            }
        )

        # 3. Assemble components
        environment: Environment
        evaluator: Evaluator
        if bfcl_case is not None:
            bfcl_environment = BFCLEnvironment(bfcl_case)
            environment = bfcl_environment
            validator = bfcl_environment.validator
            evaluator = BFCLEvaluator()
            environment_version = "bfcl-adapted-single-call-v1"
            agent = agent.model_copy(update={"tool_set_version": "bfcl-v4-pinned"})
        else:
            if req.tool_transport == "mcp":
                environment = MCPToolLabEnvironment()
                validator = environment._validator
            else:
                registry = create_tool_lab_registry()
                validator = DefaultToolValidator(registry)
                executor = ToolExecutor(registry, validator)
                environment = ToolLabEnvironment(
                    registry=registry, executor=executor, validator=validator
                )
            evaluator = OrderStatusEvaluator()
            environment_version = (
                "tool-lab-mcp-v1" if req.tool_transport == "mcp" else "tool-lab-m0-v1"
            )
        runtime = create_runtime(agent, provider, validator)
        run_config = RunConfig(
            seed=1,
            environment_version=environment_version,
            runtime_version=runtime_version(agent.runtime_backend),
        )

        # 4. Execute episode
        if bfcl_case is None and req.tool_transport == "local":
            return await run_checkpointed_episode(
                agent,
                task,
                run_config,
                runtime,
                environment,
                evaluator,
                self.artifacts_dir,
                fake_scenario=(req.scenario or "success") if req.provider == "fake" else None,
            )
        artifact = await run_episode(
            agent,
            task,
            run_config,
            runtime,
            environment,
            evaluator,
        )
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        write_artifact(artifact, self.artifacts_dir / f"{artifact.episode.episode_id}.json")

        return artifact

    def get_episode(self, episode_id: UUID) -> EpisodeArtifact | None:
        """Strictly read previously saved artifact from disk without invoking any model."""
        target_file = self.artifacts_dir / f"{episode_id}.json"
        if not target_file.is_file():
            return None
        return read_artifact(target_file)

    def resumable_episode_ids(self) -> list[UUID]:
        """Show only unfinished checkpoints saved before this API instance started."""
        store = CheckpointStore(self.artifacts_dir / "checkpoints")
        result: list[UUID] = []
        for path in store.directory.glob("*.json"):
            try:
                episode_id = UUID(path.stem)
                if (
                    path.stat().st_mtime_ns < self._started_ns
                    and not (self.artifacts_dir / f"{episode_id}.json").is_file()
                    and episode_id not in self._resuming
                ):
                    result.append(episode_id)
            except (ValueError, OSError):
                continue
        return sorted(result)

    async def resume_episode(self, episode_id: UUID) -> EpisodeArtifact:
        """Restore a prior API instance's unfinished ToolLab episode."""
        if episode_id not in self.resumable_episode_ids():
            raise ValueError("No resumable episode exists for this API instance")
        self._resuming.add(episode_id)
        try:
            return await self._resume_episode_once(episode_id)
        finally:
            self._resuming.discard(episode_id)

    async def _resume_episode_once(self, episode_id: UUID) -> EpisodeArtifact:
        """Assemble the saved provider and continue one claimed Episode."""
        checkpoint = CheckpointStore(self.artifacts_dir / "checkpoints").load(episode_id)
        if checkpoint.agent.model.provider == "fake":
            scenario = checkpoint.fake_scenario or "success"
            if scenario not in ALLOWED_FAKE_SCENARIOS:
                raise ValueError("Unsupported saved Fake scenario")
            provider: ModelProvider = FakeModelProvider(
                scenario=scenario,
                initial_call_count=checkpoint.session.budget.model_call_count,
            )
        else:
            model_id = checkpoint.agent.model.model
            if not is_model_permitted(model_id, self._configured_model_ids()):
                raise ValueError("Saved model is no longer permitted")
            self._require_live_model(model_id)
            provider = AIHubMixModelProvider(min_request_interval=13.0)
        registry = create_tool_lab_registry()
        validator = DefaultToolValidator(registry)
        environment = ToolLabEnvironment(
            registry=registry, executor=ToolExecutor(registry, validator), validator=validator
        )
        return await resume_checkpointed_episode(
            episode_id,
            create_runtime(checkpoint.agent, provider, validator),
            environment,
            OrderStatusEvaluator(),
            self.artifacts_dir,
        )

    async def execute_experiment(self, req: CreateExperimentRequest) -> ExperimentArtifact:
        """Run a paired policy or runtime comparison and persist its artifact."""
        if not req.task_ids:
            raise ValueError("Experiment requires at least one task ID")
        resolved_seeds = req.seeds if req.seeds is not None else [req.seed]
        if len(set(resolved_seeds)) != len(resolved_seeds):
            raise ValueError("Experiment seeds must be unique")

        # 1. Load tasks
        tasks = [
            self._with_token_budget(self._get_task(tid), req.token_budget) for tid in req.task_ids
        ]

        # 2. Validate requested model/scenario and configure agents & provider factory
        if req.provider == "aihubmix":
            if not is_model_permitted(req.model, self._configured_model_ids()):
                raise ValueError(f"Model '{req.model}' is not in the allowed free model whitelist")
            self._require_live_model(req.model)
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
                return AIHubMixModelProvider(min_request_interval=13.0)

            resolved_scenario: str | None = None

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

            if req.model:
                baseline_agent = baseline_agent.model_copy(
                    update={"model": baseline_agent.model.model_copy(update={"model": req.model})}
                )
                recovery_agent = recovery_agent.model_copy(
                    update={"model": recovery_agent.model.model_copy(update={"model": req.model})}
                )

            def provider_factory() -> ModelProvider:
                return FakeModelProvider(scenario=scenario)

            resolved_scenario = scenario

        else:
            raise ValueError(f"Unsupported provider: {req.provider}")

        # 3. Run paired experiment
        baseline_agent = self._agent_with_token_budget(baseline_agent, req.token_budget)
        recovery_agent = self._agent_with_token_budget(recovery_agent, req.token_budget)
        if req.comparison_axis == "runtime_backend":
            baseline_agent = baseline_agent.model_copy(
                update={
                    "schema_version": "1.1",
                    "runtime_backend": "handwritten",
                    "runtime_strategy": req.runtime_strategy,
                }
            )
            recovery_agent = baseline_agent.model_copy(
                update={
                    "id": uuid4(),
                    "name": f"{baseline_agent.name}-langgraph",
                    "runtime_backend": "langgraph",
                }
            )
        else:
            baseline_agent = baseline_agent.model_copy(
                update={
                    "schema_version": "1.1",
                    "runtime_backend": req.runtime_backend,
                }
            )
            recovery_agent = recovery_agent.model_copy(
                update={
                    "schema_version": "1.1",
                    "runtime_backend": req.runtime_backend,
                }
            )
        config_metadata = {
            "provider": req.provider,
            "requested_model": req.model,
            "scenario": resolved_scenario,
            "token_budget": req.token_budget,
            "task_ids": req.task_ids,
            "seed": resolved_seeds[0],
            "seeds": resolved_seeds,
            "repeat_count": req.repeat_count,
            "baseline_strategy": baseline_agent.runtime_strategy,
            "recovery_strategy": recovery_agent.runtime_strategy,
            "baseline_backend": baseline_agent.runtime_backend,
            "recovery_backend": recovery_agent.runtime_backend,
            "comparison_axis": req.comparison_axis,
        }

        return await run_experiment(
            baseline_agent=baseline_agent,
            recovery_agent=recovery_agent,
            tasks=tasks,
            provider_factory=provider_factory,
            seed=resolved_seeds[0],
            seeds=resolved_seeds,
            repeat_count=req.repeat_count,
            artifacts_dir=self.artifacts_dir,
            config_metadata=config_metadata,
            comparison_axis=req.comparison_axis,
        )

    def get_experiment(self, experiment_id: UUID) -> ExperimentArtifact | None:
        """Strictly read previously saved ExperimentArtifact from disk without invoking models."""
        target_file = self.artifacts_dir / "experiments" / f"{experiment_id}.json"
        if not target_file.is_file():
            return None
        return read_experiment(target_file)
