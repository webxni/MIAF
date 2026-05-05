from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAt, UUIDPK

MONEY = Numeric(20, 2)


class NetWorthSnapshot(UUIDPK, CreatedAt, Base):
    """Point-in-time net worth. Stored once per (entity, as_of) so we can
    reconstruct trends without re-running the ledger query.
    """

    __tablename__ = "net_worth_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "entity_id", "as_of", name="uq_net_worth_snapshots_entity_as_of"
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)

    total_assets: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_liabilities: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    net_worth: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    # Per-account-type breakdown for later "what changed" analysis. Shape:
    # {"asset": [{"account_id": "...", "code": "1110", "name": "Checking", "balance": "100.00"}, ...],
    #  "liability": [...]}
    breakdown: Mapped[dict | None] = mapped_column(JSONB)
