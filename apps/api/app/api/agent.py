from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DB
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.agent import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])
service = AgentService()


@router.post("/chat", response_model=AgentChatResponse)
async def chat(
    payload: AgentChatRequest,
    db: DB,
    me: CurrentUserDep,
) -> AgentChatResponse:
    return await service.chat(db, me=me, payload=payload)
