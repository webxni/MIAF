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
from app.models.heartbeat import (
    Alert,
    AlertSeverity,
    AlertStatus,
    GeneratedReport,
    HeartbeatRun,
    HeartbeatRunStatus,
    HeartbeatType,
    ReportKind,
)
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
from app.models.memory import (
    Memory,
    MemoryEmbedding,
    MemoryEvent,
    MemoryEventType,
    MemoryReview,
    MemoryReviewStatus,
    MemoryType,
)
from app.models.net_worth import NetWorthSnapshot
from app.models.security import LoginAttempt
from app.models.session import Session
from app.models.skill import SkillRunLog, SkillState
from app.models.source_transaction import SourceTransaction, SourceTransactionStatus
from app.models.tenant import Tenant
from app.models.telegram import (
    TelegramLink,
    TelegramMessage,
    TelegramMessageDirection,
    TelegramMessageStatus,
    TelegramMessageType,
)
from app.models.user import User
from app.models.user_settings import UserSettings

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
    "GeneratedReport",
    "Goal",
    "GoalKind",
    "GoalStatus",
    "HeartbeatRun",
    "HeartbeatRunStatus",
    "HeartbeatType",
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
    "LoginAttempt",
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "Memory",
    "MemoryEmbedding",
    "MemoryEvent",
    "MemoryEventType",
    "MemoryReview",
    "MemoryReviewStatus",
    "MemoryType",
    "DocumentExtraction",
    "NetWorthSnapshot",
    "NormalSide",
    "Payment",
    "PaymentKind",
    "ReportKind",
    "Role",
    "Session",
    "SkillRunLog",
    "SkillState",
    "SourceTransaction",
    "SourceTransactionStatus",
    "CandidateStatus",
    "TaxRate",
    "TaxReserve",
    "Tenant",
    "TelegramLink",
    "TelegramMessage",
    "TelegramMessageDirection",
    "TelegramMessageStatus",
    "TelegramMessageType",
    "User",
    "UserSettings",
    "Vendor",
]
