"""add study json provenance

Revision ID: d76b54a3210f
Revises: cbf5230ed8e2
Create Date: 2026-07-30 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d76b54a3210f"
down_revision: str | None = "cbf5230ed8e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assignment_study_sets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_metadata_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "assumptions_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch_op.add_column(sa.Column("payload_digest", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assignment_study_sets") as batch_op:
        batch_op.drop_column("payload_digest")
        batch_op.drop_column("assumptions_json")
        batch_op.drop_column("source_metadata_json")
