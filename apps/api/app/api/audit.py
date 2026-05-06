from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DB, require_tenant_admin_or_owner
from app.models import AuditLog
from app.schemas.audit import AuditLogListOut, AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogListOut)
async def list_audit_logs(
    db: DB,
    me: Annotated[CurrentUser, Depends(require_tenant_admin_or_owner)],
    action: str | None = None,
    object_type: str | None = None,
    user_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditLogListOut:
    filters = [AuditLog.tenant_id == me.tenant_id]
    if action:
        filters.append(AuditLog.action == action)
    if object_type:
        filters.append(AuditLog.object_type == object_type)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if entity_id is not None:
        filters.append(AuditLog.entity_id == entity_id)
    if since is not None:
        filters.append(AuditLog.created_at >= since)
    if until is not None:
        filters.append(AuditLog.created_at <= until)

    total = (
        await db.execute(select(func.count(AuditLog.id)).where(*filters))
    ).scalar_one()
    rows = (
        await db.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return AuditLogListOut(
        rows=[AuditLogOut.model_validate(row) for row in rows],
        total=total,
    )
