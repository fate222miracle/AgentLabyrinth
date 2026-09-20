"""Tests for the real-model verification command's safe local boundaries."""

import asyncio
import json
from pathlib import Path

import pytest

from scripts.verify_selected_models import catalog_model_ids, verify_models


def test_catalog_model_ids_selects_only_aihubmix(tmp_path: Path) -> None:
    catalog = tmp_path / "models.json"
    catalog.write_text(
        json.dumps(
            {
                "models": [
                    {"id": "free-a", "provider": "aihubmix"},
                    {"id": "fake", "provider": "fake"},
                    {"id": "free-b", "provider": "aihubmix"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert catalog_model_ids(catalog) == ("free-a", "free-b")


def test_verification_stops_before_network_without_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("AIHUBMIX_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="AIHUBMIX_API_KEY is not configured"):
        asyncio.run(verify_models(("free-a",), tmp_path / "results.json"))

    assert not (tmp_path / "results.json").exists()
