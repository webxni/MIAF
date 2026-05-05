"""Phase 2 — personal finance: budgets, goals, debts, investments, net worth.

Revision ID: 0002_personal_finance
Revises: 0001_initial
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_personal_finance"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GOAL_KIND = sa.Enum(
    "savings", "emergency_fund", "debt_payoff", "investment", "custom",
    name="goal_kind",
)
GOAL_STATUS = sa.Enum("active", "paused", "achieved", "abandoned", name="goal_status")
DEBT_KIND = sa.Enum(
    "credit_card", "personal_loan", "student_loan", "mortgage", "auto_loan", "other",
    name="debt_kind",
)
DEBT_STATUS = sa.Enum(
    "active", "paid_off", "in_collections", "written_off", name="debt_status"
)
INV_ACCT_KIND = sa.Enum(
    "taxable_brokerage", "ira", "roth_ira", "k401", "crypto", "retirement_other", "other",
    name="investment_account_kind",
)
HOLDING_KIND = sa.Enum(
    "equity", "etf", "mutual_fund", "bond", "crypto", "cash", "other",
    name="holding_kind",
)


def upgrade() -> None:
    # budgets
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "name", "period_start", name="uq_budgets_entity_name_period"),
    )
    op.create_index("ix_budgets_entity_id", "budgets", ["entity_id"])

    # budget_lines
    op.create_table(
        "budget_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("budget_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("planned_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("budget_id", "account_id", name="uq_budget_lines_budget_account"),
    )
    op.create_index("ix_budget_lines_budget_id", "budget_lines", ["budget_id"])
    op.create_index("ix_budget_lines_account_id", "budget_lines", ["account_id"])

    # goals
    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", GOAL_KIND, nullable=False),
        sa.Column("target_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("target_date", sa.Date()),
        sa.Column("current_amount", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("linked_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("status", GOAL_STATUS, nullable=False, server_default=sa.text("'active'")),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_goals_entity_id", "goals", ["entity_id"])

    # debts
    op.create_table(
        "debts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", DEBT_KIND, nullable=False),
        sa.Column("original_principal", sa.Numeric(20, 2)),
        sa.Column("current_balance", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("interest_rate_apr", sa.Numeric(7, 4)),
        sa.Column("minimum_payment", sa.Numeric(20, 2)),
        sa.Column("due_day_of_month", sa.Integer()),
        sa.Column("next_due_date", sa.Date()),
        sa.Column("linked_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("status", DEBT_STATUS, nullable=False, server_default=sa.text("'active'")),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_debts_entity_id", "debts", ["entity_id"])

    # investment_accounts
    op.create_table(
        "investment_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("broker", sa.String(length=200)),
        sa.Column("kind", INV_ACCT_KIND, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("linked_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_investment_accounts_entity_id", "investment_accounts", ["entity_id"])

    # investment_holdings
    op.create_table(
        "investment_holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("investment_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("investment_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200)),
        sa.Column("kind", HOLDING_KIND, nullable=False),
        sa.Column("shares", sa.Numeric(20, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("cost_basis_per_share", sa.Numeric(20, 6)),
        sa.Column("current_price", sa.Numeric(20, 6)),
        sa.Column("last_priced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_investment_holdings_investment_account_id", "investment_holdings", ["investment_account_id"])

    # net_worth_snapshots
    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("total_assets", sa.Numeric(20, 2), nullable=False),
        sa.Column("total_liabilities", sa.Numeric(20, 2), nullable=False),
        sa.Column("net_worth", sa.Numeric(20, 2), nullable=False),
        sa.Column("breakdown", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "as_of", name="uq_net_worth_snapshots_entity_as_of"),
    )
    op.create_index("ix_net_worth_snapshots_entity_id", "net_worth_snapshots", ["entity_id"])


def downgrade() -> None:
    op.drop_table("net_worth_snapshots")
    op.drop_table("investment_holdings")
    op.drop_table("investment_accounts")
    op.drop_table("debts")
    op.drop_table("goals")
    op.drop_table("budget_lines")
    op.drop_table("budgets")

    bind = op.get_bind()
    HOLDING_KIND.drop(bind, checkfirst=True)
    INV_ACCT_KIND.drop(bind, checkfirst=True)
    DEBT_STATUS.drop(bind, checkfirst=True)
    DEBT_KIND.drop(bind, checkfirst=True)
    GOAL_STATUS.drop(bind, checkfirst=True)
    GOAL_KIND.drop(bind, checkfirst=True)
