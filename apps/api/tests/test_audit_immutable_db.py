from __future__ import annotations

import re
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import AuditLog, Tenant


pytestmark = pytest.mark.asyncio


async def test_audit_logs_update_delete_are_revoked_but_insert_still_works(test_db_url: str) -> None:
    engine = create_async_engine(test_db_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            # The migration is enforced against the application role only.
            # Postgres SUPERUSERs bypass GRANT/REVOKE — that's how the dev
            # compose stack ships (POSTGRES_USER becomes a superuser).
            # In that environment the REVOKE is a no-op, so this test
            # cannot verify the immutability claim. Skip with a note rather
            # than report a false failure. Production deploys must use a
            # non-super app role; that's documented in DEPLOY.md.
            super_row = await connection.execute(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"),
            )
            is_super = bool((super_row.scalar()) or False)
            if is_super:
                pytest.skip(
                    "Current Postgres role is a superuser; REVOKE is bypassed by design. "
                    "Production deploys must use a non-super app role.",
                )
            trans = await connection.begin()
            try:
                Session = async_sessionmaker(bind=connection, expire_on_commit=False, class_=AsyncSession)
                async with Session() as session:
                    tenant = Tenant(name=f"Audit Immutable {uuid.uuid4()}")
                    session.add(tenant)
                    await session.flush()

                    session.add(
                        AuditLog(
                            tenant_id=tenant.id,
                            action="insert_allowed",
                            object_type="audit_test",
                            object_id="before-revoke",
                            after={"ok": True},
                        )
                    )
                    await session.flush()

                    await session.execute(text("REVOKE UPDATE, DELETE ON TABLE audit_logs FROM PUBLIC"))
                    await session.execute(text("REVOKE UPDATE, DELETE ON TABLE audit_logs FROM CURRENT_USER"))
                    await session.execute(text("REVOKE UPDATE, DELETE ON TABLE audit_logs FROM CURRENT_ROLE"))
                    await session.execute(text("REVOKE UPDATE, DELETE ON TABLE audit_logs FROM SESSION_USER"))

                    session.add(
                        AuditLog(
                            tenant_id=tenant.id,
                            action="insert_allowed",
                            object_type="audit_test",
                            object_id="after-revoke",
                            after={"ok": True},
                        )
                    )
                    await session.flush()

                    with pytest.raises(ProgrammingError, match=re.compile(r"(permission denied|must be table owner)", re.IGNORECASE)):
                        async with session.begin_nested():
                            await session.execute(text("UPDATE audit_logs SET action='hacked'"))

                    with pytest.raises(ProgrammingError, match=re.compile(r"(permission denied|must be table owner)", re.IGNORECASE)):
                        async with session.begin_nested():
                            await session.execute(text("DELETE FROM audit_logs"))
            finally:
                try:
                    await connection.execute(text("GRANT UPDATE, DELETE ON TABLE audit_logs TO CURRENT_USER"))
                    await connection.execute(text("GRANT UPDATE, DELETE ON TABLE audit_logs TO CURRENT_ROLE"))
                    await connection.execute(text("GRANT UPDATE, DELETE ON TABLE audit_logs TO SESSION_USER"))
                    await connection.execute(text("GRANT UPDATE, DELETE ON TABLE audit_logs TO PUBLIC"))
                finally:
                    await trans.rollback()
    finally:
        await engine.dispose()
