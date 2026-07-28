"""add assignment replanning flags

Revision ID: 6d67bb7f6030
Revises: 0909dbebe6f1
Create Date: 2026-07-28 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6d67bb7f6030"
down_revision: str | None = "0909dbebe6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column("source_changed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "assignment_block_links",
        sa.Column("needs_replanning", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("assignment_block_links", "needs_replanning")
    op.drop_column("assignments", "source_changed")
