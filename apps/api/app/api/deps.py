"""Shared FastAPI dependencies."""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal
from app.errors import AuthError, ForbiddenError, NotFoundError
from app.models import Entity, EntityMember, Role, Session, User
from app.services.auth import resolve_session_token


@dataclass
class CurrentUser:
    """Authenticated principal for a request."""

    user: User
    session: Session

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.user.tenant_id


@dataclass
class RequestContext:
    """IP and user agent extracted at request boundary, attached to audit logs."""

    ip: str | None
    user_agent: str | None


async def get_db() -> AsyncIterator[AsyncSession]:
    """Per-request DB session. Commits on success, rolls back on exception."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DB = Annotated[AsyncSession, Depends(get_db)]


def get_request_context(request: Request) -> RequestContext:
    # When behind a reverse proxy, X-Forwarded-For is already trusted because
    # uvicorn is run with --proxy-headers in prod and the proxy is Caddy.
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
    if ip:
        ip = ip.split(",")[0].strip()
    return RequestContext(ip=ip, user_agent=request.headers.get("user-agent"))


RequestCtx = Annotated[RequestContext, Depends(get_request_context)]


async def get_current_user(
    request: Request,
    db: DB,
    finclaw_session: Annotated[str | None, Cookie()] = None,
) -> CurrentUser:
    settings = get_settings()
    cookie_name = settings.session_cookie_name
    # The default arg name `finclaw_session` matches the default cookie name,
    # but if the deployment overrides SESSION_COOKIE_NAME we read from headers.
    token = finclaw_session if cookie_name == "finclaw_session" else request.cookies.get(cookie_name)
    if not token:
        raise AuthError("Authentication required", code="not_authenticated")
    session, user = await resolve_session_token(db, token)
    return CurrentUser(user=user, session=session)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def get_entity_for_user(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
) -> tuple[Entity, EntityMember]:
    """Resolve an entity AND verify the caller is a member of it.

    Enforces tenant isolation at the data layer per the hard rules.
    """
    row = (
        await db.execute(
            select(Entity, EntityMember)
            .join(EntityMember, EntityMember.entity_id == Entity.id)
            .where(
                Entity.id == entity_id,
                Entity.tenant_id == me.tenant_id,
                EntityMember.user_id == me.id,
            )
        )
    ).first()
    if row is None:
        # Don't leak whether the entity exists in another tenant.
        raise NotFoundError(f"Entity {entity_id} not found", code="entity_not_found")
    entity, membership = row
    return entity, membership


def require_role(*allowed: Role):
    """Returns a dependency that requires the entity membership to have one of the listed roles."""

    allowed_set = set(allowed)

    async def _dep(
        scoped: Annotated[tuple[Entity, EntityMember], Depends(get_entity_for_user)],
    ) -> tuple[Entity, EntityMember]:
        _, membership = scoped
        if membership.role not in allowed_set:
            raise ForbiddenError(
                f"Role {membership.role.value} cannot perform this action",
                code="role_forbidden",
                details={"required_any": [r.value for r in allowed_set]},
            )
        return scoped

    return _dep


# Common role bundles
require_writer = require_role(Role.owner, Role.admin, Role.accountant, Role.agent)
require_poster = require_role(Role.owner, Role.admin, Role.accountant)
require_reader = require_role(Role.owner, Role.admin, Role.accountant, Role.viewer, Role.agent)


async def require_tenant_admin_or_owner(
    db: DB,
    me: CurrentUserDep,
) -> CurrentUser:
    row = (
        await db.execute(
            select(EntityMember.id)
            .join(Entity, Entity.id == EntityMember.entity_id)
            .where(
                Entity.tenant_id == me.tenant_id,
                EntityMember.user_id == me.id,
                EntityMember.role.in_((Role.owner, Role.admin)),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ForbiddenError(
            "Role must be owner or admin on at least one entity",
            code="role_forbidden",
            details={"required_any": [Role.owner.value, Role.admin.value]},
        )
    return me
