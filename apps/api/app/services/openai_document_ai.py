from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError

try:
    import openai as _openai_sdk
except ImportError:  # pragma: no cover
    _openai_sdk = None

from app.config import Settings
from app.errors import MIAFError
from app.schemas.ingestion import ExtractedFinancialItem

log = logging.getLogger(__name__)


_IMAGE_PROMPT = (
    "You are extracting financial data from a receipt, invoice, bill, or bank document for "
    "bookkeeping review. Return strict JSON only. Do not guess totals. If unclear, use null and add a question."
)
_TEXT_PROMPT = (
    "You are extracting bookkeeping data from text or a transcript. Return strict JSON only. "
    "Do not guess amounts, dates, or accounting decisions. If unclear, use null and add a question."
)
_CSV_PROMPT = (
    "You are mapping CSV columns for deterministic bookkeeping import. "
    "Return strict JSON only. Identify likely date, description, amount, debit, credit, merchant, category, and account columns. "
    "Do not calculate totals. Do not transform row values."
)


class OpenAIQuestion(BaseModel):
    code: str
    question: str
    status: str = "open"
    answer: str | None = None


class OpenAICandidateAccount(BaseModel):
    account_id: str | None = None
    code: str | None = None
    name: str | None = None
    reason: str | None = None


class OpenAIItemPayload(BaseModel):
    source_id: str | None = None
    source_type: str
    detected_document_type: str = "unknown"
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
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    payment_method: str | None = None
    invoice_number: str | None = None
    bill_number: str | None = None
    account_last4: str | None = None
    candidate_entity_type: str = "unknown"
    candidate_accounts: list[OpenAICandidateAccount] = Field(default_factory=list)
    confidence: Decimal = Decimal("0.0000")
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[OpenAIQuestion] = Field(default_factory=list)
    raw_text_reference: str | None = None
    file_id: str | None = None
    model_used: str | None = None
    extraction_method: str
    audit_id: str | None = None


class OpenAIExtractionEnvelope(BaseModel):
    raw_text: str | None = None
    item: OpenAIItemPayload


class OpenAICsvMapping(BaseModel):
    date_column: str | None = None
    description_column: str | None = None
    amount_column: str | None = None
    debit_column: str | None = None
    credit_column: str | None = None
    merchant_column: str | None = None
    category_column: str | None = None
    account_column: str | None = None
    notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class DocumentAIContext:
    api_key: str
    settings: Settings
    vision_model: str
    pdf_model: str
    transcription_model: str


def _client(api_key: str, *, settings: Settings):
    if _openai_sdk is None:
        raise MIAFError("OpenAI SDK is not installed", code="openai_sdk_missing")
    return _openai_sdk.OpenAI(
        api_key=api_key,
        timeout=settings.openai_document_timeout_seconds,
    )


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    if isinstance(response, dict):
        if isinstance(response.get("output_text"), str):
            return response["output_text"].strip()
    raise MIAFError("OpenAI did not return structured text output", code="openai_empty_response")


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        parts = stripped.split("\n", 1)
        stripped = parts[1] if len(parts) == 2 else parts[0]
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise MIAFError("OpenAI returned malformed JSON", code="openai_invalid_json") from exc
    if not isinstance(parsed, dict):
        raise MIAFError("OpenAI returned an unexpected response shape", code="openai_invalid_json")
    return parsed


def _validate_item(payload: dict[str, Any]) -> OpenAIExtractionEnvelope:
    try:
        return OpenAIExtractionEnvelope.model_validate(payload)
    except ValidationError as exc:
        raise MIAFError("OpenAI response did not match the extraction schema", code="openai_schema_invalid") from exc


def _to_item(envelope: OpenAIExtractionEnvelope) -> tuple[str | None, ExtractedFinancialItem]:
    item = ExtractedFinancialItem.model_validate(envelope.item.model_dump(mode="json"))
    return envelope.raw_text, item


