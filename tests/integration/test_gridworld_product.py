"""API, streaming, and SQLite restart checks for the fixed GridWorld slice."""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Generator
from decimal import Decimal
from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import JsonValue

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))

from apps.api.main import app, get_episode_service  # noqa: E402
from apps.api.schemas import GRIDWORLD_ALLOWED_MODEL_IDS, CreateEpisodeRequest  # noqa: E402
from apps.api.service import EpisodeService  # noqa: E402
from packages.application.checkpoint import CheckpointStore, build_checkpoint  # noqa: E402
from packages.application.gridworld_review import (  # noqa: E402
    PairReview,
    build_pair_input,
    ordered_pair,
)
from packages.application.runner import run_episode  # noqa: E402
from packages.application.trace import JsonTraceRecorder, content_hash  # noqa: E402
from packages.domain.models import (  # noqa: E402
    EstimatedCost,
    FinalAnswer,
    Message,
    ModelConfig,
    ModelResponse,
    RunConfig,
    TokenUsage,
    ToolSchema,
)
from packages.domain.ports import ModelProviderError  # noqa: E402
from packages.environments.gridworld.environment import (  # noqa: E402
    ENVIRONMENT_VERSION,
    GALLERY_TASK_NAME,
    GRID_LAYOUTS,
    TASK_NAME,
    GridWorldEnvironment,
)
from packages.environments.gridworld.evaluator import GridWorldKeyDoorEvaluator  # noqa: E402
from packages.providers.gridworld_fake import GridWorldFakeProvider  # noqa: E402
from packages.runtime.factory import create_runtime, runtime_version  # noqa: E402
from packages.runtime.handwritten.runtime import HandwrittenRuntime  # noqa: E402
from scripts.course_demo import DemoService  # noqa: E402

REAL_MODEL_ID = "coding-minimax-m2.7-free"
REAL_GRIDWORLD_MODELS = (
    REAL_MODEL_ID,
    "coding-minimax-m3-free",
    "coding-glm-5.3-free",
    "coding-glm-5.3-flash-free",
)


@pytest.fixture
def product_client(tmp_path: Path) -> Generator[tuple[TestClient, EpisodeService], None, None]:
    artifacts = tmp_path / "artifacts"
    models_path = tmp_path / "models.json"
    models_path.write_text(
        json.dumps(
            {
                "models": [
                    *[
                        {"id": model, "name": model, "provider": "aihubmix"}
                        for model in REAL_GRIDWORLD_MODELS
                    ],
                    {"id": "fake", "name": "Fake", "provider": "fake"},
                ]
            }
        ),
        encoding="utf-8",
    )
    service = EpisodeService(
        artifacts_dir=artifacts,
        models_path=models_path,
        database_path=artifacts / "agentlabyrinth.sqlite3",
    )
    app.dependency_overrides[get_episode_service] = lambda: service
    with TestClient(app) as client:
        yield client, service
    app.dependency_overrides.clear()


def _episode_request(scenario: str) -> dict[str, Any]:
    return {
        "schema_version": "1.3",
        "provider": "fake",
        "model": "fake-model",
        "scenario": scenario,
        "task_id": TASK_NAME,
        "suite": "gridworld",
        "max_steps": 16,
        "max_execution_time_ms": 300000,
        "token_budget": 16000,
        "runtime_backend": "handwritten",
        "runtime_strategy": "handwritten",
        "tool_transport": "local",
        "fault_profile": "none",
    }


def _real_episode_request(**overrides: Any) -> dict[str, Any]:
    return {
        **_episode_request("success"),
        "provider": "aihubmix",
        "model": REAL_MODEL_ID,
        "scenario": None,
        "token_budget": None,
        **overrides,
    }


class LocalGridWorldModelSubstitute:
    """Use deterministic actions to exercise the real-provider path without network calls."""

    def __init__(
        self, *, fail: bool = False, task_name: str = TASK_NAME, prompt_tokens: int = 13_500
    ) -> None:
        self.delegate = GridWorldFakeProvider("success", task_name=task_name)
        self.fail = fail
        self.prompt_tokens = prompt_tokens
        self.calls = 0
        self.output_limits: list[int | None] = []
        self.inputs: list[list[Message]] = []

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        self.calls += 1
        self.output_limits.append(config.max_tokens)
        self.inputs.append(messages)
        if self.fail:
            raise ModelProviderError("NETWORK_CONNECTION_FAILED")
        response = await self.delegate.generate(messages, tools, config)
        return response.model_copy(
            update={
                "token_usage": TokenUsage(
                    prompt_tokens=self.prompt_tokens,
                    completion_tokens=1_000,
                    simulated=False,
                ),
                "estimated_cost": EstimatedCost(
                    amount=Decimal("0"),
                    is_known=False,
                    price_table_version="test-unknown-v1",
                ),
            }
        )


