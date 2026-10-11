"""Trusted catalog exceptions and description versions retain execution boundaries."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.checkpoint import CheckpointStore
from packages.application.runner import run_episode
from packages.application.trace import JsonTraceRecorder, content_hash, write_artifact
from packages.domain.models import (
    AgentSpec,
    EventType,
    Message,
    ModelConfig,
    ModelResponse,
    RunConfig,
    RuntimeBackend,
    ToolCall,
    ToolSchema,
)
from packages.domain.ports import ModelProviderError
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.environments.tool_lab.mcp import MCPToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from packages.runtime.factory import create_runtime
from packages.runtime.session import SessionState

ROOT = Path(__file__).resolve().parents[2]
FLASH = "coding-glm-5.3-flash-free"


@pytest.mark.parametrize("catalog_error", [False, True])
def test_explicit_exception_survives_missing_catalog_without_claiming_health(
    tmp_path: Path,
    catalog_error: bool,
) -> None:
    """Only a server-configured exact true survives missing/failed discovery."""
    models = tmp_path / "models.json"
    models.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": FLASH,
                        "name": "Flash",
                        "provider": "aihubmix",
                        "allow_catalog_missing": True,
                    },
                    {
                        "id": "unverified-free",
                        "name": "unverified",
                        "provider": "aihubmix",
                        "allow_catalog_missing": "true",
                    },
                    {"id": "fake", "name": "Fake", "provider": "fake"},
                ]
            }
        ),
        encoding="utf-8",
    )
    service = EpisodeService(
        artifacts_dir=tmp_path / "runs", models_path=models, live_model_catalog=True
    )
    with patch(
        "apps.api.service.list_available_model_ids",
        side_effect=ModelProviderError("REQUEST_TIMEOUT") if catalog_error else None,
        return_value=set(),
    ):
        meta = service.get_meta()
        assert {m.id for m in meta.models} == {FLASH, "fake"}
        assert "当前目录未确认" in meta.models[0].notes
        assert meta.model_catalog_status == ("unavailable" if catalog_error else "live")
        service._require_live_model(FLASH)
        with pytest.raises(ValueError, match="not visible"):
            service._require_live_model("unverified-free")


def test_exception_keeps_provider_failures_and_rejects_client_override(tmp_path: Path) -> None:
    """An admitted candidate is still subject to provider errors and strict DTOs."""
    service = EpisodeService(artifacts_dir=tmp_path, live_model_catalog=True)
    with (
        patch("apps.api.service.list_available_model_ids", return_value=set()),
        patch(
            "apps.api.service.AIHubMixModelProvider.generate",
            side_effect=ModelProviderError("RATE_LIMIT_EXCEEDED"),
        ) as generate,
    ):
        artifact = asyncio.run(
            service.execute_episode(
                CreateEpisodeRequest(
                    provider="aihubmix",
                    model=FLASH,
                    task_id="order-status-007",
                )
            )
        )
        assert artifact.episode.detail == "provider_error: RATE_LIMIT_EXCEEDED"
        assert not artifact.evaluation.success
        assert artifact.episode.tool_call_count == 0
        assert generate.call_count == 1
        with pytest.raises(ValueError, match="whitelist"):
            asyncio.run(
                service.execute_episode(
                    CreateEpisodeRequest(
                        provider="aihubmix",
                        model="unapproved-paid-model",
                    )
                )
            )
        assert generate.call_count == 1
    with pytest.raises(ValueError):
        CreateEpisodeRequest.model_validate(
            {"provider": "aihubmix", "model": FLASH, "allow_catalog_missing": True}
        )


@pytest.mark.parametrize("backend", ["handwritten", "langgraph"])
def test_new_runs_and_paired_plans_pin_grounded_descriptions(
    tmp_path: Path,
    backend: RuntimeBackend,
) -> None:
    """New API runs explicitly pin the new tool set on both experiment arms."""
    service = EpisodeService(artifacts_dir=tmp_path)
    artifact = asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(
                provider="fake",
                model="fake",
                task_id="order-status-007",
                runtime_backend=backend,
            )
        )
    )
    assert artifact.evaluation.success
    assert artifact.agent.tool_set_version == "v1.1.0"
    assert artifact.config_hashes["agent"] == content_hash(artifact.agent)
    plan = asyncio.run(
        service.prepare_experiment(
            CreateExperimentRequest(
                provider="fake",
                model="fake",
                scenario="clean",
                task_ids=["order-status-007"],
                runtime_backend=backend,
            )
        )
    )
    assert plan.baseline_agent.tool_set_version == plan.recovery_agent.tool_set_version == "v1.1.0"
    env, _, _ = service._saved_environment(artifact.task, "tool-lab-mcp-v1", "v1.1.0")
    assert isinstance(env, MCPToolLabEnvironment)
    submit = next(t for t in env.available_tools() if t.name == "submit_answer")
    assert submit.version == "1.1.0"
    assert "read_document" in str(submit.parameters["properties"])


@pytest.mark.parametrize("version", ["v1.0.0", "v1.1.0"])
def test_saved_resume_and_failed_rerun_use_original_description_version(
    tmp_path: Path,
    version: str,
) -> None:
    """Resume retains acquired evidence, and failure reruns retain saved tool inputs."""
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task("order-status-007")
    agent = AgentSpec.model_validate_json(
        (ROOT / "benchmarks/tool_lab_core/agents/baseline-m0.json").read_text(encoding="utf-8")
    ).model_copy(update={"tool_set_version": version})
    config = RunConfig()
    recorder = JsonTraceRecorder(config)
    store = CheckpointStore(tmp_path / "checkpoints")
    env = ToolLabEnvironment(tool_set_version=version)

    def save(state: SessionState) -> None:
        store.save(state, agent, task, config, recorder, "success")
        if state.next_node == "model" and state.budget.tool_call_count == 2:
            raise SystemExit(0)

    with pytest.raises(SystemExit):
        asyncio.run(
            run_episode(
                agent,
                task,
                config,
                create_runtime(agent, FakeModelProvider()),
                env,
                OrderStatusEvaluator(),
                recorder=recorder,
                save_checkpoint=save,
            )
        )
    original_schema = next(t for t in env.available_tools() if t.name == "submit_answer")
    original_generate = FakeModelProvider.generate

    async def observed_generate(
        provider: FakeModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        assert next(t for t in tools if t.name == "submit_answer") == original_schema
        return await original_generate(provider, messages, tools, config)

    with patch(
        "apps.api.service.FakeModelProvider.generate", autospec=True, side_effect=observed_generate
    ):
        resumed = asyncio.run(
            EpisodeService(artifacts_dir=tmp_path).resume_episode(recorder.episode_id)
        )
    assert resumed.evaluation.success
    assert resumed.agent == agent
    assert (
        sum(
            e.event_type == EventType.TOOL_CALL_PROPOSED
            and e.payload.get("name") == "read_document"
            for e in resumed.events
        )
        == 1
    )

    # Explicitly save a forged submission; the unchanged evaluator must reject it.
    failure = asyncio.run(
        run_episode(
            agent,
            task,
            config,
            create_runtime(
                agent,
                FakeModelProvider(
                    custom_responses=[
                        ModelResponse(
                            action=ToolCall(
                                call_id="forged",
                                name="submit_answer",
                                arguments={"answer": "approved", "evidence": ["document:DOC-007"]},
                            )
                        )
                    ]
                ),
            ),
            ToolLabEnvironment(tool_set_version=version),
            OrderStatusEvaluator(),
        )
    )
    assert not failure.evaluation.success
    assert failure.episode.final_state["acquired_evidence"] == []
    write_artifact(failure, tmp_path / f"{failure.episode.episode_id}.json")
    service._save_fake_scenario(failure.episode.episode_id, "success")
    with patch(
        "apps.api.service.FakeModelProvider.generate", autospec=True, side_effect=observed_generate
    ):
        rerun = asyncio.run(service.rerun_failed_episode(failure.episode.episode_id))
    assert rerun.evaluation.success
    assert rerun.agent == agent
    assert rerun.config_hashes == failure.config_hashes


def test_description_versions_preserve_strict_arguments_and_reject_mixed_registry() -> None:
    """Descriptions cannot weaken validation, forge evidence, or mix tool versions."""
    old = ToolLabEnvironment()
    new = ToolLabEnvironment(tool_set_version="v1.1.0")
    old_schema = next(t for t in old.available_tools() if t.name == "submit_answer")
    new_schema = next(t for t in new.available_tools() if t.name == "submit_answer")
    assert old_schema.version == "1.0.0"
    assert "query_records" in str(old_schema.parameters["properties"])
    assert "read_document" not in str(old_schema.parameters["properties"])
    assert new_schema.version == "1.1.0"
    assert "read_document" in str(new_schema.parameters["properties"])
    invalid = ToolCall(
        call_id="invalid",
        name="submit_answer",
        arguments={"answer": "approved", "evidence": "document:DOC-007"},
    )
    assert new._validator.inspect(invalid, ("submit_answer",)).error_code == "INVALID_ARGUMENTS"
    with pytest.raises(ValueError, match="version mismatch"):
        ToolLabEnvironment(registry=old._registry, tool_set_version="v1.1.0")
    with pytest.raises(ValueError, match="Unsupported"):
        ToolLabEnvironment(tool_set_version="v99")
