"""The second BFCL category is reproducible from its pinned upstream files."""

from pathlib import Path

from packages.environments.bfcl.adapter import BFCLAdapter
from scripts.import_bfcl_subset import materialize_subset

ROOT = Path(__file__).resolve().parents[2]


def test_java_manifest_rebuilds_verified_subset(tmp_path: Path) -> None:
    """Both source hashes and transformed hash must match before tasks are exposed."""
    manifest = ROOT / "benchmarks/bfcl_java_adapted/dataset_manifest.json"
    cache = ROOT / ".cache/bfcl"
    output = tmp_path / "subset.json"
    count, _ = materialize_subset(manifest, cache, output)
    adapter = BFCLAdapter(manifest, output)
    assert count == len(adapter.tasks()) == 5
    assert {task.evaluator_config["suite"] for task in adapter.tasks()} == {"bfcl_java_adapted"}
