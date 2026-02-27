"""Tests for ORM models — field types, defaults, constraints, relationships.

All tests use SQLAlchemy inspect() to verify model structure without
requiring a running database.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import RelationshipProperty

from app.db.models import (
    AuditLog,
    Base,
    Group,
    GroupSyncStatus,
    Message,
    MessageEmbedding,
    MessageProcessingStatus,
    Nugget,
    NuggetSourceType,
    NuggetStatus,
    Thread,
    ThreadMessage,
    User,
)

# ---------------------------------------------------------------------------
# Helper: get mapper & column info
# ---------------------------------------------------------------------------


def _col(model: type, name: str):
    """Return the Column object for *name* on *model*."""
    mapper = sa_inspect(model)
    return mapper.columns[name]


def _relationships(model: type) -> dict[str, RelationshipProperty]:
    mapper = sa_inspect(model)
    return {r.key: r for r in mapper.relationships}


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------


class TestEnums:
    """Verify Python enum definitions used by the models."""

    def test_group_sync_status_values(self) -> None:
        assert set(GroupSyncStatus) == {
            GroupSyncStatus.idle,
            GroupSyncStatus.syncing,
            GroupSyncStatus.error,
        }

    def test_message_processing_status_values(self) -> None:
        assert set(MessageProcessingStatus) == {
            MessageProcessingStatus.pending,
            MessageProcessingStatus.threaded,
            MessageProcessingStatus.embedded,
            MessageProcessingStatus.error,
        }

    def test_nugget_source_type_values(self) -> None:
        assert set(NuggetSourceType) == {
            NuggetSourceType.llm_extracted,
            NuggetSourceType.manual,
        }

    def test_nugget_status_values(self) -> None:
        assert set(NuggetStatus) == {
            NuggetStatus.suggested,
            NuggetStatus.accepted,
            NuggetStatus.rejected,
        }

    def test_enums_are_str_enum(self) -> None:
        """All enums should be (str, enum.Enum) so values are serializable."""
        for e in (GroupSyncStatus, MessageProcessingStatus, NuggetSourceType, NuggetStatus):
            assert issubclass(e, str)
            assert issubclass(e, enum.Enum)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class TestBase:
    def test_base_is_declarative(self) -> None:
        assert hasattr(Base, "metadata")
        assert hasattr(Base, "registry")


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------


class TestUserModel:
    def test_tablename(self) -> None:
        assert User.__tablename__ == "users"

    def test_id_column(self) -> None:
        col = _col(User, "id")
        assert isinstance(col.type, UUID)
        assert col.primary_key
        assert col.default is not None  # uuid4 default

    def test_google_id_unique_not_null(self) -> None:
        col = _col(User, "google_id")
        assert col.unique
        assert not col.nullable

    def test_email_unique_not_null(self) -> None:
        col = _col(User, "email")
        assert col.unique
        assert not col.nullable

    def test_display_name_not_null(self) -> None:
        col = _col(User, "display_name")
        assert not col.nullable

    def test_avatar_url_nullable(self) -> None:
        col = _col(User, "avatar_url")
        assert col.nullable

    def test_encrypted_token_columns(self) -> None:
        for name in ("encrypted_access_token", "encrypted_refresh_token"):
            col = _col(User, name)
            assert col.nullable

    def test_token_expires_at(self) -> None:
        col = _col(User, "token_expires_at")
        assert col.nullable

    def test_llm_consent_given_at(self) -> None:
        col = _col(User, "llm_consent_given_at")
        assert col.nullable

    def test_timestamps(self) -> None:
        for name in ("created_at", "updated_at"):
            col = _col(User, name)
            assert col.server_default is not None or col.default is not None

    def test_relationships_exist(self) -> None:
        rels = _relationships(User)
        assert "groups" in rels
        assert "nuggets" in rels
        assert "audit_logs" in rels


# ---------------------------------------------------------------------------
# Group model
# ---------------------------------------------------------------------------


class TestGroupModel:
    def test_tablename(self) -> None:
        assert Group.__tablename__ == "groups"

    def test_id_column(self) -> None:
        col = _col(Group, "id")
        assert isinstance(col.type, UUID)
        assert col.primary_key

    def test_owner_id_foreign_key(self) -> None:
        col = _col(Group, "owner_id")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "users.id" in fk_targets

    def test_google_group_email_not_null(self) -> None:
        col = _col(Group, "google_group_email")
        assert not col.nullable

    def test_display_name_not_null(self) -> None:
        col = _col(Group, "display_name")
        assert not col.nullable

    def test_sync_status_enum_default(self) -> None:
        col = _col(Group, "sync_status")
        # Check it has a default
        assert col.default is not None or col.server_default is not None

    def test_sync_error_message_nullable(self) -> None:
        col = _col(Group, "sync_error_message")
        assert col.nullable

    def test_sync_progress_columns(self) -> None:
        for name in ("sync_progress_current", "sync_progress_total"):
            col = _col(Group, name)
            assert col.nullable

    def test_gmail_history_id_nullable(self) -> None:
        col = _col(Group, "gmail_history_id")
        assert col.nullable

    def test_auto_extract_nuggets_default(self) -> None:
        col = _col(Group, "auto_extract_nuggets")
        assert col.default is not None or col.server_default is not None

    def test_timestamps(self) -> None:
        for name in ("created_at", "updated_at"):
            col = _col(Group, name)
            assert col.server_default is not None or col.default is not None

    def test_relationships(self) -> None:
        rels = _relationships(Group)
        assert "owner" in rels
        assert "messages" in rels
        assert "threads" in rels
        assert "nuggets" in rels

    def test_unique_constraint_google_group_email_per_owner(self) -> None:
        """google_group_email should be unique per owner (unique constraint on table)."""
        table = Group.__table__
        # Check for a unique constraint involving both owner_id and google_group_email
        unique_constraints = [
            c
            for c in table.constraints
            if hasattr(c, "columns")
            and {col.name for col in c.columns} == {"owner_id", "google_group_email"}
        ]
        assert len(unique_constraints) == 1


# ---------------------------------------------------------------------------
# Message model
# ---------------------------------------------------------------------------


class TestMessageModel:
    def test_tablename(self) -> None:
        assert Message.__tablename__ == "messages"

    def test_id_column(self) -> None:
        col = _col(Message, "id")
        assert isinstance(col.type, UUID)
        assert col.primary_key

    def test_group_id_foreign_key(self) -> None:
        col = _col(Message, "group_id")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "groups.id" in fk_targets

    def test_gmail_id_unique(self) -> None:
        col = _col(Message, "gmail_id")
        assert col.unique
        assert not col.nullable

    def test_message_id_header_not_null(self) -> None:
        col = _col(Message, "message_id_header")
        assert not col.nullable

    def test_in_reply_to_nullable(self) -> None:
        col = _col(Message, "in_reply_to")
        assert col.nullable

    def test_references_header_is_array(self) -> None:
        col = _col(Message, "references_header")
        assert isinstance(col.type, ARRAY)

    def test_subject_not_null(self) -> None:
        col = _col(Message, "subject")
        assert not col.nullable

    def test_sender_email_not_null(self) -> None:
        col = _col(Message, "sender_email")
        assert not col.nullable

    def test_sender_name_nullable(self) -> None:
        col = _col(Message, "sender_name")
        assert col.nullable

    def test_recipients_jsonb(self) -> None:
        col = _col(Message, "recipients")
        assert isinstance(col.type, JSONB)

    def test_date_not_null(self) -> None:
        col = _col(Message, "date")
        assert not col.nullable

    def test_body_text_nullable(self) -> None:
        col = _col(Message, "body_text")
        assert col.nullable

    def test_body_html_nullable(self) -> None:
        col = _col(Message, "body_html")
        assert col.nullable

    def test_raw_headers_jsonb(self) -> None:
        col = _col(Message, "raw_headers")
        assert isinstance(col.type, JSONB)

    def test_has_attachments_default(self) -> None:
        col = _col(Message, "has_attachments")
        assert col.default is not None or col.server_default is not None

    def test_processing_status_column(self) -> None:
        col = _col(Message, "processing_status")
        assert col.default is not None or col.server_default is not None

    def test_created_at(self) -> None:
        col = _col(Message, "created_at")
        assert col.server_default is not None or col.default is not None

    def test_relationships(self) -> None:
        rels = _relationships(Message)
        assert "group" in rels
        assert "embedding" in rels
        assert "thread_messages" in rels


# ---------------------------------------------------------------------------
# Thread model
# ---------------------------------------------------------------------------


class TestThreadModel:
    def test_tablename(self) -> None:
        assert Thread.__tablename__ == "threads"

    def test_id_column(self) -> None:
        col = _col(Thread, "id")
        assert isinstance(col.type, UUID)
        assert col.primary_key

    def test_group_id_foreign_key(self) -> None:
        col = _col(Thread, "group_id")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "groups.id" in fk_targets

    def test_subject_not_null(self) -> None:
        col = _col(Thread, "subject")
        assert not col.nullable

    def test_message_count_default(self) -> None:
        col = _col(Thread, "message_count")
        assert col.default is not None or col.server_default is not None

    def test_participant_count_default(self) -> None:
        col = _col(Thread, "participant_count")
        assert col.default is not None or col.server_default is not None

    def test_last_message_at_nullable(self) -> None:
        col = _col(Thread, "last_message_at")
        assert col.nullable

    def test_timestamps(self) -> None:
        for name in ("created_at", "updated_at"):
            col = _col(Thread, name)
            assert col.server_default is not None or col.default is not None

    def test_relationships(self) -> None:
        rels = _relationships(Thread)
        assert "group" in rels
        assert "thread_messages" in rels


# ---------------------------------------------------------------------------
# ThreadMessage model
# ---------------------------------------------------------------------------


class TestThreadMessageModel:
    def test_tablename(self) -> None:
        assert ThreadMessage.__tablename__ == "thread_messages"

    def test_id_column(self) -> None:
        col = _col(ThreadMessage, "id")
        assert isinstance(col.type, UUID)
        assert col.primary_key

    def test_thread_id_foreign_key(self) -> None:
        col = _col(ThreadMessage, "thread_id")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "threads.id" in fk_targets

    def test_message_id_foreign_key_unique(self) -> None:
        col = _col(ThreadMessage, "message_id")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "messages.id" in fk_targets
        assert col.unique

    def test_parent_message_id_nullable(self) -> None:
        col = _col(ThreadMessage, "parent_message_id")
        assert col.nullable
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "messages.id" in fk_targets

    def test_position_not_null(self) -> None:
        col = _col(ThreadMessage, "position")
        assert not col.nullable

    def test_depth_not_null(self) -> None:
        col = _col(ThreadMessage, "depth")
        assert not col.nullable

    def test_is_ghost_default(self) -> None:
        col = _col(ThreadMessage, "is_ghost")
        assert col.default is not None or col.server_default is not None

    def test_relationships(self) -> None:
        rels = _relationships(ThreadMessage)
        assert "thread" in rels
        assert "message" in rels
        assert "parent_message" in rels


# ---------------------------------------------------------------------------
# MessageEmbedding model
# ---------------------------------------------------------------------------


class TestMessageEmbeddingModel:
    def test_tablename(self) -> None:
        assert MessageEmbedding.__tablename__ == "message_embeddings"

    def test_id_column(self) -> None:
        col = _col(MessageEmbedding, "id")
        assert isinstance(col.type, UUID)
        assert col.primary_key

    def test_message_id_unique_fk(self) -> None:
        col = _col(MessageEmbedding, "message_id")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "messages.id" in fk_targets
        assert col.unique

    def test_embedding_column_exists(self) -> None:
        """Embedding column should be a vector(384) type."""
        col = _col(MessageEmbedding, "embedding")
        # pgvector Vector type — just check it exists and is not nullable
        assert not col.nullable

    def test_created_at(self) -> None:
        col = _col(MessageEmbedding, "created_at")
        assert col.server_default is not None or col.default is not None

    def test_relationships(self) -> None:
        rels = _relationships(MessageEmbedding)
        assert "message" in rels


# ---------------------------------------------------------------------------
# Nugget model
# ---------------------------------------------------------------------------


class TestNuggetModel:
    def test_tablename(self) -> None:
        assert Nugget.__tablename__ == "nuggets"

    def test_id_column(self) -> None:
        col = _col(Nugget, "id")
        assert isinstance(col.type, UUID)
        assert col.primary_key

    def test_group_id_foreign_key(self) -> None:
        col = _col(Nugget, "group_id")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "groups.id" in fk_targets

    def test_source_message_id_nullable(self) -> None:
        col = _col(Nugget, "source_message_id")
        assert col.nullable
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "messages.id" in fk_targets

    def test_title_not_null(self) -> None:
        col = _col(Nugget, "title")
        assert not col.nullable

    def test_content_not_null(self) -> None:
        col = _col(Nugget, "content")
        assert not col.nullable

    def test_tags_array(self) -> None:
        col = _col(Nugget, "tags")
        assert isinstance(col.type, ARRAY)

    def test_source_type_column(self) -> None:
        col = _col(Nugget, "source_type")
        assert not col.nullable

    def test_status_column(self) -> None:
        col = _col(Nugget, "status")
        assert not col.nullable

    def test_created_by_foreign_key(self) -> None:
        col = _col(Nugget, "created_by")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "users.id" in fk_targets

    def test_timestamps(self) -> None:
        for name in ("created_at", "updated_at"):
            col = _col(Nugget, name)
            assert col.server_default is not None or col.default is not None

    def test_relationships(self) -> None:
        rels = _relationships(Nugget)
        assert "group" in rels
        assert "source_message" in rels
        assert "creator" in rels


# ---------------------------------------------------------------------------
# AuditLog model
# ---------------------------------------------------------------------------


class TestAuditLogModel:
    def test_tablename(self) -> None:
        assert AuditLog.__tablename__ == "audit_log"

    def test_id_column(self) -> None:
        col = _col(AuditLog, "id")
        assert isinstance(col.type, UUID)
        assert col.primary_key

    def test_user_id_foreign_key(self) -> None:
        col = _col(AuditLog, "user_id")
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "users.id" in fk_targets

    def test_action_not_null(self) -> None:
        col = _col(AuditLog, "action")
        assert not col.nullable

    def test_resource_type_not_null(self) -> None:
        col = _col(AuditLog, "resource_type")
        assert not col.nullable

    def test_resource_id_not_null(self) -> None:
        col = _col(AuditLog, "resource_id")
        assert not col.nullable

    def test_metadata_jsonb(self) -> None:
        # Python attr is audit_metadata to avoid clash with DeclarativeBase.metadata,
        # but the DB column is still named "metadata".
        col = _col(AuditLog, "audit_metadata")
        # The underlying DB column name should be "metadata"
        assert col.name == "metadata"
        assert isinstance(col.type, JSONB)

    def test_ip_address_nullable(self) -> None:
        col = _col(AuditLog, "ip_address")
        assert col.nullable

    def test_created_at(self) -> None:
        col = _col(AuditLog, "created_at")
        assert col.server_default is not None or col.default is not None

    def test_relationships(self) -> None:
        rels = _relationships(AuditLog)
        assert "user" in rels


# ---------------------------------------------------------------------------
# Table-level index tests
# ---------------------------------------------------------------------------


class TestIndexes:
    """Verify that important indexes are declared on the models."""

    def _index_names(self, model: type) -> set[str]:
        table = model.__table__
        return {idx.name for idx in table.indexes}

    def test_messages_group_date_index(self) -> None:
        names = self._index_names(Message)
        assert "ix_messages_group_id_date" in names

    def test_messages_message_id_header_index(self) -> None:
        names = self._index_names(Message)
        assert "ix_messages_message_id_header" in names

    def test_messages_body_text_gin_index(self) -> None:
        names = self._index_names(Message)
        assert "ix_messages_body_text_fts" in names

    def test_messages_raw_headers_gin_index(self) -> None:
        names = self._index_names(Message)
        assert "ix_messages_raw_headers_gin" in names

    def test_threads_group_last_message_index(self) -> None:
        names = self._index_names(Thread)
        assert "ix_threads_group_id_last_message_at" in names

    def test_thread_messages_thread_position_index(self) -> None:
        names = self._index_names(ThreadMessage)
        assert "ix_thread_messages_thread_id_position" in names

    def test_nuggets_group_status_index(self) -> None:
        names = self._index_names(Nugget)
        assert "ix_nuggets_group_id_status" in names

    def test_nuggets_content_fts_index(self) -> None:
        names = self._index_names(Nugget)
        assert "ix_nuggets_content_fts" in names

    def test_nuggets_tags_gin_index(self) -> None:
        names = self._index_names(Nugget)
        assert "ix_nuggets_tags_gin" in names

    def test_audit_log_user_created_at_index(self) -> None:
        names = self._index_names(AuditLog)
        assert "ix_audit_log_user_id_created_at" in names

    def test_audit_log_action_created_at_index(self) -> None:
        names = self._index_names(AuditLog)
        assert "ix_audit_log_action_created_at" in names

    def test_message_embeddings_hnsw_index(self) -> None:
        names = self._index_names(MessageEmbedding)
        assert "ix_message_embeddings_hnsw" in names
