"""Serve a fresh, Fake-only API for browser tests without loading local secrets."""

import argparse
from pathlib import Path
from uuid import UUID

import uvicorn
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apps.api.main import app, get_episode_service
from scripts.course_demo import DemoService

ROOT = Path(__file__).resolve().parents[1]
SQLITE_PREVIEW_MARKER = ".agentlabyrinth-fake-sqlite-preview"
SQLITE_PREVIEW_MARKER_CONTENT = "AgentLabyrinth isolated Fake SQLite preview v1\n"


class TestRunIdentityMiddleware:
    """Mark the isolated browser-test API so its proxy target can be verified."""

    def __init__(self, application: ASGIApp, run_id: UUID) -> None:
        self.application = application
        self.run_id = str(run_id)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_identity(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-AgentLabyrinth-Test-Run-ID"] = self.run_id
            await send(message)

        await self.application(scope, receive, send_with_identity)


def main() -> None:
    """Require a new isolated directory; never reuse a running or historical service."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--run-id", type=UUID, required=True)
    parser.add_argument(
        "--sqlite",
        action="store_true",
        help="persist this isolated Fake-only preview in a SQLite database",
    )
    parser.add_argument(
        "--reuse-artifacts-dir",
        action="store_true",
        help="reopen an existing isolated SQLite directory after a server restart",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.reuse_artifacts_dir and not args.sqlite:
        parser.error("--reuse-artifacts-dir requires --sqlite")

    directory = args.artifacts_dir.resolve()
    artifacts_root = (ROOT / "artifacts").resolve()
    if directory == artifacts_root or not directory.is_relative_to(artifacts_root):
        parser.error(
            "--artifacts-dir must be a dedicated subdirectory of this worktree's artifacts"
        )

    database_path = directory / "agentlabyrinth.sqlite3" if args.sqlite else None
    marker_path = directory / SQLITE_PREVIEW_MARKER
    if args.reuse_artifacts_dir:
        if (
            not directory.is_dir()
            or database_path is None
            or not database_path.is_file()
            or not marker_path.is_file()
            or marker_path.read_text(encoding="utf-8") != SQLITE_PREVIEW_MARKER_CONTENT
        ):
            parser.error(
                "--reuse-artifacts-dir requires a directory created by this isolated SQLite preview"
            )
    else:
        directory.mkdir(parents=True, exist_ok=False)
        if args.sqlite:
            marker_path.write_text(SQLITE_PREVIEW_MARKER_CONTENT, encoding="utf-8")

    service = DemoService(artifacts_dir=directory, database_path=database_path)
    app.dependency_overrides[get_episode_service] = lambda: service
    uvicorn.run(TestRunIdentityMiddleware(app, args.run_id), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
