"""SQLAlchemy 2.0 ORM models for the Smart Meat database schema.

All models use ``mapped_column`` with ``Mapped[]`` type annotations.
UUID primary keys default to ``uuid.uuid4``.
Enums are native Python ``enum.Enum`` subclasses stored as PostgreSQL enum types.
"""

from __future__ import annotations

import enum
import uuid
from datetime import (
    datetime,  # noqa: TC003 — required at runtime for SQLAlchemy annotation resolution
)

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GroupSyncStatus(enum.StrEnum):
    """Sync status for a Google Group."""

    idle = "idle"
    syncing = "syncing"
    error = "error"


class MessageProcessingStatus(enum.StrEnum):
    """Processing pipeline status for a message."""

    pending = "pending"
    threaded = "threaded"
    embedded = "embedded"
    error = "error"


class NuggetSourceType(enum.StrEnum):
    """How a knowledge nugget was created."""

    llm_extracted = "llm_extracted"
    manual = "manual"


class NuggetStatus(enum.StrEnum):
    """Lifecycle status of a knowledge nugget."""

    suggested = "suggested"
    accepted = "accepted"
    rejected = "rejected"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    llm_consent_given_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    groups: Mapped[list[Group]] = relationship(back_populates="owner")
    nuggets: Mapped[list[Nugget]] = relationship(
        back_populates="creator", foreign_keys="[Nugget.created_by]"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("owner_id", "google_group_email", name="uq_groups_owner_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    google_group_email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    sync_status: Mapped[GroupSyncStatus] = mapped_column(
        Enum(GroupSyncStatus, name="group_sync_status", create_constraint=False),
        default=GroupSyncStatus.idle,
        nullable=False,
    )
    sync_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_progress_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_progress_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gmail_history_id: Mapped[str | None] = mapped_column(String, nullable=True)
    auto_extract_nuggets: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    owner: Mapped[User] = relationship(back_populates="groups")
    messages: Mapped[list[Message]] = relationship(back_populates="group")
    threads: Mapped[list[Thread]] = relationship(back_populates="group")
    nuggets: Mapped[list[Nugget]] = relationship(back_populates="group")


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_group_id_date", "group_id", "date"),
        Index("ix_messages_message_id_header", "message_id_header"),
        Index(
            "ix_messages_body_text_fts",
            text("to_tsvector('english', coalesce(body_text, ''))"),
            postgresql_using="gin",
        ),
        Index(
            "ix_messages_raw_headers_gin",
            "raw_headers",
            postgresql_using="gin",
            postgresql_ops={"raw_headers": "jsonb_path_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False
    )
    gmail_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    message_id_header: Mapped[str] = mapped_column(String, nullable=False)
    in_reply_to: Mapped[str | None] = mapped_column(String, nullable=True)
    references_header: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    sender_email: Mapped[str] = mapped_column(String, nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String, nullable=True)
    recipients: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_status: Mapped[MessageProcessingStatus] = mapped_column(
        Enum(
            MessageProcessingStatus,
            name="message_processing_status",
            create_constraint=False,
        ),
        default=MessageProcessingStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group: Mapped[Group] = relationship(back_populates="messages")
    embedding: Mapped[MessageEmbedding | None] = relationship(
        back_populates="message", uselist=False
    )
    thread_messages: Mapped[list[ThreadMessage]] = relationship(
        back_populates="message",
        foreign_keys="[ThreadMessage.message_id]",
    )


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = (Index("ix_threads_group_id_last_message_at", "group_id", "last_message_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    group: Mapped[Group] = relationship(back_populates="threads")
    thread_messages: Mapped[list[ThreadMessage]] = relationship(back_populates="thread")


# ---------------------------------------------------------------------------
# ThreadMessages
# ---------------------------------------------------------------------------


class ThreadMessage(Base):
    __tablename__ = "thread_messages"
    __table_args__ = (Index("ix_thread_messages_thread_id_position", "thread_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), unique=True, nullable=False
    )
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    is_ghost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    thread: Mapped[Thread] = relationship(back_populates="thread_messages")
    message: Mapped[Message] = relationship(
        back_populates="thread_messages", foreign_keys=[message_id]
    )
    parent_message: Mapped[Message | None] = relationship(foreign_keys=[parent_message_id])


# ---------------------------------------------------------------------------
# MessageEmbeddings
# ---------------------------------------------------------------------------


class MessageEmbedding(Base):
    __tablename__ = "message_embeddings"
    __table_args__ = (
        Index(
            "ix_message_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), unique=True, nullable=False
    )
    embedding = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    message: Mapped[Message] = relationship(back_populates="embedding")


# ---------------------------------------------------------------------------
# Nuggets
# ---------------------------------------------------------------------------


class Nugget(Base):
    __tablename__ = "nuggets"
    __table_args__ = (
        Index("ix_nuggets_group_id_status", "group_id", "status"),
        Index(
            "ix_nuggets_content_fts",
            text("to_tsvector('english', content)"),
            postgresql_using="gin",
        ),
        Index(
            "ix_nuggets_tags_gin",
            "tags",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    source_type: Mapped[NuggetSourceType] = mapped_column(
        Enum(NuggetSourceType, name="nugget_source_type", create_constraint=False),
        nullable=False,
    )
    status: Mapped[NuggetStatus] = mapped_column(
        Enum(NuggetStatus, name="nugget_status", create_constraint=False),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    group: Mapped[Group] = relationship(back_populates="nuggets")
    source_message: Mapped[Message | None] = relationship()
    creator: Mapped[User] = relationship(back_populates="nuggets", foreign_keys=[created_by])


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_user_id_created_at", "user_id", "created_at"),
        Index("ix_audit_log_action_created_at", "action", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, nullable=False)
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped[User] = relationship(back_populates="audit_logs")
