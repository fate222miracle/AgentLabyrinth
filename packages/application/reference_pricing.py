"""Versioned model-maker list-price estimates, separate from gateway billing."""

import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

from packages.domain.models import EstimatedCost, TokenUsage


@lru_cache(maxsize=1)
def _table() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        Path(__file__).with_name("official_reference_prices.json").read_text(encoding="utf-8")
    )
    if (
        data.get("schema_version") != "1.0"
        or data.get("currency") != "USD"
        or data.get("unit_tokens") != 1_000_000
        or not isinstance(data.get("price_table_version"), str)
        or not isinstance(data.get("models"), dict)
    ):
        raise ValueError("Invalid official reference price table")
    return data


def reference_price_version(model_id: str) -> str | None:
    """Return the verified snapshot version for one exact gateway model ID."""
    table = _table()
    return table["price_table_version"] if model_id in table["models"] else None


def official_reference_cost(model_id: str, usage: TokenUsage) -> EstimatedCost | None:
    """Use all prompt tokens at the uncached rate when cache-hit usage is unavailable."""
    if usage.simulated:
        return None
    table = _table()
    row = table["models"].get(model_id)
    if row is None:
        return None
    try:
        input_rate = Decimal(row["input_uncached"])
        output_rate = Decimal(row["output"])
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError("Invalid official reference price") from exc
    if input_rate < 0 or output_rate < 0:
        raise ValueError("Negative official reference price")
    amount = (input_rate * usage.prompt_tokens + output_rate * usage.completion_tokens) / Decimal(
        table["unit_tokens"]
    )
    return EstimatedCost(amount=amount, price_table_version=table["price_table_version"])
