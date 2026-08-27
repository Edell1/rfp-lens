"""Track the source fingerprint represented by stored highlights.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_summaries",
        sa.Column("highlights_fingerprint", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_summaries", "highlights_fingerprint")
