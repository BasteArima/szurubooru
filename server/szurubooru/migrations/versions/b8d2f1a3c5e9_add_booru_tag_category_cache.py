"""
Add booru_tag_category (persistent tag -> category cache for hash import)

Revision ID: b8d2f1a3c5e9
Created at: 2026-07-23 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d2f1a3c5e9"
down_revision = "a7c1e9d4f2b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "booru_tag_category",
        sa.Column("source", sa.Unicode(32), nullable=False),
        sa.Column("name", sa.Unicode(255), nullable=False),
        sa.Column("category", sa.Unicode(32), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("source", "name"),
    )


def downgrade():
    op.drop_table("booru_tag_category")
