"""The portable course pack verifies failures and survives a real child exit."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from apps.api.schemas import CreateEpisodeRequest
from packages.domain.models import EpisodeArtifact, EventType, TerminationReason
from scripts.course_demo import DemoService, generate, preview

ROOT = Path(__file__).resolve().parents[2]


def test_local_pack_preserves_identity_and_truthful_timeout(tmp_path: Path) -> None:
    """Exercise the user entry point and inspect saved artifacts, not just its exit code."""
    directory = tmp_path / "pack"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.course_demo",
            "--skip-mcp",
            "--artifacts-dir",
            str(directory),
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=40,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    report = json.loads((directory / "demo-index.json").read_text(encoding="utf-8"))
    assert report["provider"] == "fake"
    assert report["mcp_http_verified"] is False
    assert "mcp_success" not in report["cases"]

    def episode(name: str) -> EpisodeArtifact:
        return EpisodeArtifact.model_validate_json(
            (directory / f"{report['cases'][name]}.json").read_text(encoding="utf-8")
        )

    assert episode("argument_baseline").evaluation.success is False
    assert episode("argument_recovery").evaluation.success is True
    timed_out = episode("time_limit")
    assert timed_out.episode.termination_reason == TerminationReason.TIME_BUDGET_EXCEEDED
    assert not timed_out.episode.estimated_cost.is_known
    assert timed_out.episode.tool_call_count == 0
    resumed = episode("resumed")
    assert str(resumed.episode.episode_id) == report["cases"]["resumed"]
    assert resumed.evaluation.success
    starts = [event for event in resumed.events if event.event_type == EventType.TOOL_STARTED]
    assert [event.payload["name"] for event in starts] == ["query_records", "submit_answer"]
    assert any(event.event_type == EventType.EPISODE_RESUMED for event in resumed.events)
    assert not list((directory / "checkpoints").glob("*.json"))


def test_existing_pack_is_never_overwritten(tmp_path: Path) -> None:
    """A mistaken repeated directory selection cannot destroy prior evidence."""
    marker = tmp_path / "demo-index.json"
    marker.write_bytes(b"prior-evidence")
    with pytest.raises(FileExistsError):
        generate(tmp_path, skip_mcp=True)
    assert marker.read_bytes() == b"prior-evidence"


def test_preview_rejects_live_requests_before_provider_creation(tmp_path: Path) -> None:
    """The demonstration preview cannot accidentally spend the local API Key."""
    service = DemoService(artifacts_dir=tmp_path)
    meta = service.get_meta()
    assert meta.models and all(model.provider == "fake" for model in meta.models)
    assert meta.default_model in {model.id for model in meta.models}
    with pytest.raises(ValueError, match="Fake models only"):
        asyncio.run(
            service.execute_episode(
                CreateEpisodeRequest(provider="aihubmix", model="coding-minimax-m2.7-free")
            )
        )
    assert not list(tmp_path.glob("*.json"))


def test_preview_refuses_an_existing_listener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A busy port cannot trigger a takeover or spawn competing preview processes."""
    monkeypatch.setattr("scripts.course_demo.port_in_use", lambda port: True)
    monkeypatch.setattr(
        "scripts.course_demo.subprocess.Popen",
        lambda *args, **kwargs: pytest.fail("Must not spawn a competing preview"),
    )
    with pytest.raises(RuntimeError, match="occupied"):
        preview(tmp_path)
    assert list(tmp_path.iterdir()) == []
