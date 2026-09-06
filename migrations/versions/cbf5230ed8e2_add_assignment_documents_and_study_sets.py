"""add assignment documents and study sets

Revision ID: cbf5230ed8e2
Revises: 6d67bb7f6030
Create Date: 2026-07-29 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import semester_ops.db.models

revision: str = "cbf5230ed8e2"
down_revision: str | None = "6d67bb7f6030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assignment_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extracted_character_count", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("is_truncated", sa.Boolean(), nullable=False),
        sa.Column("created_at", semester_ops.db.models.UTCDateTime(), nullable=False),
        sa.Column("updated_at", semester_ops.db.models.UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="ck_assignment_document_pages",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_assignment_document_size"),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "sha256", name="uq_assignment_document_hash"),
    )
    op.create_index(
        op.f("ix_assignment_documents_assignment_id"),
        "assignment_documents",
        ["assignment_id"],
        unique=False,
    )
    op.create_table(
        "assignment_study_sets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("generator", sa.String(length=100), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_points_json", sa.JSON(), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", semester_ops.db.models.UTCDateTime(), nullable=False),
        sa.Column("created_at", semester_ops.db.models.UTCDateTime(), nullable=False),
        sa.Column("updated_at", semester_ops.db.models.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assignment_study_sets_assignment_id"),
        "assignment_study_sets",
        ["assignment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assignment_study_sets_assignment_id"),
        table_name="assignment_study_sets",
    )
    op.drop_table("assignment_study_sets")
    op.drop_index(
        op.f("ix_assignment_documents_assignment_id"),
        table_name="assignment_documents",
    )
    op.drop_table("assignment_documents")
