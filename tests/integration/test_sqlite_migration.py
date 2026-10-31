"""Exercise the actual Alembic version on a disposable database."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_episode_migration_is_versioned_and_non_destructive(tmp_path: Path) -> None:
    """Upgrade and reapply safely; never drop records on an implicit downgrade."""
    root = Path(__file__).resolve().parents[2]
    config = Config()
    config.set_main_option("script_location", str(root / "packages/infrastructure/migrations"))
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert inspect(connection).has_table("episode_records")
        assert inspect(connection).has_table("artifact_records")
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0002_experiment_records"
        )
        connection.execute(
            text(
                "INSERT INTO episode_records "
                "(episode_id, kind, payload, sha256, fake_scenario, updated_at_ns) "
                "VALUES ('id', 'finished', '{}', 'hash', NULL, 1)"
            )
        )
        command.upgrade(config, "head")
        with pytest.raises(RuntimeError, match="backup/export"):
            command.downgrade(config, "base")
        assert connection.execute(text("SELECT COUNT(*) FROM episode_records")).scalar_one() == 1
    engine.dispose()
