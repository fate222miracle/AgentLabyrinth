"""The real-model probe stays bounded and reports saved evidence, including failures."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from apps.api.service import EpisodeService
from packages.domain.models import ModelResponse, ToolCall
from packages.domain.ports import ModelProviderError
from packages.providers.fake import FakeModelProvider
from scripts.episodic_memory_ablation import run_window_pair


def test_same_window_pair_uses_saved_artifacts_and_rejects_overwrite(tmp_path: Path) -> None:
    """Only memory changes; two saved Fake episodes verify the production probe path."""
    service = EpisodeService(artifacts_dir=tmp_path / "episodes")
    directory = tmp_path / "report"
    rows = asyncio.run(run_window_pair(directory, service, "fake", provider="fake"))
    report = json.loads((directory / "memory-pair.json").read_text(encoding="utf-8"))
    assert report["simulated"] and report["paired"] and report["cases"] == rows
    assert [row["success"] for row in rows] == [False, True]
    assert rows[0]["evaluation_reason"] == "evidence_mismatch"
    assert all(row["tool_calls"] == 5 and row["repeated_document_reads"] == 0 for row in rows)
    assert rows[1]["submission"] == {
        "answer": "approved",
        "evidence": ["document:RET-DECISION", "document:RET-ENTRY", "document:RET-POLICY"],
    }
    assert len(list((tmp_path / "episodes").glob("*.json"))) == 2
    hashes = [row["config_hashes"] for row in report["cases"]]
    assert hashes[0]["agent"] != hashes[1]["agent"]
    assert hashes[0]["task"] == hashes[1]["task"]
    assert hashes[0]["run_config"] == hashes[1]["run_config"]
    with pytest.raises(FileExistsError):
        asyncio.run(run_window_pair(directory, service, "fake", provider="fake"))
    assert json.loads((directory / "memory-pair.json").read_text()) == report


def test_provider_failure_preserves_partial_report_and_stops(tmp_path: Path) -> None:
    """An unavailable provider does not trigger retries, another arm or false zero-token gain."""
    service = EpisodeService(artifacts_dir=tmp_path / "episodes")
    provider = FakeModelProvider()
    with (
        patch("apps.api.service.FakeModelProvider", return_value=provider),
        patch.object(
            provider, "generate", AsyncMock(side_effect=ModelProviderError("REQUEST_TIMEOUT"))
        ) as generate,
    ):
        rows = asyncio.run(run_window_pair(tmp_path / "report", service, "fake", provider="fake"))
    assert generate.call_count == 1
    assert len(rows) == 1 and not rows[0]["success"]
    assert rows[0]["detail"] == "provider_error: REQUEST_TIMEOUT"
    report = json.loads((tmp_path / "report/memory-pair.json").read_text())
    assert report["paired"] is False
    assert len(list((tmp_path / "episodes").glob("*.json"))) == 1


def test_missing_saved_artifact_rejects_report(tmp_path: Path) -> None:
    """In-memory outcomes cannot become a report when their durable evidence is missing."""
    service = EpisodeService(artifacts_dir=tmp_path / "episodes")
    with patch.object(service, "get_episode", return_value=None):
        with pytest.raises(ValueError, match="provenance"):
            asyncio.run(run_window_pair(tmp_path / "report", service, "fake", provider="fake"))
    assert not (tmp_path / "report/memory-pair.json").exists()


def test_repeat_count_requires_actual_document_not_just_tool_success(tmp_path: Path) -> None:
    """An empty successful return is not a document read; identical real returns are repeats."""
    service = EpisodeService(artifacts_dir=tmp_path / "episodes")
    responses = [
        ModelResponse(
            action=ToolCall(
                call_id=str(i),
                name="read_document",
                arguments={
                    "document_id": document_id,
                },
            )
        )
        for i, document_id in enumerate(("RET-ENTRY", "RET-ENTRY", "missing"))
    ] + [
        ModelResponse(
            action=ToolCall(
                call_id="submit",
                name="submit_answer",
                arguments={
                    "answer": "approved",
                    "evidence": ["document:RET-ENTRY"],
                },
            )
        )
    ]
    with patch(
        "apps.api.service.FakeModelProvider",
        side_effect=lambda **_: FakeModelProvider(
            custom_responses=responses,
        ),
    ):
        rows = asyncio.run(run_window_pair(tmp_path / "report", service, "fake", provider="fake"))
    assert all(not row["success"] and row["tool_calls"] == 4 for row in rows)
    assert all(row["successful_document_reads"] == ["RET-ENTRY", "RET-ENTRY"] for row in rows)
    assert all(row["repeated_document_reads"] == 1 for row in rows)
