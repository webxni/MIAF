from __future__ import annotations

import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK

MONEY = Numeric(20, 2)


class GoalKind(str, enum.Enum):
    savings = "savings"
    emergency_fund = "emergency_fund"
    debt_payoff = "debt_payoff"
    investment = "investment"
    custom = "custom"


class GoalStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    achieved = "achieved"
    abandoned = "abandoned"


class Goal(UUIDPK, Timestamps, Base):
    """A target amount the user wants to reach by a date.

    `linked_account_id` (when set) makes `current_amount` derived from the
    account's balance — the stored `current_amount` field is a manual override
    used when no account is linked.
    """

    __tablename__ = "goals"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[GoalKind] = mapped_column(
        SAEnum(GoalKind, name="goal_kind"), nullable=False
    )
    target_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    # Manual override; ignored when linked_account_id is set.
    current_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    status: Mapped[GoalStatus] = mapped_column(
        SAEnum(GoalStatus, name="goal_status"),
        nullable=False,
        default=GoalStatus.active,
    )
    notes: Mapped[str | None] = mapped_column(String(500))
