"""Independent Episode reviews never alter execution artifacts or rerun a model."""

import asyncio
import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateEpisodeRequest
from apps.api.service import EpisodeService
from packages.application.review import (
    JUDGE_SYSTEM_PROMPT,
    EpisodeReviewArtifact,
    build_review_input,
    create_judge_review,
    read_review,
    write_review,
)
from packages.domain.models import (
    EpisodeArtifact,
    EstimatedCost,
    FinalAnswer,
    ModelConfig,
    ModelResponse,
    TokenUsage,
)
from packages.providers.fake import FakeModelProvider


@pytest.fixture
def review_client(tmp_path: Path) -> Generator[tuple[TestClient, EpisodeService], None, None]:
    """Use isolated artifacts and no live model catalog."""
    service = EpisodeService(artifacts_dir=tmp_path)
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client, service
    finally:
        app.dependency_overrides.clear()


def create_episode(service: EpisodeService, scenario: str = "success") -> EpisodeArtifact:
    """Create one saved Fake Episode through the normal service boundary."""
    return asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(
                schema_version="1.4",
                provider="fake",
                model="fake-model",
                scenario=scenario,
                task_id="order-status-001",
                tool_call_mode="single",
            )
        )
    )


def human_payload(episode_id: str, *, event_ids: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "episode_id": episode_id,
        "method": "human",
        "human": {
            "reviewer_label": "课堂复核",
            "verdict": "pass",
            "answer_correctness": "pass",
            "evidence_support": "pass",
            "process_safety": "pass",
            "rationale": "答案与已读取证据一致。",
            "event_ids": event_ids or [],
        },
    }


