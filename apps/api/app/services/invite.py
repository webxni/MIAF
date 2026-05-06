"""Invite token service: create, accept, list, and revoke team invites."""
from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AuthError, ConflictError, NotFoundError
from app.models import Entity, EntityMember, InviteToken, Role, User
from app.models.base import utcnow
from app.security import hash_password

_INVITE_TTL_HOURS = 72


async def create_invite(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    inviter_id: uuid.UUID,
    email: str,
    role: Role,
    ttl_hours: int = _INVITE_TTL_HOURS,
) -> InviteToken:
    email_norm = email.strip().lower()

    # Reject if the email is already a member of this tenant.
    existing_user = (
        await db.execute(
            select(User).where(User.email == email_norm, User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if existing_user is not None:
        raise ConflictError(
            f"{email_norm} is already a member of this workspace.",
            code="invite_already_member",
        )

    # Reuse an existing pending invite for the same email rather than creating duplicates.
    existing = (
        await db.execute(
            select(InviteToken).where(
                InviteToken.tenant_id == tenant_id,
                InviteToken.email == email_norm,
                InviteToken.accepted_at.is_(None),
                InviteToken.is_revoked.is_(False),
                InviteToken.expires_at > utcnow(),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Refresh the expiry so the invitee has a fresh window.
        existing.expires_at = utcnow() + timedelta(hours=ttl_hours)
        existing.role = role.value
        await db.flush()
        return existing

    invite = InviteToken(
        tenant_id=tenant_id,
        inviter_id=inviter_id,
        email=email_norm,
        role=role.value,
        token=secrets.token_urlsafe(48),
        expires_at=utcnow() + timedelta(hours=ttl_hours),
    )
    db.add(invite)
    await db.flush()
    return invite


async def accept_invite(
    db: AsyncSession,
    *,
    token: str,
    name: str,
    password: str,
) -> User:
    invite = (
        await db.execute(
            select(InviteToken).where(InviteToken.token == token)
        )
    ).scalar_one_or_none()

    if invite is None:
        raise AuthError("Invalid or expired invite token.", code="invalid_invite")
    if invite.is_revoked:
        raise AuthError("This invite has been revoked.", code="invite_revoked")
    if invite.accepted_at is not None:
        raise AuthError("This invite has already been accepted.", code="invite_already_accepted")
    if invite.expires_at <= utcnow():
        raise AuthError("This invite has expired.", code="invite_expired")

    email_norm = invite.email
    existing = (
        await db.execute(select(User).where(User.email == email_norm))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"{email_norm} is already registered.", code="email_taken")

    user = User(
        tenant_id=invite.tenant_id,
        email=email_norm,
        name=name.strip(),
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Grant membership on every entity in the tenant.
    entities = (
        await db.execute(
            select(Entity).where(Entity.tenant_id == invite.tenant_id)
        )
    ).scalars().all()
    role = Role(invite.role)
    for entity in entities:
        membership = EntityMember(entity_id=entity.id, user_id=user.id, role=role)
        db.add(membership)

    invite.accepted_at = utcnow()
    await db.flush()
    return user


async def list_invites(db: AsyncSession, tenant_id: uuid.UUID) -> list[InviteToken]:
    return (
        await db.execute(
            select(InviteToken)
            .where(InviteToken.tenant_id == tenant_id)
            .order_by(InviteToken.created_at.desc())
        )
    ).scalars().all()


async def revoke_invite(
    db: AsyncSession,
    *,
    invite_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> InviteToken:
    invite = await db.get(InviteToken, invite_id)
    if invite is None or invite.tenant_id != tenant_id:
        raise NotFoundError("Invite not found", code="invite_not_found")
    if invite.accepted_at is not None:
        raise ConflictError("Cannot revoke an already accepted invite.", code="invite_already_accepted")
    invite.is_revoked = True
    await db.flush()
    return invite
