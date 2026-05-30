"""add variant measurements

Revision ID: 202605300001
Revises: 202605290004
Create Date: 2026-05-30 11:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202605300001"
down_revision: Union[str, None] = "202605290004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product_variants", sa.Column("measurements", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("product_variants", "measurements")
