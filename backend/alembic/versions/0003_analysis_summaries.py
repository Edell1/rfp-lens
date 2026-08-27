"""Add stored project analysis summaries.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


summary_scope = sa.Enum("all", "reviewed", name="summary_scope")
summary_state = sa.Enum(
    "pending", "running", "succeeded", "failed", name="summary_state"
)


def upgrade() -> None:
    op.create_table(
        "analysis_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("scope", summary_scope, nullable=False),
        sa.Column("state", summary_state, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "highlights",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "scope", name="uq_analysis_summaries_scope"
        ),
    )
    op.create_index(
        "ix_analysis_summaries_project_id", "analysis_summaries", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_summaries_project_id", table_name="analysis_summaries"
    )
    op.drop_table("analysis_summaries")
    bind = op.get_bind()
    postgresql.ENUM(name="summary_state").drop(bind, checkfirst=True)
    postgresql.ENUM(name="summary_scope").drop(bind, checkfirst=True)
