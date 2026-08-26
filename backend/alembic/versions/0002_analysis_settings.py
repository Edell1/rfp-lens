"""Add analysis settings table for runtime provider overrides.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ai_provider", sa.String(length=20), nullable=False),
        sa.Column("openai_api_key", sa.String(length=512), nullable=True),
        sa.Column("openai_model", sa.String(length=120), nullable=True),
        sa.Column("local_base_url", sa.String(length=500), nullable=True),
        sa.Column("local_model", sa.String(length=120), nullable=True),
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
    )


def downgrade() -> None:
    op.drop_table("analysis_settings")
