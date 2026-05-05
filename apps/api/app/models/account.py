from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK


class AccountType(str, enum.Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    income = "income"
    expense = "expense"


class NormalSide(str, enum.Enum):
    debit = "debit"
    credit = "credit"


# Default normal side per type (standard accounting).
NORMAL_SIDE_FOR_TYPE: dict[AccountType, NormalSide] = {
    AccountType.asset: NormalSide.debit,
    AccountType.liability: NormalSide.credit,
    AccountType.equity: NormalSide.credit,
    AccountType.income: NormalSide.credit,
    AccountType.expense: NormalSide.debit,
}


class Account(UUIDPK, Timestamps, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("entity_id", "code", name="uq_accounts_entity_code"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, name="account_type"),
        nullable=False,
    )
    normal_side: Mapped[NormalSide] = mapped_column(
        SAEnum(NormalSide, name="account_normal_side"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(500))
