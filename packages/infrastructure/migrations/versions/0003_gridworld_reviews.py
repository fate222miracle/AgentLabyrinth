"""Create the independent GridWorld pair review table."""

from alembic import op
from sqlalchemy import BigInteger, Column, String, Text

revision = "0003_gridworld_reviews"
down_revision = "0002_experiment_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add pair reviews without rewriting existing artifacts."""
    op.create_table(
        "gridworld_comparison_reviews",
        Column("review_id", String(36), primary_key=True),
        Column("pair_key", String(73), nullable=False),
        Column("payload", Text, nullable=False),
        Column("sha256", String(64), nullable=False),
        Column("created_at_ns", BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_gridworld_reviews_pair",
        "gridworld_comparison_reviews",
        ["pair_key", "created_at_ns"],
    )


def downgrade() -> None:
    """Require an explicit export before destructive downgrade."""
    raise RuntimeError("GridWorld review downgrade requires an explicit backup/export procedure")
