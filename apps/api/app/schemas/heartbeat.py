from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import AlertSeverity, AlertStatus, HeartbeatRunStatus, HeartbeatType, ReportKind


class HeartbeatRunRequest(BaseModel):
    heartbeat_type: HeartbeatType
    as_of: date | None = None


class HeartbeatRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    heartbeat_type: HeartbeatType
    status: HeartbeatRunStatus
    trigger_source: str
    started_at: datetime | None
    finished_at: datetime | None
    initiated_by_user_id: uuid.UUID | None
    summary: dict | None
    error_message: str | None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID | None
    heartbeat_run_id: uuid.UUID | None
    alert_type: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    payload: dict | None
    resolved_at: datetime | None
    created_at: datetime


class GeneratedReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID | None
    heartbeat_run_id: uuid.UUID | None
    report_kind: ReportKind
    period_start: date
    period_end: date
    title: str
    body: str
    created_at: datetime
