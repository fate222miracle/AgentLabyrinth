"""Model-maker reference prices are separate from gateway charges."""

from decimal import Decimal

import pytest

from packages.application.reference_pricing import official_reference_cost, reference_price_version
from packages.domain.models import TokenUsage


@pytest.mark.parametrize(
    "model_id,input_rate,output_rate",
    [
        ("coding-minimax-m2.7-free", "0.30", "1.20"),
        ("xiaomi-mimo-v2.6-pro-free", "0.435", "0.87"),
        ("xiaomi-mimo-v2.5-pro-free", "0.435", "0.87"),
        ("coding-glm-5.3-free", "1.40", "4.40"),
    ],
)
def test_official_reference_cost_uses_uncached_input(
    model_id: str, input_rate: str, output_rate: str
) -> None:
    """One million prompt and completion tokens reproduce the reviewed rate card."""
    usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000, simulated=False)
    cost = official_reference_cost(model_id, usage)
    assert cost is not None
    assert cost.amount == Decimal(input_rate) + Decimal(output_rate)
    assert cost.price_table_version == reference_price_version(model_id)
    assert cost.currency == "USD" and cost.estimated


def test_reference_price_does_not_invent_unknown_or_fake_charges() -> None:
    """Unknown IDs and simulated usage cannot enter the official reference metric."""
    usage = TokenUsage(prompt_tokens=100, completion_tokens=20, simulated=False)
    assert official_reference_cost("custom-free-model", usage) is None
    assert reference_price_version("custom-free-model") is None
    assert (
        official_reference_cost("coding-glm-5.3-free", usage.model_copy(update={"simulated": True}))
        is None
    )
