from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserSettings
from app.schemas.user_settings import UserSettingsUpdate
from app.services.audit import write_audit
from app.services.crypto import encrypt_secret

_REDACTED = "[REDACTED]"


def _snapshot(row: UserSettings) -> dict:
    return {
        "jurisdiction": row.jurisdiction,
        "base_currency": row.base_currency,
        "fiscal_year_start_month": row.fiscal_year_start_month,
        "ai_provider": row.ai_provider,
        "ai_model": row.ai_model,
        "ai_api_key_hint": row.ai_api_key_hint,
        "ai_api_key_present": row.ai_api_key_encrypted is not None,
        "openai_document_ai_enabled": row.openai_document_ai_enabled,
        "openai_document_ai_consent_granted": row.openai_document_ai_consent_granted,
        "openai_vision_model": row.openai_vision_model,
        "openai_pdf_model": row.openai_pdf_model,
        "openai_transcription_model": row.openai_transcription_model,
    }


async def get_or_create(db: AsyncSession, *, user: User) -> UserSettings:
    row = (
        await db.execute(
            select(UserSettings).where(
                UserSettings.user_id == user.id,
                UserSettings.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row

    row = UserSettings(user_id=user.id, tenant_id=user.tenant_id)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def update(
    db: AsyncSession,
    *,
    user: User,
    payload: UserSettingsUpdate,
    ip: str | None = None,
    user_agent: str | None = None,
) -> UserSettings:
    row = await get_or_create(db, user=user)
    before = _snapshot(row)
    provided_fields = payload.model_fields_set

    if "jurisdiction" in provided_fields:
        row.jurisdiction = payload.jurisdiction
    if "base_currency" in provided_fields:
        row.base_currency = payload.base_currency.upper() if payload.base_currency else None
    if "fiscal_year_start_month" in provided_fields:
        row.fiscal_year_start_month = payload.fiscal_year_start_month
    if "ai_provider" in provided_fields:
        row.ai_provider = payload.ai_provider
    if "ai_model" in provided_fields:
        row.ai_model = payload.ai_model
    if "openai_document_ai_enabled" in provided_fields:
        row.openai_document_ai_enabled = bool(payload.openai_document_ai_enabled)
    if "openai_document_ai_consent_granted" in provided_fields:
        row.openai_document_ai_consent_granted = bool(payload.openai_document_ai_consent_granted)
    if "openai_vision_model" in provided_fields:
        row.openai_vision_model = payload.openai_vision_model
    if "openai_pdf_model" in provided_fields:
        row.openai_pdf_model = payload.openai_pdf_model
    if "openai_transcription_model" in provided_fields:
        row.openai_transcription_model = payload.openai_transcription_model

    if payload.ai_api_key_clear:
        row.ai_api_key_encrypted = None
        row.ai_api_key_hint = None
    elif payload.ai_api_key is not None:
        row.ai_api_key_encrypted = encrypt_secret(payload.ai_api_key)
        row.ai_api_key_hint = payload.ai_api_key[-4:]

    await db.flush()
    await db.refresh(row)

    after = _snapshot(row)
    if payload.ai_api_key is not None:
        after["ai_api_key"] = _REDACTED
    if payload.ai_api_key_clear:
        after["ai_api_key"] = _REDACTED

    await write_audit(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        entity_id=None,
        action="update",
        object_type="user_settings",
        object_id=row.id,
        before=before,
        after=after,
        ip=ip,
        user_agent=user_agent,
    )
    return row