def _sse_messages(text: str) -> list[tuple[str, dict[str, Any]]]:
    messages = []
    for block in text.strip().split("\n\n"):
        if not block:
            continue
        lines = block.splitlines()
        kind = next(line[7:] for line in lines if line.startswith("event: "))
        data = "\n".join(line[6:] for line in lines if line.startswith("data: "))
        messages.append((kind, json.loads(data)))
    return messages


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(set().union(_keys(item)) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


@pytest.mark.parametrize(
    ("scenario", "termination", "success", "actions", "illegal"),
    [
        ("success", "SUCCESS", True, 8, 0),
        ("illegal-action", "SUCCESS", True, 9, 1),
        ("max-steps", "MAX_STEPS", False, 16, 0),
    ],
)
def test_gridworld_stream_and_get_use_only_arrived_public_trace(
    product_client: tuple[TestClient, EpisodeService],
    scenario: str,
    termination: str,
    success: bool,
    actions: int,
    illegal: int,
) -> None:
    client, service = product_client
    metadata = client.get("/api/v1/meta")
    assert metadata.status_code == 200
    assert any(
        task["suite"] == "gridworld" and task["id"] == TASK_NAME
        for task in metadata.json()["tasks"]
    )

    response = client.post("/api/v1/episodes/stream", json=_episode_request(scenario))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    messages = _sse_messages(response.text)
    assert messages[-1][0] == "complete"
    streamed = [body for kind, body in messages if kind == "trace"]
    artifact = messages[-1][1]["artifact"]
    assert streamed == artifact["events"]
    assert artifact["run_config"]["environment_version"] == ENVIRONMENT_VERSION
    assert artifact["episode"]["termination_reason"] == termination
    assert artifact["evaluation"]["success"] is success
    assert artifact["episode"]["model_call_count"] == actions
    assert artifact["episode"]["tool_call_count"] == actions
    assert artifact["episode"]["final_state"]["action_count"] == actions
    assert artifact["episode"]["final_state"]["illegal_action_count"] == illegal
    assert artifact["agent"]["budget"]["max_execution_time_ms"] == 300000
    assert artifact["agent"]["budget"]["max_steps"] == 16
    assert artifact["agent"]["budget"]["max_model_calls"] == 16
    assert artifact["agent"]["budget"]["max_tool_calls"] == 16
    assert artifact["agent"]["model"]["max_tokens"] == 800

    initial = next(event for event in streamed if event["event_type"] == "OBSERVATION_CREATED")
    initial_state = initial["payload"]["initial_state"]
    assert all(cell["kind"] != "goal" for cell in initial_state["known_cells"])
    assert initial_state["position"] == [1, 2]
    assert not _keys(artifact) & {
        "has_key",
        "key_available",
        "door_open",
        "visible_cells",
        "last_state",
        "snapshot",
    }

    requests = [event for event in streamed if event["event_type"] == "MODEL_REQUESTED"]
    tools = [event for event in streamed if event["event_type"] == "TOOL_STARTED"]
    assert len(requests) == actions
    assert len(tools) == actions
    if scenario == "max-steps":
        assert streamed[-1]["event_type"] == "EPISODE_FINISHED"
        assert sum(event["event_type"] == "MODEL_REQUESTED" for event in streamed) == 16
    if scenario == "illegal-action":
        assert not any(event["event_type"] == "TOOL_FAILED" for event in streamed)
        rejected = next(
            event
            for event in streamed
            if event["event_type"] == "TOOL_SUCCEEDED"
            and event["payload"]["observation"]["action_result"]["accepted"] is False
        )
        assert rejected["payload"]["observation"]["action_result"]["code"] == "movement_blocked"

    episode_id = artifact["episode"]["episode_id"]
    readback = client.get(f"/api/v1/episodes/{episode_id}")
    assert readback.status_code == 200
    assert readback.json()["artifact"] == artifact
    assert service.get_episode(UUID(episode_id)) is not None


def test_gridworld_rejects_non_fake_and_non_frozen_options(
    product_client: tuple[TestClient, EpisodeService],
) -> None:
    client, _ = product_client
    for changes in (
        {"provider": "aihubmix"},
        {"max_steps": 15},
        {"token_budget": 15000},
        {"runtime_backend": "langgraph"},
        {"scenario": "wrong-answer"},
    ):
        response = client.post(
            "/api/v1/episodes",
            json={**_episode_request("success"), **changes},
        )
        assert response.status_code == 422


@pytest.mark.parametrize("model_id", REAL_GRIDWORLD_MODELS)
def test_gridworld_real_run_uses_the_frozen_temporary_budget_and_saves_unknown_cost(
    product_client: tuple[TestClient, EpisodeService],
    model_id: str,
) -> None:
    client, service = product_client
    metadata = client.get("/api/v1/meta")
    assert metadata.status_code == 200
    gridworld_task = next(task for task in metadata.json()["tasks"] if task["suite"] == "gridworld")
    assert gridworld_task["allowed_model_ids"] == sorted(GRIDWORLD_ALLOWED_MODEL_IDS)

    substitute = LocalGridWorldModelSubstitute()
    with (
        patch.object(service, "_require_live_model") as model_preflight,
        patch(
            "apps.api.service.AIHubMixModelProvider", return_value=substitute
        ) as provider_factory,
    ):
        response = client.post("/api/v1/episodes", json=_real_episode_request(model=model_id))

    assert response.status_code == 201
    model_preflight.assert_called_once_with(model_id)
    provider_factory.assert_called_once_with(min_request_interval=13.0)
    artifact = response.json()["artifact"]
    assert artifact["evaluation"]["success"] is True, artifact["episode"]
    assert substitute.calls == 8
    assert substitute.output_limits == [2_048] * 8
    assert artifact["agent"]["model"]["provider"] == "aihubmix"
    assert artifact["agent"]["model"]["model"] == model_id
    assert artifact["agent"]["model"]["max_tokens"] == 2_048
    assert artifact["agent"]["model"]["tool_call_mode"] == "single"
    assert artifact["agent"].get("context_policy") is None
    assert artifact["agent"]["budget"]["max_steps"] == 16
    assert artifact["agent"]["budget"]["max_model_calls"] == 16
    assert artifact["agent"]["budget"]["max_tool_calls"] == 16
    assert artifact["agent"]["budget"]["max_prompt_tokens"] == 160_000
    assert artifact["agent"]["budget"]["max_completion_tokens"] == 32_768
    assert artifact["agent"]["budget"]["max_execution_time_ms"] == 300_000
    assert artifact["agent"]["budget"]["max_estimated_cost"] == "1"
    assert artifact["task"]["token_budget"] == 160_000
    assert artifact["task"]["version"].endswith("temporary-real-160k-v2")
    assert artifact["task"]["evaluator_config"]["source_token_budget"] == 16_000
    assert artifact["episode"]["token_usage"] == {
        "schema_version": "1.0",
        "prompt_tokens": 108_000,
        "completion_tokens": 8_000,
        "simulated": False,
    }
    assert artifact["episode"]["estimated_cost"]["is_known"] is False
    assert artifact["evaluation"]["success"] is True
    assert artifact["episode"]["step_count"] == 8
    assert (
        client.get(f"/api/v1/episodes/{artifact['episode']['episode_id']}").json()["artifact"]
        == artifact
    )


def test_real_gallery_uses_recent_complete_rounds_and_retains_current_world(
    product_client: tuple[TestClient, EpisodeService],
) -> None:
    client, service = product_client
    substitute = LocalGridWorldModelSubstitute(task_name=GALLERY_TASK_NAME, prompt_tokens=1_000)
    with (
        patch.object(service, "_require_live_model"),
        patch("apps.api.service.AIHubMixModelProvider", return_value=substitute),
    ):
        response = client.post(
            "/api/v1/episodes", json=_real_episode_request(task_id=GALLERY_TASK_NAME, max_steps=20)
        )

    assert response.status_code == 201
    artifact = response.json()["artifact"]
    policy = artifact["agent"].get("context_policy")
    assert policy and policy["mode"] == "recent_tool_rounds" and policy["max_tool_rounds"] == 2
    assert artifact["evaluation"]["success"] is True
    assert artifact["task"]["token_budget"] == 160_000
    assert artifact["agent"]["budget"]["max_steps"] == 20
    assert artifact["agent"]["budget"]["max_execution_time_ms"] == 300_000
    assert artifact["agent"]["model"]["max_tokens"] == 2_048
    assert [len(messages) for messages in substitute.inputs] == [2, 4, *([6] * 12)]
    for messages in substitute.inputs:
        assert [message.role for message in messages[:2]] == ["system", "user"]
        for call, result in zip(messages[2::2], messages[3::2], strict=True):
            assert call.tool_calls is not None
            assert call.tool_calls[0].call_id == result.tool_call_id
    latest = substitute.inputs[7][-1].content
    assert isinstance(latest, dict)
    world = latest["world"]
    assert isinstance(world, dict)
    assert world["position"] == [3, 3]
    assert world["inventory"] == ["key-amber"]
    assert world["visible_targets"] == [{"target_id": "door-amber", "position": [4, 3]}]
    known_cells = world["known_cells"]
    assert isinstance(known_cells, list)
    assert {
        "x": 2,
        "y": 1,
        "kind": "floor",
        "observed_at_action": 5,
        "visible": False,
    } in known_cells
    assert sum(event["event_type"] == "TOOL_SUCCEEDED" for event in artifact["events"]) == 14
    last_request = [
        event for event in artifact["events"] if event["event_type"] == "MODEL_REQUESTED"
    ][-1]
    assert last_request["payload"]["context"]["history_messages_count"] == 28
    assert last_request["payload"]["context"]["visible_messages_count"] == 6
    assert (
        client.get(f"/api/v1/episodes/{artifact['episode']['episode_id']}").json()["artifact"]
        == artifact
    )


def test_real_gallery_default_budget_can_finish_the_saved_detour(
    product_client: tuple[TestClient, EpisodeService],
) -> None:
    client, service = product_client
    substitute = LocalGridWorldModelSubstitute(task_name=GALLERY_TASK_NAME, prompt_tokens=3_500)
    actions = (
        "inspect",
        "move_right",
        "move_left",
        "move_down",
        "move_down",
        "move_right",
        "move_right",
        "move_up",
        "move_up",
        "pickup",
        "move_up",
        "move_up",
        "pickup",
        "move_down",
        "move_down",
        "use",
        "move_right",
        "move_right",
        "move_up",
        "move_up",
        "move_right",
        "move_right",
        "move_down",
        "move_down",
    )
    substitute.delegate._actions = tuple(
        (action, {"target_id": "door-amber"} if action == "use" else {}) for action in actions
    )
    with (
        patch.object(service, "_require_live_model"),
        patch(
            "apps.api.service.AIHubMixModelProvider", return_value=substitute
        ) as provider_factory,
    ):
        response = client.post(
            "/api/v1/episodes",
            json=_real_episode_request(
                task_id=GALLERY_TASK_NAME, max_steps=None, max_execution_time_ms=None
            ),
        )
    assert response.status_code == 201
    provider_factory.assert_called_once_with(timeout=60.0, min_request_interval=13.0)
    artifact = response.json()["artifact"]
    assert artifact["evaluation"]["success"] is True, artifact["episode"]["detail"]
    assert artifact["evaluation"]["metrics"]["illegal_action_count"] == 1
    assert artifact["episode"]["step_count"] == substitute.calls == 24
    assert artifact["episode"]["final_state"]["position"] == [7, 3]
    assert artifact["task"]["version"].endswith("temporary-real-gallery-v3")
    assert artifact["task"]["token_budget"] == 160_000
    assert artifact["agent"]["model"]["max_tokens"] == 2_048
    budget = artifact["agent"]["budget"]
    assert budget["max_steps"] == budget["max_model_calls"] == budget["max_tool_calls"] == 24
    assert budget["max_execution_time_ms"] == 330_000
    assert budget["max_prompt_tokens"] == 160_000
    assert budget["max_completion_tokens"] == 49_152
    assert len(substitute.inputs[-1]) == 6
    system = substitute.inputs[0][0].content
    assert isinstance(system, dict)
    constraints = system["constraints"]
    assert isinstance(constraints, list)
    assert "For pickup, first move to the key's exact cell." in constraints


def test_gridworld_comparison_groups_only_same_configuration_and_handles_missing_usage(
    product_client: tuple[TestClient, EpisodeService],
) -> None:
    client, service = product_client
    second_model = REAL_GRIDWORLD_MODELS[1]
    with (
        patch.object(service, "_require_live_model"),
        patch(
            "apps.api.service.AIHubMixModelProvider",
            side_effect=[
                LocalGridWorldModelSubstitute(),
                LocalGridWorldModelSubstitute(fail=True),
                LocalGridWorldModelSubstitute(task_name=GALLERY_TASK_NAME),
            ],
        ) as provider,
    ):
        first = client.post("/api/v1/episodes", json=_real_episode_request())
        timeout = client.post("/api/v1/episodes", json=_real_episode_request(model=second_model))
        gallery = client.post(
            "/api/v1/episodes",
            json=_real_episode_request(
                task_id=GALLERY_TASK_NAME, max_steps=None, max_execution_time_ms=None
            ),
        )
        assert all(response.status_code == 201 for response in (first, timeout, gallery))
        assert provider.call_count == 3
        response = client.get("/api/v1/episodes/gridworld-comparison")
        assert provider.call_count == 3
    assert response.status_code == 200
    latest, failed, completed = response.json()["items"]
    assert latest["task_name"] == GALLERY_TASK_NAME
    assert latest["comparison_key"] != completed["comparison_key"]
    assert failed["comparison_key"] == completed["comparison_key"]
    assert failed["model_id"] == second_model
    assert failed["actions"] == 0
    assert failed["input_tokens"] is failed["output_tokens"] is None
    assert failed["usage_complete"] is False
    assert completed["success"] and completed["actions"] == 8
    assert completed["input_tokens"] == 108_000
    assert completed["usage_complete"]


def test_gridworld_real_request_rejects_model_scenario_and_budget_overrides_before_provider(
    product_client: tuple[TestClient, EpisodeService],
) -> None:
    client, _ = product_client
    with patch("apps.api.service.AIHubMixModelProvider") as provider_factory:
        for changes in (
            {"model": "unapproved-model"},
            {"scenario": "success"},
            {"token_budget": 16_000},
            {"token_budget": 100_000},
            {"token_budget": 160_000},
            {"max_steps": 15},
            {"max_execution_time_ms": 299_999},
        ):
            response = client.post(
                "/api/v1/episodes/stream",
                json=_real_episode_request(**changes),
            )
            assert response.status_code == 422
    provider_factory.assert_not_called()


def test_pair_judge_checks_sources_citations_and_reloads_saved_results(
    product_client: tuple[TestClient, EpisodeService],
) -> None:
    client, service = product_client
    model_a, model_b, judge_model, model_d = REAL_GRIDWORLD_MODELS
    endpoint = "/api/v1/gridworld-comparison-reviews"
    reported = TokenUsage(prompt_tokens=650, completion_tokens=200, simulated=False)
    seen = []

    class Judge:
        async def generate(
            self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
        ) -> ModelResponse:
            assert not tools
            assert config.model == judge_model and config.max_tokens == 4096
            payload = messages[-1].content
            assert isinstance(messages[0].content, str) and "key decision" in messages[0].content
            assert isinstance(payload, dict)
            serialized = json.dumps(payload)
            assert all(model not in serialized for model in REAL_GRIDWORLD_MODELS)
            assert all(
                key not in serialized for key in ("known_cells", "hidden_reasoning", "episode_id")
            )
            a, b = payload["a"], payload["b"]
            assert isinstance(a, dict) and isinstance(b, dict)
            actions_a, actions_b = a["actions"], b["actions"]
            assert isinstance(actions_a, list) and isinstance(actions_b, list)
            assert len(actions_a) == len(actions_b) == 8
            assert isinstance(actions_a[0], dict) and isinstance(actions_b[0], dict)
            assert "new_cells" in actions_a[0] and actions_b[0]["revisited"] is False
            seen.append(payload)
            if len(seen) == 3:
                raise ModelProviderError("OUTPUT_TRUNCATED", token_usage=reported)
            if len(seen) == 4:
                raise ModelProviderError("NETWORK_CONNECTION_FAILED")
            if len(seen) == 5:
                raise ModelProviderError("REQUEST_TIMEOUT")
            event_a = actions_a[0]["event_id"]
            event_b = actions_b[0]["event_id"]
            output = {
                "assessment": "tradeoff",
                "rationale": "两局都执行了拾取钥匙与开门。",
                "citations": [
                    {"side": "a", "event_id": event_a},
                    {"side": "b", "event_id": event_b if len(seen) == 1 else event_a},
                ],
            }
            return ModelResponse(action=FinalAnswer(text=json.dumps(output)), token_usage=reported)

    with (
        patch.object(service, "_require_live_model"),
        patch(
            "apps.api.service.AIHubMixModelProvider",
            side_effect=[
                LocalGridWorldModelSubstitute(),
                LocalGridWorldModelSubstitute(),
                LocalGridWorldModelSubstitute(),
                LocalGridWorldModelSubstitute(fail=True),
                LocalGridWorldModelSubstitute(fail=True),
                Judge(),
                Judge(),
                Judge(),
                Judge(),
                Judge(),
            ],
        ) as provider,
    ):
        requests = [
            _real_episode_request(model=model_a),
            _real_episode_request(model=model_b),
            _real_episode_request(
                model=model_d, task_id=GALLERY_TASK_NAME, max_steps=None, max_execution_time_ms=None
            ),
            _real_episode_request(model=model_a),
            _real_episode_request(model=model_d),
        ]
        runs = [client.post("/api/v1/episodes", json=req) for req in requests]
        assert all(run.status_code == 201 for run in runs)
        artifacts = [run.json()["artifact"] for run in runs]
        a, b, other, failed_a, failed_b = [item["episode"]["episode_id"] for item in artifacts]
        body = {"schema_version": "1.0", "episode_ids": [b, a], "judge_model": judge_model}
        for rejected in (
            {"judge_model": model_a},
            {"judge_model": "unapproved-judge"},
            {"episode_ids": [a, a]},
            {"episode_ids": [a, other]},
            {"episode_ids": [a, failed_a]},
            {"episode_ids": [failed_a, failed_b]},
        ):
            assert client.post(endpoint, json={**body, **rejected}).status_code == 400
        assert (
            client.post(endpoint, json={**body, "episode_ids": [a, str(uuid4())]}).status_code
            == 404
        )
        assert provider.call_count == 5
        assert client.get(endpoint, params={"episode_a": a, "episode_b": b}).json()["reviews"] == []
        results = [client.post(endpoint, json=body) for _ in range(5)]
        assert all(result.status_code == 201 for result in results)
        assert provider.call_count == 10
        for _, options in provider.call_args_list[5:]:
            assert options == {
                "timeout": 60.0,
                "min_request_interval": 13.0,
                "reasoning_split": None,
            }
    good, invalid_ref, truncated, failed, timed_out = [response.json() for response in results]
    assert len(seen) == 5
    assert good["episode_ids"] == sorted([a, b])
    assert good["output"]["assessment"] == "tradeoff"
    assert good["prompt_version"] == "gridworld-pair-review-v2"
    assert invalid_ref["failure_code"] == "INVALID_EVENT_REFERENCE"
    assert truncated["failure_code"] == "INVALID_JUDGE_OUTPUT"
    assert truncated["token_usage"]["completion_tokens"] == 200
    assert failed["failure_code"] == "JUDGE_PROVIDER_ERROR" and failed["token_usage"] is None
    assert timed_out["failure_code"] == "JUDGE_REQUEST_TIMEOUT" and timed_out["token_usage"] is None
    assert service._sqlite_store is not None
    first, second = service._pair_sources(ordered_pair(UUID(a), UUID(b)))
    legacy = PairReview.model_validate_json(results[0].text).model_copy(
        update={
            "review_id": uuid4(),
            "prompt_version": "gridworld-pair-review-v1",
            "review_input_hash": content_hash(
                build_pair_input(first, second, "gridworld-pair-review-v1")
            ),
        }
    )
    service._sqlite_store.save_pair_review(legacy)
    legacy_json = legacy.model_dump(mode="json")
    restarted = EpisodeService(
        artifacts_dir=service.artifacts_dir, database_path=service._sqlite_store.path
    )
    app.dependency_overrides[get_episode_service] = lambda: restarted
    try:
        with patch("apps.api.service.AIHubMixModelProvider") as unused:
            history = client.get(endpoint, params={"episode_a": b, "episode_b": a}).json()
            assert history["reviews"] == [
                legacy_json,
                timed_out,
                failed,
                truncated,
                invalid_ref,
                good,
            ]
            assert history["skipped_count"] == 0
            for artifact in artifacts[:2]:
                episode_id = artifact["episode"]["episode_id"]
                assert client.get(f"/api/v1/episodes/{episode_id}").json()["artifact"] == artifact
            with sqlite3.connect(service._sqlite_store.path) as connection:
                connection.execute(
                    "UPDATE gridworld_comparison_reviews SET sha256='invalid' WHERE review_id=?",
                    (invalid_ref["review_id"],),
                )
            history = client.get(endpoint, params={"episode_a": a, "episode_b": b}).json()
            assert history["reviews"] == [legacy_json, timed_out, failed, truncated, good]
            assert history["skipped_count"] == 1
            unused.assert_not_called()
    finally:
        app.dependency_overrides[get_episode_service] = lambda: service


@pytest.mark.parametrize("unavailable", [False, True])
def test_fixed_gridworld_batch_persists_four_slots_and_reuses_saved_rows(
    product_client: tuple[TestClient, EpisodeService],
    unavailable: bool,
) -> None:
    client, service = product_client
    endpoint = "/api/v1/gridworld-batches"
    first_call = threading.Event()
    release = threading.Event()
    models_seen: list[str] = []

    class BatchProvider(LocalGridWorldModelSubstitute):
        async def generate(
            self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
        ) -> ModelResponse:
            if not self.calls:
                models_seen.append(config.model)
                if config.model == REAL_MODEL_ID:
                    first_call.set()
                    assert await asyncio.to_thread(release.wait, 10)
            return await super().generate(messages, tools, config)

    def admission(model: str) -> None:
        if unavailable and model == REAL_GRIDWORLD_MODELS[2]:
            raise ValueError("Missing from directory")

    expected_models = [
        model for i, model in enumerate(REAL_GRIDWORLD_MODELS) if i != 2 or not unavailable
    ]

    with (
        patch.object(service, "_require_live_model", side_effect=admission),
        patch(
            "apps.api.service.AIHubMixModelProvider",
            side_effect=[
                BatchProvider(task_name=GALLERY_TASK_NAME, prompt_tokens=500),
                BatchProvider(fail=True),
                *(
                    []
                    if unavailable
                    else [BatchProvider(task_name=GALLERY_TASK_NAME, prompt_tokens=500)]
                ),
                BatchProvider(task_name=GALLERY_TASK_NAME, prompt_tokens=500),
            ],
        ) as provider,
    ):
        assert client.get(endpoint).json()["items"] == []
        response = client.post(endpoint, json={"schema_version": "1.0"})
        assert response.status_code == 202
        batch_id = response.json()["batch_id"]
        assert first_call.wait(5)
        try:
            assert client.post(endpoint, json={"schema_version": "1.0"}).status_code == 400
            view = client.get(endpoint).json()["items"][0]
            assert [run["status"] for run in view["runs"]] == [
                "running",
                "queued",
                "queued",
                "queued",
            ]
            assert service._sqlite_store is not None
            restarted = EpisodeService(
                artifacts_dir=service.artifacts_dir, database_path=service._sqlite_store.path
            )
            stranded = restarted.gridworld_batches().items[0]
            assert [run.status for run in stranded.runs] == [
                "interrupted",
                "not_started",
                "not_started",
                "not_started",
            ]
        finally:
            release.set()
        deadline = monotonic() + 12
        while view["running"] and monotonic() < deadline:
            sleep(0.05)
            view = client.get(endpoint).json()["items"][0]
        assert not view["running"]
        assert view["batch_id"] == batch_id
        assert [run["status"] for run in view["runs"]] == [
            "completed",
            "failed",
            "unavailable" if unavailable else "completed",
            "completed",
        ]
        assert models_seen == expected_models
        assert provider.call_count == len(expected_models)
        rows = [run["row"] for run in view["runs"] if run["row"] is not None]
        assert len({row["comparison_key"] for row in rows}) == 1
        assert all(row["max_steps"] == 24 and row["context_rounds"] == 2 for row in rows)
        assert rows[1]["input_tokens"] is None
        assert [run.model for run in restarted.gridworld_batches().items[0].runs] == list(
            REAL_GRIDWORLD_MODELS
        )
        assert provider.call_count == len(expected_models)


def test_demo_service_keeps_gridworld_fake_only(
    tmp_path: Path,
) -> None:
    demo = DemoService(artifacts_dir=tmp_path)
    assert {model.provider for model in demo.get_meta().models} == {"fake"}
    request = CreateEpisodeRequest.model_validate(_real_episode_request())
    with patch("apps.api.service.AIHubMixModelProvider") as provider_factory:
        with pytest.raises(ValueError, match="Fake models only"):
            asyncio.run(demo.execute_episode(request))
    provider_factory.assert_not_called()


def test_real_gridworld_network_failure_is_saved_and_cannot_resume_or_rerun(
    product_client: tuple[TestClient, EpisodeService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, service = product_client
    substitute = LocalGridWorldModelSubstitute(fail=True)
    with (
        patch.object(service, "_require_live_model"),
        patch("apps.api.service.AIHubMixModelProvider", return_value=substitute),
    ):
        response = client.post("/api/v1/episodes", json=_real_episode_request())

    assert response.status_code == 201
    artifact = response.json()["artifact"]
    episode_id = UUID(artifact["episode"]["episode_id"])
    assert artifact["evaluation"]["success"] is False
    assert substitute.calls == 1
    assert service.get_episode(episode_id) is not None
    assert service.resumable_episode_ids() == []
    assert client.post(f"/api/v1/episodes/{episode_id}/rerun").status_code == 409
    assert substitute.calls == 1

    resume_id = uuid4()
    agent = service._gridworld_agent(
        provider="aihubmix",
        model=REAL_MODEL_ID,
    )
    checkpoint = SimpleNamespace(
        agent=agent,
        run_config=RunConfig(
            seed=1,
            environment_version=ENVIRONMENT_VERSION,
            runtime_version=runtime_version("handwritten"),
        ),
    )
    monkeypatch.setattr(service, "resumable_episode_ids", lambda: [resume_id])
    monkeypatch.setattr(
        CheckpointStore,
        "load_checkpoint",
        lambda _store, _episode_id: checkpoint,
    )
    with patch("apps.api.service.AIHubMixModelProvider") as provider_factory:
        resume_response = client.post(f"/api/v1/episodes/{resume_id}/resume")
    assert resume_response.status_code == 400
    provider_factory.assert_not_called()


def test_gridworld_old_real_budget_remains_a_valid_task(
    product_client: tuple[TestClient, EpisodeService],
) -> None:
    _, service = product_client
    source = service._get_gridworld_task(TASK_NAME)
    legacy_task = source.model_copy(
        update={
            "version": f"{source.version}+temporary-real-100k-v1",
            "token_budget": 100_000,
            "evaluator_config": {
                **source.evaluator_config,
                "budget_profile": "temporary-real-100k-v1",
                "source_token_budget": 16_000,
            },
        }
    )
    GridWorldEnvironment().reset(legacy_task, seed=1)


@pytest.mark.parametrize(
    ("scenario", "steps", "success"),
    [("success", 14, True), ("illegal-action", 15, True), ("max-steps", 20, False)],
)
def test_gallery_has_its_own_budget_and_public_observations(
    product_client: tuple[TestClient, EpisodeService], scenario: str, steps: int, success: bool
) -> None:
    client, service = product_client
    request = {**_episode_request(scenario), "task_id": GALLERY_TASK_NAME, "max_steps": 20}
    assert client.post("/api/v1/episodes", json={**request, "max_steps": 16}).status_code == 422
    response = client.post("/api/v1/episodes", json=request)
    assert response.status_code == 201
    artifact = response.json()["artifact"]
    episode = artifact["episode"]
    assert episode["step_count"] == steps
    assert artifact["evaluation"]["success"] is success
    assert artifact["agent"]["budget"]["max_model_calls"] == 20
    assert artifact["agent"]["budget"]["max_completion_tokens"] == 16_000
    initial = next(
        event["payload"]["initial_state"]
        for event in artifact["events"]
        if event["event_type"] == "OBSERVATION_CREATED"
    )
    assert initial["position"] == [1, 3]
    assert {cell["kind"] for cell in initial["known_cells"]} == {"floor", "wall"}
    if success:
        assert episode["final_state"]["position"] == [7, 3]
    else:
        assert episode["termination_reason"] == "MAX_STEPS"
    assert client.get(f"/api/v1/episodes/{episode['episode_id']}").json()["artifact"] == artifact
    environment = GridWorldEnvironment()
    environment.reset(service._get_gridworld_task(GALLERY_TASK_NAME), seed=1)
    environment.restore(environment.snapshot())


def test_gallery_shortest_solution_requires_the_door_and_fourteen_actions() -> None:
    layout = GRID_LAYOUTS[GALLERY_TASK_NAME]
    todo = deque([(layout.start, 0, 0)])
    visited = {(layout.start, 0)}
    shortest = None
    while todo:
        position, phase, steps = todo.popleft()
        if position == layout.goal:
            assert phase == 2
            shortest = steps
            break
        x, y = position
        successors = [
            (target, phase)
            for target in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
            if target not in layout.walls and (phase == 2 or target != layout.door)
        ]
        if (position == layout.key and phase == 0) or (
            phase == 1 and abs(x - layout.door[0]) + abs(y - layout.door[1]) == 1
        ):
            successors.append((position, phase + 1))
        for state in successors:
            if state not in visited:
                visited.add(state)
                todo.append((*state, steps + 1))
    assert shortest == 14


def _crash_gridworld_after_actions(
    artifacts: Path, database: Path, action_count: int, episode_id: UUID
) -> None:
    service = EpisodeService(artifacts_dir=artifacts, database_path=database)
    assert service._sqlite_store is not None
    store = service._sqlite_store
    task = service._get_gridworld_task(TASK_NAME)
    agent = service._gridworld_agent()
    config = RunConfig(
        seed=1,
        environment_version=ENVIRONMENT_VERSION,
        runtime_version=runtime_version("handwritten"),
    )
    environment = GridWorldEnvironment()
    recorder = JsonTraceRecorder(config, episode_id=episode_id)

    def save(state: Any) -> None:
        checkpoint = build_checkpoint(state, agent, task, config, recorder, "success")
        store.save_checkpoint(checkpoint)
        if state.next_node == "model" and state.budget.tool_call_count == action_count:
            os._exit(0)

    asyncio.run(
        run_episode(
            agent,
            task,
            config,
            create_runtime(agent, GridWorldFakeProvider("success"), environment._validator),
            environment,
            GridWorldKeyDoorEvaluator(),
            recorder=recorder,
            save_checkpoint=save,
        )
    )
    raise AssertionError("GridWorld worker did not stop after its committed checkpoint")


@pytest.mark.parametrize(
    ("saved_actions", "has_key", "door_open", "episode_id"),
    [
        (3, True, False, UUID("e9346d5f-ae63-47bd-b5b9-9b99b6bb1230")),
        (5, False, True, UUID("a6b0bd6b-3854-485e-a187-5e9d45fd9419")),
    ],
)
def test_gridworld_private_checkpoint_resumes_after_process_exit(
    tmp_path: Path, saved_actions: int, has_key: bool, door_open: bool, episode_id: UUID
) -> None:
    artifacts = tmp_path / "artifacts"
    database = artifacts / "agentlabyrinth.sqlite3"
    worker = subprocess.run(
        [
            sys.executable,
            str(Path(__file__)),
            "--crash-gridworld",
            str(artifacts),
            str(database),
            str(saved_actions),
            str(episode_id),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert worker.returncode == 0, worker.stderr

    restarted = EpisodeService(artifacts_dir=artifacts, database_path=database)
    resumable = restarted.resumable_episode_ids()
    assert resumable == [episode_id]
    assert restarted.get_episode(episode_id) is None
    assert restarted._sqlite_store is not None
    checkpoint = restarted._sqlite_store.load_checkpoint(episode_id)
    assert checkpoint.session.budget.tool_call_count == saved_actions
    assert checkpoint.session.last_state["has_key"] is has_key
    assert checkpoint.session.last_state["door_open"] is door_open
    restored = GridWorldEnvironment()
    restored.reset(restarted._get_gridworld_task(TASK_NAME), seed=1)
    restored.restore(checkpoint.session.last_state)
    restored_public = restored.public_state()
    assert restored_public["environment_version"] == ENVIRONMENT_VERSION
    assert restored_public["action_count"] == saved_actions
    restored_known_cells = restored_public["known_cells"]
    saved_known_cells = checkpoint.session.last_state["known_cells"]
    assert isinstance(restored_known_cells, list)
    assert isinstance(saved_known_cells, list)
    assert len(restored_known_cells) == len(saved_known_cells)
    last_public_event = next(
        event for event in reversed(checkpoint.events) if event.event_type == "ENVIRONMENT_UPDATED"
    )
    assert last_public_event.payload["state"] == restored_public

    tampered_private = dict(checkpoint.session.last_state)
    known_cells = tampered_private["known_cells"]
    assert isinstance(known_cells, list)
    tampered_cells: list[JsonValue] = []
    for cell in known_cells:
        assert isinstance(cell, dict)
        tampered_cells.append(cell.copy())
    stale_cell: dict[str, JsonValue] | None = None
    for cell in tampered_cells:
        if not isinstance(cell, dict):
            continue
        observed_at_action = cell.get("observed_at_action")
        if isinstance(observed_at_action, int) and observed_at_action < saved_actions:
            stale_cell = cell
            break
    assert stale_cell is not None
    observed_at_action = stale_cell["observed_at_action"]
    assert isinstance(observed_at_action, int)
    stale_cell["observed_at_action"] = observed_at_action + 1
    tampered_private["known_cells"] = tampered_cells
    tampered_session = checkpoint.session.model_copy(update={"last_state": tampered_private})
    tampered_environment = GridWorldEnvironment()
    tampered_runtime = HandwrittenRuntime(
        GridWorldFakeProvider("success", initial_call_count=saved_actions),
        tampered_environment._validator,
    )
    with pytest.raises(ValueError, match="differs from the saved Trace prefix"):
        asyncio.run(
            tampered_runtime.run_resumable(
                checkpoint.agent,
                checkpoint.task,
                tampered_environment,
                checkpoint.validated_recorder(),
                resume_state=tampered_session,
            )
        )

    artifact = asyncio.run(restarted.resume_episode(episode_id))
    assert artifact.evaluation.success
    assert artifact.episode.step_count == 8
    assert artifact.episode.tool_call_count == 8
    assert artifact.events[: len(checkpoint.events)] == checkpoint.events
    assert sum(event.event_type == "MODEL_REQUESTED" for event in artifact.events) == 8
    assert restarted.resumable_episode_ids() == []
    assert restarted.get_episode(episode_id) == artifact
    assert not (artifacts / f"{episode_id}.json").exists()

    payload = json.dumps(artifact.model_dump(mode="json"))
    assert '"has_key"' not in payload
    assert '"door_open"' not in payload
    assert '"visible_cells"' not in payload
    with sqlite3.connect(database) as connection:
        kind, stored_payload = connection.execute(
            "SELECT kind, payload FROM episode_records WHERE episode_id=?", (str(episode_id),)
        ).fetchone()
    assert kind == "finished"
    assert json.loads(stored_payload) == artifact.model_dump(mode="json")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--crash-gridworld":
    _crash_gridworld_after_actions(
        Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), UUID(sys.argv[5])
    )
