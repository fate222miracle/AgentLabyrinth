"""Tests for reproducible BFCL source import and cache validation."""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from scripts.import_bfcl_subset import materialize_subset


def _write_jsonl(path: Path, value: Mapping[str, Any]) -> str:
    content = (json.dumps(value, separators=(",", ":")) + "\n").encode()
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _fixture_manifest(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    questions_path = tmp_path / "questions.jsonl"
    answers_path = tmp_path / "answers.jsonl"
    question = {
        "id": "simple_python_test",
        "question": [[{"content": "Calculate the factorial of 5."}]],
        "function": [
            {
                "name": "math.factorial",
                "description": "Calculate a factorial.",
                "parameters": {
                    "type": "dict",
                    "properties": {"number": {"type": "integer"}},
                    "required": ["number"],
                },
            }
        ],
    }
    answer = {
        "id": "simple_python_test",
        "ground_truth": [{"math.factorial": {"number": [5]}}],
    }
    question_hash = _write_jsonl(questions_path, question)
    answer_hash = _write_jsonl(answers_path, answer)
    expected_cases = [
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
    ]
    serialized = json.dumps(expected_cases, ensure_ascii=False, indent=2) + "\n"
    output_content = serialized.replace("\n", "\r\n").encode()
    manifest: dict[str, object] = {
        "source_version_or_commit": "fixed-test-commit",
        "source_files": [
            {"path": "questions.jsonl", "cache_name": questions_path.name, "sha256": question_hash},
            {"path": "answers.jsonl", "cache_name": answers_path.name, "sha256": answer_hash},
        ],
        "checksum": hashlib.sha256(output_content).hexdigest(),
        "selected_cases": {"development": ["simple_python_test"], "evaluation": []},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, tmp_path / "subset.json", manifest


def test_cached_sources_rebuild_offline_with_stable_checksum(tmp_path: Path) -> None:
    manifest_path, output_path, manifest = _fixture_manifest(tmp_path)

    def fail_download(url: str, target: Path) -> object:
        pytest.fail(f"unexpected download of {url} to {target}")

    count, digest = materialize_subset(
        manifest_path=manifest_path,
        cache_dir=tmp_path,
        output_path=output_path,
        downloader=fail_download,
    )

    assert count == 1
    assert digest == manifest["checksum"]
    assert hashlib.sha256(output_path.read_bytes()).hexdigest() == digest


def test_source_checksum_mismatch_stops_without_replacing_output(tmp_path: Path) -> None:
    manifest_path, output_path, _ = _fixture_manifest(tmp_path)
    output_path.write_text("known-good-output", encoding="utf-8")
    (tmp_path / "questions.jsonl").write_text("corrupt", encoding="utf-8")

    with pytest.raises(RuntimeError, match="source checksum mismatch: questions.jsonl"):
        materialize_subset(manifest_path, tmp_path, output_path)

    assert output_path.read_text(encoding="utf-8") == "known-good-output"


def test_missing_source_reports_offline_download_failure(tmp_path: Path) -> None:
    manifest_path, output_path, _ = _fixture_manifest(tmp_path)
    (tmp_path / "questions.jsonl").unlink()

    def offline(url: str, target: Path) -> object:
        raise OSError("offline")

    with pytest.raises(RuntimeError, match="download failed and no verified cache exists"):
        materialize_subset(manifest_path, tmp_path, output_path, offline)

    assert not output_path.exists()
