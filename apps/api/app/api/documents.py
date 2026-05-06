from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUserDep, RequestCtx, get_entity_for_user, require_reader, require_writer
from app.errors import ForbiddenError, RateLimitError
from app.models import AuditLog, Entity, EntityMember, Role
from app.models.base import utcnow
from app.schemas.ingestion import (
    CandidateApprovalIn,
    CandidateApprovalOut,
    CsvImportOut,
    DocumentQuestionAnswerIn,
    DocumentQuestionListOut,
    DocumentUploadOut,
    DownloadUrlOut,
    PendingDraftOut,
    ReceiptIngestionOut,
    StoredDocumentOut,
    TextIngestionIn,
    TextIngestionOut,
)
from app.services.audit import write_audit
from app.services.ingestion import (
    answer_document_question,
    approve_candidate,
    classify_document,
    create_draft_from_document,
    get_attachment_scoped,
    get_document_detail,
    import_csv_transactions,
    ingest_receipt,
    ingest_text_message,
    list_documents,
    list_document_questions,
    list_pending_source_drafts,
    reject_document,
    rerun_document_extraction,
    signed_download_url,
    transcribe_document_audio,
    upload_document,
)

router = APIRouter(prefix="/entities/{entity_id}/documents", tags=["documents"])
global_router = APIRouter(prefix="/documents", tags=["documents"])
ingest_router = APIRouter(prefix="/ingest", tags=["documents"])

_UPLOAD_RATE_WINDOW_SECONDS = 300  # 5-minute window
_UPLOAD_RATE_LIMIT = 20  # max uploads per window per user


async def _check_upload_rate_limit(db: DB, user_id: uuid.UUID) -> None:
    since = utcnow() - timedelta(seconds=_UPLOAD_RATE_WINDOW_SECONDS)
    recent = (
        await db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == user_id,
                AuditLog.action.in_(["upload", "import"]),
                AuditLog.object_type.in_(["receipt", "csv_batch", "document"]),
                AuditLog.created_at >= since,
            )
        )
    ).scalar_one()
    if recent >= _UPLOAD_RATE_LIMIT:
        raise RateLimitError(
            f"Too many uploads. Maximum {_UPLOAD_RATE_LIMIT} uploads per {_UPLOAD_RATE_WINDOW_SECONDS // 60} minutes.",
            code="upload_rate_limited",
            details={"window_seconds": _UPLOAD_RATE_WINDOW_SECONDS, "limit": _UPLOAD_RATE_LIMIT},
        )


async def _require_writer_for_entity(entity_id: uuid.UUID, db: DB, me: CurrentUserDep) -> tuple[Entity, EntityMember]:
    entity, membership = await get_entity_for_user(entity_id, db, me)
    if membership.role not in {Role.owner, Role.admin, Role.accountant, Role.agent}:
        raise ForbiddenError("Role cannot perform this action", code="role_forbidden")
    return entity, membership


