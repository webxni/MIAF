from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import FinClawError, NotFoundError
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
from app.schemas.ingestion import CandidateApprovalOut, CsvImportOut, PendingDraftOut, PendingDraftSourceOut, ReceiptIngestionOut
from app.schemas.journal import JournalEntryCreate, JournalLineIn
from app.config import get_settings
from app.services.audit import write_audit
from app.services.classifier import build_memory_lookup, classify_source_transaction
from app.services.journal import create_draft
from app.storage import ensure_bucket, minio_client

MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "text/plain",
    "text/csv",
    "application/pdf",
    "image/png",
    "image/jpeg",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
        raise FinClawError("Unsupported file type", code="unsupported_file_type")
    if len(data) > MAX_FILE_BYTES:
        raise FinClawError("File exceeds max upload size", code="file_too_large")

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
    extracted_text = data.decode("utf-8", errors="ignore")
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
        status=ExtractionStatus.extracted if confidence >= Decimal("0.80") else ExtractionStatus.needs_review,
        extracted_text=extracted_text,
        extracted_data=extracted_data,
        confidence_score=confidence,
        duplicate_detected=_detect_duplicate(existing_attachment, merchant, amount, occurred_at),
    )
    db.add(extraction)
    await db.flush()

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
        raise FinClawError("Candidate is not pending approval", code="candidate_not_pending")

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
    text = data.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

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
    for row in rows:
        try:
            occurred_at = _parse_datetime(row.get("date") or row.get("occurred_at"))
            amount_raw = row.get("amount") or row.get("total") or row.get("debit") or row.get("credit")
            amount = to_money(amount_raw) if amount_raw not in (None, "") else None
            merchant = row.get("merchant") or row.get("description") or row.get("memo")
            content_hash = _content_hash("|".join([row.get(k, "") for k in sorted(row.keys())]))
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
    if failures:
        batch.error_message = f"{failures} row(s) failed"
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
