# MIAF Ingestion Guide

MIAF treats every uploaded file, message, and manual note as untrusted input until it is stored, extracted, classified, reviewed, and audited.

## Supported input types

Implemented today:

- plain text note through `POST /ingest/text`
- plain text file upload
- CSV bank export
- PDF document upload
- image upload: `png`, `jpg`, `jpeg`, `webp`
- audio upload: `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `wav`, `ogg`, `webm`

Current handling level:

- Text: implemented locally, with optional OpenAI extraction for ambiguous notes
- CSV: implemented locally, with optional OpenAI column mapping suggestions only
- Image OCR: implemented with Tesseract, with optional OpenAI vision fallback
- PDF: implemented with local embedded-text extraction, with optional OpenAI PDF fallback for scanned or low-text PDFs
- Audio: review-only by default, with optional OpenAI transcription and extraction when enabled

Not implemented as a specialized parser yet:

- XLSX import
- full invoice/bill workflow creation from extracted documents

## Unified ingestion pipeline

The current pipeline is:

Input received
→ detect type and validate size/content
→ store raw file or text note in attachment storage
→ create or update source transaction context
→ extract text/data
→ normalize into `ExtractedFinancialItem`
→ detect document type
→ infer personal/business/unknown
→ score confidence
→ generate short accounting questions when needed
→ create a draft candidate when confidence and ambiguity allow it
→ require user review for uncertain items
→ create draft journal entry only from approved candidate flow
→ learn from corrections when posted entries differ from initial classification
→ audit upload, extraction, classification, question answers, and approvals

## Security model

Safety rules in the current implementation:

- uploads are size-limited
- unsupported file types are rejected
- files are stored as bytes only and never executed
- uploaded files stay in object storage and are accessed through signed URLs
- SHA-256 hashes are stored for every attachment
- CSV rows use deterministic content hashes and duplicate rows are skipped
- duplicate document detections are surfaced for review
- OCR and parsing results are treated as suggestions, not truth
- OpenAI document reading is disabled by default
- external document processing requires explicit user enablement and consent
- MIAF never lets OpenAI post journal entries directly

## Type detection

Detection uses:

- file extension
- MIME type
- file size

Current categories:

- `text`
- `csv`
- `pdf`
- `image`
- `audio`
- `unsupported`

## Extraction output

MIAF normalizes extracted content into `ExtractedFinancialItem` records with fields such as:

- detected document type
- amount
- date
- merchant/vendor/customer
- candidate entity type
- candidate accounts
- confidence and confidence level
- missing fields
- review questions
- raw text reference

This output is stored in document extraction JSON so the review UI and APIs can use one common structure.

## CSV workflow

CSV import behavior today:

1. Store the original CSV file as an attachment.
2. Validate that date and amount-style columns exist.
3. Parse rows into `source_transactions`.
4. Skip duplicate rows using content hashes.
5. Auto-draft outflow journal entries only.
6. Leave inflows as source transactions pending review.
7. Use merchant memory rules when available.
8. Log classifier reasons in the audit trail.

CSV imports do not post ledger entries automatically.

## PDF and image workflow

### PDF

Current behavior:

- store the original PDF
- attempt extraction with `pypdf` first
- fall back to safe printable-text scraping if structured extraction is weak
- normalize extracted text into a structured item locally
- if the PDF appears scanned or the local text is too weak, optionally send it to OpenAI PDF extraction when enabled
- if OpenAI is disabled or fails, keep the document in review status

### Image

Current behavior:

- OCR with Tesseract first
- normalize text into extracted fields
- generate confidence and review questions
- optionally escalate low-confidence images to OpenAI vision extraction
- create candidate draft only when ambiguity is low enough

## Audio workflow

Audio files are accepted and stored.

Default behavior:

- store the original audio file
- mark extraction as `needs_review`
- create a low-confidence `audio_note` item
- tell the user that audio transcription requires OpenAI document reading to be enabled

When OpenAI document reading is enabled:

- send the uploaded audio bytes to the configured OpenAI transcription model
- take the transcript through the same financial extraction schema as text notes
- still keep human review and deterministic accounting boundaries

## Text workflow

Text notes support direct manual capture and chat-like spending capture.

Examples:

- `I spent $25 on gas today`
- `Business paid $120 for internet`
- `I bought supplies for the business on my personal card`

MIAF extracts:

- amount when present
- date when present
- merchant/vendor/customer hints
- likely entity type
- confidence level
- questions when the entry is ambiguous

## Confidence policy

Current thresholds:

- High: `>= 0.80`
- Medium: `>= 0.55`
- Low: `< 0.55`

Confidence drops when:

- amount is missing
- date is missing
- entity is unclear
- owner draw / reimbursement language appears
- asset-vs-expense ambiguity appears
- open accounting questions remain

Behavior:

- High confidence: extraction can produce a candidate draft
- Medium confidence: extraction stays review-oriented and may still propose a candidate
- Low confidence: extraction stays in review with explicit questions

No uncertain item is silently posted.

## Questions and review

Questions are linked to the extracted item and currently stored in extraction JSON.

Examples:

- `Is this personal or business?`
- `What is the amount for this item?`
- `What date should I use for this item?`
- `Was this bill already paid, or should I record it as accounts payable?`
- `Should this be expensed now or recorded as an asset?`

The current review UI is on `/documents`.

## Enable AI document reading

1. Open `/settings`.
2. Save an OpenAI API key.
3. Turn on `Enable OpenAI document reading`.
4. Turn on `Allow MIAF to send uploaded documents to OpenAI for extraction`.
5. Choose the vision, PDF, and transcription models.
6. Upload or reprocess a document in `/documents`.
7. Review the result before posting anything.

## Learning from corrections

MIAF learns most clearly today from merchant corrections in the source-transaction and draft-entry flow.

Current behavior:

- if a CSV-imported draft is corrected to a different expense account and then posted
- MIAF creates or updates a merchant rule memory
- future imports for that merchant can use the remembered account

This learning is intentionally narrow and conservative. Broad rules are not inferred from one document type across the entire system.

## Heartbeat integration

The heartbeat pipeline now checks for ingestion issues such as:

- documents still needing review
- duplicate document detections
- open accounting questions
- low-confidence extractions
- source-linked draft journal entries still unposted

These appear as alerts in `/alerts`.

## API surfaces

Current ingestion-related endpoints:

- `POST /documents/upload`
- `GET /documents`
- `GET /documents/{id}`
- `POST /documents/{id}/extract`
- `POST /documents/{id}/extract?mode=openai`
- `POST /documents/{id}/classify`
- `POST /documents/{id}/create-draft`
- `POST /documents/{id}/approve`
- `POST /documents/{id}/reject`
- `GET /documents/{id}/questions`
- `POST /documents/{id}/questions`
- `POST /documents/{id}/answer-question`
- `POST /documents/{id}/transcribe`
- `POST /ingest/text`

Legacy entity-scoped document endpoints still exist and are used by some current frontend flows.

## Safety limits

MIAF does not:

- execute uploaded files
- trust OCR or parsing blindly
- expose uploaded files publicly
- move money
- trade
- file taxes
- silently post uncertain accounting records
