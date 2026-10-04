"""Serve a fresh, Fake-only API for browser tests without loading local secrets."""

import argparse
from pathlib import Path

import uvicorn

from apps.api.main import app, get_episode_service
from scripts.course_demo import DemoService


def main() -> None:
    """Require a new isolated directory; never reuse a running or historical service."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.artifacts_dir.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    service = DemoService(artifacts_dir=directory)
    app.dependency_overrides[get_episode_service] = lambda: service
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
