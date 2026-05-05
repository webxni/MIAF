from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK


class MemoryType(str, enum.Enum):
    user_profile = "user_profile"
    personal_preference = "personal_preference"
    business_profile = "business_profile"
    financial_rule = "financial_rule"
    merchant_rule = "merchant_rule"
    tax_context = "tax_context"
    goal_context = "goal_context"
    risk_preference = "risk_preference"
    recurring_pattern = "recurring_pattern"
    advisor_note = "advisor_note"


class MemoryReviewStatus(str, enum.Enum):
    accepted = "accepted"
    needs_update = "needs_update"
    archived = "archived"


class MemoryEventType(str, enum.Enum):
    created = "created"
    updated = "updated"
    accessed = "accessed"
    deleted = "deleted"
    expired = "expired"
    reviewed = "reviewed"
    promoted = "promoted"


class Memory(UUIDPK, Timestamps, Base):
    __tablename__ = "memories"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        SAEnum(MemoryType, name="memory_type"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    keywords: Mapped[list[str] | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    consent_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryEmbedding(UUIDPK, Timestamps, Base):
    __tablename__ = "memory_embeddings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, default="deterministic-v1")
    embedding: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    redacted_text: Mapped[str] = mapped_column(Text, nullable=False)


class MemoryEvent(UUIDPK, Timestamps, Base):
    __tablename__ = "memory_events"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[MemoryEventType] = mapped_column(
        SAEnum(MemoryEventType, name="memory_event_type"),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict | None] = mapped_column(JSONB)


class MemoryReview(UUIDPK, Timestamps, Base):
    __tablename__ = "memory_reviews"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[MemoryReviewStatus] = mapped_column(
        SAEnum(MemoryReviewStatus, name="memory_review_status"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
