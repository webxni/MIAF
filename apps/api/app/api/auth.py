from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import DB, CurrentUserDep, RequestCtx
from app.config import get_settings
from app.errors import AuthError
from app.schemas.auth import LoginRequest, UserOut
from app.services.audit import write_audit
from app.services.auth import (
    authenticate_user,
    check_login_rate_limit,
    create_session,
    find_user_by_email,
    record_login_attempt,
    revoke_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
async def login(payload: LoginRequest, response: Response, db: DB, ctx: RequestCtx) -> UserOut:
    settings = get_settings()
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

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )

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
