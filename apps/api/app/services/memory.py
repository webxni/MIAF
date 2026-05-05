from __future__ import annotations

import math
import re
import uuid
from collections import Counter

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FinClawError, NotFoundError
from app.models import Memory, MemoryEmbedding, MemoryEvent, MemoryEventType, MemoryReview, MemoryType
from app.models.base import utcnow
from app.schemas.memory import MemoryCreate, MemoryReviewCreate, MemoryUpdate

_SENSITIVE_PATTERNS = [
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\bapi[_ -]?key\b", re.IGNORECASE),
    re.compile(r"\bbank\b.{0,20}\bpassword\b", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
]


def _redact_sensitive_text(text: str) -> str:
    redacted = text
    for pattern in _SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _embedding_for_text(text: str) -> list[float]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    counts = Counter(tokens)
    top = counts.most_common(8)
    total = sum(count for _, count in top) or 1
    return [round(count / total, 6) for _, count in top]


async def _log_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    memory_id: uuid.UUID,
    user_id: uuid.UUID | None,
    event_type: MemoryEventType,
    payload: dict | None = None,
) -> MemoryEvent:
    row = MemoryEvent(
        tenant_id=tenant_id,
        memory_id=memory_id,
        user_id=user_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(row)
    await db.flush()
    return row


async def create_memory(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MemoryCreate,
) -> Memory:
    if not payload.consent_granted:
        raise FinClawError(
            "Memory writes require explicit consent",
            code="memory_consent_required",
        )

    if any(pattern.search(payload.content) for pattern in _SENSITIVE_PATTERNS):
        raise FinClawError(
            "Sensitive credentials must not be stored in memory",
            code="memory_sensitive_content_blocked",
        )

    memory = Memory(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=payload.entity_id,
        memory_type=payload.memory_type,
        title=payload.title,
        content=payload.content,
        summary=payload.summary,
        keywords=payload.keywords,
        source=payload.source,
        consent_granted=payload.consent_granted,
    )
    db.add(memory)
    await db.flush()

    redacted_text = _redact_sensitive_text(" ".join(part for part in [payload.title, payload.summary, payload.content] if part))
    db.add(
        MemoryEmbedding(
            tenant_id=tenant_id,
            memory_id=memory.id,
            embedding_model="deterministic-v1",
            embedding=_embedding_for_text(redacted_text),
            redacted_text=redacted_text,
        )
    )
    await _log_event(
        db,
        tenant_id=tenant_id,
        memory_id=memory.id,
        user_id=user_id,
        event_type=MemoryEventType.created,
        payload={"memory_type": payload.memory_type.value, "title": payload.title},
    )
    await db.flush()
    return memory


async def list_memories(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    query: str | None = None,
    memory_type: MemoryType | None = None,
    limit: int = 20,
) -> list[Memory]:
    stmt = select(Memory).where(Memory.tenant_id == tenant_id, Memory.is_active.is_(True))
    if memory_type is not None:
        stmt = stmt.where(Memory.memory_type == memory_type)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            or_(
                Memory.title.ilike(like),
                Memory.content.ilike(like),
                Memory.summary.ilike(like),
            )
        )
    stmt = stmt.order_by(Memory.updated_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def get_memory_scoped(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    memory_id: uuid.UUID,
    accessed_by_id: uuid.UUID | None = None,
) -> Memory:
    row = await db.get(Memory, memory_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError(f"Memory {memory_id} not found", code="memory_not_found")
    row.last_accessed_at = utcnow()
    await _log_event(
        db,
        tenant_id=tenant_id,
        memory_id=row.id,
        user_id=accessed_by_id,
        event_type=MemoryEventType.accessed,
    )
    await db.flush()
    return row


async def update_memory(
    db: AsyncSession,
    memory: Memory,
    *,
    payload: MemoryUpdate,
    user_id: uuid.UUID,
) -> Memory:
    if payload.title is not None:
        memory.title = payload.title
    if payload.content is not None:
        if any(pattern.search(payload.content) for pattern in _SENSITIVE_PATTERNS):
            raise FinClawError(
                "Sensitive credentials must not be stored in memory",
                code="memory_sensitive_content_blocked",
            )
        memory.content = payload.content
    if payload.summary is not None:
        memory.summary = payload.summary
    if payload.keywords is not None:
        memory.keywords = payload.keywords
    if payload.is_active is not None:
        memory.is_active = payload.is_active

    embedding = (
        await db.execute(select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory.id))
    ).scalar_one_or_none()
    redacted_text = _redact_sensitive_text(
        " ".join(part for part in [memory.title, memory.summary, memory.content] if part)
    )
    if embedding is not None:
        embedding.redacted_text = redacted_text
        embedding.embedding = _embedding_for_text(redacted_text)
    await _log_event(
        db,
        tenant_id=memory.tenant_id,
        memory_id=memory.id,
        user_id=user_id,
        event_type=MemoryEventType.updated,
    )
    await db.flush()
    return memory


async def delete_memory(
    db: AsyncSession,
    memory: Memory,
    *,
    user_id: uuid.UUID,
) -> None:
    memory.is_active = False
    memory.expires_at = utcnow()
    await _log_event(
        db,
        tenant_id=memory.tenant_id,
        memory_id=memory.id,
        user_id=user_id,
        event_type=MemoryEventType.deleted,
    )
    await db.flush()


async def expire_memory(
    db: AsyncSession,
    memory: Memory,
    *,
    user_id: uuid.UUID,
) -> Memory:
    memory.expires_at = utcnow()
    memory.is_active = False
    await _log_event(
        db,
        tenant_id=memory.tenant_id,
        memory_id=memory.id,
        user_id=user_id,
        event_type=MemoryEventType.expired,
    )
    await db.flush()
    return memory


async def review_memory(
    db: AsyncSession,
    memory: Memory,
    *,
    payload: MemoryReviewCreate,
    reviewer_user_id: uuid.UUID,
) -> MemoryReview:
    review = MemoryReview(
        tenant_id=memory.tenant_id,
        memory_id=memory.id,
        reviewer_user_id=reviewer_user_id,
        status=payload.status,
        notes=payload.notes,
        reviewed_at=utcnow(),
    )
    db.add(review)
    await db.flush()
    await _log_event(
        db,
        tenant_id=memory.tenant_id,
        memory_id=memory.id,
        user_id=reviewer_user_id,
        event_type=MemoryEventType.reviewed,
        payload={"status": payload.status.value},
    )
    return review


async def promote_observation_to_memory(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    content: str,
    memory_type: MemoryType,
    entity_id: uuid.UUID | None = None,
) -> Memory:
    memory = await create_memory(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=MemoryCreate(
            memory_type=memory_type,
            title=title,
            content=content,
            summary=content[:200],
            entity_id=entity_id,
            consent_granted=True,
            source="agent",
        ),
    )
    await _log_event(
        db,
        tenant_id=tenant_id,
        memory_id=memory.id,
        user_id=user_id,
        event_type=MemoryEventType.promoted,
    )
    return memory