def _encode_bytes(data: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _build_financial_prompt(prompt_context: str | None) -> str:
    if prompt_context:
        return f"{_IMAGE_PROMPT}\nContext: {prompt_context}"
    return _IMAGE_PROMPT


def _responses_json(client: Any, *, model: str, input_payload: list[dict[str, Any]]) -> dict[str, Any]:
    response = client.responses.create(model=model, input=input_payload)
    return _extract_json(_extract_response_text(response))


def openai_extract_image(
    ctx: DocumentAIContext,
    *,
    file_bytes: bytes,
    mime_type: str,
    filename: str,
    prompt_context: str | None,
) -> tuple[str | None, ExtractedFinancialItem]:
    client = _client(ctx.api_key, settings=ctx.settings)
    payload = _responses_json(
        client,
        model=ctx.vision_model,
        input_payload=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _build_financial_prompt(prompt_context)},
                    {"type": "input_image", "image_url": _encode_bytes(file_bytes, mime_type)},
                    {"type": "input_text", "text": f"Filename: {filename}"},
                ],
            }
        ],
    )
    raw_text, item = _to_item(_validate_item(payload))
    item.model_used = ctx.vision_model
    item.extraction_method = "openai_vision"
    return raw_text, item


def openai_extract_pdf(
    ctx: DocumentAIContext,
    *,
    file_bytes: bytes,
    filename: str,
    prompt_context: str | None,
) -> tuple[str | None, ExtractedFinancialItem]:
    client = _client(ctx.api_key, settings=ctx.settings)
    payload = _responses_json(
        client,
        model=ctx.pdf_model,
        input_payload=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _build_financial_prompt(prompt_context)},
                    {
                        "type": "input_file",
                        "filename": filename,
                        "file_data": _encode_bytes(file_bytes, "application/pdf"),
                    },
                ],
            }
        ],
    )
    raw_text, item = _to_item(_validate_item(payload))
    item.model_used = ctx.pdf_model
    item.extraction_method = "openai_pdf"
    return raw_text, item


def openai_transcribe_audio(
    ctx: DocumentAIContext,
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
) -> str:
    client = _client(ctx.api_key, settings=ctx.settings)
    response = client.audio.transcriptions.create(
        model=ctx.transcription_model,
        file=(filename, io.BytesIO(file_bytes), mime_type),
    )
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise MIAFError("OpenAI did not return a transcription", code="openai_transcription_empty")


def openai_extract_from_text(
    ctx: DocumentAIContext,
    *,
    text: str,
    prompt_context: str | None,
) -> tuple[str | None, ExtractedFinancialItem]:
    client = _client(ctx.api_key, settings=ctx.settings)
    prompt = _TEXT_PROMPT if not prompt_context else f"{_TEXT_PROMPT}\nContext: {prompt_context}"
    payload = _responses_json(
        client,
        model=ctx.vision_model,
        input_payload=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_text", "text": text},
                ],
            }
        ],
    )
    raw_text, item = _to_item(_validate_item(payload))
    item.model_used = ctx.vision_model
    item.extraction_method = "openai_text"
    return raw_text, item


def openai_classify_extracted_item(
    ctx: DocumentAIContext,
    *,
    raw_text: str,
    metadata: dict[str, Any],
) -> tuple[str | None, ExtractedFinancialItem]:
    prompt = (
        "Classify the extracted bookkeeping item using strict JSON only. "
        "Preserve any amounts and dates already present. Do not invent values."
    )
    merged_text = f"{raw_text}\nMetadata: {json.dumps(metadata, ensure_ascii=True)}"
    return openai_extract_from_text(ctx, text=merged_text, prompt_context=prompt)


def openai_map_csv_columns(
    ctx: DocumentAIContext,
    *,
    sample_rows: list[dict[str, str]],
    columns: list[str],
    remembered_mappings: dict[str, str] | None,
) -> OpenAICsvMapping:
    client = _client(ctx.api_key, settings=ctx.settings)
    payload = _responses_json(
        client,
        model=ctx.vision_model,
        input_payload=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _CSV_PROMPT},
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "columns": columns,
                                "sample_rows": sample_rows[:5],
                                "remembered_mappings": remembered_mappings or {},
                            },
                            ensure_ascii=True,
                        ),
                    },
                ],
            }
        ],
    )
    try:
        return OpenAICsvMapping.model_validate(payload)
    except ValidationError as exc:
        raise MIAFError(
            "OpenAI response did not match the CSV mapping schema",
            code="openai_csv_mapping_invalid",
        ) from exc
