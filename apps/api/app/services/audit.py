"""Audit service: append-only logging of every sensitive action.

Callers pass before/after snapshots already shaped as plain JSON-safe dicts.
This module redacts a small set of obviously sensitive keys before insert.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

# Keys that must never be persisted. Lower-case match.
_REDACT_KEYS = {
    "password",
    "password_hash",
    "token",
    "token_hash",
    "secret",
    "secret_key",
    "api_key",
    "ai_api_key",
    "ai_api_key_encrypted",
    "authorization",
    "cookie",
}

_REDACTED = "[REDACTED]"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _REDACT_KEYS:
                out[k] = _REDACTED
            else:
                out[k] = _redact(v)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact(v) for v in value)
    return value


async def write_audit(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    entity_id: uuid.UUID | None,
    action: str,
    object_type: str,
    object_id: str | uuid.UUID | None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        action=action,
        object_type=object_type,
        object_id=str(object_id) if object_id is not None else None,
        before=_redact(before) if before is not None else None,
        after=_redact(after) if after is not None else None,
        ip=ip,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(log)
    await db.flush()
    return log
