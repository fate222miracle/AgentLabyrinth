"""Application service for running and retrieving ToolLab episodes and experiments."""

import asyncio
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, time_ns
from uuid import UUID, uuid4

from apps.api.schemas import (
    ALLOWED_FAKE_SCENARIOS,
    CreateEpisodeRequest,
    CreateExperimentRequest,
    ExperimentDashboardItem,
    ExperimentDashboardResponse,
    ExperimentJobState,
    FaultProfile,
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
    compute_config_hash,
    experiment_checkpoint_path,
    read_experiment,
    read_experiment_checkpoint,
    run_experiment,
)
from packages.application.reference_pricing import reference_price_version
from packages.application.regression import fixed_config
from packages.application.trace import read_artifact, write_text_atomically
from packages.domain.models import AgentSpec, EpisodeArtifact, RunConfig, TaskSpec, TraceEvent
from packages.domain.ports import Environment, Evaluator, ModelProvider, ToolValidator
from packages.environments.bfcl.adapter import ROOT as BFCL_ROOT
from packages.environments.bfcl.adapter import BFCLAdapter
from packages.environments.bfcl.environment import BFCLEnvironment
from packages.environments.tool_lab.environment import (
    ToolLabEnvironment,
    create_tool_lab_registry,
)
from packages.environments.tool_lab.mcp import MCP_DISCONNECTED_URL, MCPToolLabEnvironment
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


