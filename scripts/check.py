"""Run the shared local/CI quality gate with Fake models and isolated outputs."""

import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], directory: Path = ROOT) -> None:
    """Stop on the first failed check instead of hiding a partial failure."""
    subprocess.run(command, cwd=directory, check=True, timeout=600)


def main() -> int:
    """Use locked installed dependencies; prepare only checksum-pinned BFCL inputs."""
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        raise RuntimeError("Install Node.js 22.21+ and run npm ci in apps/web first")
    python = sys.executable
    output = ROOT / "artifacts" / "quality" / str(uuid4())
    output.mkdir(parents=True)
    for suite in ("python", "java"):
        run([python, "-m", "scripts.import_bfcl_subset", "--suite", suite])
    paths = ["packages", "tests", "scripts", "apps/api"]
    run([python, "-m", "ruff", "format", "--check", *paths])
    run([python, "-m", "ruff", "check", *paths])
    run([python, "-m", "mypy"])
    run([python, "-m", "pytest", "-q", "--basetemp", str(output / "pytest")])
    for name in ("course-smoke", "course-four-categories", "course-runtime", "course-timeout"):
        run(
            [
                python,
                "-m",
                "scripts.run_regression",
                f"benchmarks/regression/{name}.json",
                "--artifacts-dir",
                str(output / "regression"),
            ]
        )
    web = ROOT / "apps/web"
    run([python, "-m", "scripts.context_ablation", "--artifacts-dir", str(output / "context")])
    run([npm, "run", "typecheck"], web)
    run([npm, "run", "build"], web)
    run([npm, "test"], web)
    run(
        [
            npm,
            "audit",
            "--audit-level=high",
            "--registry=https://registry.npmjs.org",
            "--offline=false",
            "--cache",
            str(ROOT / "artifacts/npm-cache"),
        ],
        web,
    )
    run([npm, "run", "test:e2e"], web)
    run(["git", "diff", "--check"])
    print(f"Quality gate passed. Python/regression evidence: {output}")
    print("Browser evidence: artifacts/playwright-report; no real model or release was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
