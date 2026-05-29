"""add product image review metadata

Revision ID: 202605290002
Revises: 202605290001
Create Date: 2026-05-29 00:00:02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202605290002"
down_revision: Union[str, None] = "202605290001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="draft",
            nullable=False,
        ),
    )
    op.add_column(
        "product_images",
        sa.Column(
            "image_type",
            sa.String(length=50),
            server_default="product",
            nullable=False,
        ),
    )
    op.add_column(
        "product_images",
        sa.Column(
            "is_main",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "product_images",
        sa.Column("review_note", sa.Text(), nullable=True),
    )
    op.execute(
        "update product_images "
        "set image_type = 'brief', status = 'draft', is_main = false "
        "where url like 'data/input/images/%'"
    )
    op.alter_column("product_images", "status", server_default=None)
    op.alter_column("product_images", "image_type", server_default=None)
    op.alter_column("product_images", "is_main", server_default=None)


def downgrade() -> None:
    op.drop_column("product_images", "review_note")
    op.drop_column("product_images", "is_main")
    op.drop_column("product_images", "image_type")
    op.drop_column("product_images", "status")
