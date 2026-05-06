"""Phase 12 — revoke audit log UPDATE/DELETE from the application role.

Revision ID: 0011_audit_logs_revoke
Revises: 0010_user_settings
Create Date: 2026-05-06

This migration relies on Alembic running as the same database role the app uses,
so CURRENT_USER / CURRENT_ROLE / SESSION_USER resolve to that application role at
runtime. PostgreSQL superusers bypass GRANT/REVOKE checks, so this only enforces
immutability for the non-superuser application role used by the app.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0011_audit_logs_revoke"
down_revision: Union[str, None] = "0010_user_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("REVOKE UPDATE, DELETE ON TABLE audit_logs FROM PUBLIC")
    op.execute("REVOKE UPDATE, DELETE ON TABLE audit_logs FROM CURRENT_USER")
    op.execute("REVOKE UPDATE, DELETE ON TABLE audit_logs FROM CURRENT_ROLE")
    op.execute("REVOKE UPDATE, DELETE ON TABLE audit_logs FROM SESSION_USER")


def downgrade() -> None:
    op.execute("GRANT UPDATE, DELETE ON TABLE audit_logs TO CURRENT_USER")
    op.execute("GRANT UPDATE, DELETE ON TABLE audit_logs TO CURRENT_ROLE")
    op.execute("GRANT UPDATE, DELETE ON TABLE audit_logs TO SESSION_USER")
    op.execute("GRANT UPDATE, DELETE ON TABLE audit_logs TO PUBLIC")
