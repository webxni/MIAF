from __future__ import annotations

from sqlalchemy import select
from fastapi import APIRouter, Response, status

from app.api.deps import DB, CurrentUserDep, RequestCtx
from app.config import get_settings
from app.errors import AuthError, ConflictError
from app.models import EntityMode, Tenant, User
from app.schemas.auth import LoginRequest, RegisterOwnerRequest, UserOut
from app.services.entities import create_entity
from app.services.audit import write_audit
from app.services.auth import (
    authenticate_user,
    check_login_rate_limit,
    create_session,
    find_user_by_email,
    record_login_attempt,
    revoke_session,
)
from app.services.seed import create_default_chart_of_accounts
from app.security import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=UserOut)
async def login(payload: LoginRequest, response: Response, db: DB, ctx: RequestCtx) -> UserOut:
    await check_login_rate_limit(db, email=payload.email, ip=ctx.ip)
    try:
        user = await authenticate_user(db, payload.email, payload.password)
    except AuthError as exc:
        user = await find_user_by_email(db, payload.email)
        await record_login_attempt(
            db,
            email=payload.email,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
            was_successful=False,
            user=user,
            failure_reason=getattr(exc, "code", "login_failed"),
        )
        if user is not None:
            await write_audit(
                db,
                tenant_id=user.tenant_id,
                user_id=user.id,
                entity_id=None,
                action="login_failed",
                object_type="session",
                object_id=None,
                after={"email": payload.email.lower(), "reason": getattr(exc, "code", "login_failed")},
                ip=ctx.ip,
                user_agent=ctx.user_agent,
            )
        raise

    await record_login_attempt(
        db,
        email=payload.email,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
        was_successful=True,
        user=user,
    )
    session, token = await create_session(db, user, ip=ctx.ip, user_agent=ctx.user_agent)
    _set_session_cookie(response, token)

    await write_audit(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        entity_id=None,
        action="login",
        object_type="session",
        object_id=session.id,
        before=None,
        after={"user_id": str(user.id)},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return UserOut.model_validate(user)


@router.post("/register-owner", response_model=UserOut)
async def register_owner(
    payload: RegisterOwnerRequest, response: Response, db: DB, ctx: RequestCtx
) -> UserOut:
    await check_login_rate_limit(db, email=payload.email, ip=ctx.ip)

    any_user_exists = (
        await db.execute(select(User.id).limit(1))
    ).scalar_one_or_none()
    if any_user_exists is not None:
        raise ConflictError(
            "An owner account already exists. Please sign in instead.",
            code="owner_already_exists",
        )

    tenant = Tenant(name="My FinClaw")
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email.strip().lower(),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    personal = await create_entity(
        db,
        tenant_id=tenant.id,
        owner_user_id=user.id,
        name="Personal",
        mode=EntityMode.personal,
    )
    business = await create_entity(
        db,
        tenant_id=tenant.id,
        owner_user_id=user.id,
        name="My Business",
        mode=EntityMode.business,
    )
    await create_default_chart_of_accounts(db, personal)
    await create_default_chart_of_accounts(db, business)

    await record_login_attempt(
        db,
        email=payload.email,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
        was_successful=True,
        user=user,
    )
    session, token = await create_session(db, user, ip=ctx.ip, user_agent=ctx.user_agent)
    _set_session_cookie(response, token)

    await write_audit(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        entity_id=None,
        action="register_owner",
        object_type="user",
        object_id=user.id,
        after={"email": user.email, "name": user.name},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, db: DB, me: CurrentUserDep, ctx: RequestCtx) -> Response:
    settings = get_settings()
    await revoke_session(db, me.session.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="logout",
        object_type="session",
        object_id=me.session.id,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    response.delete_cookie(settings.session_cookie_name, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(me: CurrentUserDep) -> UserOut:
    return UserOut.model_validate(me.user)
