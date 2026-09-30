"""A failed final publish cannot damage the last complete artifact."""

import os
from pathlib import Path

import pytest

from packages.application.trace import write_text_atomically


def test_failed_replace_preserves_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A complete temporary file is removed if the final rename fails."""
    target = tmp_path / "artifact.json"
    target.write_text("old", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated publish failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="publish failure"):
        write_text_atomically(target, "new")
    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob("*.tmp")) == []
