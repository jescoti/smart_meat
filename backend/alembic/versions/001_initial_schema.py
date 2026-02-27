"""Initial schema — all tables, indexes, and RLS policies.

Revision ID: 001
Revises: None
Create Date: 2026-02-27

Creates the complete Smart Meat database schema:
- users, groups, messages, threads, thread_messages
- message_embeddings (pgvector), nuggets, audit_log
- All indexes (B-tree, GIN, HNSW)
- Row-Level Security policies for multi-tenant isolation
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.rls import RLS_POLICIES_SQL

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- Enum types ---
    group_sync_status = sa.Enum("idle", "syncing", "error", name="group_sync_status")
    group_sync_status.create(op.get_bind(), checkfirst=True)

    message_processing_status = sa.Enum(
        "pending", "threaded", "embedded", "error", name="message_processing_status"
    )
    message_processing_status.create(op.get_bind(), checkfirst=True)

    nugget_source_type = sa.Enum("llm_extracted", "manual", name="nugget_source_type")
    nugget_source_type.create(op.get_bind(), checkfirst=True)

    nugget_status = sa.Enum("suggested", "accepted", "rejected", name="nugget_status")
    nugget_status.create(op.get_bind(), checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("google_id", sa.String, unique=True, nullable=False),
        sa.Column("email", sa.String, unique=True, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("avatar_url", sa.String, nullable=True),
        sa.Column("encrypted_access_token", sa.Text, nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("llm_consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- groups ---
    op.create_table(
        "groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("google_group_email", sa.String, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("sync_status", group_sync_status, nullable=False, server_default="idle"),
        sa.Column("sync_error_message", sa.Text, nullable=True),
        sa.Column("sync_progress_current", sa.Integer, nullable=True),
        sa.Column("sync_progress_total", sa.Integer, nullable=True),
        sa.Column("gmail_history_id", sa.String, nullable=True),
        sa.Column("auto_extract_nuggets", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "google_group_email", name="uq_groups_owner_email"),
    )

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("gmail_id", sa.String, unique=True, nullable=False),
        sa.Column("message_id_header", sa.String, nullable=False),
        sa.Column("in_reply_to", sa.String, nullable=True),
        sa.Column("references_header", sa.ARRAY(sa.String), nullable=True),
        sa.Column("subject", sa.String, nullable=False),
        sa.Column("sender_email", sa.String, nullable=False),
        sa.Column("sender_name", sa.String, nullable=True),
        sa.Column("recipients", JSONB, nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("raw_headers", JSONB, nullable=True),
        sa.Column("has_attachments", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("processing_status", message_processing_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Messages indexes
    op.create_index("ix_messages_group_id_date", "messages", ["group_id", sa.text("date DESC")])
    op.create_index("ix_messages_message_id_header", "messages", ["message_id_header"])
    op.execute(
        "CREATE INDEX ix_messages_body_text_fts ON messages "
        "USING GIN (to_tsvector('english', coalesce(body_text, '')))"
    )
    op.execute(
        "CREATE INDEX ix_messages_raw_headers_gin ON messages "
        "USING GIN (raw_headers jsonb_path_ops)"
    )

    # --- threads ---
    op.create_table(
        "threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("subject", sa.String, nullable=False),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("participant_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index(
        "ix_threads_group_id_last_message_at",
        "threads",
        ["group_id", sa.text("last_message_at DESC")],
    )

    # --- thread_messages ---
    op.create_table(
        "thread_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), unique=True, nullable=False),
        sa.Column("parent_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("depth", sa.Integer, nullable=False),
        sa.Column("is_ghost", sa.Boolean, nullable=False, server_default="false"),
    )

    op.create_index(
        "ix_thread_messages_thread_id_position",
        "thread_messages",
        ["thread_id", "position"],
    )

    # --- message_embeddings ---
    op.create_table(
        "message_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), unique=True, nullable=False),
        sa.Column("embedding", sa.Column("embedding", sa.text("vector(384)")), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # HNSW index for cosine similarity search
    op.execute(
        "CREATE INDEX ix_message_embeddings_hnsw ON message_embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )

    # --- nuggets ---
    op.create_table(
        "nuggets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("source_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", sa.ARRAY(sa.String), nullable=True),
        sa.Column("source_type", nugget_source_type, nullable=False),
        sa.Column("status", nugget_status, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_nuggets_group_id_status", "nuggets", ["group_id", "status"])
    op.execute(
        "CREATE INDEX ix_nuggets_content_fts ON nuggets "
        "USING GIN (to_tsvector('english', content))"
    )
    op.execute("CREATE INDEX ix_nuggets_tags_gin ON nuggets USING GIN (tags)")

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("resource_type", sa.String, nullable=False),
        sa.Column("resource_id", sa.String, nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("ip_address", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_audit_log_user_id_created_at", "audit_log", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_audit_log_action_created_at", "audit_log", ["action", sa.text("created_at DESC")])

    # --- Row-Level Security ---
    for statement in RLS_POLICIES_SQL.split(";"):
        statement = statement.strip()
        if statement:
            op.execute(statement)


def downgrade() -> None:
    # Drop RLS policies
    for table in ("audit_log", "nuggets", "message_embeddings",
                  "thread_messages", "threads", "messages", "groups"):
        op.execute(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse dependency order
    op.drop_table("audit_log")
    op.drop_table("nuggets")
    op.drop_table("message_embeddings")
    op.drop_table("thread_messages")
    op.drop_table("threads")
    op.drop_table("messages")
    op.drop_table("groups")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS nugget_status")
    op.execute("DROP TYPE IF EXISTS nugget_source_type")
    op.execute("DROP TYPE IF EXISTS message_processing_status")
    op.execute("DROP TYPE IF EXISTS group_sync_status")

    # Drop extensions
    op.execute("DROP EXTENSION IF EXISTS vector")
