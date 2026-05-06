from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DB, RequestCtx
from app.schemas.user_settings import UserSettingsOut, UserSettingsUpdate
from app.services.user_settings import get_or_create, update

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_out(row) -> UserSettingsOut:
    return UserSettingsOut(
        id=row.id,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        jurisdiction=row.jurisdiction,
        base_currency=row.base_currency,
        fiscal_year_start_month=row.fiscal_year_start_month,
        ai_provider=row.ai_provider,
        ai_model=row.ai_model,
        ai_api_key_hint=row.ai_api_key_hint,
        ai_api_key_present=row.ai_api_key_encrypted is not None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=UserSettingsOut)
async def get_settings(db: DB, me: CurrentUserDep) -> UserSettingsOut:
    row = await get_or_create(db, user=me.user)
    return _to_out(row)


@router.put("", response_model=UserSettingsOut)
async def put_settings(
    payload: UserSettingsUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> UserSettingsOut:
    row = await update(
        db,
        user=me.user,
        payload=payload,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return _to_out(row)
