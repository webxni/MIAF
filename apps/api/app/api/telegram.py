from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, DB
from app.schemas.telegram import (
    TelegramInboundMessageIn,
    TelegramLinkCreate,
    TelegramLinkOut,
    TelegramMessageOut,
    TelegramWebhookResponse,
)
from app.services.telegram import create_or_update_link, list_links, list_messages, process_inbound_message

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.get("/links", response_model=list[TelegramLinkOut])
async def list_links_endpoint(db: DB, me: CurrentUserDep) -> list[TelegramLinkOut]:
    return [TelegramLinkOut.model_validate(item) for item in await list_links(db, tenant_id=me.tenant_id)]


@router.post("/links", response_model=TelegramLinkOut, status_code=status.HTTP_201_CREATED)
async def create_link_endpoint(
    payload: TelegramLinkCreate,
    db: DB,
    me: CurrentUserDep,
) -> TelegramLinkOut:
    row = await create_or_update_link(db, tenant_id=me.tenant_id, user_id=me.id, payload=payload)
    return TelegramLinkOut.model_validate(row)


@router.get("/messages", response_model=list[TelegramMessageOut])
async def list_messages_endpoint(
    db: DB,
    me: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[TelegramMessageOut]:
    return [TelegramMessageOut.model_validate(item) for item in await list_messages(db, tenant_id=me.tenant_id, limit=limit)]


@router.post("/webhook", response_model=TelegramWebhookResponse)
async def webhook_endpoint(payload: TelegramInboundMessageIn, db: DB) -> TelegramWebhookResponse:
    return await process_inbound_message(db, payload=payload)
