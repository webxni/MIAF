"""Tailscale private-access settings API.

Only authenticated owner/admin callers may read or modify these settings.
All mutations are audited. The serve/start and serve/reset actions run
tailscale commands on the host only when the binary is available; otherwise
they return manual_commands the operator should run themselves.

Tailscale Funnel (public internet exposure) is never started by this API.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DB, RequestCtx, require_tenant_admin_or_owner
from app.schemas.tailscale import (
    TailscaleLiveStatusOut,
    TailscaleSettingsOut,
    TailscaleSettingsUpdate,
)
from app.services import tailscale as ts_svc
from app.services import tailscale_settings as ts_db
from app.services.audit import write_audit

router = APIRouter(prefix="/settings/tailscale", tags=["tailscale"])

AdminOrOwner = Annotated[CurrentUser, Depends(require_tenant_admin_or_owner)]

_SETUP_INSTRUCTIONS = [
    "Step 1: Install Tailscale on the machine running MIAF — https://tailscale.com/download",
    "Step 2: Run: sudo tailscale up",
    "Step 3: Install Tailscale on your phone and sign in to the same tailnet.",
    "Step 4 (direct IP): Run: tailscale ip -4  →  open http://<tailscale-ip> on your phone.",
    "Step 5 (Serve – recommended): Run: sudo tailscale serve --bg http://127.0.0.1:80",
    "Step 6 (Serve): Run: tailscale serve status  →  open the shown https://*.ts.net URL on your phone.",
    "Note: Tailscale Serve keeps access inside your private tailnet only. It is NOT public internet access.",
]


def _to_out(row) -> TailscaleSettingsOut:
    return TailscaleSettingsOut.model_validate(row)


async def _build_live_status(db: DB, me: CurrentUser) -> TailscaleLiveStatusOut:
    settings_row = await ts_db.get_or_create(db, tenant_id=me.tenant_id)
    status = await ts_svc.get_tailscale_status()

    serve_result = await ts_svc.get_tailscale_serve_status()
    serve_text = serve_result.stdout if serve_result.ok else None

    if status.available:
        settings_row = await ts_db.record_status_check(
            db,
            tenant_id=me.tenant_id,
            status_text=status.raw or "",
            tailscale_ip=status.tailscale_ip,
            hostname=status.hostname,
            tailnet_url=status.tailnet_url,
        )

    private_url = settings_row.tailscale_tailnet_url or (
        f"http://{status.tailscale_ip}" if status.tailscale_ip else None
    )

    return TailscaleLiveStatusOut(
        settings=_to_out(settings_row),
        binary_available=status.available,
        tailscale_ip=status.tailscale_ip,
        hostname=status.hostname,
        serve_status=serve_text,
        private_url=private_url,
        warnings=status.warnings,
        instructions_only=status.instructions_only,
        manual_commands=ts_svc.manual_serve_instructions(settings_row.tailscale_target_url),
        setup_instructions=_SETUP_INSTRUCTIONS,
    )


@router.get("", response_model=TailscaleLiveStatusOut)
async def get_tailscale_settings(db: DB, me: AdminOrOwner) -> TailscaleLiveStatusOut:
    return await _build_live_status(db, me)


@router.post("", response_model=TailscaleSettingsOut)
async def update_tailscale_settings(
    payload: TailscaleSettingsUpdate,
    db: DB,
    me: AdminOrOwner,
    ctx: RequestCtx,
) -> TailscaleSettingsOut:
    # Validate target_url if provided.
    if payload.tailscale_target_url is not None:
        valid, err = ts_svc.validate_tailscale_target(payload.tailscale_target_url)
        if not valid:
            from app.errors import MIAFError
            raise MIAFError(err, code="tailscale_invalid_target")

    row = await ts_db.update(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        payload=payload,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return _to_out(row)


@router.post("/check", response_model=TailscaleLiveStatusOut)
async def check_tailscale_status(
    db: DB,
    me: AdminOrOwner,
    ctx: RequestCtx,
) -> TailscaleLiveStatusOut:
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="check",
        object_type="tailscale_settings",
        object_id=None,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return await _build_live_status(db, me)


@router.post("/serve/start", response_model=TailscaleLiveStatusOut)
async def start_serve(
    db: DB,
    me: AdminOrOwner,
    ctx: RequestCtx,
) -> TailscaleLiveStatusOut:
    settings_row = await ts_db.get_or_create(db, tenant_id=me.tenant_id)
    target = settings_row.tailscale_target_url or "http://127.0.0.1:80"

    result = await ts_svc.start_tailscale_serve(target)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="serve_start",
        object_type="tailscale_settings",
        object_id=settings_row.id,
        after={
            "target": target,
            "ok": result.ok,
            "instructions_only": result.instructions_only,
            "error": result.error,
        },
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return await _build_live_status(db, me)


@router.post("/serve/reset", response_model=TailscaleLiveStatusOut)
async def reset_serve(
    db: DB,
    me: AdminOrOwner,
    ctx: RequestCtx,
) -> TailscaleLiveStatusOut:
    settings_row = await ts_db.get_or_create(db, tenant_id=me.tenant_id)
    result = await ts_svc.reset_tailscale_serve()
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=None,
        action="serve_reset",
        object_type="tailscale_settings",
        object_id=settings_row.id,
        after={
            "ok": result.ok,
            "instructions_only": result.instructions_only,
            "error": result.error,
        },
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return await _build_live_status(db, me)