class ExperimentJobStopped(Exception):
    """A user requested a stop at an Experiment Episode boundary."""

    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__(action)


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
        self._model_catalog_lock = threading.Lock()
        self.bfcl = BFCLAdapter()
        self.bfcl_java = BFCLAdapter(
            BFCL_ROOT / "benchmarks/bfcl_java_adapted/dataset_manifest.json",
            BFCL_ROOT / ".cache/bfcl/java_subset.json",
        )
        self._started_ns = time_ns()
        self._resuming: set[UUID] = set()
        self._resuming_experiments: set[UUID] = set()

    def _job_path(self, experiment_id: UUID) -> Path:
        return self.artifacts_dir / "experiments" / "jobs" / f"{experiment_id}.json"

    def get_experiment_job(self, experiment_id: UUID) -> ExperimentJobState | None:
        """Read a saved job without executing an Experiment."""
        path = self._job_path(experiment_id)
        if not path.is_file():
            return None
        state = ExperimentJobState.model_validate_json(path.read_text(encoding="utf-8"))
        if state.experiment_id != experiment_id:
            raise ValueError("Experiment job ID mismatch")
        return state

    def resumable_experiment_job_ids(self) -> list[UUID]:
        """Find stopped local jobs with a valid saved plan and no complete result."""
        result: list[UUID] = []
        for path in (self.artifacts_dir / "experiments" / "jobs").glob("*.json"):
            try:
                experiment_id = UUID(path.stem)
                state = self.get_experiment_job(experiment_id)
                if state is None or state.status in {"completed", "cancelled", "failed"}:
                    continue
                if not experiment_checkpoint_path(self.artifacts_dir, experiment_id).is_file():
                    continue
                try:
                    final = self.get_experiment(experiment_id)
                except ValueError:
                    final = None
                if final is None:
                    result.append(experiment_id)
            except (OSError, ValueError):
                continue
        return sorted(result)

    def _save_job(self, state: ExperimentJobState) -> ExperimentJobState:
        write_text_atomically(
            self._job_path(state.experiment_id), state.model_dump_json(indent=2) + "\n"
        )
        return state

    def reserve_experiment_job(self, experiment_id: UUID) -> ExperimentJobState:
        """Claim a new ID before queueing any work or invoking a model."""
        if (
            self._job_path(experiment_id).exists()
            or experiment_checkpoint_path(self.artifacts_dir, experiment_id).exists()
            or (self.artifacts_dir / "experiments" / f"{experiment_id}.json").exists()
        ):
            raise ValueError("Experiment ID already exists")
        return self._save_job(
            ExperimentJobState(
                experiment_id=experiment_id,
                status="queued",
                updated_at=datetime.now(UTC).isoformat(),
            )
        )

    def update_experiment_job(
        self,
        experiment_id: UUID,
        *,
        status: str | None = None,
        requested_action: str | None = None,
        error_code: str | None = None,
    ) -> ExperimentJobState:
        """Persist one local job transition atomically."""
        current = self.get_experiment_job(experiment_id)
        if current is None:
            raise ValueError("Experiment job does not exist")
        data = current.model_dump()
        if status is not None:
            data["status"] = status
        data["requested_action"] = requested_action
        data["error_code"] = error_code
        data["updated_at"] = datetime.now(UTC).isoformat()
        return self._save_job(ExperimentJobState.model_validate(data))

    def request_experiment_action(self, experiment_id: UUID, action: str) -> ExperimentJobState:
        """Request pause or cancel; the runner applies it at its next safe boundary."""
        if action not in {"pause", "cancel"}:
            raise ValueError("Unknown experiment action")
        current = self.get_experiment_job(experiment_id)
        if current is None or current.status not in {"queued", "running", "paused", "interrupted"}:
            raise ValueError("Experiment job cannot be controlled in its current state")
        if current.status in {"paused", "interrupted"}:
            if action != "cancel":
                raise ValueError("Only cancellation is available for a stopped job")
            return self.update_experiment_job(experiment_id, status="cancelled")
        return self.update_experiment_job(
            experiment_id, status=current.status, requested_action=action
        )

    def _check_experiment_action(self, experiment_id: UUID) -> None:
        state = self.get_experiment_job(experiment_id)
        if state is None:
            raise ValueError("Experiment job disappeared")
        if state.requested_action is not None:
            raise ExperimentJobStopped(state.requested_action)

    def _get_live_model_ids(self) -> set[str]:
        """Cache visible IDs; the catalog does not prove invocation permission."""
        if not self.live_model_catalog:
            return set()
        with self._model_catalog_lock:
            now = monotonic()
            if now >= self._model_catalog_expires_at:
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
    def _with_fault_profile(task: TaskSpec, profile: FaultProfile) -> TaskSpec:
        """Create an explicit test-only task variant without changing catalog data."""
        if profile == "none":
            return task
        initial_state = {**task.initial_state}
        if profile == "tool_timeout":
            initial_state["timeout_tool"] = (
                "search_documents" if initial_state.get("documents") else "query_records"
            )
        elif profile == "empty_result":
            if initial_state.get("documents"):
                initial_state["document_query"] = "__fault_no_match__"
            else:
                initial_state["target_order_id"] = "ORD-FAULT-NOT-FOUND"
        elif profile == "mcp_disconnect":
            if not initial_state.get("documents"):
                raise ValueError("MCP disconnect requires a document task")
            initial_state["mcp_disconnect"] = True
        return task.model_copy(
            update={
                "initial_state": initial_state,
                "evaluator_config": {**task.evaluator_config, "fault_profile": profile},
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

    @staticmethod
    def _agent_with_time_budget(agent: AgentSpec, limit: int | None) -> AgentSpec:
        """Bind an opt-in total time limit without altering historical configurations."""
        if limit is None:
            return agent
        return agent.model_copy(
            update={
                "budget": agent.budget.model_copy(
                    update={"schema_version": "1.1", "max_execution_time_ms": limit}
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
        for suite, adapter in (("bfcl_adapted", self.bfcl), ("bfcl_java_adapted", self.bfcl_java)):
            try:
                tasks.extend(
                    TaskOption(
                        id=t.name,
                        name=t.name,
                        category=t.category,
                        description=t.description,
                        max_steps=t.max_steps,
                        token_budget=t.token_budget,
                        suite=suite,
                        split=str(t.evaluator_config.get("split", "evaluation")),
                    )
                    for t in adapter.tasks()
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
        """Reject IDs absent from the visible catalog; invocation remains unverified."""
        if self.live_model_catalog and model_id not in self._get_live_model_ids():
            raise ValueError("Model is not visible in the current AIHubMix catalog")

    async def execute_episode(
        self,
        req: CreateEpisodeRequest,
        on_event: Callable[[TraceEvent], None] | None = None,
    ) -> EpisodeArtifact:
        """Assemble the selected runtime and suite, execute, and persist the episode."""
        # 1. Validate requested model/scenario against permissive free model catalog
        if req.provider == "aihubmix":
            if not is_model_permitted(req.model, self._configured_model_ids()):
                raise ValueError(f"Model '{req.model}' is not in the allowed free model whitelist")
            await asyncio.to_thread(self._require_live_model, req.model)
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
        agent = self._agent_with_time_budget(agent, req.max_execution_time_ms)
        bfcl_case = None
        if req.suite in ("bfcl_adapted", "bfcl_java_adapted"):
            adapter = self.bfcl if req.suite == "bfcl_adapted" else self.bfcl_java
            bfcl_case, loaded_task = adapter.case_for_task(req.task_id)
        else:
            loaded_task = self._get_task(req.task_id)
        task = self._with_token_budget(loaded_task, req.token_budget)
        if req.fault_profile != "none":
            if req.provider != "fake" or req.suite != "tool_lab_core":
                raise ValueError("Fault injection supports Fake ToolLab only")
            if (req.fault_profile == "mcp_disconnect") != (req.tool_transport == "mcp"):
                raise ValueError(
                    "MCP disconnect requires MCP transport; other faults require local"
                )
            task = self._with_fault_profile(task, req.fault_profile)
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
                environment = MCPToolLabEnvironment(
                    MCP_DISCONNECTED_URL if req.fault_profile == "mcp_disconnect" else None
                )
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
        episode_id = uuid4()
        if req.provider == "fake":
            self._save_fake_scenario(episode_id, req.scenario or "success")
        artifact = await run_checkpointed_episode(
            agent,
            task,
            run_config,
            runtime,
            environment,
            evaluator,
            self.artifacts_dir,
            fake_scenario=(req.scenario or "success") if req.provider == "fake" else None,
            on_event=on_event,
            episode_id=episode_id,
        )
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
                final_path = self.artifacts_dir / f"{episode_id}.json"
                if final_path.is_file():
                    try:
                        read_artifact(final_path)
                    except ValueError:
                        pass
                    else:
                        continue
                if path.stat().st_mtime_ns < self._started_ns and episode_id not in self._resuming:
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
            await asyncio.to_thread(self._require_live_model, model_id)
            provider = AIHubMixModelProvider(min_request_interval=13.0)
        environment, validator, evaluator = self._saved_environment(
            checkpoint.task, checkpoint.run_config.environment_version
        )
        return await resume_checkpointed_episode(
            episode_id,
            create_runtime(checkpoint.agent, provider, validator),
            environment,
            evaluator,
            self.artifacts_dir,
        )

    def _saved_environment(
        self, task: TaskSpec, environment_version: str
    ) -> tuple[Environment, ToolValidator, Evaluator]:
        """Reconstruct one pinned environment for resume or explicit rerun."""
        if environment_version == "bfcl-adapted-single-call-v1":
            suite = task.evaluator_config.get("suite")
            adapter = self.bfcl_java if suite == "bfcl_java_adapted" else self.bfcl
            case, loaded_task = adapter.case_for_task(task.name)
            expected_task = (
                self._with_token_budget(loaded_task, task.token_budget)
                if "source_token_budget" in task.evaluator_config
                else loaded_task
            )
            if expected_task != task:
                raise ValueError("BFCL source changed since the original Episode")
            bfcl_environment = BFCLEnvironment(case)
            environment: Environment = bfcl_environment
            validator = bfcl_environment.validator
            evaluator: Evaluator = BFCLEvaluator()
        elif environment_version == "tool-lab-mcp-v1":
            environment = MCPToolLabEnvironment(
                MCP_DISCONNECTED_URL if task.initial_state.get("mcp_disconnect") else None
            )
            validator = environment._validator
            evaluator = OrderStatusEvaluator()
        elif environment_version == "tool-lab-m0-v1":
            registry = create_tool_lab_registry()
            validator = DefaultToolValidator(registry)
            environment = ToolLabEnvironment(
                registry=registry, executor=ToolExecutor(registry, validator), validator=validator
            )
            evaluator = OrderStatusEvaluator()
        else:
            raise ValueError("Unsupported checkpoint environment")
        return environment, validator, evaluator

    def _saved_fake_scenario(self, episode_id: UUID) -> str:
        """Recover a Fake scenario from saved single-run or paired provenance."""
        input_path = self.artifacts_dir / "episode-inputs" / f"{episode_id}.json"
        if input_path.is_file():
            data = json.loads(input_path.read_text(encoding="utf-8"))
            if data.get("schema_version") != "1.0" or data.get("episode_id") != str(episode_id):
                raise ValueError("Episode input provenance mismatch")
            scenario = data.get("scenario")
        else:
            scenario = None
            for path in (self.artifacts_dir / "experiments").glob("*.json"):
                try:
                    experiment = read_experiment(path)
                except (OSError, ValueError):
                    continue
                if episode_id in experiment.episode_ids:
                    scenario = experiment.config.get("scenario")
                    break
        if scenario not in ALLOWED_FAKE_SCENARIOS:
            raise ValueError("Saved Fake scenario is unavailable")
        return str(scenario)

    def _save_fake_scenario(self, episode_id: UUID, scenario: str) -> None:
        """Persist only public Fake scenario metadata before an Episode starts."""
        source = {"schema_version": "1.0", "episode_id": str(episode_id), "scenario": scenario}
        write_text_atomically(
            self.artifacts_dir / "episode-inputs" / f"{episode_id}.json",
            json.dumps(source, indent=2) + "\n",
        )

    async def rerun_failed_episode(self, episode_id: UUID) -> EpisodeArtifact:
        """Run a failed saved Episode under its exact Agent, Task and RunConfig."""
        source = self.get_episode(episode_id)
        if source is None:
            raise FileNotFoundError("Source Episode not found")
        if source.evaluation.success:
            raise ValueError("Only failed Episodes may be rerun")
        model = source.agent.model
        if model.provider == "fake":
            scenario = self._saved_fake_scenario(episode_id)
            provider: ModelProvider = FakeModelProvider(scenario=scenario)
        else:
            if not is_model_permitted(model.model, self._configured_model_ids()):
                raise ValueError("Saved model is no longer permitted")
            await asyncio.to_thread(self._require_live_model, model.model)
            scenario = None
            provider = AIHubMixModelProvider(min_request_interval=13.0)
        environment, validator, evaluator = self._saved_environment(
            source.task, source.run_config.environment_version
        )
        rerun_id = uuid4()
        if scenario is not None:
            self._save_fake_scenario(rerun_id, scenario)
        artifact = await run_checkpointed_episode(
            source.agent,
            source.task,
            source.run_config,
            create_runtime(source.agent, provider, validator),
            environment,
            evaluator,
            self.artifacts_dir,
            fake_scenario=scenario,
            episode_id=rerun_id,
        )
        lineage = {
            "schema_version": "1.0",
            "source_episode_id": str(episode_id),
            "rerun_episode_id": str(artifact.episode.episode_id),
            "source_config_hashes": source.config_hashes,
            "created_at": datetime.now(UTC).isoformat(),
        }
        write_text_atomically(
            self.artifacts_dir / "reruns" / f"{artifact.episode.episode_id}.json",
            json.dumps(lineage, indent=2) + "\n",
        )
        return artifact

    async def execute_experiment(
        self, req: CreateExperimentRequest, *, job_id: UUID | None = None
    ) -> ExperimentArtifact:
        """Run a paired policy or runtime comparison and persist its artifact."""
        if not req.task_ids:
            raise ValueError("Experiment requires at least one task ID")
        resolved_seeds = req.seeds if req.seeds is not None else [req.seed]
        if len(set(resolved_seeds)) != len(resolved_seeds):
            raise ValueError("Experiment seeds must be unique")
        if req.fault_profile != "none" and (
            req.provider != "fake" or req.fault_profile == "mcp_disconnect"
        ):
            raise ValueError("Experiment fault injection supports local Fake ToolLab only")
        if req.max_reference_cost_usd is not None and (
            req.provider != "aihubmix" or reference_price_version(req.model) is None
        ):
            raise ValueError("Reference USD budget requires a priced real model")

        # 1. Load tasks
        tasks = [
            self._with_fault_profile(
                self._with_token_budget(self._get_task(tid), req.token_budget), req.fault_profile
            )
            for tid in req.task_ids
        ]

        # 2. Validate requested model/scenario and configure agents & provider factory
        if req.provider == "aihubmix":
            if not is_model_permitted(req.model, self._configured_model_ids()):
                raise ValueError(f"Model '{req.model}' is not in the allowed free model whitelist")
            await asyncio.to_thread(self._require_live_model, req.model)
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
        baseline_agent = self._agent_with_time_budget(baseline_agent, req.max_execution_time_ms)
        recovery_agent = self._agent_with_time_budget(recovery_agent, req.max_execution_time_ms)
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
            "fault_profile": req.fault_profile,
            "max_reference_cost_usd": (
                str(req.max_reference_cost_usd) if req.max_reference_cost_usd is not None else None
            ),
            "reference_price_version": (
                reference_price_version(req.model) if req.provider == "aihubmix" else None
            ),
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
            experiment_id=job_id,
            before_arm=(lambda: self._check_experiment_action(job_id)) if job_id else None,
        )

    def get_experiment(self, experiment_id: UUID) -> ExperimentArtifact | None:
        """Strictly read previously saved ExperimentArtifact from disk without invoking models."""
        target_file = self.artifacts_dir / "experiments" / f"{experiment_id}.json"
        if not target_file.is_file():
            return None
        return read_experiment(target_file)

    def experiment_dashboard(self) -> ExperimentDashboardResponse:
        """Summarize saved comparisons without invoking models or mixing score protocols."""
        items: list[ExperimentDashboardItem] = []
        skipped = 0
        for path in (self.artifacts_dir / "experiments").glob("*.json"):
            try:
                artifact = read_experiment(path)
                if path.stem != str(artifact.experiment_id):
                    raise ValueError("Experiment file ID mismatch")
                if compute_config_hash(artifact.config) != artifact.config_hash:
                    raise ValueError("Experiment configuration hash mismatch")
                metrics = artifact.metrics
                if metrics.total_pairs != len(artifact.pairs):
                    raise ValueError("Experiment pair count mismatch")
                try:
                    comparison_key = compute_config_hash(fixed_config(artifact))
                except ValueError:
                    comparison_key = None  # Legacy records retain detail access, without trends.
                config = artifact.config
                model = config.get("model")
                model_id = model.get("model") if isinstance(model, dict) else model
                provider = (
                    model.get("provider") if isinstance(model, dict) else config.get("provider")
                )
                items.append(
                    ExperimentDashboardItem(
                        experiment_id=artifact.experiment_id,
                        created_at=artifact.created_at,
                        config_hash=artifact.config_hash,
                        environment_version=str(
                            artifact.config.get("environment_version", "unknown")
                        ),
                        comparison_axis=str(
                            artifact.config.get("comparison_axis", "recovery_policy")
                        ),
                        total_pairs=metrics.total_pairs,
                        baseline_success_rate=metrics.baseline_success_rate,
                        recovery_success_rate=metrics.recovery_success_rate,
                        baseline_total_tokens=metrics.baseline_total_tokens,
                        recovery_total_tokens=metrics.recovery_total_tokens,
                        baseline_avg_duration_ms=metrics.baseline_avg_duration_ms,
                        recovery_avg_duration_ms=metrics.recovery_avg_duration_ms,
                        baseline_total_cost=metrics.baseline_total_cost,
                        recovery_total_cost=metrics.recovery_total_cost,
                        model_id=model_id if isinstance(model_id, str) else None,
                        provider=provider if isinstance(provider, str) else None,
                        task_ids=list(dict.fromkeys(pair.task_id for pair in artifact.pairs)),
                        seeds=config.get("seeds", []),
                        repeat_count=config.get("repeat_count"),
                        scenario=config.get("scenario"),
                        fault_profile=config.get("fault_profile"),
                        comparison_key=comparison_key,
                        baseline_reference_cost=metrics.baseline_total_reference_cost,
                        recovery_reference_cost=metrics.recovery_total_reference_cost,
                        reference_price_version=config.get("reference_price_version"),
                    )
                )
            except (OSError, ValueError):
                skipped += 1
        items.sort(key=lambda item: item.created_at, reverse=True)
        return ExperimentDashboardResponse(items=items[:100], skipped_count=skipped)

    def resumable_experiment_ids(self) -> list[UUID]:
        """List only unfinished plans left by an earlier API instance."""
        directory = self.artifacts_dir / "experiments" / "checkpoints"
        result: list[UUID] = []
        for path in directory.glob("*.json"):
            try:
                experiment_id = UUID(path.stem)
                final_path = self.artifacts_dir / "experiments" / f"{experiment_id}.json"
                if final_path.is_file():
                    try:
                        read_experiment(final_path)
                    except ValueError:
                        pass
                    else:
                        continue
                if (
                    path.stat().st_mtime_ns < self._started_ns
                    and experiment_id not in self._resuming_experiments
                    and self.get_experiment_job(experiment_id) is None
                ):
                    result.append(experiment_id)
            except (ValueError, OSError):
                continue
        return sorted(result)

    async def resume_experiment(self, experiment_id: UUID) -> ExperimentArtifact:
        """Continue the original paired matrix without rerunning completed arms."""
        if self.get_experiment_job(experiment_id) is not None:
            raise ValueError("Use the Experiment job resume endpoint")
        if experiment_id not in self.resumable_experiment_ids():
            raise ValueError("No resumable experiment exists for this API instance")
        return await self._resume_experiment_once(experiment_id)

    async def resume_experiment_job(self, experiment_id: UUID) -> ExperimentArtifact:
        """Continue a deliberately paused or interrupted local job."""
        job = self.get_experiment_job(experiment_id)
        if job is None or job.status not in {"paused", "interrupted", "queued", "running"}:
            raise ValueError("No paused or interrupted job exists")
        if not experiment_checkpoint_path(self.artifacts_dir, experiment_id).is_file():
            raise ValueError("Experiment plan is unavailable")
        return await self._resume_experiment_once(experiment_id, controlled=True)

    async def _resume_experiment_once(
        self, experiment_id: UUID, *, controlled: bool = False
    ) -> ExperimentArtifact:
        """Rebuild providers from a validated plan, preserving completed arms."""
        self._resuming_experiments.add(experiment_id)
        try:
            state = read_experiment_checkpoint(
                experiment_checkpoint_path(self.artifacts_dir, experiment_id)
            )
            if state.experiment_id != experiment_id:
                raise ValueError("Foreign experiment checkpoint")
            model = state.baseline_agent.model
            if model.provider == "fake":
                scenario = state.config_metadata.get("scenario") or "success"
                if scenario not in ALLOWED_FAKE_SCENARIOS:
                    raise ValueError("Unsupported saved Fake scenario")

                def provider_factory() -> ModelProvider:
                    return FakeModelProvider(scenario=scenario)

                def resume_provider_factory(call_count: int) -> ModelProvider:
                    return FakeModelProvider(scenario=scenario, initial_call_count=call_count)

            else:
                if not is_model_permitted(model.model, self._configured_model_ids()):
                    raise ValueError("Saved model is no longer permitted")
                saved_price_version = state.config_metadata.get("reference_price_version")
                if saved_price_version is not None and (
                    reference_price_version(model.model) != saved_price_version
                ):
                    raise ValueError("Saved Experiment reference price version changed")
                await asyncio.to_thread(self._require_live_model, model.model)

                def provider_factory() -> ModelProvider:
                    return AIHubMixModelProvider(min_request_interval=13.0)

                def resume_provider_factory(call_count: int) -> ModelProvider:
                    return AIHubMixModelProvider(min_request_interval=13.0)

            return await run_experiment(
                baseline_agent=state.baseline_agent,
                recovery_agent=state.recovery_agent,
                tasks=state.tasks,
                provider_factory=provider_factory,
                seeds=state.seeds,
                repeat_count=state.repeat_count,
                artifacts_dir=self.artifacts_dir,
                config_metadata=state.config_metadata,
                comparison_axis=state.comparison_axis,
                checkpoint_state=state,
                resume_provider_factory=resume_provider_factory,
                before_arm=(lambda: self._check_experiment_action(experiment_id))
                if controlled
                else None,
            )
        finally:
            self._resuming_experiments.discard(experiment_id)