def test_human_reviews_are_additive_and_source_bound(
    review_client: tuple[TestClient, EpisodeService],
) -> None:
    """Two annotations create two files while the Episode remains byte-identical."""
    client, service = review_client
    episode = create_episode(service)
    source = service.artifacts_dir / f"{episode.episode.episode_id}.json"
    original = source.read_bytes()
    event_id = str(episode.events[-1].event_id)

    first = client.post(
        "/api/v1/episode-reviews",
        json=human_payload(str(episode.episode.episode_id), event_ids=[event_id]),
    )
    second = client.post(
        "/api/v1/episode-reviews", json=human_payload(str(episode.episode.episode_id))
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["review"]["review_id"] != second.json()["review"]["review_id"]
    assert source.read_bytes() == original

    listed = client.get(f"/api/v1/episodes/{episode.episode.episode_id}/reviews")
    assert listed.status_code == 200
    assert len(listed.json()["reviews"]) == 2
    review_id = first.json()["review"]["review_id"]
    assert (
        client.get(f"/api/v1/episode-reviews/{review_id}").json()["review"]["episode_content_hash"]
        == first.json()["review"]["episode_content_hash"]
    )


@pytest.mark.parametrize(
    "scenario,status,failure,usage",
    [
        ("success", "completed", None, True),
        ("invalid_json", "failed", "INVALID_JUDGE_OUTPUT", True),
        ("bad_reference", "failed", "INVALID_EVENT_REFERENCE", True),
        ("provider_error", "failed", "JUDGE_PROVIDER_ERROR", False),
    ],
)
def test_fake_judge_records_one_outcome(
    review_client: tuple[TestClient, EpisodeService],
    scenario: str,
    status: str,
    failure: str | None,
    usage: bool,
) -> None:
    """Fake outcomes remain labeled and malformed output is never repaired or retried."""
    client, service = review_client
    episode = create_episode(service)
    response = client.post(
        "/api/v1/episode-reviews",
        json={
            "episode_id": str(episode.episode.episode_id),
            "method": "llm_judge",
            "judge_scenario": scenario,
        },
    )
    assert response.status_code == 201
    review = response.json()["review"]
    assert review["status"] == status and review["failure_code"] == failure
    assert (review["token_usage"] is not None) is usage
    assert review["provider"] == "fake" and review["model"] == "fake-judge-v1"
    assert review["prompt_version"] == "episode-review-v2"


def real_judge_payload(episode_id: str) -> dict[str, object]:
    """Select a real provider explicitly while tests replace its transport."""
    return {
        "schema_version": "1.1",
        "episode_id": episode_id,
        "method": "llm_judge",
        "judge_provider": "aihubmix",
        "judge_model": "coding-minimax-m2.7-free",
    }


@pytest.mark.parametrize("outcome", ["valid", "invalid_json", "bad_reference", "provider_error"])
def test_real_judge_entry_calls_once_and_preserves_source(
    review_client: tuple[TestClient, EpisodeService], outcome: str
) -> None:
    """A mocked real transport exercises the public path with no live inference."""
    client, service = review_client
    episode = create_episode(service)
    source = service.artifacts_dir / f"{episode.episode.episode_id}.json"
    original = source.read_bytes()
    text = json.dumps(
        {
            "verdict": "pass",
            "answer_correctness": "pass",
            "evidence_support": "pass",
            "process_safety": "pass",
            "rationale": "Offline fixture: the saved evidence supports the answer.",
            "event_ids": [
                str(uuid4() if outcome == "bad_reference" else episode.events[0].event_id)
            ],
        }
    )
    provider = (
        FakeModelProvider("unparseable")
        if outcome == "provider_error"
        else FakeModelProvider(
            custom_responses=[
                ModelResponse(
                    action=FinalAnswer(text="not-json" if outcome == "invalid_json" else text),
                    token_usage=TokenUsage(prompt_tokens=11, completion_tokens=7),
                    estimated_cost=EstimatedCost(is_known=False, price_table_version="unverified"),
                )
            ]
        )
    )
    with (
        patch("apps.api.service.AIHubMixModelProvider", return_value=provider) as factory,
        patch.object(provider, "generate", wraps=provider.generate) as generate,
    ):
        response = client.post(
            "/api/v1/episode-reviews", json=real_judge_payload(str(episode.episode.episode_id))
        )
    assert response.status_code == 201
    assert generate.call_count == 1
    factory.assert_called_once_with(timeout=30.0, min_request_interval=13.0, reasoning_split=True)
    messages, tools, config = generate.call_args.args
    assert tools == [] and config.provider == "aihubmix" and config.max_tokens == 800
    assert messages[0].content == JUDGE_SYSTEM_PROMPT
    assert "evaluation" not in messages[1].content
    review = response.json()["review"]
    assert review["provider"] == "aihubmix" and review["model"] == "coding-minimax-m2.7-free"
    assert review["prompt_version"] == "episode-review-v2"
    if outcome == "valid":
        assert review["status"] == "completed" and review["verdict"] == "pass"
        assert review["token_usage"]["prompt_tokens"] == 11
    else:
        assert review["status"] == "failed" and review["verdict"] is None
        assert (
            review["failure_code"]
            == {
                "invalid_json": "INVALID_JUDGE_OUTPUT",
                "bad_reference": "INVALID_EVENT_REFERENCE",
                "provider_error": "JUDGE_PROVIDER_ERROR",
            }[outcome]
        )
    assert review["estimated_cost"]["is_known"] is False
    assert source.read_bytes() == original
    assert len(list((service.artifacts_dir / "reviews").glob("*.json"))) == 1
    assert client.get(f"/api/v1/episode-reviews/{review['review_id']}").status_code == 200
    assert client.get(f"/api/v1/episodes/{episode.episode.episode_id}/reviews").status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "1.0"},
        {"schema_version": "1.0", "judge_provider": None, "judge_model": None},
        {"schema_version": "1.2"},
        {"judge_provider": "fake"},
        {"judge_model": None},
        {"judge_model": " "},
        {"method": "human"},
        {"human": None},
        {"judge_scenario": "success"},
        {"judge_scenario": None},
    ],
)
def test_real_judge_request_revisions_fail_before_transport(
    review_client: tuple[TestClient, EpisodeService], changes: dict[str, object]
) -> None:
    """Old requests never silently become real calls; mixed inputs fail closed."""
    client, service = review_client
    episode = create_episode(service)
    with patch("apps.api.service.AIHubMixModelProvider") as factory:
        response = client.post(
            "/api/v1/episode-reviews",
            json={**real_judge_payload(str(episode.episode.episode_id)), **changes},
        )
    assert response.status_code == 422
    factory.assert_not_called()


