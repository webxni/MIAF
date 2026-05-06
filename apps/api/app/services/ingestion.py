from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import MIAFError, NotFoundError
from app.models import (
    Account,
    AccountType,
    Attachment,
    CandidateStatus,
    DocumentExtraction,
    ExtractionCandidate,
    ExtractionStatus,
    ImportBatch,
    ImportBatchStatus,
    JournalEntry,
    JournalEntryStatus,
    SourceTransaction,
    SourceTransactionStatus,
)
from app.models.base import utcnow
from app.money import ZERO, to_money
from app.schemas.ingestion import (
    CandidateApprovalOut,
    CandidateAccountOut,
    CsvImportOut,
    DocumentQuestionListOut,
    DocumentUploadOut,
    ExtractedFinancialItem,
    ExtractedFinancialQuestion,
    PendingDraftOut,
    PendingDraftSourceOut,
    ReceiptIngestionOut,
    StoredDocumentOut,
    TextIngestionOut,
)
from app.schemas.journal import JournalEntryCreate, JournalLineIn
from app.config import get_settings
from app.services.audit import write_audit
from app.services.classifier import build_memory_lookup, classify_source_transaction
from app.services.journal import create_draft
from app.services import ocr
from app.skills.accounting.workflows.questions import generate_accounting_question
from app.storage import ensure_bucket, minio_client

MAX_FILE_BYTES = 10 * 1024 * 1024
TEXT_CONTENT_TYPES = {"text/plain", "application/octet-stream"}
CSV_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}
PDF_CONTENT_TYPES = {"application/pdf"}
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
AUDIO_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "application/ogg",
}
ALLOWED_UPLOAD_TYPES = TEXT_CONTENT_TYPES | CSV_CONTENT_TYPES | PDF_CONTENT_TYPES | IMAGE_CONTENT_TYPES | AUDIO_CONTENT_TYPES
ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt",
    ".csv",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".mp3",
    ".m4a",
    ".wav",
    ".ogg",
}
SUPPORTED_TEXT_NOTES = {"text", "txt"}
HIGH_CONFIDENCE = Decimal("0.8000")
MEDIUM_CONFIDENCE = Decimal("0.5500")
QUESTION_BLOCKING_CODES = {
    "personal_business_ambiguous",
    "owner_draw_possible",
    "asset_vs_expense",
    "payable_status_unknown",
    "missing_amount",
    "missing_date",
}


@dataclass(frozen=True)
class DetectedUpload:
    input_type: str
    file_extension: str
    content_type: str
    warnings: list[str]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def detect_upload_type(filename: str, content_type: str, size_bytes: int) -> DetectedUpload:
    extension = _file_extension(filename)
    normalized_type = (content_type or "application/octet-stream").lower()
    warnings: list[str] = []

    if size_bytes > MAX_FILE_BYTES:
        raise MIAFError("File exceeds max upload size", code="file_too_large")

    if extension == ".csv" or normalized_type in CSV_CONTENT_TYPES:
        return DetectedUpload("csv", extension, normalized_type, warnings)
    if extension == ".pdf" or normalized_type in PDF_CONTENT_TYPES:
        return DetectedUpload("pdf", extension, normalized_type, warnings)
    if extension in {".png", ".jpg", ".jpeg", ".webp"} or normalized_type in IMAGE_CONTENT_TYPES:
        return DetectedUpload("image", extension, normalized_type, warnings)
    if extension in {".mp3", ".m4a", ".wav", ".ogg"} or normalized_type in AUDIO_CONTENT_TYPES:
        return DetectedUpload("audio", extension, normalized_type, warnings)
    if extension in {".txt", ""} or normalized_type in TEXT_CONTENT_TYPES:
        return DetectedUpload("text", extension, normalized_type, warnings)
    if extension and extension not in ALLOWED_UPLOAD_EXTENSIONS:
        warnings.append(f"Unsupported extension: {extension}")
    if normalized_type and normalized_type not in ALLOWED_UPLOAD_TYPES:
        warnings.append(f"Unsupported content type: {normalized_type}")
    return DetectedUpload("unsupported", extension, normalized_type, warnings)


def _printable_pdf_text(data: bytes) -> str:
    decoded = data.decode("latin-1", errors="ignore")
    chunks = re.findall(r"[A-Za-z0-9][A-Za-z0-9 \t,:;./$%()#&'\"-]{5,}", decoded)
    cleaned_chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    text = "\n".join(cleaned_chunks)
    meaningful = text.lower()
    if len(text) < 20 and not any(token in meaningful for token in ("total", "invoice", "bill", "vendor", "merchant")):
        return ""
    return _sanitize_extracted_text(text)


def _normalize_text_note(data: bytes) -> str:
    return _sanitize_extracted_text(data.decode("utf-8", errors="ignore"))


def _detect_document_type(text: str, *, source_type: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ("invoice", "factura", "inv #", "invoice #")):
        return "invoice"
    if any(token in lower for token in ("bill due", "vendor bill", "statement due")):
        return "bill"
    if any(token in lower for token in ("receipt", "merchant", "total", "subtotal", "tax")):
        return "receipt"
    if any(token in lower for token in ("deposit", "withdrawal", "bank", "debit", "credit")):
        return "bank_transaction"
    if source_type == "audio":
        return "audio_note"
    if source_type == "text":
        return "text_note"
    return "unknown"


def _detect_candidate_entity_type(text: str) -> tuple[str, list[str]]:
    lower = text.lower()
    personal = any(token in lower for token in ("personal", "mi casa", "my home", "lunch", "gasolina personal"))
    business = any(
        token in lower
        for token in ("business", "negocio", "client", "cliente", "vendor", "invoice", "bill", "consulting")
    )
    if personal and business:
        return "unknown", ["personal_business_ambiguous"]
    if business:
        return "business", []
    if personal:
        return "personal", []
    return "unknown", ["personal_business_ambiguous"]


def _detect_payment_method(text: str) -> str | None:
    lower = text.lower()
    if "personal card" in lower:
        return "personal_card"
    if "business card" in lower:
        return "business_card"
    if "cash" in lower:
        return "cash"
    if "bank transfer" in lower or "transfer" in lower:
        return "bank_transfer"
    if "credit card" in lower:
        return "credit_card"
    return None


