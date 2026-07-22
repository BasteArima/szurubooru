"""
Add auto-tag tables (config, per-post-per-method state, jobs)

Revision ID: a7c1e9d4f2b8
Created at: 2026-07-22 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c1e9d4f2b8"
down_revision = "5b5c940b4e78"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auto_tag_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "value", sa.UnicodeText(), nullable=False, server_default="{}"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "post_auto_tag",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.Unicode(16), nullable=False),
        sa.Column("status", sa.Unicode(16), nullable=False),
        sa.Column("source", sa.Unicode(32), nullable=True),
        sa.Column(
            "added_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("message", sa.UnicodeText(), nullable=True),
        sa.Column("attempt_time", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"], ["post.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("post_id", "method"),
    )

    op.create_table(
        "auto_tag_job",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Unicode(16), nullable=False),
        sa.Column(
            "methods", sa.UnicodeText(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "selection_mode",
            sa.Unicode(16),
            nullable=False,
            server_default="new",
        ),
        sa.Column(
            "retry_empty",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "scope_query", sa.UnicodeText(), nullable=False, server_default=""
        ),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "processed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("tagged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_post_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.UnicodeText(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("auto_tag_job")
    op.drop_table("post_auto_tag")
    op.drop_table("auto_tag_config")
