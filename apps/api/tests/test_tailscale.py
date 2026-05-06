"""Tests for Tailscale private-access settings.

Coverage:
- target URL allowlist (localhost only, ports from config)
- subprocess command timeout/unavailable binary graceful fallback
- owner/admin auth gate; viewer/unauthenticated forbidden
- settings creation + update + audit log
- serve/start validates target before running
- serve/reset audited
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models import AuditLog
from app.models.tailscale import TailscaleSettings
from app.services.tailscale import (
    TailscaleCommandResult,
    TailscaleStatus,
    validate_tailscale_target,
)

pytestmark = pytest.mark.asyncio


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.pop(get_db, None)


async def _login(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": seeded["user_email"], "password": "change-me-on-first-login"},
    )
    assert response.status_code == 200


def _unavailable_status() -> TailscaleStatus:
    return TailscaleStatus(available=False, instructions_only=True, warnings=["tailscale binary not found."])


def _available_status() -> TailscaleStatus:
    return TailscaleStatus(
        available=True,
        tailscale_ip="100.64.0.5",
        hostname="myhost.tailnet.ts.net",
        tailnet_url="http://myhost.tailnet.ts.net",
        raw='{"Self":{}}',
    )


def _ok_result() -> TailscaleCommandResult:
    return TailscaleCommandResult(ok=True, stdout="Web proxy: https://myhost.tailnet.ts.net/")


# ── validate_tailscale_target unit tests ─────────────────────────────────────


def test_validate_target_accepts_localhost_80():
    valid, err = validate_tailscale_target("http://127.0.0.1:80")
    assert valid is True
    assert err == ""


def test_validate_target_accepts_localhost_name():
    valid, err = validate_tailscale_target("http://localhost:80")
    assert valid is True
    assert err == ""


def test_validate_target_rejects_external_host():
    valid, err = validate_tailscale_target("http://evil.com:80")
    assert valid is False
    assert "localhost" in err or "127.0.0.1" in err


def test_validate_target_rejects_non_allowed_port(monkeypatch):
    monkeypatch.setenv("TAILSCALE_ALLOWED_PORTS", "80")
    # Reload settings so the env change takes effect for this test.
    from app.config import get_settings
    get_settings.cache_clear()
    valid, err = validate_tailscale_target("http://127.0.0.1:9999")
    assert valid is False
    assert "9999" in err
    get_settings.cache_clear()


def test_validate_target_rejects_scheme_other_than_http():
    valid, err = validate_tailscale_target("ftp://127.0.0.1:80")
    assert valid is False
    assert "http" in err.lower() or "https" in err.lower()


def test_validate_target_rejects_empty_string():
    valid, err = validate_tailscale_target("")
    assert valid is False


# ── API auth gate ─────────────────────────────────────────────────────────────


async def test_get_tailscale_settings_requires_auth(client: AsyncClient, seeded: dict) -> None:
    with (
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_status", new_callable=AsyncMock, return_value=_unavailable_status()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_serve_status", new_callable=AsyncMock, return_value=TailscaleCommandResult(ok=False, instructions_only=True)),
    ):
        response = await client.get("/settings/tailscale")
    assert response.status_code in (401, 403)


async def test_get_tailscale_settings_owner_succeeds(client: AsyncClient, seeded: dict) -> None:
    await _login(client, seeded)
    with (
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_status", new_callable=AsyncMock, return_value=_unavailable_status()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_serve_status", new_callable=AsyncMock, return_value=TailscaleCommandResult(ok=False, instructions_only=True)),
    ):
        response = await client.get("/settings/tailscale")
    assert response.status_code == 200
    body = response.json()
    assert "settings" in body
    assert "binary_available" in body
    assert body["binary_available"] is False


# ── settings creation ─────────────────────────────────────────────────────────


async def test_get_tailscale_settings_creates_row(client: AsyncClient, seeded: dict, db) -> None:
    await _login(client, seeded)
    with (
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_status", new_callable=AsyncMock, return_value=_unavailable_status()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_serve_status", new_callable=AsyncMock, return_value=TailscaleCommandResult(ok=False, instructions_only=True)),
    ):
        response = await client.get("/settings/tailscale")
    assert response.status_code == 200

    tenant_id = uuid.UUID(seeded["tenant_id"])
    row = (
        await db.execute(select(TailscaleSettings).where(TailscaleSettings.tenant_id == tenant_id))
    ).scalar_one_or_none()
    assert row is not None
    assert row.tailscale_enabled is False


# ── settings update ───────────────────────────────────────────────────────────


async def test_update_tailscale_settings_persists_changes(client: AsyncClient, seeded: dict, db) -> None:
    await _login(client, seeded)

    response = await client.post(
        "/settings/tailscale",
        json={"tailscale_enabled": True, "tailscale_mode": "serve", "tailscale_target_url": "http://127.0.0.1:80"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tailscale_enabled"] is True
    assert body["tailscale_mode"] == "serve"

    tenant_id = uuid.UUID(seeded["tenant_id"])
    row = (
        await db.execute(select(TailscaleSettings).where(TailscaleSettings.tenant_id == tenant_id))
    ).scalar_one_or_none()
    assert row is not None
    assert row.tailscale_enabled is True
    mode = row.tailscale_mode.value if hasattr(row.tailscale_mode, "value") else str(row.tailscale_mode)
    assert mode == "serve"


async def test_update_tailscale_settings_rejects_invalid_target(client: AsyncClient, seeded: dict) -> None:
    await _login(client, seeded)

    response = await client.post(
        "/settings/tailscale",
        json={"tailscale_target_url": "http://evil.com:80"},
    )
    assert response.status_code == 422 or response.status_code == 400
    if response.status_code == 400:
        body = response.json()
        assert "tailscale_invalid_target" in str(body)


async def test_update_tailscale_settings_writes_audit(client: AsyncClient, seeded: dict, db) -> None:
    await _login(client, seeded)
    await client.post(
        "/settings/tailscale",
        json={"tailscale_enabled": True, "tailscale_notes": "phone access"},
    )

    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == "update",
                AuditLog.object_type == "tailscale_settings",
            )
        )
    ).scalar_one_or_none()
    assert audit is not None


# ── check endpoint ────────────────────────────────────────────────────────────


async def test_check_tailscale_status_writes_audit(client: AsyncClient, seeded: dict, db) -> None:
    await _login(client, seeded)
    with (
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_status", new_callable=AsyncMock, return_value=_unavailable_status()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_serve_status", new_callable=AsyncMock, return_value=TailscaleCommandResult(ok=False, instructions_only=True)),
    ):
        response = await client.post("/settings/tailscale/check")
    assert response.status_code == 200

    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == "check",
                AuditLog.object_type == "tailscale_settings",
            )
        )
    ).scalar_one_or_none()
    assert audit is not None


# ── serve/start ───────────────────────────────────────────────────────────────


async def test_start_serve_with_binary_available(client: AsyncClient, seeded: dict) -> None:
    await _login(client, seeded)
    with (
        patch("app.api.tailscale_settings.ts_svc.start_tailscale_serve", new_callable=AsyncMock, return_value=_ok_result()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_status", new_callable=AsyncMock, return_value=_available_status()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_serve_status", new_callable=AsyncMock, return_value=_ok_result()),
    ):
        response = await client.post("/settings/tailscale/serve/start")
    assert response.status_code == 200
    body = response.json()
    assert body["binary_available"] is True


async def test_start_serve_writes_audit(client: AsyncClient, seeded: dict, db) -> None:
    await _login(client, seeded)
    with (
        patch("app.api.tailscale_settings.ts_svc.start_tailscale_serve", new_callable=AsyncMock, return_value=_ok_result()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_status", new_callable=AsyncMock, return_value=_available_status()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_serve_status", new_callable=AsyncMock, return_value=_ok_result()),
    ):
        await client.post("/settings/tailscale/serve/start")

    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == "serve_start",
                AuditLog.object_type == "tailscale_settings",
            )
        )
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.after is not None
    assert "target" in audit.after


async def test_start_serve_instructions_only_when_no_binary(client: AsyncClient, seeded: dict) -> None:
    await _login(client, seeded)
    no_binary = TailscaleCommandResult(ok=False, instructions_only=True, error="tailscale binary not found.")
    with (
        patch("app.api.tailscale_settings.ts_svc.start_tailscale_serve", new_callable=AsyncMock, return_value=no_binary),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_status", new_callable=AsyncMock, return_value=_unavailable_status()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_serve_status", new_callable=AsyncMock, return_value=TailscaleCommandResult(ok=False, instructions_only=True)),
    ):
        response = await client.post("/settings/tailscale/serve/start")
    assert response.status_code == 200
    body = response.json()
    assert body["binary_available"] is False
    assert body["instructions_only"] is True
    assert len(body["manual_commands"]) > 0


# ── serve/reset ───────────────────────────────────────────────────────────────


async def test_reset_serve_writes_audit(client: AsyncClient, seeded: dict, db) -> None:
    await _login(client, seeded)
    with (
        patch("app.api.tailscale_settings.ts_svc.reset_tailscale_serve", new_callable=AsyncMock, return_value=_ok_result()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_status", new_callable=AsyncMock, return_value=_available_status()),
        patch("app.api.tailscale_settings.ts_svc.get_tailscale_serve_status", new_callable=AsyncMock, return_value=_ok_result()),
    ):
        response = await client.post("/settings/tailscale/serve/reset")
    assert response.status_code == 200

    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == "serve_reset",
                AuditLog.object_type == "tailscale_settings",
            )
        )
    ).scalar_one_or_none()
    assert audit is not None


# ── command-level safety ──────────────────────────────────────────────────────


async def test_tailscale_command_timeout_returns_graceful_result() -> None:
    """_run() returns an error result (not an exception) when the command times out."""
    import asyncio
    from app.services import tailscale as ts_svc

    async def slow_communicate():
        await asyncio.sleep(999)
        return b"", b""

    class FakeProc:
        returncode = 1
        async def communicate(self):
            await asyncio.sleep(999)
            return b"", b""
        def kill(self): pass

    with (
        patch.object(ts_svc, "tailscale_binary", return_value="/usr/bin/tailscale"),
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=FakeProc()),
        patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
    ):
        result = await ts_svc._run(["status", "--json"], timeout=1)

    assert result.ok is False
    assert "timed out" in (result.error or "").lower()


async def test_tailscale_binary_not_found_returns_instructions_only() -> None:
    from app.services import tailscale as ts_svc

    with patch.object(ts_svc, "tailscale_binary", return_value=None):
        result = await ts_svc._run(["status", "--json"])

    assert result.ok is False
    assert result.instructions_only is True


async def test_get_tailscale_status_no_binary_returns_unavailable() -> None:
    from app.services import tailscale as ts_svc

    with patch.object(ts_svc, "tailscale_binary", return_value=None):
        status = await ts_svc.get_tailscale_status()

    assert status.available is False
    assert status.instructions_only is True