def _extract_named_party(text: str, keywords: tuple[str, ...]) -> str | None:
    for keyword in keywords:
        match = re.search(rf"{keyword}\s+([A-Z0-9][A-Za-z0-9 .,&'-]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".")
    return None


def _parse_amount_from_text(text: str) -> Decimal | None:
    match = re.search(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)
    if not match:
        return None
    return Decimal(match.group(1).replace(",", ""))


def _format_question(code: str, item: ExtractedFinancialItem) -> ExtractedFinancialQuestion:
    description = item.description or item.merchant or item.vendor or item.customer or "this item"
    amount = item.amount or "unknown amount"
    record = {"id": item.source_id, "amount": amount, "description": description, "merchant": item.merchant}
    if code in {"personal_business_ambiguous", "owner_draw_possible", "asset_vs_expense"}:
        generated = generate_accounting_question(record, [code])
        return ExtractedFinancialQuestion(code=code, question=generated["question"], status=generated["status"])
    if code == "payable_status_unknown":
        return ExtractedFinancialQuestion(
            code=code,
            question="Was this bill already paid, or should I record it as accounts payable?",
        )
    if code == "missing_amount":
        return ExtractedFinancialQuestion(code=code, question="What is the amount for this item?")
    if code == "missing_date":
        return ExtractedFinancialQuestion(code=code, question="What date should I use for this item?")
    return ExtractedFinancialQuestion(code=code, question=f"Please clarify how to handle {description}.")


def _confidence_level(confidence: Decimal) -> str:
    if confidence >= HIGH_CONFIDENCE:
        return "high"
    if confidence >= MEDIUM_CONFIDENCE:
        return "medium"
    return "low"


def _calculate_confidence(
    *,
    amount: Decimal | None,
    occurred_at: datetime | None,
    candidate_entity_type: str,
    document_type: str,
    merchant: str | None,
    vendor: str | None,
    customer: str | None,
    reason_codes: list[str],
) -> Decimal:
    score = Decimal("0.00")
    if amount is not None:
        score += Decimal("0.35")
    if occurred_at is not None:
        score += Decimal("0.20")
    if candidate_entity_type != "unknown":
        score += Decimal("0.15")
    if any(value for value in (merchant, vendor, customer)):
        score += Decimal("0.15")
    if document_type != "unknown":
        score += Decimal("0.10")
    if not reason_codes:
        score += Decimal("0.05")
    if any(code in QUESTION_BLOCKING_CODES for code in reason_codes):
        score -= Decimal("0.20")
    return _clamp_decimal(score).quantize(Decimal("0.0001"))


def _build_extracted_item(
    *,
    source_id: str | None,
    source_type: str,
    text: str,
    file_id: str | None,
    merchant: str | None,
    vendor: str | None,
    customer: str | None,
    occurred_at: datetime | None,
    amount: Decimal | None,
    currency: str | None,
    payment_method: str | None,
    candidate_entity_type: str,
    reason_codes: list[str],
) -> ExtractedFinancialItem:
    document_type = _detect_document_type(text, source_type=source_type)
    missing_fields: list[str] = []
    if amount is None:
        missing_fields.append("amount")
        reason_codes = [*reason_codes, "missing_amount"]
    if occurred_at is None:
        missing_fields.append("date")
        reason_codes = [*reason_codes, "missing_date"]

    if any(token in text.lower() for token in ("owner draw", "reimbursement", "loan from owner", "owner contribution")):
        reason_codes = [*reason_codes, "owner_draw_possible"]
    if any(token in text.lower() for token in ("amazon", "equipment", "laptop", "computer", "desk", "monitor")):
        reason_codes = [*reason_codes, "asset_vs_expense"]
    if document_type == "bill" and not any(token in text.lower() for token in ("paid", "pagado", "payment", "cash")):
        reason_codes = [*reason_codes, "payable_status_unknown"]

    # preserve order while de-duplicating
    deduped_reason_codes = list(dict.fromkeys(reason_codes))
    confidence = _calculate_confidence(
        amount=amount,
        occurred_at=occurred_at,
        candidate_entity_type=candidate_entity_type,
        document_type=document_type,
        merchant=merchant,
        vendor=vendor,
        customer=customer,
        reason_codes=deduped_reason_codes,
    )
    item = ExtractedFinancialItem(
        source_id=source_id,
        source_type=source_type,
        detected_document_type=document_type,  # type: ignore[arg-type]
        date=occurred_at.date().isoformat() if occurred_at else None,
        amount=str(to_money(amount)) if amount is not None else None,
        currency=currency,
        merchant=merchant,
        vendor=vendor,
        customer=customer,
        description=_sanitize_extracted_text(text)[:500] or None,
        tax_amount=None,
        payment_method=payment_method,
        candidate_entity_type=candidate_entity_type,  # type: ignore[arg-type]
        confidence=confidence,
        confidence_level=_confidence_level(confidence),  # type: ignore[arg-type]
        missing_fields=missing_fields,
        raw_text_reference=_sanitize_extracted_text(text)[:500] or None,
        file_id=file_id,
    )
    item.questions = [_format_question(code, item) for code in dict.fromkeys(deduped_reason_codes)]
    return item


def extract_financial_items_from_text(
    *,
    text: str,
    source_type: str,
    file_id: str | None = None,
    source_id: str | None = None,
    suppress_entity_questions: bool = False,
) -> list[ExtractedFinancialItem]:
    occurred_at = _parse_datetime(next(iter(re.findall(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}", text)), None))
    amount = _parse_amount_from_text(text)
    merchant = None
    vendor = _extract_named_party(text, ("vendor", "proveedor", "from"))
    customer = _extract_named_party(text, ("client", "cliente", "customer", "to"))
    if vendor is None and customer is None:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        merchant = first_line[:255] or None
    entity_type, reason_codes = _detect_candidate_entity_type(text)
    if suppress_entity_questions:
        reason_codes = [code for code in reason_codes if code != "personal_business_ambiguous"]
    item = _build_extracted_item(
        source_id=source_id,
        source_type=source_type,
        text=text,
        file_id=file_id,
        merchant=merchant,
        vendor=vendor,
        customer=customer,
        occurred_at=occurred_at,
        amount=amount,
        currency="USD" if amount is not None else None,
        payment_method=_detect_payment_method(text),
        candidate_entity_type=entity_type,
        reason_codes=reason_codes,
    )
    return [item]


def _candidate_account_for_item(item: ExtractedFinancialItem, accounts: list[Account]) -> tuple[Account | None, str | None]:
    source_tx = SourceTransaction(
        entity_id=uuid.uuid4(),
        kind="api",
        amount=to_money(item.amount) if item.amount else None,
        currency=item.currency,
        merchant=item.merchant or item.vendor or item.customer,
        raw={"description": item.description},
        content_hash=None,
        status=SourceTransactionStatus.pending,
    )
    active_accounts = [account for account in accounts if account.is_active]
    if not active_accounts:
        return None, None
    account, reason = classify_source_transaction(source_tx, active_accounts, memory_lookup=None)
    return account, reason


async def _put_object(client: Minio, bucket: str, key: str, data: bytes, content_type: str) -> None:
    stream = io.BytesIO(data)
    await asyncio.to_thread(
        client.put_object,
        bucket,
        key,
        stream,
        len(data),
        content_type=content_type,
    )


async def _presigned_get_url(client: Minio, bucket: str, key: str) -> str:
    return await asyncio.to_thread(client.presigned_get_object, bucket, key)


async def _get_object_bytes(client: Minio, bucket: str, key: str) -> bytes:
    def _read() -> bytes:
        response = client.get_object(bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    return await asyncio.to_thread(_read)


def _detect_duplicate(existing_attachment: Attachment | None, merchant: str | None, amount: Decimal | None, occurred_at: datetime | None) -> bool:
    return existing_attachment is not None and (merchant is not None or amount is not None or occurred_at is not None)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _sanitize_extracted_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    cleaned = "".join(char for char in cleaned if char in {"\n", "\t"} or ord(char) >= 32)
    return cleaned[:100_000]


def _clamp_decimal(value: Decimal, *, lower: Decimal = Decimal("0.00"), upper: Decimal = Decimal("1.00")) -> Decimal:
    return min(max(value, lower), upper)


def _empty_receipt_fields() -> dict:
    return {
        "merchant": {"value": None, "confidence": "0.0000"},
        "date": {"value": None, "confidence": "0.0000"},
        "total": {"value": None, "confidence": "0.0000"},
    }


def _apply_ocr_confidence(extracted_data: dict, ocr_confidence: float) -> tuple[dict, Decimal]:
    scale = _clamp_decimal(Decimal(str(ocr_confidence)) / Decimal("100"))
    adjusted: dict[str, dict[str, str | None]] = {}
    total_confidence = Decimal("0.00")

    for field_name in ("merchant", "date", "total"):
        raw_field = extracted_data[field_name]
        field_confidence = _clamp_decimal(Decimal(str(raw_field["confidence"])) * scale).quantize(Decimal("0.0001"))
        adjusted[field_name] = {
            "value": raw_field["value"],
            "confidence": str(field_confidence),
        }
        total_confidence += field_confidence

    return adjusted, (total_confidence / Decimal("3")).quantize(Decimal("0.0001"))


def extract_receipt_fields(text: str) -> tuple[dict, Decimal]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merchant = lines[0] if lines else None
    merchant_conf = Decimal("0.95") if merchant else Decimal("0.00")

    date_match = re.search(r"(?P<date>\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", text)
    date_value = date_match.group("date") if date_match else None
    date_conf = Decimal("0.90") if date_value else Decimal("0.00")

    total_match = re.search(r"(?im)total[^0-9]*(?P<amount>\d+(?:\.\d{2})?)", text)
    if not total_match:
        amount_matches = re.findall(r"(?<!\d)(\d+(?:\.\d{2}))", text)
        total_value = amount_matches[-1] if amount_matches else None
        total_conf = Decimal("0.55") if total_value else Decimal("0.00")
    else:
        total_value = total_match.group("amount")
        total_conf = Decimal("0.92")

    confidence = (merchant_conf + date_conf + total_conf) / Decimal("3")
    data = {
        "merchant": {"value": merchant, "confidence": str(merchant_conf)},
        "date": {"value": date_value, "confidence": str(date_conf)},
        "total": {"value": total_value, "confidence": str(total_conf)},
    }
    return data, confidence.quantize(Decimal("0.0001"))


async def _default_expense_account(db: AsyncSession, entity_id: uuid.UUID, merchant: str | None) -> Account:
    rows = (
        await db.execute(
            select(Account).where(Account.entity_id == entity_id, Account.type == AccountType.expense).order_by(Account.code)
        )
    ).scalars().all()
    if not rows:
        raise NotFoundError("No expense account found for entity", code="account_not_found")
    merchant_lower = (merchant or "").lower()
    for account in rows:
        if "food" in account.name.lower() and any(token in merchant_lower for token in ("cafe", "coffee", "restaurant", "pizza", "burger")):
            return account
    for account in rows:
        if account.code == "5200":
            return account
    return rows[0]


def _csv_memo(raw: dict | None) -> str | None:
    raw = raw or {}
    return raw.get("memo") or raw.get("description")


def _outflow_amount(amount: Decimal | None) -> Decimal | None:
    if amount is None or amount >= ZERO:
        return None
    return to_money(abs(amount))


async def _cash_account(db: AsyncSession, entity_id: uuid.UUID) -> Account:
    account = (
        await db.execute(select(Account).where(Account.entity_id == entity_id, Account.code == "1110"))
    ).scalar_one_or_none()
    if account is None:
        raise NotFoundError("Cash account 1110 not found", code="account_not_found")
    return account


async def store_attachment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID | None,
    filename: str,
    content_type: str,
    data: bytes,
    source_transaction_id: uuid.UUID | None = None,
    journal_entry_id: uuid.UUID | None = None,
) -> Attachment:
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise MIAFError("Unsupported file type", code="unsupported_file_type")
    if len(data) > MAX_FILE_BYTES:
        raise MIAFError("File exceeds max upload size", code="file_too_large")

    settings = get_settings()
    await asyncio.to_thread(ensure_bucket, minio_client, settings.minio_bucket)
    digest = _sha256(data)
    storage_key = f"{tenant_id}/{entity_id}/{digest}/{filename}"
    await _put_object(minio_client, settings.minio_bucket, storage_key, data, content_type)

    attachment = Attachment(
        tenant_id=tenant_id,
        entity_id=entity_id,
        source_transaction_id=source_transaction_id,
        journal_entry_id=journal_entry_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        sha256=digest,
        storage_key=storage_key,
        uploaded_by_id=user_id,
    )
    db.add(attachment)
    await db.flush()
    return attachment


async def signed_download_url(attachment: Attachment) -> str:
    settings = get_settings()
    return await _presigned_get_url(minio_client, settings.minio_bucket, attachment.storage_key)


async def _extraction_for_attachment(db: AsyncSession, attachment_id: uuid.UUID) -> DocumentExtraction | None:
    return (
        await db.execute(
            select(DocumentExtraction).where(DocumentExtraction.attachment_id == attachment_id)
        )
    ).scalar_one_or_none()


async def _candidate_for_extraction(db: AsyncSession, extraction_id: uuid.UUID) -> ExtractionCandidate | None:
    return (
        await db.execute(
            select(ExtractionCandidate).where(ExtractionCandidate.document_extraction_id == extraction_id)
        )
    ).scalar_one_or_none()


async def _batch_for_attachment(db: AsyncSession, attachment_id: uuid.UUID) -> ImportBatch | None:
    return (
        await db.execute(
            select(ImportBatch).where(ImportBatch.attachment_id == attachment_id)
        )
    ).scalar_one_or_none()


def _items_from_extraction(extraction: DocumentExtraction | None) -> list[ExtractedFinancialItem]:
    if extraction is None:
        return []
    raw_items = (extraction.extracted_data or {}).get("items") if isinstance(extraction.extracted_data, dict) else None
    if not raw_items:
        return []
    return [ExtractedFinancialItem.model_validate(item) for item in raw_items]


async def build_stored_document_out(db: AsyncSession, attachment: Attachment) -> StoredDocumentOut:
    extraction = await _extraction_for_attachment(db, attachment.id)
    candidate = await _candidate_for_extraction(db, extraction.id) if extraction is not None else None
    batch = await _batch_for_attachment(db, attachment.id)
    return StoredDocumentOut(
        attachment=attachment,
        extraction=extraction,
        candidate=candidate,
        batch=batch,
        extracted_items=_items_from_extraction(extraction),
    )


async def list_documents(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[StoredDocumentOut]:
    stmt = select(Attachment).where(Attachment.tenant_id == tenant_id).order_by(Attachment.created_at.desc()).limit(limit)
    if entity_id is not None:
        stmt = stmt.where(Attachment.entity_id == entity_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [await build_stored_document_out(db, row) for row in rows]


async def get_document_detail(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> StoredDocumentOut:
    attachment = await get_attachment_scoped(db, tenant_id=tenant_id, attachment_id=attachment_id)
    return await build_stored_document_out(db, attachment)


async def _read_attachment_bytes(attachment: Attachment) -> bytes:
    settings = get_settings()
    return await _get_object_bytes(minio_client, settings.minio_bucket, attachment.storage_key)


async def _upsert_extraction_candidate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    source_tx: SourceTransaction,
    extraction: DocumentExtraction,
    item: ExtractedFinancialItem,
    accounts: list[Account],
) -> ExtractionCandidate | None:
    if item.detected_document_type not in {"receipt", "text_note", "audio_note", "bank_transaction", "unknown"}:
        return None
    if item.amount is None:
        return None
    if any(question.code in QUESTION_BLOCKING_CODES for question in item.questions):
        return None

    expense_account, classifier_reason = _candidate_account_for_item(item, accounts)
    if expense_account is None:
        return None
    cash_account = await _cash_account(db, entity_id)
    amount = to_money(item.amount)
    suggestion = {
        "entry_date": item.date or utcnow().date().isoformat(),
        "memo": item.merchant or item.vendor or item.customer or item.description,
        "lines": [
            {"account_id": str(expense_account.id), "debit": str(amount), "credit": "0.00"},
            {"account_id": str(cash_account.id), "debit": "0.00", "credit": str(amount)},
        ],
    }

    item.candidate_accounts = [
        CandidateAccountOut(
            account_id=expense_account.id,
            code=expense_account.code,
            name=expense_account.name,
            reason=classifier_reason,
        )
    ]
    extraction.extracted_data = {**(extraction.extracted_data or {}), "items": [item.model_dump(mode="json")]}
    candidate = await _candidate_for_extraction(db, extraction.id)
    if candidate is None:
        candidate = ExtractionCandidate(
            tenant_id=tenant_id,
            entity_id=entity_id,
            document_extraction_id=extraction.id,
            source_transaction_id=source_tx.id,
            suggested_account_id=expense_account.id,
            suggested_memo=item.merchant or item.vendor or item.customer or item.description,
            suggested_entry=suggestion,
            confidence_score=item.confidence,
            status=CandidateStatus.suggested,
            rationale=classifier_reason,
        )
        db.add(candidate)
    else:
        candidate.source_transaction_id = source_tx.id
        candidate.suggested_account_id = expense_account.id
        candidate.suggested_memo = item.merchant or item.vendor or item.customer or item.description
        candidate.suggested_entry = suggestion
        candidate.confidence_score = item.confidence
        candidate.status = CandidateStatus.suggested
        candidate.rationale = classifier_reason
    await db.flush()
    return candidate


async def _store_source_transaction_for_item(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    item: ExtractedFinancialItem,
    kind: str,
    external_ref: str | None = None,
) -> SourceTransaction:
    row = SourceTransaction(
        entity_id=entity_id,
        kind=kind,
        external_ref=external_ref,
        occurred_at=_parse_datetime(item.date),
        amount=to_money(item.amount) if item.amount is not None else None,
        currency=item.currency,
        merchant=item.merchant or item.vendor or item.customer,
        raw={
            "description": item.description,
            "document_type": item.detected_document_type,
            "payment_method": item.payment_method,
            "questions": [question.model_dump(mode="json") for question in item.questions],
        },
        content_hash=_content_hash(item.raw_text_reference or item.description or str(item.source_id)),
        status=SourceTransactionStatus.pending,
    )
    db.add(row)
    await db.flush()
    return row


async def _extract_document_from_attachment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID | None,
    attachment: Attachment,
    data_override: bytes | None = None,
) -> StoredDocumentOut:
    data = data_override if data_override is not None else await _read_attachment_bytes(attachment)
    detected = detect_upload_type(attachment.filename, attachment.content_type, attachment.size_bytes)
    if detected.input_type == "unsupported":
        raise MIAFError("Unsupported file type", code="unsupported_file_type", details={"warnings": detected.warnings})

    if detected.input_type == "audio":
        extracted_text = ""
        items = [
            ExtractedFinancialItem(
                source_type="audio",
                detected_document_type="audio_note",
                candidate_entity_type="unknown",
                confidence=Decimal("0.0000"),
                confidence_level="low",
                missing_fields=["amount", "date", "entity"],
                questions=[
                    ExtractedFinancialQuestion(
                        code="audio_transcription_pending",
                        question="Audio transcription is not implemented yet. Please review this note manually or add a text summary.",
                    )
                ],
                raw_text_reference=None,
                file_id=str(attachment.id),
            )
        ]
    elif detected.input_type == "image":
        raw_text, _ocr_confidence = ocr.extract_text_from_image(data)
        extracted_text = _sanitize_extracted_text(raw_text)
        items = extract_financial_items_from_text(
            text=extracted_text or attachment.filename,
            source_type="image",
            file_id=str(attachment.id),
        )
    elif detected.input_type == "pdf":
        extracted_text = _printable_pdf_text(data)
        items = extract_financial_items_from_text(
            text=extracted_text or attachment.filename,
            source_type="pdf",
            file_id=str(attachment.id),
        )
    else:
        extracted_text = _normalize_text_note(data)
        text_doc_type = _detect_document_type(extracted_text, source_type="text")
        items = extract_financial_items_from_text(
            text=extracted_text or attachment.filename,
            source_type="text",
            file_id=str(attachment.id),
            suppress_entity_questions=text_doc_type == "receipt",
        )

    source_tx = await _store_source_transaction_for_item(
        db,
        entity_id=entity_id,
        item=items[0],
        kind="ocr" if detected.input_type in {"image", "pdf"} else "manual",
    )
    existing_attachment = (
        await db.execute(
            select(Attachment).where(Attachment.tenant_id == tenant_id, Attachment.sha256 == attachment.sha256, Attachment.id != attachment.id)
        )
    ).scalar_one_or_none()
    extraction = await _extraction_for_attachment(db, attachment.id)
    if extraction is None:
        extraction = DocumentExtraction(
            tenant_id=tenant_id,
            entity_id=entity_id,
            attachment_id=attachment.id,
            source_transaction_id=source_tx.id,
            extraction_kind=items[0].detected_document_type,
            status=ExtractionStatus.pending,
        )
        db.add(extraction)

    top_item = items[0]
    duplicate_detected = existing_attachment is not None
    extraction.entity_id = entity_id
    extraction.source_transaction_id = source_tx.id
    extraction.extraction_kind = top_item.detected_document_type
    extraction.extracted_text = extracted_text or top_item.raw_text_reference
    extraction.extracted_data = {
        "input_type": detected.input_type,
        "file_extension": detected.file_extension,
        "content_type": detected.content_type,
        "warnings": detected.warnings,
        "items": [item.model_dump(mode="json") for item in items],
    }
    extraction.confidence_score = top_item.confidence
    extraction.duplicate_detected = duplicate_detected
    extraction.status = (
        ExtractionStatus.extracted if top_item.confidence_level == "high" and not top_item.questions else ExtractionStatus.needs_review
    )
    await db.flush()

    accounts = (
        await db.execute(select(Account).where(Account.entity_id == entity_id, Account.is_active.is_(True)).order_by(Account.code))
    ).scalars().all()
    await _upsert_extraction_candidate(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        source_tx=source_tx,
        extraction=extraction,
        item=top_item,
        accounts=accounts,
    )
    await db.flush()
    return await build_stored_document_out(db, attachment)


async def upload_document(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID | None,
    filename: str,
    content_type: str,
    data: bytes,
) -> DocumentUploadOut:
    detected = detect_upload_type(filename, content_type, len(data))
    if detected.input_type == "unsupported":
        raise MIAFError("Unsupported file type", code="unsupported_file_type", details={"warnings": detected.warnings})

    if detected.input_type == "csv":
        result = await import_csv_transactions(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            data=data,
        )
        return DocumentUploadOut(input_type="csv", csv_import=result, warnings=detected.warnings)

    attachment = await store_attachment(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        data=data,
    )
    stored_document = await _extract_document_from_attachment(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        attachment=attachment,
        data_override=data,
    )
    return DocumentUploadOut(input_type=detected.input_type, stored_document=stored_document, warnings=detected.warnings)


async def ingest_text_message(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID | None,
    text: str,
) -> TextIngestionOut:
    data = text.encode("utf-8")
    attachment = await store_attachment(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="text-note.txt",
        content_type="text/plain",
        data=data,
    )
    stored = await _extract_document_from_attachment(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        attachment=attachment,
        data_override=data,
    )
    return TextIngestionOut(stored_document=stored)


async def rerun_document_extraction(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> StoredDocumentOut:
    attachment = await get_attachment_scoped(db, tenant_id=tenant_id, attachment_id=attachment_id)
    entity_id = attachment.entity_id
    if entity_id is None:
        raise NotFoundError("Attachment is not linked to an entity", code="entity_not_found")
    return await _extract_document_from_attachment(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        attachment=attachment,
    )


async def classify_document(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> StoredDocumentOut:
    attachment = await get_attachment_scoped(db, tenant_id=tenant_id, attachment_id=attachment_id)
    extraction = await _extraction_for_attachment(db, attachment.id)
    if extraction is None:
        raise NotFoundError("Extraction not found", code="extraction_not_found")
    item = _items_from_extraction(extraction)[0]
    if attachment.entity_id is None or extraction.source_transaction_id is None:
        raise NotFoundError("Source transaction not found", code="source_transaction_not_found")
    source_tx = await db.get(SourceTransaction, extraction.source_transaction_id)
    if source_tx is None:
        raise NotFoundError("Source transaction not found", code="source_transaction_not_found")
    accounts = (
        await db.execute(select(Account).where(Account.entity_id == attachment.entity_id, Account.is_active.is_(True)).order_by(Account.code))
    ).scalars().all()
    await _upsert_extraction_candidate(
        db,
        tenant_id=tenant_id,
        entity_id=attachment.entity_id,
        source_tx=source_tx,
        extraction=extraction,
        item=item,
        accounts=accounts,
    )
    await db.flush()
    return await build_stored_document_out(db, attachment)


async def create_draft_from_document(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> CandidateApprovalOut:
    detail = await get_document_detail(db, tenant_id=tenant_id, attachment_id=attachment_id)
    if detail.candidate is None:
        raise MIAFError("No candidate draft is available for this document", code="candidate_not_found")
    return await approve_candidate(
        db,
        entity_id=detail.candidate.entity_id,
        candidate_id=detail.candidate.id,
        user_id=user_id,
    )


async def reject_document(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> StoredDocumentOut:
    attachment = await get_attachment_scoped(db, tenant_id=tenant_id, attachment_id=attachment_id)
    extraction = await _extraction_for_attachment(db, attachment.id)
    if extraction is None:
        raise NotFoundError("Extraction not found", code="extraction_not_found")
    extraction.status = ExtractionStatus.rejected
    extraction.reviewed_at = utcnow()
    extraction.reviewed_by_id = user_id
    candidate = await _candidate_for_extraction(db, extraction.id)
    if candidate is not None:
        candidate.status = CandidateStatus.rejected
    await db.flush()
    return await build_stored_document_out(db, attachment)


async def list_document_questions(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> DocumentQuestionListOut:
    detail = await get_document_detail(db, tenant_id=tenant_id, attachment_id=attachment_id)
    questions = detail.extracted_items[0].questions if detail.extracted_items else []
    return DocumentQuestionListOut(attachment_id=attachment_id, questions=questions)


async def answer_document_question(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
    code: str,
    answer: str,
) -> StoredDocumentOut:
    attachment = await get_attachment_scoped(db, tenant_id=tenant_id, attachment_id=attachment_id)
    extraction = await _extraction_for_attachment(db, attachment.id)
    if extraction is None:
        raise NotFoundError("Extraction not found", code="extraction_not_found")
    items = _items_from_extraction(extraction)
    if not items:
        raise NotFoundError("Extracted item not found", code="extracted_item_not_found")
    item = items[0]
    matched = False
    for question in item.questions:
        if question.code == code:
            question.answer = answer
            question.status = "answered"
            matched = True
    if not matched:
        raise NotFoundError("Question not found", code="document_question_not_found")

    lower_answer = answer.lower()
    if code == "personal_business_ambiguous":
        if "business" in lower_answer or "negocio" in lower_answer:
            item.candidate_entity_type = "business"
        elif "personal" in lower_answer:
            item.candidate_entity_type = "personal"
    if code == "missing_amount":
        parsed_amount = _parse_amount_from_text(answer)
        if parsed_amount is not None:
            item.amount = str(to_money(parsed_amount))
            item.missing_fields = [field for field in item.missing_fields if field != "amount"]
    if code == "missing_date":
        parsed_date = _parse_datetime(answer)
        if parsed_date is not None:
            item.date = parsed_date.date().isoformat()
            item.missing_fields = [field for field in item.missing_fields if field != "date"]

    open_questions = [question for question in item.questions if question.status != "answered"]
    item.questions = open_questions
    item.confidence = _calculate_confidence(
        amount=to_money(item.amount) if item.amount else None,
        occurred_at=_parse_datetime(item.date),
        candidate_entity_type=item.candidate_entity_type,
        document_type=item.detected_document_type,
        merchant=item.merchant,
        vendor=item.vendor,
        customer=item.customer,
        reason_codes=[question.code for question in open_questions],
    )
    item.confidence_level = _confidence_level(item.confidence)  # type: ignore[assignment]
    extraction.extracted_data = {**(extraction.extracted_data or {}), "items": [item.model_dump(mode="json")]}
    extraction.confidence_score = item.confidence
    extraction.status = ExtractionStatus.needs_review if open_questions else ExtractionStatus.extracted
    await db.flush()
    return await classify_document(db, tenant_id=tenant_id, attachment_id=attachment_id)


async def transcribe_document_audio(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> StoredDocumentOut:
    attachment = await get_attachment_scoped(db, tenant_id=tenant_id, attachment_id=attachment_id)
    if attachment.content_type not in AUDIO_CONTENT_TYPES and _file_extension(attachment.filename) not in {".mp3", ".m4a", ".wav", ".ogg"}:
        raise MIAFError("Attachment is not an audio file", code="invalid_audio_file")
    extraction = await _extraction_for_attachment(db, attachment.id)
    if extraction is None:
        raise NotFoundError("Extraction not found", code="extraction_not_found")
    extraction.extracted_data = {
        **(extraction.extracted_data or {}),
        "transcription_status": "planned",
        "warnings": [*list((extraction.extracted_data or {}).get("warnings", [])), "Audio transcription is not implemented yet."],
    }
    extraction.status = ExtractionStatus.needs_review
    await db.flush()
    return await build_stored_document_out(db, attachment)


async def ingest_receipt(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID | None,
    filename: str,
    content_type: str,
    data: bytes,
) -> ReceiptIngestionOut:
    """Ingest receipts via PDF text fallback, image OCR, or text decode fallback."""
    candidate = None
    detected = detect_upload_type(filename, content_type, len(data))

    if detected.input_type == "pdf":
        extracted_text = _printable_pdf_text(data)
        extracted_data = {
            **_empty_receipt_fields(),
            "reason": "pdf_text_extracted" if extracted_text else "pdf_not_supported_yet",
        }
        if extracted_text:
            extracted_data, confidence = extract_receipt_fields(extracted_text)
        else:
            confidence = Decimal("0.0000")
    elif detected.input_type == "image":
        raw_text, ocr_confidence = ocr.extract_text_from_image(data)
        extracted_text = _sanitize_extracted_text(raw_text)
        extracted_data, confidence = extract_receipt_fields(extracted_text)
        extracted_data, confidence = _apply_ocr_confidence(extracted_data, ocr_confidence)
    else:
        extracted_text = _sanitize_extracted_text(data.decode("utf-8", errors="ignore"))
        extracted_data, confidence = extract_receipt_fields(extracted_text)

    merchant = extracted_data["merchant"]["value"]
    amount_value = extracted_data["total"]["value"]
    date_value = extracted_data["date"]["value"]
    amount = to_money(amount_value) if amount_value else None
    occurred_at = _parse_datetime(date_value)

    existing_attachment = (
        await db.execute(select(Attachment).where(Attachment.tenant_id == tenant_id, Attachment.sha256 == _sha256(data)))
    ).scalar_one_or_none()

    source_tx = SourceTransaction(
        entity_id=entity_id,
        kind="ocr",
        external_ref=None,
        occurred_at=occurred_at,
        amount=amount,
        currency="USD" if amount is not None else None,
        merchant=merchant,
        raw={"filename": filename, "content_type": content_type},
        content_hash=_content_hash(extracted_text),
        status=SourceTransactionStatus.pending,
    )
    db.add(source_tx)
    await db.flush()

    attachment = await store_attachment(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        data=data,
        source_transaction_id=source_tx.id,
    )

    extraction = DocumentExtraction(
        tenant_id=tenant_id,
        entity_id=entity_id,
        attachment_id=attachment.id,
        source_transaction_id=source_tx.id,
        extraction_kind="receipt",
        status=(
            ExtractionStatus.needs_review
            if content_type == "application/pdf" or extracted_text == ""
            else ExtractionStatus.extracted if confidence >= Decimal("0.80") else ExtractionStatus.needs_review
        ),
        extracted_text=extracted_text,
        extracted_data=extracted_data,
        confidence_score=confidence,
        duplicate_detected=_detect_duplicate(existing_attachment, merchant, amount, occurred_at),
    )
    db.add(extraction)
    await db.flush()

    items = extract_financial_items_from_text(
        text=extracted_text or merchant or filename,
        source_type=detected.input_type if detected.input_type != "unsupported" else "text",
        file_id=str(attachment.id),
        source_id=str(source_tx.id),
        suppress_entity_questions=True,
    )
    if items and (detected.input_type != "pdf" or extracted_text):
        extraction.extracted_data = {
            **(extraction.extracted_data or extracted_data),
            "merchant": extracted_data["merchant"],
            "date": extracted_data["date"],
            "total": extracted_data["total"],
            "reason": extracted_data.get("reason"),
            "items": [item.model_dump(mode="json") for item in items],
            "input_type": detected.input_type,
            "content_type": detected.content_type,
        }
        extraction.confidence_score = max(extraction.confidence_score or Decimal("0.0000"), items[0].confidence)
        extraction.status = (
            ExtractionStatus.extracted
            if extraction.status == ExtractionStatus.extracted and not items[0].questions
            else ExtractionStatus.needs_review if items[0].questions else extraction.status
        )
        await db.flush()

    if detected.input_type != "pdf":
        expense_account = await _default_expense_account(db, entity_id, merchant)
        cash_account = (
            await db.execute(select(Account).where(Account.entity_id == entity_id, Account.code == "1110"))
        ).scalar_one_or_none()
        if cash_account is None:
            cash_account = expense_account
        suggestion = {
            "entry_date": occurred_at.date().isoformat() if occurred_at else utcnow().date().isoformat(),
            "memo": merchant or filename,
            "lines": [
                {"account_id": str(expense_account.id), "debit": str(amount or ZERO), "credit": "0.00"},
                {"account_id": str(cash_account.id), "debit": "0.00", "credit": str(amount or ZERO)},
            ],
        }
        candidate = ExtractionCandidate(
            tenant_id=tenant_id,
            entity_id=entity_id,
            document_extraction_id=extraction.id,
            source_transaction_id=source_tx.id,
            suggested_account_id=expense_account.id,
            suggested_memo=merchant or filename,
            suggested_entry=suggestion,
            confidence_score=confidence,
            status=CandidateStatus.suggested,
            rationale="deterministic receipt heuristic",
        )
        if items and items[0].questions:
            candidate.status = CandidateStatus.suggested
            candidate.rationale = f"deterministic receipt heuristic; questions={','.join(question.code for question in items[0].questions)}"
        db.add(candidate)
        await db.flush()

    return ReceiptIngestionOut(
        attachment=attachment,
        extraction=extraction,
        candidate=candidate,
    )


async def approve_candidate(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    candidate_id: uuid.UUID,
    user_id: uuid.UUID | None,
    account_id: uuid.UUID | None = None,
    memo: str | None = None,
) -> CandidateApprovalOut:
    candidate = (
        await db.execute(
            select(ExtractionCandidate).where(
                ExtractionCandidate.id == candidate_id,
                ExtractionCandidate.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise NotFoundError(f"Candidate {candidate_id} not found", code="candidate_not_found")
    if candidate.status != CandidateStatus.suggested:
        raise MIAFError("Candidate is not pending approval", code="candidate_not_pending")

    extraction = await db.get(DocumentExtraction, candidate.document_extraction_id)
    if extraction is None:
        raise NotFoundError("Extraction not found", code="extraction_not_found")
    source_tx = await db.get(SourceTransaction, candidate.source_transaction_id) if candidate.source_transaction_id else None
    if source_tx is None:
        raise NotFoundError("Source transaction not found", code="source_transaction_not_found")

    suggested_entry = candidate.suggested_entry or {}
    debit_account_id = uuid.UUID(str(account_id or candidate.suggested_account_id))
    credit_account = (
        await db.execute(select(Account).where(Account.entity_id == entity_id, Account.code == "1110"))
    ).scalar_one_or_none()
    if credit_account is None:
        raise NotFoundError("Cash account 1110 not found", code="account_not_found")
    amount = source_tx.amount or ZERO
    occurred_at = source_tx.occurred_at or utcnow()
    entry = await create_draft(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=JournalEntryCreate(
            entry_date=occurred_at.date(),
            memo=memo or candidate.suggested_memo or source_tx.merchant,
            source_transaction_id=source_tx.id,
            lines=[
                JournalLineIn(account_id=debit_account_id, debit=amount, credit=ZERO),
                JournalLineIn(account_id=credit_account.id, debit=ZERO, credit=amount),
            ],
        ),
    )
    candidate.status = CandidateStatus.approved
    candidate.approved_entry_id = entry.id
    extraction.status = ExtractionStatus.approved
    extraction.reviewed_at = utcnow()
    extraction.reviewed_by_id = user_id
    source_tx.status = SourceTransactionStatus.matched

    attachment = await db.get(Attachment, extraction.attachment_id)
    if attachment is not None:
        attachment.journal_entry_id = entry.id
    await db.flush()
    return CandidateApprovalOut(candidate=candidate, journal_entry_id=entry.id)


async def _auto_draft_csv_outflow(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID | None,
    source_tx: SourceTransaction,
    accounts: list[Account],
    memory_lookup: Callable[[str], Account | None] | None = None,
) -> JournalEntry | None:
    amount = _outflow_amount(source_tx.amount)
    if amount is None:
        return None

    expense_account, classifier_reason = classify_source_transaction(
        source_tx,
        accounts,
        memory_lookup=memory_lookup,
    )
    cash_account = await _cash_account(db, entity_id)
    entry = await create_draft(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=JournalEntryCreate(
            entry_date=(source_tx.occurred_at or utcnow()).date(),
            memo=source_tx.merchant or _csv_memo(source_tx.raw),
            source_transaction_id=source_tx.id,
            lines=[
                JournalLineIn(account_id=expense_account.id, debit=amount, credit=ZERO),
                JournalLineIn(account_id=cash_account.id, debit=ZERO, credit=amount),
            ],
        ),
    )
    source_tx.status = SourceTransactionStatus.matched
    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        action="auto_draft",
        object_type="journal_entry",
        object_id=entry.id,
        after={
            "source_transaction_id": str(source_tx.id),
            "classifier_reason": classifier_reason,
        },
    )
    return entry


async def list_pending_source_drafts(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
) -> list[PendingDraftOut]:
    rows = (
        await db.execute(
            select(JournalEntry, SourceTransaction)
            .join(SourceTransaction, SourceTransaction.id == JournalEntry.source_transaction_id)
            .options(selectinload(JournalEntry.lines))
            .where(
                JournalEntry.entity_id == entity_id,
                JournalEntry.status == JournalEntryStatus.draft,
                JournalEntry.source_transaction_id.is_not(None),
            )
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        )
    ).all()

    return [
        PendingDraftOut(
            id=entry.id,
            entry_date=entry.entry_date,
            memo=entry.memo,
            lines=entry.lines,
            source=PendingDraftSourceOut(
                merchant=source_tx.merchant,
                memo=_csv_memo(source_tx.raw),
                amount=source_tx.amount,
                currency=source_tx.currency,
                posted_at=source_tx.occurred_at,
            ),
        )
        for entry, source_tx in rows
    ]


async def import_csv_transactions(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID | None,
    filename: str,
    content_type: str,
    data: bytes,
) -> CsvImportOut:
    """Import CSV rows into source transactions and auto-draft outflow journal entries.

    Positive amounts are imported as SourceTransaction rows only and intentionally do not
    create draft journal entries in this initial pass.
    """
    detected = detect_upload_type(filename, content_type, len(data))
    if detected.input_type != "csv":
        raise MIAFError("Unsupported file type for CSV import", code="unsupported_file_type")

    text = data.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    fieldnames = {name.strip().lower() for name in (reader.fieldnames or []) if name}
    if not rows:
        raise MIAFError("CSV import is empty", code="csv_empty")
    if not ({"date", "occurred_at"} & fieldnames):
        raise MIAFError("CSV import is missing a date column", code="csv_missing_date_column")
    if not ({"amount", "total", "debit", "credit"} & fieldnames):
        raise MIAFError("CSV import is missing an amount column", code="csv_missing_amount_column")

    attachment = await store_attachment(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        data=data,
    )
    batch = ImportBatch(
        tenant_id=tenant_id,
        entity_id=entity_id,
        attachment_id=attachment.id,
        kind="csv_bank_transactions",
        status=ImportBatchStatus.processing,
        rows_total=len(rows),
        created_by_id=user_id,
    )
    db.add(batch)
    await db.flush()

    accounts = (
        await db.execute(select(Account).where(Account.entity_id == entity_id, Account.is_active.is_(True)).order_by(Account.code))
    ).scalars().all()
    memory_lookup = await build_memory_lookup(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        accounts=accounts,
    )
    created: list[SourceTransaction] = []
    drafts_created = 0
    failures = 0
    duplicate_rows = 0
    for row in rows:
        try:
            occurred_at = _parse_datetime(row.get("date") or row.get("occurred_at"))
            amount_raw = row.get("amount") or row.get("total") or row.get("debit") or row.get("credit")
            amount = to_money(amount_raw) if amount_raw not in (None, "") else None
            merchant = row.get("merchant") or row.get("description") or row.get("memo")
            content_hash = _content_hash("|".join([row.get(k, "") for k in sorted(row.keys())]))
            existing = (
                await db.execute(
                    select(SourceTransaction).where(
                        SourceTransaction.entity_id == entity_id,
                        SourceTransaction.content_hash == content_hash,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                duplicate_rows += 1
                continue
            source_tx = SourceTransaction(
                entity_id=entity_id,
                kind="csv_row",
                external_ref=row.get("external_ref") or row.get("id"),
                occurred_at=occurred_at,
                amount=amount,
                currency=(row.get("currency") or "USD")[:3] if amount is not None else row.get("currency"),
                merchant=merchant,
                raw=row,
                content_hash=content_hash,
                status=SourceTransactionStatus.pending,
            )
            db.add(source_tx)
            await db.flush()
            if await _auto_draft_csv_outflow(
                db,
                tenant_id=tenant_id,
                entity_id=entity_id,
                user_id=user_id,
                source_tx=source_tx,
                accounts=accounts,
                memory_lookup=memory_lookup,
            ):
                drafts_created += 1
            created.append(source_tx)
        except Exception:
            failures += 1
    batch.rows_imported = len(created)
    batch.rows_failed = failures
    batch.status = ImportBatchStatus.completed if failures == 0 else ImportBatchStatus.failed
    warnings: list[str] = []
    if failures:
        warnings.append(f"{failures} row(s) failed")
    if duplicate_rows:
        warnings.append(f"{duplicate_rows} duplicate row(s) skipped")
    if warnings:
        batch.error_message = "; ".join(warnings)
    await db.flush()
    return CsvImportOut(batch=batch, source_transactions=created, drafts_created=drafts_created)


async def get_attachment_scoped(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> Attachment:
    attachment = await db.get(Attachment, attachment_id)
    if attachment is None or attachment.tenant_id != tenant_id:
        raise NotFoundError(f"Attachment {attachment_id} not found", code="attachment_not_found")
    return attachment
