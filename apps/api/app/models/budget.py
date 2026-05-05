from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPK

MONEY = Numeric(20, 2)


class Budget(UUIDPK, Timestamps, Base):
    """A planning envelope for a date range. Personal-only at the service layer."""

    __tablename__ = "budgets"
    __table_args__ = (
        # One budget per name per period start per entity. Multiple budgets per
        # period are allowed if names differ (e.g. "groceries", "vacation").
        UniqueConstraint(
            "entity_id", "name", "period_start", name="uq_budgets_entity_name_period"
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))

    lines: Mapped[list[BudgetLine]] = relationship(
        "BudgetLine",
        back_populates="budget",
        cascade="all, delete-orphan",
        order_by="BudgetLine.created_at",
    )


class BudgetLine(UUIDPK, Timestamps, Base):
    """One planned amount for one expense account inside a budget."""

    __tablename__ = "budget_lines"
    __table_args__ = (
        UniqueConstraint("budget_id", "account_id", name="uq_budget_lines_budget_account"),
    )

    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    planned_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))

    budget: Mapped[Budget] = relationship("Budget", back_populates="lines")
