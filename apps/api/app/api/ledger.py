from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DB, require_reader
from app.models import Entity, EntityMember
from app.schemas.ledger import LedgerResponse, TrialBalanceResponse
from app.services.ledger import general_ledger
from app.services.trial_balance import trial_balance

router = APIRouter(prefix="/entities/{entity_id}", tags=["reports"])


@router.get("/ledger", response_model=LedgerResponse)
async def general_ledger_endpoint(
    entity_id: uuid.UUID,
    account_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> LedgerResponse:
    return await general_ledger(
        db,
        entity_id=entity_id,
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def trial_balance_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> TrialBalanceResponse:
    return await trial_balance(db, entity_id=entity_id, as_of=as_of)
