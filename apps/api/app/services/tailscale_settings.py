from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tailscale import TailscaleSettings
from app.models.base import utcnow
from app.schemas.tailscale import TailscaleSettingsUpdate
from app.services.audit import write_audit


async def get_or_create(db: AsyncSession, *, tenant_id: uuid.UUID) -> TailscaleSettings:
    row = (
        await db.execute(
            select(TailscaleSettings).where(TailscaleSettings.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = TailscaleSettings(tenant_id=tenant_id)
        db.add(row)
        await db.flush()
    return row


async def update(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: TailscaleSettingsUpdate,
    ip: str | None = None,
    user_agent: str | None = None,
) -> TailscaleSettings:
    row = await get_or_create(db, tenant_id=tenant_id)
    before: dict = {
        "tailscale_enabled": row.tailscale_enabled,
        "tailscale_mode": row.tailscale_mode,
        "tailscale_target_url": row.tailscale_target_url,
        "tailscale_setup_completed": row.tailscale_setup_completed,
    }
    changed = False
    for field_name, value in payload.model_dump(exclude_none=True).items():
        if getattr(row, field_name) != value:
            setattr(row, field_name, value)
            changed = True
    if changed:
        row.updated_at = utcnow()
        await db.flush()
        await write_audit(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            entity_id=None,
            action="update",
            object_type="tailscale_settings",
            object_id=row.id,
            before=before,
            after={
                "tailscale_enabled": row.tailscale_enabled,
                "tailscale_mode": row.tailscale_mode,
                "tailscale_target_url": row.tailscale_target_url,
                "tailscale_setup_completed": row.tailscale_setup_completed,
            },
            ip=ip,
            user_agent=user_agent,
        )
    return row


async def record_status_check(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    status_text: str,
    tailscale_ip: str | None,
    hostname: str | None,
    tailnet_url: str | None,
) -> TailscaleSettings:
    row = await get_or_create(db, tenant_id=tenant_id)
    row.tailscale_last_status = status_text[:2000]
    row.tailscale_last_checked_at = utcnow()
    if tailscale_ip and not row.tailscale_hostname:
        row.tailscale_hostname = hostname
    if tailnet_url:
        row.tailscale_tailnet_url = tailnet_url
    row.updated_at = utcnow()
    await db.flush()
    return row
