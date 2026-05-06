"""Phase 8 — heartbeat runs, alerts, reports.

Revision ID: 0006_heartbeat_ops
Revises: 0005_memory
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_heartbeat_ops"
down_revision: Union[str, None] = "0005_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HEARTBEAT_TYPE_LABELS = (
    "daily_personal_check",
    "weekly_personal_report",
    "monthly_personal_close",
    "daily_business_check",
    "weekly_business_report",
    "monthly_business_close",
    "tax_reserve_check",
    "cash_runway_check",
    "budget_overspend_check",
    "ar_ap_aging_check",
)
_HEARTBEAT_RUN_STATUS_LABELS = ("running", "completed", "failed")
_ALERT_SEVERITY_LABELS = ("info", "warning", "critical")
_ALERT_STATUS_LABELS = ("open", "resolved", "dismissed")
_REPORT_KIND_LABELS = ("weekly_business_report", "weekly_personal_report")

HEARTBEAT_TYPE = postgresql.ENUM(*_HEARTBEAT_TYPE_LABELS, name="heartbeat_type", create_type=False)
HEARTBEAT_RUN_STATUS = postgresql.ENUM(*_HEARTBEAT_RUN_STATUS_LABELS, name="heartbeat_run_status", create_type=False)
ALERT_SEVERITY = postgresql.ENUM(*_ALERT_SEVERITY_LABELS, name="alert_severity", create_type=False)
ALERT_STATUS = postgresql.ENUM(*_ALERT_STATUS_LABELS, name="alert_status", create_type=False)
REPORT_KIND = postgresql.ENUM(*_REPORT_KIND_LABELS, name="report_kind", create_type=False)


def _create_enum(name: str, *labels: str) -> None:
    postgresql.ENUM(*labels, name=name).create(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    _create_enum("heartbeat_type", *_HEARTBEAT_TYPE_LABELS)
    _create_enum("heartbeat_run_status", *_HEARTBEAT_RUN_STATUS_LABELS)
    _create_enum("alert_severity", *_ALERT_SEVERITY_LABELS)
    _create_enum("alert_status", *_ALERT_STATUS_LABELS)
    _create_enum("report_kind", *_REPORT_KIND_LABELS)

    op.create_table(
        "heartbeat_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("heartbeat_type", HEARTBEAT_TYPE, nullable=False),
        sa.Column("status", HEARTBEAT_RUN_STATUS, nullable=False),
        sa.Column("trigger_source", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("summary", postgresql.JSONB),
        sa.Column("error_message", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_heartbeat_runs_tenant_id", "heartbeat_runs", ["tenant_id"])
    op.create_index("ix_heartbeat_runs_heartbeat_type", "heartbeat_runs", ["heartbeat_type"])
    op.create_index("ix_heartbeat_runs_status", "heartbeat_runs", ["status"])

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE")),
        sa.Column("heartbeat_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("heartbeat_runs.id", ondelete="SET NULL")),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", ALERT_SEVERITY, nullable=False),
        sa.Column("status", ALERT_STATUS, nullable=False, server_default=sa.text("'open'")),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_alerts_tenant_id", "alerts", ["tenant_id"])
    op.create_index("ix_alerts_entity_id", "alerts", ["entity_id"])
    op.create_index("ix_alerts_alert_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])

    op.create_table(
        "generated_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE")),
        sa.Column("heartbeat_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("heartbeat_runs.id", ondelete="SET NULL")),
        sa.Column("report_kind", REPORT_KIND, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_generated_reports_tenant_id", "generated_reports", ["tenant_id"])
    op.create_index("ix_generated_reports_entity_id", "generated_reports", ["entity_id"])
    op.create_index("ix_generated_reports_report_kind", "generated_reports", ["report_kind"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("generated_reports")
    op.drop_table("alerts")
    op.drop_table("heartbeat_runs")
    REPORT_KIND.drop(bind, checkfirst=True)
    ALERT_STATUS.drop(bind, checkfirst=True)
    ALERT_SEVERITY.drop(bind, checkfirst=True)
    HEARTBEAT_RUN_STATUS.drop(bind, checkfirst=True)
    HEARTBEAT_TYPE.drop(bind, checkfirst=True)
