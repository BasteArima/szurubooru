import sqlalchemy as sa

from szurubooru.model.base import Base


class AutoTagConfig(Base):
    __tablename__ = "auto_tag_config"

    config_id = sa.Column("id", sa.Integer, primary_key=True)
    value = sa.Column(
        "value", sa.UnicodeText, nullable=False, default="{}"
    )


class PostAutoTag(Base):
    __tablename__ = "post_auto_tag"

    # one row per (post, method); records whether a given auto-tag method has
    # been applied to a given post, regardless of whether it produced any tags
    METHOD_TYPE_TAGS = "type_tags"
    METHOD_HASH = "hash"
    METHOD_AI = "ai"

    STATUS_DONE = "done"  # ran successfully (tags may or may not be added)
    STATUS_EMPTY = "empty"  # ran, nothing found to add (hash lookups)
    STATUS_ERROR = "error"  # could not run (retryable)

    post_id = sa.Column(
        "post_id",
        sa.Integer,
        sa.ForeignKey("post.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    method = sa.Column(
        "method", sa.Unicode(16), primary_key=True, nullable=False
    )
    status = sa.Column("status", sa.Unicode(16), nullable=False)
    source = sa.Column("source", sa.Unicode(32), nullable=True)
    added_count = sa.Column(
        "added_count", sa.Integer, nullable=False, default=0
    )
    message = sa.Column("message", sa.UnicodeText, nullable=True)
    attempt_time = sa.Column("attempt_time", sa.DateTime, nullable=False)


class BooruTagCategory(Base):
    __tablename__ = "booru_tag_category"

    # persistent cache of a booru tag's canonical category, so a bulk hash
    # import resolves each unique tag against the booru at most once ever
    # (rule34 has no batch tag lookup, making this the difference between a
    # feasible and an unfeasible backfill). Keyed by (source, tag name).
    source = sa.Column(
        "source", sa.Unicode(32), primary_key=True, nullable=False
    )
    name = sa.Column(
        "name", sa.Unicode(255), primary_key=True, nullable=False
    )
    category = sa.Column("category", sa.Unicode(32), nullable=False)
    updated_time = sa.Column("updated_time", sa.DateTime, nullable=True)


class AutoTagJob(Base):
    __tablename__ = "auto_tag_job"

    STATUS_RUNNING = "running"
    STATUS_PAUSED = "paused"
    STATUS_CANCELLING = "cancelling"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_ERROR = "error"
    STATUS_INTERRUPTED = "interrupted"

    ACTIVE_STATUSES = (STATUS_RUNNING, STATUS_PAUSED, STATUS_CANCELLING)

    job_id = sa.Column("id", sa.Integer, primary_key=True)
    status = sa.Column("status", sa.Unicode(16), nullable=False)
    methods = sa.Column(
        "methods", sa.UnicodeText, nullable=False, default="[]"
    )
    selection_mode = sa.Column(
        "selection_mode", sa.Unicode(16), nullable=False, default="new"
    )
    retry_empty = sa.Column(
        "retry_empty", sa.Boolean, nullable=False, default=False
    )
    scope_query = sa.Column(
        "scope_query", sa.UnicodeText, nullable=False, default=""
    )
    total = sa.Column("total", sa.Integer, nullable=False, default=0)
    processed = sa.Column("processed", sa.Integer, nullable=False, default=0)
    tagged = sa.Column("tagged", sa.Integer, nullable=False, default=0)
    failed = sa.Column("failed", sa.Integer, nullable=False, default=0)
    errors = sa.Column("errors", sa.Integer, nullable=False, default=0)
    current_post_id = sa.Column(
        "current_post_id", sa.Integer, nullable=True
    )
    message = sa.Column("message", sa.UnicodeText, nullable=True)
    started_at = sa.Column("started_at", sa.DateTime, nullable=True)
    updated_at = sa.Column("updated_at", sa.DateTime, nullable=True)
    finished_at = sa.Column("finished_at", sa.DateTime, nullable=True)
