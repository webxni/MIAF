from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK


class HeartbeatType(str, enum.Enum):
    daily_personal_check = "daily_personal_check"
    weekly_personal_report = "weekly_personal_report"
    monthly_personal_close = "monthly_personal_close"
    daily_business_check = "daily_business_check"
    weekly_business_report = "weekly_business_report"
    monthly_business_close = "monthly_business_close"
    tax_reserve_check = "tax_reserve_check"
    cash_runway_check = "cash_runway_check"
    budget_overspend_check = "budget_overspend_check"
    ar_ap_aging_check = "ar_ap_aging_check"


class HeartbeatRunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class AlertStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


class ReportKind(str, enum.Enum):
    weekly_business_report = "weekly_business_report"
    weekly_personal_report = "weekly_personal_report"


class HeartbeatRun(UUIDPK, Timestamps, Base):
    __tablename__ = "heartbeat_runs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    heartbeat_type: Mapped[HeartbeatType] = mapped_column(
        SAEnum(HeartbeatType, name="heartbeat_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[HeartbeatRunStatus] = mapped_column(
        SAEnum(HeartbeatRunStatus, name="heartbeat_run_status"),
        nullable=False,
        index=True,
    )
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(String(500))


class Alert(UUIDPK, Timestamps, Base):
    __tablename__ = "alerts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    heartbeat_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("heartbeat_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity, name="alert_severity"),
        nullable=False,
        index=True,
    )
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, name="alert_status"),
        nullable=False,
        default=AlertStatus.open,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GeneratedReport(UUIDPK, Timestamps, Base):
    __tablename__ = "generated_reports"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    heartbeat_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("heartbeat_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_kind: Mapped[ReportKind] = mapped_column(
        SAEnum(ReportKind, name="report_kind"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
