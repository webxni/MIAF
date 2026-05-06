from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select

from app.api.deps import DB, CurrentUser, CurrentUserDep, RequestCtx, require_tenant_admin_or_owner
from app.config import get_settings
from app.core.brand import SHORT_NAME
from app.errors import AuthError, ConflictError
from app.models import EntityMode, Tenant, User
from app.schemas.auth import LoginRequest, PasswordChangeRequest, RegisterOwnerRequest, UserOut
from app.schemas.invite import AcceptInviteRequest, InviteCreate, InviteOut
from app.services.audit import write_audit
from app.services.auth import (
    authenticate_user,
    check_login_rate_limit,
    cleanup_expired_sessions,
    create_session,
    find_user_by_email,
    record_login_attempt,
    revoke_all_sessions,
    revoke_session,
)
from app.services.entities import create_entity
from app.services.invite import (
    accept_invite,
    create_invite,
    list_invites,
    revoke_invite,
)
from app.services.seed import create_default_chart_of_accounts
from app.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
internal_router = APIRouter(prefix="/internal/auth", tags=["internal-auth"])


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

    tenant = Tenant(name=f"{SHORT_NAME} Workspace")
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


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> Response:
    if not verify_password(payload.current_password, me.user.password_hash):
        raise AuthError("Current password is incorrect", code="wrong_password")
    me.user.password_hash = hash_password(payload.new_password)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="password_change",
        object_type="user",
        object_id=me.id,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/revoke-all-sessions", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_my_sessions(
    response: Response,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> Response:
    count = await revoke_all_sessions(db, user_id=me.id)
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="revoke_all_sessions",
        object_type="session",
        object_id=me.id,
        after={"sessions_revoked": count},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Team invites ──────────────────────────────────────────────────────────────

@router.post("/invites", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite_endpoint(
    payload: InviteCreate,
    db: DB,
    me: Annotated[CurrentUser, Depends(require_tenant_admin_or_owner)],
    ctx: RequestCtx,
) -> InviteOut:
    invite = await create_invite(
        db,
        tenant_id=me.tenant_id,
        inviter_id=me.id,
        email=payload.email,
        role=payload.role,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="create_invite",
        object_type="invite",
        object_id=invite.id,
        after={"email": invite.email, "role": invite.role, "expires_at": invite.expires_at.isoformat()},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return InviteOut.model_validate(invite)


@router.get("/invites", response_model=list[InviteOut])
async def list_invites_endpoint(
    db: DB,
    me: Annotated[CurrentUser, Depends(require_tenant_admin_or_owner)],
) -> list[InviteOut]:
    invites = await list_invites(db, tenant_id=me.tenant_id)
    return [InviteOut.model_validate(inv) for inv in invites]


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def revoke_invite_endpoint(
    invite_id: uuid.UUID,
    db: DB,
    me: Annotated[CurrentUser, Depends(require_tenant_admin_or_owner)],
    ctx: RequestCtx,
) -> Response:
    invite = await revoke_invite(db, invite_id=invite_id, tenant_id=me.tenant_id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="revoke_invite",
        object_type="invite",
        object_id=invite.id,
        after={"email": invite.email},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/accept-invite", response_model=UserOut)
async def accept_invite_endpoint(
    payload: AcceptInviteRequest,
    response: Response,
    db: DB,
    ctx: RequestCtx,
) -> UserOut:
    user = await accept_invite(db, token=payload.token, name=payload.name, password=payload.password)
    session, token = await create_session(db, user, ip=ctx.ip, user_agent=ctx.user_agent)
    _set_session_cookie(response, token)
    await write_audit(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        entity_id=None,
        action="accept_invite",
        object_type="user",
        object_id=user.id,
        after={"email": user.email, "name": user.name},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return UserOut.model_validate(user)


# ── Internal maintenance ──────────────────────────────────────────────────────

@internal_router.post("/cleanup-sessions", status_code=200)
async def cleanup_sessions_endpoint(
    db: DB,
    x_automation_token: Annotated[str | None, Header()] = None,
) -> dict:
    from fastapi import HTTPException
    expected = get_settings().automation_token
    if not expected or x_automation_token != expected:
        raise HTTPException(status_code=401, detail="Invalid automation token")
    deleted = await cleanup_expired_sessions(db)
    return {"sessions_deleted": deleted}
