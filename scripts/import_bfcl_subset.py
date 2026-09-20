"""Download and deterministically transform the pinned BFCL reference subset."""

import hashlib
import json
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/bfcl_adapted/dataset_manifest.json"
CACHE = ROOT / ".cache/bfcl"
OUTPUT = CACHE / "subset.json"
Downloader = Callable[[str, Path], object]


def sha256(path: Path) -> str:
    """Return a lowercase SHA256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(content: bytes) -> str:
    """Return a lowercase SHA256 digest for in-memory content."""
    return hashlib.sha256(content).hexdigest()


def normalize_schema(value: Any) -> Any:
    """Map BFCL's `dict` spelling to standard JSON Schema without changing fields."""
    if isinstance(value, list):
        return [normalize_schema(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "object" if key == "type" and item == "dict" else normalize_schema(item)
            for key, item in value.items()
        }
    return value


def load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    """Index a JSONL source by upstream case ID."""
    return {
        item["id"]: item
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for item in [json.loads(line)]
    }


def materialize_subset(
    manifest_path: Path = MANIFEST,
    cache_dir: Path = CACHE,
    output_path: Path = OUTPUT,
    downloader: Downloader = urllib.request.urlretrieve,
) -> tuple[int, str]:
    """Build the pinned subset from verified sources and return count and digest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    commit = manifest["source_version_or_commit"]
    raw_base = f"https://raw.githubusercontent.com/ShishirPatil/gorilla/{commit}/"
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_files: list[Path] = []
    for source in manifest["source_files"]:
        target = cache_dir / source["cache_name"]
        if not target.exists():
            try:
                downloader(raw_base + source["path"], target)
            except OSError as exc:
                target.unlink(missing_ok=True)
                raise RuntimeError(
                    f"BFCL source unavailable: {target.name}; "
                    "download failed and no verified cache exists"
                ) from exc
        if sha256(target) != source["sha256"]:
            raise RuntimeError(f"BFCL source checksum mismatch: {target.name}")
        local_files.append(target)

    if len(local_files) != 2:
        raise RuntimeError("BFCL manifest must define question and answer source files")

    questions, answers = map(load_jsonl, local_files)
    split_by_id = {
        case_id: split for split, ids in manifest["selected_cases"].items() for case_id in ids
    }
    cases = []
    for case_id, split in split_by_id.items():
        question, answer = questions[case_id], answers[case_id]
        if len(question["function"]) != 1 or len(answer["ground_truth"]) != 1:
            raise RuntimeError(f"Selected BFCL case is not a single-call case: {case_id}")
        cases.append(
            {
                "id": case_id,
                "split": split,
                "question": question["question"][0][0]["content"],
                "tool": normalize_schema(question["function"][0]),
                "ground_truth": answer["ground_truth"][0],
            }
        )
    serialized = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    content = serialized.replace("\n", "\r\n").encode("utf-8")
    actual = sha256_bytes(content)
    expected = manifest["checksum"]
    if actual != expected:
        raise RuntimeError("BFCL transformed subset checksum mismatch")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)
    return len(cases), actual


def main() -> None:
    """Materialize a verified local cache; never execute upstream code."""
    count, digest = materialize_subset()
    print(f"BFCL subset ready: {count} cases, sha256={digest}")


if __name__ == "__main__":
    main()