@router.post("/receipts", response_model=ReceiptIngestionOut, status_code=status.HTTP_201_CREATED)
async def upload_receipt_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
    file: UploadFile = File(...),
) -> ReceiptIngestionOut:
    await _check_upload_rate_limit(db, me.id)
    data = await file.read()
    result = await ingest_receipt(
        db,
        tenant_id=me.tenant_id,
        entity_id=entity_id,
        user_id=me.id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="upload",
        object_type="receipt",
        object_id=result.attachment.id,
        after={"filename": result.attachment.filename, "sha256": result.attachment.sha256},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@router.post("/csv-imports", response_model=CsvImportOut, status_code=status.HTTP_201_CREATED)
async def upload_csv_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
    file: UploadFile = File(...),
) -> CsvImportOut:
    await _check_upload_rate_limit(db, me.id)
    data = await file.read()
    result = await import_csv_transactions(
        db,
        tenant_id=me.tenant_id,
        entity_id=entity_id,
        user_id=me.id,
        filename=file.filename or "import.csv",
        content_type=file.content_type or "text/csv",
        data=data,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="import",
        object_type="csv_batch",
        object_id=result.batch.id,
        after={"rows_total": result.batch.rows_total, "rows_imported": result.batch.rows_imported},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@router.post("/extraction-candidates/{candidate_id}/approve", response_model=CandidateApprovalOut)
async def approve_candidate_endpoint(
    entity_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: CandidateApprovalIn,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> CandidateApprovalOut:
    result = await approve_candidate(
        db,
        entity_id=entity_id,
        candidate_id=candidate_id,
        user_id=me.id,
        account_id=payload.account_id,
        memo=payload.memo,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="approve",
        object_type="extraction_candidate",
        object_id=candidate_id,
        after={"journal_entry_id": str(result.journal_entry_id)},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@router.get("/attachments/{attachment_id}/download-url", response_model=DownloadUrlOut)
async def attachment_download_url_endpoint(
    entity_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> DownloadUrlOut:
    attachment = await get_attachment_scoped(db, tenant_id=me.tenant_id, attachment_id=attachment_id)
    url = await signed_download_url(attachment)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="download_url",
        object_type="attachment",
        object_id=attachment_id,
        after={"filename": attachment.filename},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return DownloadUrlOut(attachment_id=attachment.id, url=url)


@router.get("/pending-drafts", response_model=list[PendingDraftOut])
async def pending_drafts_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> list[PendingDraftOut]:
    return await list_pending_source_drafts(db, entity_id=entity_id)


@global_router.post("/upload", response_model=DocumentUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_document_endpoint(
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    entity_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
) -> DocumentUploadOut:
    await _require_writer_for_entity(entity_id, db, me)
    data = await file.read()
    result = await upload_document(
        db,
        tenant_id=me.tenant_id,
        entity_id=entity_id,
        user_id=me.id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="upload",
        object_type="document",
        object_id=result.stored_document.attachment.id if result.stored_document else result.csv_import.batch.attachment_id if result.csv_import else None,
        after={"input_type": result.input_type, "warnings": result.warnings},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@global_router.get("", response_model=list[StoredDocumentOut])
async def list_documents_endpoint(
    db: DB,
    me: CurrentUserDep,
    entity_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[StoredDocumentOut]:
    if entity_id is not None:
        await get_entity_for_user(entity_id, db, me)
    return await list_documents(db, tenant_id=me.tenant_id, entity_id=entity_id, limit=limit)


@global_router.get("/{attachment_id}", response_model=StoredDocumentOut)
async def get_document_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
) -> StoredDocumentOut:
    return await get_document_detail(db, tenant_id=me.tenant_id, attachment_id=attachment_id)


@global_router.post("/{attachment_id}/extract", response_model=StoredDocumentOut)
async def extract_document_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> StoredDocumentOut:
    result = await rerun_document_extraction(db, tenant_id=me.tenant_id, attachment_id=attachment_id, user_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=result.attachment.entity_id,
        action="extract",
        object_type="document",
        object_id=attachment_id,
        after={"status": result.extraction.status.value if result.extraction else None},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@global_router.post("/{attachment_id}/classify", response_model=StoredDocumentOut)
async def classify_document_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> StoredDocumentOut:
    result = await classify_document(db, tenant_id=me.tenant_id, attachment_id=attachment_id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=result.attachment.entity_id,
        action="classify",
        object_type="document",
        object_id=attachment_id,
        after={"candidate_id": str(result.candidate.id) if result.candidate else None},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@global_router.post("/{attachment_id}/create-draft", response_model=CandidateApprovalOut)
async def create_draft_document_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> CandidateApprovalOut:
    result = await create_draft_from_document(db, tenant_id=me.tenant_id, attachment_id=attachment_id, user_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=result.candidate.entity_id,
        action="create_draft",
        object_type="document",
        object_id=attachment_id,
        after={"journal_entry_id": str(result.journal_entry_id)},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@global_router.post("/{attachment_id}/approve", response_model=CandidateApprovalOut)
async def approve_document_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> CandidateApprovalOut:
    result = await create_draft_from_document(db, tenant_id=me.tenant_id, attachment_id=attachment_id, user_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=result.candidate.entity_id,
        action="approve",
        object_type="document",
        object_id=attachment_id,
        after={"journal_entry_id": str(result.journal_entry_id)},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@global_router.post("/{attachment_id}/reject", response_model=StoredDocumentOut)
async def reject_document_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> StoredDocumentOut:
    result = await reject_document(db, tenant_id=me.tenant_id, attachment_id=attachment_id, user_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=result.attachment.entity_id,
        action="reject",
        object_type="document",
        object_id=attachment_id,
        after={"status": result.extraction.status.value if result.extraction else None},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@global_router.get("/{attachment_id}/questions", response_model=DocumentQuestionListOut)
async def list_document_questions_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
) -> DocumentQuestionListOut:
    return await list_document_questions(db, tenant_id=me.tenant_id, attachment_id=attachment_id)


@global_router.post("/{attachment_id}/questions", response_model=DocumentQuestionListOut)
async def list_document_questions_post_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
) -> DocumentQuestionListOut:
    return await list_document_questions(db, tenant_id=me.tenant_id, attachment_id=attachment_id)


@global_router.post("/{attachment_id}/answer-question", response_model=StoredDocumentOut)
async def answer_document_question_endpoint(
    attachment_id: uuid.UUID,
    payload: DocumentQuestionAnswerIn,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> StoredDocumentOut:
    result = await answer_document_question(
        db,
        tenant_id=me.tenant_id,
        attachment_id=attachment_id,
        code=payload.code,
        answer=payload.answer,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=result.attachment.entity_id,
        action="answer_question",
        object_type="document",
        object_id=attachment_id,
        after={"code": payload.code},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@global_router.post("/{attachment_id}/transcribe", response_model=StoredDocumentOut)
async def transcribe_document_endpoint(
    attachment_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> StoredDocumentOut:
    result = await transcribe_document_audio(db, tenant_id=me.tenant_id, attachment_id=attachment_id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=result.attachment.entity_id,
        action="transcribe",
        object_type="document",
        object_id=attachment_id,
        after={"status": result.extraction.status.value if result.extraction else None},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result


@ingest_router.post("/text", response_model=TextIngestionOut, status_code=status.HTTP_201_CREATED)
async def ingest_text_endpoint(
    payload: TextIngestionIn,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> TextIngestionOut:
    await _require_writer_for_entity(payload.entity_id, db, me)
    result = await ingest_text_message(
        db,
        tenant_id=me.tenant_id,
        entity_id=payload.entity_id,
        user_id=me.id,
        text=payload.text,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=payload.entity_id,
        action="ingest_text",
        object_type="document",
        object_id=result.stored_document.attachment.id,
        after={"filename": result.stored_document.attachment.filename},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return result
