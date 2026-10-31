"""Create versioned Episode storage for the SQLite integration.

Revision ID: 0001_episode_records
Revises:
"""

from alembic import op
from sqlalchemy import BigInteger, CheckConstraint, Column, String, Text

revision = "0001_episode_records"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial storage table without altering existing JSON files."""
    op.create_table(
        "episode_records",
        Column("episode_id", String(36), primary_key=True),
        Column("kind", String(16), nullable=False),
        Column("payload", Text, nullable=False),
        Column("sha256", String(64), nullable=False),
        Column("fake_scenario", String(64), nullable=True),
        Column("updated_at_ns", BigInteger(), nullable=False),
        CheckConstraint("kind IN ('checkpoint', 'finished')", name="episode_record_kind"),
    )


def downgrade() -> None:
    """Disallow destructive downgrades of saved Episode data."""
    raise RuntimeError("Episode storage downgrade requires an explicit backup/export procedure")
