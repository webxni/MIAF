from __future__ import annotations

import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK

MONEY = Numeric(20, 2)


class DebtKind(str, enum.Enum):
    credit_card = "credit_card"
    personal_loan = "personal_loan"
    student_loan = "student_loan"
    mortgage = "mortgage"
    auto_loan = "auto_loan"
    other = "other"


class DebtStatus(str, enum.Enum):
    active = "active"
    paid_off = "paid_off"
    in_collections = "in_collections"
    written_off = "written_off"


class Debt(UUIDPK, Timestamps, Base):
    """A liability the user owes. `current_balance` is derived from
    `linked_account_id` when set; otherwise the stored value is authoritative.
    """

    __tablename__ = "debts"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[DebtKind] = mapped_column(
        SAEnum(DebtKind, name="debt_kind"), nullable=False
    )
    original_principal: Mapped[Decimal | None] = mapped_column(MONEY)
    current_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    interest_rate_apr: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    minimum_payment: Mapped[Decimal | None] = mapped_column(MONEY)
    due_day_of_month: Mapped[int | None] = mapped_column(Integer)
    next_due_date: Mapped[date | None] = mapped_column(Date)
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    status: Mapped[DebtStatus] = mapped_column(
        SAEnum(DebtStatus, name="debt_status"),
        nullable=False,
        default=DebtStatus.active,
    )
    notes: Mapped[str | None] = mapped_column(String(500))
