from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.api.deps import CurrentUserDep, DB
from app.config import get_settings
from app.schemas.telegram import (
    TelegramInboundMessageIn,
    TelegramLinkCreate,
    TelegramLinkOut,
    TelegramMessageOut,
    TelegramWebhookResponse,
)
from app.services.telegram import create_or_update_link, list_links, list_messages, process_inbound_message

log = logging.getLogger("api.telegram")
router = APIRouter(prefix="/telegram", tags=["telegram"])


def _verify_webhook_secret(x_telegram_bot_api_secret_token: str | None) -> None:
    settings = get_settings()
    expected = settings.telegram_webhook_secret
    if expected is None:
        return  # No secret configured — allow (dev mode)
    if x_telegram_bot_api_secret_token is None:
        raise HTTPException(status_code=403, detail="Missing Telegram webhook secret token")
    if not hmac.compare_digest(expected, x_telegram_bot_api_secret_token):
        log.warning("Telegram webhook secret mismatch — request rejected")
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret token")


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
async def webhook_endpoint(
    payload: TelegramInboundMessageIn,
    db: DB,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> TelegramWebhookResponse:
    _verify_webhook_secret(x_telegram_bot_api_secret_token)
    return await process_inbound_message(db, payload=payload)
