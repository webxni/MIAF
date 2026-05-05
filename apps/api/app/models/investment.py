from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPK

MONEY = Numeric(20, 2)
SHARES = Numeric(20, 6)
PRICE = Numeric(20, 6)


class InvestmentAccountKind(str, enum.Enum):
    taxable_brokerage = "taxable_brokerage"
    ira = "ira"
    roth_ira = "roth_ira"
    k401 = "k401"
    crypto = "crypto"
    retirement_other = "retirement_other"
    other = "other"


class HoldingKind(str, enum.Enum):
    equity = "equity"
    etf = "etf"
    mutual_fund = "mutual_fund"
    bond = "bond"
    crypto = "crypto"
    cash = "cash"
    other = "other"


class InvestmentAccount(UUIDPK, Timestamps, Base):
    """Tracking-only. We never execute trades. Phase 2 advisory rule."""

    __tablename__ = "investment_accounts"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    broker: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[InvestmentAccountKind] = mapped_column(
        SAEnum(InvestmentAccountKind, name="investment_account_kind"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
    )
    notes: Mapped[str | None] = mapped_column(String(500))

    holdings: Mapped[list[InvestmentHolding]] = relationship(
        "InvestmentHolding",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="InvestmentHolding.symbol",
    )


class InvestmentHolding(UUIDPK, Timestamps, Base):
    __tablename__ = "investment_holdings"

    investment_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investment_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[HoldingKind] = mapped_column(
        SAEnum(HoldingKind, name="holding_kind"), nullable=False
    )
    shares: Mapped[Decimal] = mapped_column(SHARES, nullable=False, default=Decimal("0"))
    cost_basis_per_share: Mapped[Decimal | None] = mapped_column(PRICE)
    current_price: Mapped[Decimal | None] = mapped_column(PRICE)
    last_priced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[InvestmentAccount] = relationship(
        "InvestmentAccount", back_populates="holdings"
    )