@pytest.mark.parametrize("condition", ["unlisted", "missing_submission", "oversized", "catalog"])
def test_real_judge_preflight_spends_no_calls(
    review_client: tuple[TestClient, EpisodeService], condition: str
) -> None:
    """Source, byte-size, whitelist and catalog rejection precede provider creation."""
    client, service = review_client
    episode = create_episode(
        service, "invalid-arguments" if condition == "missing_submission" else "success"
    )
    payload = real_judge_payload(str(episode.episode.episode_id))
    if condition == "unlisted":
        payload["judge_model"] = "arbitrary-unlisted-model"
    review_input = build_review_input(episode, require_submission=False)
    if condition == "oversized":
        review_input = review_input.model_copy(update={"task": {"description": "数" * 22000}})
    with (
        patch("apps.api.service.AIHubMixModelProvider") as factory,
        patch("apps.api.service.build_review_input", return_value=review_input)
        if condition == "oversized"
        else patch("apps.api.service.build_review_input", wraps=build_review_input),
        patch.object(service, "_require_live_model", side_effect=ValueError("catalog unavailable"))
        if condition == "catalog"
        else patch.object(service, "_require_live_model", return_value=None),
    ):
        response = client.post("/api/v1/episode-reviews", json=payload)
    assert response.status_code == 400
    factory.assert_not_called()
    assert not list((service.artifacts_dir / "reviews").glob("*.json"))


def test_legacy_v1_review_stays_readable_after_prompt_upgrade(
    review_client: tuple[TestClient, EpisodeService],
) -> None:
    """Reviews saved under episode-review-v1 keep loading; only new calls use v2."""
    client, service = review_client
    episode = create_episode(service)
    created = client.post(
        "/api/v1/episode-reviews",
        json={"episode_id": str(episode.episode.episode_id), "method": "llm_judge"},
    ).json()["review"]
    source = service.artifacts_dir / "reviews" / f"{created['review_id']}.json"
    legacy = EpisodeReviewArtifact.model_validate_json(source.read_text(encoding="utf-8"))
    legacy_id = uuid4()
    legacy = legacy.model_copy(
        update={"review_id": legacy_id, "prompt_version": "episode-review-v1"}
    )
    legacy_path = source.with_name(f"{legacy_id}.json")
    write_review(legacy, legacy_path)
    original = legacy_path.read_bytes()
    assert read_review(legacy_path).prompt_version == "episode-review-v1"
    with patch(
        "packages.providers.fake.FakeModelProvider.generate",
        new=AsyncMock(side_effect=AssertionError("History must not invoke provider")),
    ):
        loaded = client.get(f"/api/v1/episode-reviews/{legacy_id}")
        assert loaded.status_code == 200
        assert loaded.json()["review"]["prompt_version"] == "episode-review-v1"
        listed = client.get(f"/api/v1/episodes/{episode.episode.episode_id}/reviews")
        assert listed.status_code == 200
        assert {item["prompt_version"] for item in listed.json()["reviews"]} == {
            "episode-review-v1",
            "episode-review-v2",
        }
    assert legacy_path.read_bytes() == original


@pytest.mark.parametrize(
    "text",
    [
        '<think>reasoning</think>{"verdict":"pass"}',
        '```json\n{"verdict":"pass"}\n```',
        '{"verdict":"PASS","answer_correctness":true,"evidence_support":true,'
        '"process_safety":true,"rationale":"review","event_ids":[]}',
        '{"verdict":"pass","answer_correctness":"pass","evidence_support":"pass",'
        '"process_safety":"pass","rationale":"review","event_ids":[]} trailing',
    ],
)
def test_v2_prompt_is_sent_once_without_repairing_nonconforming_output(
    review_client: tuple[TestClient, EpisodeService], text: str
) -> None:
    """The real v1 failure shapes remain failures after upgrading the prompt."""
    _, service = review_client
    episode = create_episode(service)
    provider = FakeModelProvider(custom_responses=[ModelResponse(action=FinalAnswer(text=text))])
    with patch.object(provider, "generate", new=AsyncMock(wraps=provider.generate)) as generate:
        review = asyncio.run(
            create_judge_review(episode, provider, ModelConfig(provider="fake", model="fake-judge"))
        )
    generate.assert_awaited_once()
    messages, tools, _ = generate.call_args.args
    assert messages[0].content == JUDGE_SYSTEM_PROMPT
    assert tools == []
    assert "evaluation" not in messages[1].content
    assert review.prompt_version == "episode-review-v2"
    assert review.status == "failed" and review.failure_code == "INVALID_JUDGE_OUTPUT"
    assert review.verdict is None


