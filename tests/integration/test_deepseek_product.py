"""Paid-provider routing across ToolLab, a comparison, and a saved Judge."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.api.schemas import (
    CreateEpisodeRequest,
    CreateEpisodeReviewRequest,
    CreateExperimentRequest,
)
from apps.api.service import EpisodeService
from packages.domain.models import EstimatedCost, FinalAnswer, ModelResponse, TokenUsage
from packages.providers.fake import FakeModelProvider


def test_deepseek_routes_toollab_experiment_and_episode_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    service = EpisodeService(artifacts_dir=tmp_path, database_path=tmp_path / "episodes.sqlite3")
    request = {"provider": "deepseek", "model": "deepseek-flash", "token_budget": 8000}
    # Every arm gets its own provider. Connection dispatch is substituted in this test.
    with patch(
        "apps.api.service.DeepSeekModelProvider", side_effect=lambda: FakeModelProvider("success")
    ):
        episode = asyncio.run(service.execute_episode(CreateEpisodeRequest.model_validate(request)))
        experiment = asyncio.run(
            service.execute_experiment(
                CreateExperimentRequest.model_validate(
                    {**request, "task_ids": ["order-status-001"]}
                )
            )
        )
    assert episode.agent.model.provider == "deepseek" and episode.evaluation.success
    assert experiment.metrics.total_pairs == 1
    for episode_id in experiment.episode_ids:
        saved = service.get_episode(episode_id)
        assert saved is not None and saved.agent.model.provider == "deepseek"
        assert saved.evaluation.success
    assert service.get_experiment(experiment.experiment_id) == experiment

    judge = FakeModelProvider(
        custom_responses=[
            ModelResponse(
                action=FinalAnswer(
                    text=json.dumps(
                        {
                            "verdict": "pass",
                            "answer_correctness": "pass",
                            "evidence_support": "pass",
                            "process_safety": "pass",
                            "rationale": "Evidence was read.",
                            "event_ids": [],
                        }
                    )
                ),
                token_usage=TokenUsage(prompt_tokens=91, completion_tokens=22, simulated=False),
                estimated_cost=EstimatedCost(
                    is_known=False, price_table_version="deepseek-official-unverified"
                ),
            )
        ]
    )
    with patch("apps.api.service.DeepSeekModelProvider", return_value=judge) as factory:
        review = asyncio.run(
            service.create_episode_review(
                CreateEpisodeReviewRequest(
                    schema_version="1.1",
                    episode_id=episode.episode.episode_id,
                    method="llm_judge",
                    judge_provider="deepseek",
                    judge_model="deepseek-flash",
                )
            )
        )
    factory.assert_called_once_with(timeout=30.0)
    assert review.provider == "deepseek" and review.verdict == "pass"
    assert service.get_episode_review(review.review_id) == review
