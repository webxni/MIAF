from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

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


DocumentInputType = Literal["text", "csv", "pdf", "image", "audio", "unsupported"]
DetectedDocumentType = Literal[
    "receipt",
    "invoice",
    "bill",
    "bank_transaction",
    "audio_note",
    "text_note",
    "statement",
    "unknown",
]
CandidateEntityType = Literal["personal", "business", "unknown"]
ConfidenceLevel = Literal["high", "medium", "low"]
ExtractionMethod = Literal[
    "local_csv",
    "local_pdf_text",
    "local_ocr",
    "local_text",
    "openai_vision",
    "openai_pdf",
    "openai_audio",
    "openai_text",
]


class ExtractedFinancialQuestion(BaseModel):
    code: str
    question: str
    status: str = "open"
    answer: str | None = None


class CandidateAccountOut(BaseModel):
    account_id: uuid.UUID | None = None
    code: str | None = None
    name: str | None = None
    reason: str | None = None


class ExtractedFinancialItem(BaseModel):
    source_id: str | None = None
    source_type: str
    detected_document_type: DetectedDocumentType
    date: str | None = None
    due_date: str | None = None
    amount: str | None = None
    subtotal: str | None = None
    tax_amount: str | None = None
    currency: str | None = None
    merchant: str | None = None
    vendor: str | None = None
    customer: str | None = None
    description: str | None = None
    line_items: list[dict] = Field(default_factory=list)
    payment_method: str | None = None
    invoice_number: str | None = None
    bill_number: str | None = None
    account_last4: str | None = None
    candidate_entity_type: CandidateEntityType = "unknown"
    candidate_accounts: list[CandidateAccountOut] = Field(default_factory=list)
    confidence: Decimal = Decimal("0.0000")
    confidence_level: ConfidenceLevel = "low"
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[ExtractedFinancialQuestion] = Field(default_factory=list)
    raw_text_reference: str | None = None
    file_id: str | None = None
    model_used: str | None = None
    extraction_method: ExtractionMethod = "local_csv"
    audit_id: str | None = None


class StoredDocumentOut(BaseModel):
    attachment: AttachmentOut
    extraction: DocumentExtractionOut | None = None
    candidate: ExtractionCandidateOut | None = None
    batch: ImportBatchOut | None = None
    extracted_items: list[ExtractedFinancialItem] = Field(default_factory=list)


class DocumentUploadOut(BaseModel):
    input_type: DocumentInputType
    stored_document: StoredDocumentOut | None = None
    csv_import: CsvImportOut | None = None
    warnings: list[str] = Field(default_factory=list)


class DocumentQuestionAnswerIn(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=1000)


class DocumentQuestionListOut(BaseModel):
    attachment_id: uuid.UUID
    questions: list[ExtractedFinancialQuestion]


class TextIngestionIn(BaseModel):
    entity_id: uuid.UUID
    text: str = Field(min_length=1, max_length=4000)


class TextIngestionOut(BaseModel):
    stored_document: StoredDocumentOut
