"""Authentication service: login, logout, session validation."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AuthError
from app.models import LoginAttempt, Session, User
from app.models.base import utcnow
from app.security import (
    generate_session_token,
    hash_session_token,
    verify_password,
)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    email_norm = email.strip().lower()
    user = (
        await db.execute(select(User).where(User.email == email_norm))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        # Same error for both branches — don't leak which one failed.
        raise AuthError("Invalid credentials", code="invalid_credentials")
    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid credentials", code="invalid_credentials")
    return user


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    email_norm = email.strip().lower()
    return (
        await db.execute(select(User).where(User.email == email_norm))
    ).scalar_one_or_none()


async def check_login_rate_limit(db: AsyncSession, *, email: str, ip: str | None) -> None:
    settings = get_settings()
    since = utcnow() - timedelta(minutes=settings.login_rate_limit_window_minutes)
    email_norm = email.strip().lower()
    filters = [
        LoginAttempt.was_successful.is_(False),
        LoginAttempt.created_at >= since,
        or_(LoginAttempt.email == email_norm, LoginAttempt.ip == ip if ip else LoginAttempt.email == email_norm),
    ]
    recent_failures = (
        await db.execute(select(func.count(LoginAttempt.id)).where(*filters))
    ).scalar_one()
    if recent_failures >= settings.login_rate_limit_attempts:
        raise AuthError("Too many login attempts. Try again later.", code="login_rate_limited")


async def record_login_attempt(
    db: AsyncSession,
    *,
    email: str,
    ip: str | None,
    user_agent: str | None,
    was_successful: bool,
    user: User | None = None,
    failure_reason: str | None = None,
) -> LoginAttempt:
    row = LoginAttempt(
        tenant_id=user.tenant_id if user is not None else None,
        user_id=user.id if user is not None else None,
        email=email.strip().lower(),
        ip=ip,
        user_agent=(user_agent or "")[:512] or None,
        was_successful=was_successful,
        failure_reason=failure_reason,
    )
    db.add(row)
    await db.flush()
    return row


async def create_session(
    db: AsyncSession,
    user: User,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[Session, str]:
    """Returns (session_row, plaintext_token). Token is shown once; only its hash is stored."""
    settings = get_settings()
    token = generate_session_token()
    session = Session(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
        ip=ip,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(session)
    await db.flush()
    return session, token


async def resolve_session_token(db: AsyncSession, token: str) -> tuple[Session, User]:
    """Look up an active session by its plaintext cookie value. Raises AuthError if invalid."""
    if not token:
        raise AuthError("No session", code="no_session")
    token_hash = hash_session_token(token)
    row = (
        await db.execute(
            select(Session, User)
            .join(User, User.id == Session.user_id)
            .where(Session.token_hash == token_hash)
        )
    ).first()
    if row is None:
        raise AuthError("Invalid session", code="invalid_session")
    session, user = row
    if session.expires_at <= utcnow():
        raise AuthError("Session expired", code="session_expired")
    if not user.is_active:
        raise AuthError("User inactive", code="user_inactive")
    session.last_seen_at = utcnow()
    return session, user


async def revoke_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    obj = await db.get(Session, session_id)
    if obj is not None:
        await db.delete(obj)
