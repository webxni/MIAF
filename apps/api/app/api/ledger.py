from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse

from app.api.deps import DB, CurrentUserDep, RequestCtx, require_reader
from app.models import Entity, EntityMember
from app.schemas.ledger import LedgerResponse, TrialBalanceResponse
from app.services.audit import write_audit
from app.services.ledger import general_ledger
from app.services.trial_balance import trial_balance

router = APIRouter(prefix="/entities/{entity_id}", tags=["reports"])


def _make_csv(headers: list[str], rows: list[list]) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment"},
    )


@router.get("/ledger", response_model=LedgerResponse)
async def general_ledger_endpoint(
    entity_id: uuid.UUID,
    account_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> LedgerResponse:
    result = await general_ledger(db, entity_id=entity_id, account_id=account_id, date_from=date_from, date_to=date_to)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="report_viewed", object_type="ledger", object_id=None, after={"account_id": str(account_id), "date_from": str(date_from), "date_to": str(date_to)}, ip=ctx.ip, user_agent=ctx.user_agent)
    return result


@router.get("/ledger/export.csv")
async def general_ledger_csv(
    entity_id: uuid.UUID,
    account_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> StreamingResponse:
    result = await general_ledger(db, entity_id=entity_id, account_id=account_id, date_from=date_from, date_to=date_to)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="export", object_type="ledger", object_id=None, after={"format": "csv", "account_id": str(account_id)}, ip=ctx.ip, user_agent=ctx.user_agent)
    headers = ["Date", "Entry ID", "Memo", "Reference", "Description", "Debit", "Credit", "Balance"]
    rows = [[str(ln.entry_date), str(ln.entry_id), ln.memo or "", ln.reference or "", ln.description or "", str(ln.debit), str(ln.credit), str(ln.running_balance)] for ln in result.lines]
    return _make_csv(headers, rows)


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def trial_balance_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> TrialBalanceResponse:
    result = await trial_balance(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="report_viewed", object_type="trial_balance", object_id=None, after={"as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    return result


@router.get("/trial-balance/export.csv")
async def trial_balance_csv(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> StreamingResponse:
    result = await trial_balance(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="export", object_type="trial_balance", object_id=None, after={"format": "csv", "as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    headers = ["Account Code", "Account Name", "Type", "Debit", "Credit"]
    rows = [[r.code, r.name, r.type.value, str(r.debit), str(r.credit)] for r in result.rows]
    rows.append(["", "TOTAL", "", str(result.total_debit), str(result.total_credit)])
    return _make_csv(headers, rows)
