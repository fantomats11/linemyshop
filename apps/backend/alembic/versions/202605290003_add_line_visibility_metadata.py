"""add line visibility metadata

Revision ID: 202605290003
Revises: 202605290002
Create Date: 2026-05-29 11:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202605290003"
down_revision: Union[str, None] = "202605290002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channel_products",
        sa.Column("is_display", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "channel_products",
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "channel_products",
        sa.Column("line_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_products", "line_payload")
    op.drop_column("channel_products", "last_refreshed_at")
    op.drop_column("channel_products", "is_display")
