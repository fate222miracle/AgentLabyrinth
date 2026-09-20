"""Download and deterministically transform the pinned BFCL reference subset."""

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/bfcl_adapted/dataset_manifest.json"
CACHE = ROOT / ".cache/bfcl"
OUTPUT = CACHE / "subset.json"


def sha256(path: Path) -> str:
    """Return a lowercase SHA256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def main() -> None:
    """Materialize a verified local cache; never execute upstream code."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    commit = manifest["source_version_or_commit"]
    raw_base = f"https://raw.githubusercontent.com/ShishirPatil/gorilla/{commit}/"
    CACHE.mkdir(parents=True, exist_ok=True)
    local_files: list[Path] = []
    for source in manifest["source_files"]:
        target = CACHE / source["cache_name"]
        if not target.exists():
            urllib.request.urlretrieve(raw_base + source["path"], target)
        if sha256(target) != source["sha256"]:
            raise RuntimeError(f"BFCL source checksum mismatch: {target.name}")
        local_files.append(target)

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
    OUTPUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    expected = manifest.get("checksum")
    actual = sha256(OUTPUT)
    if expected and actual != expected:
        raise RuntimeError("BFCL transformed subset checksum mismatch")
    print(f"BFCL subset ready: {len(cases)} cases, sha256={actual}")


if __name__ == "__main__":
    main()
