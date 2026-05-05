from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK


class EntityMode(str, enum.Enum):
    personal = "personal"
    business = "business"


class Role(str, enum.Enum):
    """Per-entity roles. owner > admin > accountant > viewer; agent is a non-human service role."""

    owner = "owner"
    admin = "admin"
    accountant = "accountant"
    viewer = "viewer"
    agent = "agent"


class Entity(UUIDPK, Timestamps, Base):
    __tablename__ = "entities"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[EntityMode] = mapped_column(
        SAEnum(EntityMode, name="entity_mode"),
        nullable=False,
    )
    # ISO 4217 currency code. Default unspecified — set per entity.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")


class EntityMember(UUIDPK, Timestamps, Base):
    __tablename__ = "entity_members"
    __table_args__ = (
        UniqueConstraint("entity_id", "user_id", name="uq_entity_members_entity_user"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="entity_role"),
        nullable=False,
    )
