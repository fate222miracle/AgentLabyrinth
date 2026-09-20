"""Tests for the fixed, non-executable BFCL reference adapter."""

import asyncio
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.application.runner import run_episode
from packages.domain.models import (
    AgentSpec,
    EpisodeArtifact,
    FinalAnswer,
    Message,
    ModelConfig,
    ModelResponse,
    RunConfig,
    ToolCall,
    ToolSchema,
)
from packages.environments.bfcl.adapter import BFCLAdapter, BFCLCase
from packages.environments.bfcl.environment import BFCLEnvironment
from packages.evaluation.bfcl import BFCLEvaluator
from packages.runtime.handwritten.runtime import HandwrittenRuntime


class _Provider:
    def __init__(self, action: ToolCall | FinalAnswer) -> None:
        self.action = action

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        return ModelResponse(action=self.action)


def make_case() -> BFCLCase:
    return BFCLCase.model_validate(
        {
            "id": "simple_python_test",
            "split": "development",
            "question": "Calculate the factorial of 5.",
            "tool": {
                "name": "math.factorial",
                "description": "Calculate a factorial.",
                "parameters": {
                    "type": "object",
                    "properties": {"number": {"type": "integer"}},
                    "required": ["number"],
                },
            },
            "ground_truth": {"math.factorial": {"number": [5]}},
        }
    )


def run_case(action: ToolCall | FinalAnswer) -> EpisodeArtifact:
    case = make_case()
    manifest = {
        "evaluator_version": "bfcl-local-exact-v1",
        "source_version_or_commit": "fixed",
        "checksum": "fixture",
        "adapter_version": "test",
        "result_label": "AgentLabyrinth-adapted subset",
    }
    task = case.task_spec(manifest, "manifest")
    environment = BFCLEnvironment(case)
    return asyncio.run(
        run_episode(
            agent=AgentSpec(
                id=uuid4(),
                name="bfcl-test",
                version="1",
                description="test",
                prompt_version="v1",
                tool_set_version="bfcl-test",
            ),
            task=task,
            config=RunConfig(environment_version="bfcl-test"),
            runtime=HandwrittenRuntime(_Provider(action), environment.validator),
            environment=environment,
            evaluator=BFCLEvaluator(),
        )
    )


def test_correct_call_succeeds_and_wrong_cases_fail() -> None:
    correct = run_case(ToolCall(call_id="1", name="math.factorial", arguments={"number": 5}))
    assert correct.evaluation.success is True
    assert correct.evaluation.metrics["official_bfcl_score"] is False
    assert correct.episode.tool_call_count == 1

    wrong_tool = run_case(ToolCall(call_id="1", name="other", arguments={"number": 5}))
    assert wrong_tool.evaluation.success is False
    assert wrong_tool.evaluation.reason == "wrong_tool"

    wrong_args = run_case(ToolCall(call_id="1", name="math.factorial", arguments={"number": 6}))
    assert wrong_args.evaluation.success is False
    assert wrong_args.evaluation.reason == "wrong_arguments"

    no_call = run_case(FinalAnswer(text="5! = 120"))
    assert no_call.evaluation.reason == "no_tool_call"

    with pytest.raises(ValidationError):
        make_case().argument_model().model_validate({"number": None})


def test_adapter_rejects_checksum_mismatch_and_unknown_id() -> None:
    case_data = [make_case().model_dump(mode="json")]
    with TemporaryDirectory() as directory:
        root = Path(directory)
        subset = root / "subset.json"
        subset.write_text(json.dumps(case_data), encoding="utf-8")
        checksum = hashlib.sha256(subset.read_bytes()).hexdigest()
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "checksum": checksum,
                    "selected_cases": {"development": ["simple_python_test"], "evaluation": []},
                    "evaluator_version": "bfcl-local-exact-v1",
                    "source_version_or_commit": "fixed",
                    "adapter_version": "test",
                    "result_label": "AgentLabyrinth-adapted subset",
                }
            ),
            encoding="utf-8",
        )
        adapter = BFCLAdapter(manifest, subset)
        assert adapter.tasks()[0].evaluator_config["source_case_id"] == "simple_python_test"
        with pytest.raises(ValueError, match="not found"):
            adapter.case_for_task("unknown")
        subset.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="checksum"):
            adapter.load()