def test_gets_never_call_a_judge_and_bad_references_fail_closed(
    review_client: tuple[TestClient, EpisodeService],
) -> None:
    """History is GET-only; a human cannot cite a foreign Trace event."""
    client, service = review_client
    episode = create_episode(service)
    bad = client.post(
        "/api/v1/episode-reviews",
        json=human_payload(str(episode.episode.episode_id), event_ids=[str(uuid4())]),
    )
    assert bad.status_code == 400
    assert list((service.artifacts_dir / "reviews").glob("*.json")) == []

    created = client.post(
        "/api/v1/episode-reviews", json=human_payload(str(episode.episode.episode_id))
    ).json()["review"]
    with patch(
        "packages.providers.fake.FakeModelProvider.generate",
        new=AsyncMock(side_effect=AssertionError("GET must not invoke provider")),
    ):
        assert client.get(f"/api/v1/episode-reviews/{created['review_id']}").status_code == 200
        assert (
            client.get(f"/api/v1/episodes/{episode.episode.episode_id}/reviews").status_code == 200
        )


def test_review_input_omits_deterministic_verdict_and_detects_source_tampering(
    review_client: tuple[TestClient, EpisodeService],
) -> None:
    """Judge input is independent of the old verdict; source hashes still guard storage."""
    client, service = review_client
    episode = create_episode(service)
    altered = episode.model_copy(
        update={
            "evaluation": episode.evaluation.model_copy(
                update={"success": not episode.evaluation.success, "reason": "changed"}
            )
        }
    )
    assert build_review_input(episode) == build_review_input(altered)

    review = client.post(
        "/api/v1/episode-reviews", json=human_payload(str(episode.episode.episode_id))
    ).json()["review"]
    source = service.artifacts_dir / f"{episode.episode.episode_id}.json"
    source.write_text(altered.model_dump_json(indent=2), encoding="utf-8")
    assert client.get(f"/api/v1/episode-reviews/{review['review_id']}").status_code == 409


def test_review_request_method_boundary(
    review_client: tuple[TestClient, EpisodeService],
) -> None:
    """Human and Judge inputs cannot be mixed or omitted."""
    client, service = review_client
    episode = create_episode(service)
    episode_id = str(episode.episode.episode_id)
    assert (
        client.post(
            "/api/v1/episode-reviews",
            json={"episode_id": episode_id, "method": "human"},
        ).status_code
        == 422
    )
    mixed = human_payload(episode_id)
    mixed["judge_scenario"] = "success"
    assert client.post("/api/v1/episode-reviews", json=mixed).status_code == 422


def test_missing_submission_allows_only_an_uncertain_human_record(
    review_client: tuple[TestClient, EpisodeService],
) -> None:
    """A failed run remains auditable by a human but cannot be judged or marked correct."""
    client, service = review_client
    episode = create_episode(service, "invalid-arguments")
    episode_id = str(episode.episode.episode_id)
    payload = human_payload(episode_id)
    human = payload["human"]
    assert isinstance(human, dict)
    human.update(
        verdict="uncertain",
        answer_correctness="unknown",
        evidence_support="unknown",
        process_safety="fail",
        rationale="运行未产生最终提交，人工仅记录过程问题。",
    )
    assert client.post("/api/v1/episode-reviews", json=payload).status_code == 201

    human["verdict"] = "pass"
    assert client.post("/api/v1/episode-reviews", json=payload).status_code == 400
    assert (
        client.post(
            "/api/v1/episode-reviews",
            json={"episode_id": episode_id, "method": "llm_judge"},
        ).status_code
        == 400
    )
