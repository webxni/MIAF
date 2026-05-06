from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import CandidateStatus, ExtractionStatus, ImportBatchStatus
from app.schemas.journal import JournalLineOut


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID | None
    source_transaction_id: uuid.UUID | None
    journal_entry_id: uuid.UUID | None
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    uploaded_by_id: uuid.UUID | None


class ExtractedFieldOut(BaseModel):
    value: str | None
    confidence: Decimal


class DocumentExtractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    attachment_id: uuid.UUID
    source_transaction_id: uuid.UUID | None
    extraction_kind: str
    status: ExtractionStatus
    extracted_text: str | None
    extracted_data: dict | None
    confidence_score: Decimal | None
    duplicate_detected: bool
    reviewed_at: datetime | None
    reviewed_by_id: uuid.UUID | None


class ExtractionCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    document_extraction_id: uuid.UUID
    source_transaction_id: uuid.UUID | None
    suggested_account_id: uuid.UUID | None
    suggested_memo: str | None
    suggested_entry: dict | None
    confidence_score: Decimal | None
    status: CandidateStatus
    approved_entry_id: uuid.UUID | None
    rationale: str | None


class ReceiptIngestionOut(BaseModel):
    attachment: AttachmentOut
    extraction: DocumentExtractionOut
    candidate: ExtractionCandidateOut | None


class CandidateApprovalIn(BaseModel):
    account_id: uuid.UUID | None = None
    memo: str | None = Field(default=None, max_length=500)


class CandidateApprovalOut(BaseModel):
    candidate: ExtractionCandidateOut
    journal_entry_id: uuid.UUID


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    attachment_id: uuid.UUID | None
    kind: str
    status: ImportBatchStatus
    rows_total: int
    rows_imported: int
    rows_failed: int
    error_message: str | None
    created_by_id: uuid.UUID | None


class SourceTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    kind: str
    external_ref: str | None
    occurred_at: datetime | None
    amount: Decimal | None
    currency: str | None
    merchant: str | None
    raw: dict | None
    content_hash: str | None
    status: str


class CsvImportOut(BaseModel):
    batch: ImportBatchOut
    source_transactions: list[SourceTransactionOut]
    drafts_created: int = 0


class PendingDraftSourceOut(BaseModel):
    merchant: str | None
    memo: str | None
    amount: Decimal | None
    currency: str | None
    posted_at: datetime | None


class PendingDraftOut(BaseModel):
    id: uuid.UUID
    entry_date: date
    memo: str | None
    lines: list[JournalLineOut]
    source: PendingDraftSourceOut


class DownloadUrlOut(BaseModel):
    attachment_id: uuid.UUID
    url: str
