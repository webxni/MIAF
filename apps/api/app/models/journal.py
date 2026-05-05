from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPK


class JournalEntryStatus(str, enum.Enum):
    draft = "draft"
    posted = "posted"
    voided = "voided"


# 20 digits total, 2 after the decimal — fits cents up to ~10^17.
MONEY = Numeric(20, 2)


class JournalEntry(UUIDPK, Timestamps, Base):
    __tablename__ = "journal_entries"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    memo: Mapped[str | None] = mapped_column(String(500))
    reference: Mapped[str | None] = mapped_column(String(100))

    status: Mapped[JournalEntryStatus] = mapped_column(
        SAEnum(JournalEntryStatus, name="journal_entry_status"),
        nullable=False,
        default=JournalEntryStatus.draft,
        index=True,
    )

    # Posting metadata (set when status -> posted)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Voiding metadata (set when status -> voided)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    voided_reason: Mapped[str | None] = mapped_column(String(500))

    # Reversal links: original.voided_by_entry_id -> reversal.id
    #                 reversal.voids_entry_id    -> original.id
    voided_by_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
    )
    voids_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
    )

    # Cross-entity transfer link (e.g. owner draw: business JE <-> personal JE).
    linked_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
    )

    # Origin metadata
    source_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_transactions.id", ondelete="SET NULL"),
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    lines: Mapped[list[JournalLine]] = relationship(
        "JournalLine",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.line_no",
    )


class JournalLine(UUIDPK, Timestamps, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        # Each line is exactly one of debit OR credit, never both, never neither.
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="single_sided",
        ),
        CheckConstraint("debit >= 0", name="debit_non_negative"),
        CheckConstraint("credit >= 0", name="credit_non_negative"),
    )

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    debit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    description: Mapped[str | None] = mapped_column(String(500))

    entry: Mapped[JournalEntry] = relationship("JournalEntry", back_populates="lines")
