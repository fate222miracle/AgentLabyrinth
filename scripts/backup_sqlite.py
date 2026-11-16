"""Create one verified online backup of the local AgentLabyrinth SQLite database."""

import argparse
from pathlib import Path

from apps.api.service import DEFAULT_ARTIFACTS_DIR
from packages.infrastructure.sqlite_episode_store import SQLiteEpisodeStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        type=Path,
        help="New backup file; an existing file is never overwritten.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR / "agentlabyrinth.sqlite3",
        help="SQLite source file (defaults to the product database).",
    )
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"source database does not exist: {args.source}")
    SQLiteEpisodeStore(args.source).backup(args.target)
    print(f"Verified backup created: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
