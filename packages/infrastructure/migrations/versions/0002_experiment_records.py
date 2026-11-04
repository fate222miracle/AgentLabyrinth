"""Add Experiment, Job and Review records to the local SQLite store.

Revision ID: 0002_experiment_records
Revises: 0001_episode_records
"""

from alembic import op
from sqlalchemy import BigInteger, CheckConstraint, Column, PrimaryKeyConstraint, String, Text

revision = "0002_experiment_records"
down_revision = "0001_episode_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create one payload table for the remaining versioned local artifacts."""
    op.create_table(
        "artifact_records",
        Column("kind", String(24), nullable=False),
        Column("record_id", String(36), nullable=False),
        Column("parent_id", String(36), nullable=True),
        Column("payload", Text, nullable=False),
        Column("sha256", String(64), nullable=False),
        Column("updated_at_ns", BigInteger(), nullable=False),
        PrimaryKeyConstraint("kind", "record_id"),
        CheckConstraint(
            "kind IN ('experiment_plan', 'experiment_result', 'experiment_job', 'review')",
            name="artifact_record_kind",
        ),
    )
    op.create_index("ix_artifact_records_parent", "artifact_records", ["kind", "parent_id"])


def downgrade() -> None:
    """Disallow destructive downgrades of saved experiment data."""
    raise RuntimeError("Artifact storage downgrade requires an explicit backup/export procedure")
