"""E2E tests executing scripts/demo.py across scenarios and verifying exit codes and artifacts."""

from pathlib import Path

from scripts.demo import main


def test_cli_demo_success_scenario(tmp_path: Path) -> None:
    """CLI demo success scenario returns exit code 0 and produces valid artifact."""
    output_file = tmp_path / "success_trace.json"
    exit_code = main(["--scenario", "success", "--output", str(output_file)])

    assert exit_code == 0
    assert output_file.exists()
    text = output_file.read_text(encoding="utf-8")
    assert '"success": true' in text.lower()


def test_cli_demo_wrong_answer_scenario(tmp_path: Path) -> None:
    """CLI demo wrong-answer scenario returns exit code 1."""
    output_file = tmp_path / "wrong_trace.json"
    exit_code = main(["--scenario", "wrong-answer", "--output", str(output_file)])

    assert exit_code == 1
    assert output_file.exists()
    text = output_file.read_text(encoding="utf-8")
    assert '"success": false' in text.lower()


def test_cli_demo_invalid_arguments_scenario(tmp_path: Path) -> None:
    """CLI demo invalid-arguments scenario returns exit code 1 and contains no TOOL_STARTED."""
    output_file = tmp_path / "invalid_trace.json"
    exit_code = main(["--scenario", "invalid-arguments", "--output", str(output_file)])

    assert exit_code == 1
    assert output_file.exists()
    text = output_file.read_text(encoding="utf-8")
    assert '"TOOL_STARTED"' not in text


def test_cli_demo_max_steps_scenario(tmp_path: Path) -> None:
    """CLI demo max-steps scenario returns exit code 1."""
    output_file = tmp_path / "max_steps_trace.json"
    exit_code = main(["--scenario", "max-steps", "--output", str(output_file)])

    assert exit_code == 1
    assert output_file.exists()
    text = output_file.read_text(encoding="utf-8")
    assert "max_steps" in text.lower()


def test_cli_demo_invalid_cli_arg() -> None:
    """CLI demo returns exit code 2 for invalid CLI arguments."""
    exit_code = main(["--scenario", "nonexistent_scenario"])
    assert exit_code == 2
