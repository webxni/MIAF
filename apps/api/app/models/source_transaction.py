from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK


class SourceTransactionStatus(str, enum.Enum):
    pending = "pending"
    matched = "matched"
    posted = "posted"
    discarded = "discarded"


class SourceTransaction(UUIDPK, Timestamps, Base):
    """Raw transaction observed before it becomes a journal entry.

    Populated by Phase 4 ingestion (CSV import, OCR, manual capture, Telegram).
    Phase 1 only creates the table so journal entries can reference it.
    """

    __tablename__ = "source_transactions"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # csv_row | ocr | manual | telegram | api
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(255))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    merchant: Mapped[str | None] = mapped_column(String(255))
    raw: Mapped[dict | None] = mapped_column(JSONB)
    # SHA-256 hex of the raw payload for duplicate detection.
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[SourceTransactionStatus] = mapped_column(
        SAEnum(SourceTransactionStatus, name="source_transaction_status"),
        nullable=False,
        default=SourceTransactionStatus.pending,
    )
