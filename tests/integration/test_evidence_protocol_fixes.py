"""Real failure fixes preserve legacy scoring and runtime permission checks."""

import asyncio
from pathlib import Path
from unittest.mock import patch

from apps.api.schemas import CreateEpisodeRequest, CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.domain.models import ModelResponse, ToolCall
from packages.environments.tool_lab.environment import ToolLabEnvironment
from packages.evaluation.order_status import OrderStatusEvaluator
from packages.providers.fake import FakeModelProvider
from scripts.run_regression import preflight


def test_new_evidence_order_without_losing_old_or_forgery_checks(tmp_path: Path) -> None:
    """Reordering is harmless only in v2; missing/duplicate/extra evidence still fails."""
    service = EpisodeService(artifacts_dir=tmp_path)
    artifact = asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(provider="fake", model="fake", task_id="return-evidence-chain-001")
        )
    )
    assert artifact.agent.tool_set_version == "v1.3.0"
    assert artifact.evaluation.evaluator_version == "order_status_v2"
    state = artifact.episode.final_state
    submission = state["submission"]
    assert isinstance(submission, dict) and isinstance(submission["evidence"], list)
    original = submission["evidence"]
    evaluator = OrderStatusEvaluator()
    for evidence, passed in (
        (original[::-1], True),
        (original[:-1], False),
        (original + original[:1], False),
        (original + ["forged"], False),
    ):
        changed = artifact.episode.model_copy(
            update={"final_state": {**state, "submission": {**submission, "evidence": evidence}}}
        )
        assert evaluator.evaluate(artifact.task, changed, artifact.events).success is passed
    old_config = {k: v for k, v in artifact.task.evaluator_config.items() if k != "evidence_order"}
    old_task = artifact.task.model_copy(update={"version": "1.1.0", "evaluator_config": old_config})
    reordered = artifact.episode.model_copy(
        update={"final_state": {**state, "submission": {**submission, "evidence": original[::-1]}}}
    )
    legacy = evaluator.evaluate(old_task, reordered, artifact.events)
    assert not legacy.success and legacy.evaluator_version == "order_status_v1"
    assert artifact.episode.final_state == state


def test_task_scoped_schemas_still_reject_forbidden_action(tmp_path: Path) -> None:
    """New profiles hide query_records; old profiles expose it, but both enforce permission."""
    service = EpisodeService(artifacts_dir=tmp_path)
    task = service._get_task("return-evidence-chain-001")
    for version, count in (("v1.1.0", 4), ("v1.2.0", 3), ("v1.3.0", 3)):
        env = ToolLabEnvironment(tool_set_version=version)
        env.reset(task, 1)
        assert len(env.available_tools()) == count
        read = next(t for t in env.available_tools() if t.name == "read_document")
        assert read.version == ("1.1.0" if version == "v1.3.0" else "1.0.0")
        assert ("reference in an already read" in str(read.parameters)) == (version == "v1.3.0")
    fake = FakeModelProvider(
        custom_responses=[
            ModelResponse(
                action=ToolCall(
                    call_id="forbidden",
                    name="query_records",
                    arguments={"table": "orders", "filters": {"order_id": "CASE-314"}},
                )
            )
        ]
    )
    with patch("apps.api.service.FakeModelProvider", return_value=fake):
        result = asyncio.run(
            service.execute_episode(
                CreateEpisodeRequest(provider="fake", model="fake", task_id=task.name)
            )
        )
    assert not result.evaluation.success
    assert result.episode.tool_call_count == 0
    req = CreateExperimentRequest(
        provider="fake", model="fake", scenario="clean", task_ids=[task.name], token_budget=20000
    )
    compared = asyncio.run(service.execute_experiment(req))
    assert compared.config["tool_set_version"] == "v1.3.0"
    assert compared.config["evaluator"] == "order_status_v2"
    preflight(compared, req, service)
