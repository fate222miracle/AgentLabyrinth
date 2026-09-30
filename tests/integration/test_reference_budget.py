"""Official reference budget stops later Episodes without rewriting gateway billing."""

import asyncio
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.api.schemas import CreateExperimentRequest
from apps.api.service import EpisodeService
from packages.application.experiment import ReferenceCostBudgetExceeded
from packages.domain.models import EstimatedCost, Message, ModelConfig, ModelResponse, ToolSchema
from packages.providers.aihubmix import AIHubMixModelProvider
from packages.providers.fake import FakeModelProvider


def test_reference_budget_and_gateway_cost_remain_separate(tmp_path: Path) -> None:
    """A paid-equivalent threshold is enforced only between saved Episodes."""
    calls = 0
    fake_providers: dict[AIHubMixModelProvider, FakeModelProvider] = {}

    async def offline(
        self: AIHubMixModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        nonlocal calls
        calls += 1
        provider = fake_providers.get(self)
        if provider is None:
            provider = FakeModelProvider(scenario="success")
            fake_providers[self] = provider
        response = await provider.generate(messages, tools, config)
        return response.model_copy(
            update={
                "token_usage": response.token_usage.model_copy(update={"simulated": False}),
                "estimated_cost": EstimatedCost(
                    price_table_version="gateway-unverified", is_known=False
                ),
            }
        )

    service = EpisodeService(artifacts_dir=tmp_path)
    request = CreateExperimentRequest(
        provider="aihubmix",
        model="coding-minimax-m2.7-free",
        task_ids=["order-status-001"],
        max_reference_cost_usd=Decimal("1"),
    )
    with patch.object(AIHubMixModelProvider, "generate", offline):
        result = asyncio.run(service.execute_experiment(request))
    assert calls > 0
    assert result.metrics.is_cost_known is False
    assert result.metrics.is_reference_cost_known
    assert result.metrics.baseline_total_reference_cost is not None
    assert result.metrics.baseline_total_reference_cost > 0
    assert result.metrics.recovery_total_reference_cost is not None
    assert result.metrics.recovery_total_reference_cost > 0
    first = service.get_episode(result.episode_ids[0])
    assert first is not None and first.reference_cost is not None
    assert first.episode.estimated_cost.is_known is False
    assert first.reference_cost.price_table_version == "official-reference-2026-09-30"

    limited = EpisodeService(artifacts_dir=tmp_path / "limited")
    with patch.object(AIHubMixModelProvider, "generate", offline):
        with pytest.raises(ReferenceCostBudgetExceeded):
            asyncio.run(
                limited.execute_experiment(
                    request.model_copy(update={"max_reference_cost_usd": Decimal("0.000001")})
                )
            )
    assert len(list((tmp_path / "limited").glob("*.json"))) == 1
    assert len(list((tmp_path / "limited" / "experiments" / "checkpoints").glob("*.json"))) == 1
