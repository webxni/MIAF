from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import AuditLog, MemoryEvent, MemoryReviewStatus, MemoryType
from app.schemas.memory import MemoryCreate, MemoryReviewCreate
from app.services.memory import (
    create_memory,
    delete_memory,
    get_memory_scoped,
    list_memories,
    review_memory,
)

pytestmark = pytest.mark.asyncio


async def test_memory_create_requires_consent(seeded, db):
    with pytest.raises(Exception):
        await create_memory(
            db,
            tenant_id=uuid.UUID(seeded["tenant_id"]),
            user_id=uuid.UUID(seeded["user_id"]),
            payload=MemoryCreate(
                memory_type=MemoryType.personal_preference,
                title="Budgeting method",
                content="Use zero-based budgeting.",
                consent_granted=False,
            ),
        )


async def test_memory_add_and_search_financial_context(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])
    business_entity_id = uuid.UUID(seeded["business_entity_id"])

    await create_memory(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=MemoryCreate(
            memory_type=MemoryType.personal_preference,
            title="Preferred budget method",
            content="Use zero-based budgeting every month.",
            summary="Zero-based budgeting preference.",
            keywords=["budget", "zero-based"],
            consent_granted=True,
        ),
    )
    await create_memory(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=MemoryCreate(
            memory_type=MemoryType.tax_context,
            title="Business tax reserve",
            content="Keep a 25 percent tax reserve for the business.",
            summary="Tax reserve target is 25%.",
            keywords=["tax", "reserve"],
            entity_id=business_entity_id,
            consent_granted=True,
        ),
    )
    await create_memory(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=MemoryCreate(
            memory_type=MemoryType.recurring_pattern,
            title="Recurring vendor",
            content="Office Supply Co is a recurring vendor paid monthly.",
            summary="Recurring office supply vendor.",
            keywords=["vendor", "office"],
            entity_id=business_entity_id,
            consent_granted=True,
        ),
    )

    budget_matches = await list_memories(db, tenant_id=tenant_id, query="budget method")
    tax_matches = await list_memories(db, tenant_id=tenant_id, query="tax reserve")
    vendor_matches = await list_memories(db, tenant_id=tenant_id, query="recurring vendor")

    assert any(row.title == "Preferred budget method" for row in budget_matches)
    assert any("25 percent" in row.content for row in tax_matches)
    assert any("Office Supply Co" in row.content for row in vendor_matches)


async def test_memory_review_and_forget_flow(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])
    memory = await create_memory(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=MemoryCreate(
            memory_type=MemoryType.business_profile,
            title="Collections note",
            content="Customer collections should be reviewed every Friday.",
            consent_granted=True,
        ),
    )

    review = await review_memory(
        db,
        memory,
        payload=MemoryReviewCreate(status=MemoryReviewStatus.accepted, notes="Still valid."),
        reviewer_user_id=user_id,
    )
    assert review.status == MemoryReviewStatus.accepted

    await delete_memory(db, memory, user_id=user_id)
    assert memory.is_active is False

    scoped = await get_memory_scoped(db, tenant_id=tenant_id, memory_id=memory.id, accessed_by_id=user_id)
    assert scoped.id == memory.id

    events = (
        await db.execute(select(MemoryEvent).where(MemoryEvent.memory_id == memory.id))
    ).scalars().all()
    assert len(events) >= 3

    memory_audits = (
        await db.execute(select(AuditLog).where(AuditLog.object_type == "memory"))
    ).scalars().all()
    assert memory_audits == []
