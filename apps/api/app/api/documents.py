from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import DB, CurrentUserDep, RequestCtx, require_reader, require_writer
from app.models import Entity, EntityMember
from app.schemas.ingestion import CandidateApprovalIn, CandidateApprovalOut, CsvImportOut, DownloadUrlOut, PendingDraftOut, ReceiptIngestionOut
from app.services.audit import write_audit
from app.services.ingestion import approve_candidate, get_attachment_scoped, import_csv_transactions, ingest_receipt, list_pending_source_drafts, signed_download_url

router = APIRouter(prefix="/entities/{entity_id}/documents", tags=["documents"])


@router.post("/receipts", response_model=ReceiptIngestionOut, status_code=status.HTTP_201_CREATED)
async def upload_receipt_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
    file: UploadFile = File(...),
) -> ReceiptIngestionOut:
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
