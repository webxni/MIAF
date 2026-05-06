from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAt, UUIDPK


class AuditLog(UUIDPK, CreatedAt, Base):
    """Append-only record of every sensitive action.

    No update/delete paths exist in the API, and Phase 12 also revokes
    UPDATE/DELETE on this table at the database layer for the app role.
    """

    __tablename__ = "audit_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
    )

    # action: create | update | post | void | delete | login | logout | export | tool_call | ...
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # object_type: entity | account | journal_entry | session | ...
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_id: Mapped[str | None] = mapped_column(String(64), index=True)

    # before/after snapshots — already redacted by the audit service before insert.
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)

    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
