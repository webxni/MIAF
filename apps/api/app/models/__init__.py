"""SQLAlchemy ORM models for FinClaw.

Importing this package registers every model with the shared Base.metadata,
which is what Alembic autogenerate and create_all read.
"""
from app.models.account import Account, AccountType, NormalSide
from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.budget import Budget, BudgetLine
from app.models.business import (
    Bill,
    BillLine,
    BusinessDocumentStatus,
    ClosingPeriod,
    ClosingPeriodStatus,
    Customer,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentKind,
    TaxRate,
    TaxReserve,
    Vendor,
)
from app.models.debt import Debt, DebtKind, DebtStatus
from app.models.entity import Entity, EntityMember, EntityMode, Role
from app.models.goal import Goal, GoalKind, GoalStatus
from app.models.ingestion import (
    CandidateStatus,
    DocumentExtraction,
    ExtractionCandidate,
    ExtractionStatus,
    ImportBatch,
    ImportBatchStatus,
)
from app.models.investment import (
    HoldingKind,
    InvestmentAccount,
    InvestmentAccountKind,
    InvestmentHolding,
)
from app.models.journal import (
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)
from app.models.net_worth import NetWorthSnapshot
from app.models.session import Session
from app.models.source_transaction import SourceTransaction, SourceTransactionStatus
from app.models.tenant import Tenant
from app.models.user import User

__all__ = [
    "Account",
    "AccountType",
    "Attachment",
    "AuditLog",
    "Base",
    "Bill",
    "BillLine",
    "Budget",
    "BudgetLine",
    "BusinessDocumentStatus",
    "ClosingPeriod",
    "ClosingPeriodStatus",
    "Customer",
    "Debt",
    "DebtKind",
    "DebtStatus",
    "Entity",
    "EntityMember",
    "EntityMode",
    "ExtractionCandidate",
    "ExtractionStatus",
    "Goal",
    "GoalKind",
    "GoalStatus",
    "HoldingKind",
    "ImportBatch",
    "ImportBatchStatus",
    "InvestmentAccount",
    "InvestmentAccountKind",
    "InvestmentHolding",
    "Invoice",
    "InvoiceLine",
    "JournalEntry",
    "JournalEntryStatus",
    "JournalLine",
    "DocumentExtraction",
    "NetWorthSnapshot",
    "NormalSide",
    "Payment",
    "PaymentKind",
    "Role",
    "Session",
    "SourceTransaction",
    "SourceTransactionStatus",
    "CandidateStatus",
    "TaxRate",
    "TaxReserve",
    "Tenant",
    "User",
    "Vendor",
]
