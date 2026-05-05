from __future__ import annotations

import os
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.deps import CurrentUserDep, DB
from app.schemas.heartbeat import AlertOut, GeneratedReportOut, HeartbeatRunOut, HeartbeatRunRequest
from app.services.heartbeat import list_alerts, list_reports, list_runs, run_default_scheduled_heartbeats, run_heartbeat

router = APIRouter(prefix="/heartbeat", tags=["heartbeat"])
internal_router = APIRouter(prefix="/internal/heartbeat", tags=["internal-heartbeat"])


@router.post("/run", response_model=HeartbeatRunOut)
async def run_heartbeat_endpoint(
    payload: HeartbeatRunRequest,
    db: DB,
    me: CurrentUserDep,
) -> HeartbeatRunOut:
    result = await run_heartbeat(
        db,
        tenant_id=me.tenant_id,
        heartbeat_type=payload.heartbeat_type,
        as_of=payload.as_of or date.today(),
        trigger_source="manual",
        initiated_by_user_id=me.id,
    )
    return HeartbeatRunOut.model_validate(result.run)


@router.get("/runs", response_model=list[HeartbeatRunOut])
async def list_runs_endpoint(
    db: DB,
    me: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[HeartbeatRunOut]:
    return [HeartbeatRunOut.model_validate(item) for item in await list_runs(db, tenant_id=me.tenant_id, limit=limit)]


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts_endpoint(
    db: DB,
    me: CurrentUserDep,
    only_open: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AlertOut]:
    return [AlertOut.model_validate(item) for item in await list_alerts(db, tenant_id=me.tenant_id, only_open=only_open, limit=limit)]


@router.get("/reports", response_model=list[GeneratedReportOut])
async def list_reports_endpoint(
    db: DB,
    me: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[GeneratedReportOut]:
    return [GeneratedReportOut.model_validate(item) for item in await list_reports(db, tenant_id=me.tenant_id, limit=limit)]


@internal_router.post("/run-defaults", status_code=status.HTTP_202_ACCEPTED)
async def run_defaults_endpoint(
    db: DB,
    x_automation_token: Annotated[str | None, Header()] = None,
) -> dict:
    expected = os.getenv("AUTOMATION_TOKEN")
    if not expected or x_automation_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid automation token")
    runs = await run_default_scheduled_heartbeats(db, as_of=date.today())
    return {"runs_started": len(runs)}
