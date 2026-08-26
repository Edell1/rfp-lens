"""Create the initial RFP Lens schema.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


document_state = sa.Enum(
    "uploaded",
    "parsing",
    "analyzing",
    "review_required",
    "completed",
    "partial",
    "failed",
    "ocr_required",
    name="document_state",
)
job_state = sa.Enum(
    "queued", "running", "succeeded", "partial", "failed", name="job_state"
)
requirement_category = sa.Enum(
    "eligibility",
    "exclusion",
    "schedule",
    "budget",
    "submission",
    "technical_goal",
    "quantitative_target",
    "evaluation",
    "other",
    name="requirement_category",
)
review_state = sa.Enum(
    "pending", "confirmed", "rejected", "edited", name="review_state"
)
importance = sa.Enum("required", "high", "medium", "low", name="importance")
compliance_status = sa.Enum(
    "not_started",
    "in_progress",
    "complete",
    "not_applicable",
    name="compliance_status",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("state", document_state, nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_documents_project_created_at", "documents", ["project_id", "created_at"]
    )
    op.create_index(
        "ix_documents_project_state", "documents", ["project_id", "state"]
    )
    op.create_table(
        "document_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("block_id", sa.String(length=160), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("heading_path", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("locator", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "block_id", name="uq_document_blocks_block_id"
        ),
    )
    op.create_index(
        "ix_document_blocks_document_order",
        "document_blocks",
        ["document_id", "order"],
    )
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("state", job_state, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("provider_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_jobs_document_id", "analysis_jobs", ["document_id"])
    op.create_index("ix_analysis_jobs_project_id", "analysis_jobs", ["project_id"])
    op.create_table(
        "requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_job_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", requirement_category, nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.String(length=10), nullable=False),
        sa.Column("review_state", review_state, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_requirements_analysis_review_state",
        "requirements",
        ["analysis_job_id", "review_state"],
    )
    op.create_index(
        "ix_requirements_project_created_at",
        "requirements",
        ["project_id", "created_at"],
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("document_block_id", sa.Uuid(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_block_id"], ["document_blocks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["requirements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_document_block_id", "evidence", ["document_block_id"])
    op.create_index("ix_evidence_requirement_id", "evidence", ["requirement_id"])
    op.create_table(
        "compliance_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("importance", importance, nullable=False),
        sa.Column("proposal_section", sa.String(length=255), nullable=False),
        sa.Column("owner_note", sa.Text(), nullable=False),
        sa.Column("status", compliance_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["requirements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id"),
    )
    op.create_index(
        "ix_compliance_items_project_id", "compliance_items", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_items_project_id", table_name="compliance_items")
    op.drop_table("compliance_items")
    op.drop_index("ix_evidence_requirement_id", table_name="evidence")
    op.drop_index("ix_evidence_document_block_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_requirements_project_created_at", table_name="requirements")
    op.drop_index("ix_requirements_analysis_review_state", table_name="requirements")
    op.drop_table("requirements")
    op.drop_index("ix_analysis_jobs_project_id", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_document_id", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    op.drop_index("ix_document_blocks_document_order", table_name="document_blocks")
    op.drop_table("document_blocks")
    op.drop_index("ix_documents_project_state", table_name="documents")
    op.drop_index("ix_documents_project_created_at", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_name in (
        "compliance_status",
        "importance",
        "review_state",
        "requirement_category",
        "job_state",
        "document_state",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
