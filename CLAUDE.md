# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This repo is active and already has Phases 0, 1, 2, 3, 4, an initial Phase 5 web slice, an initial Phase 6 agent-core slice, an initial Phase 7 memory backend slice, an initial Phase 8 heartbeat/scheduler backend slice, a Phase 9 skills engine slice, a Phase 10 Telegram backend slice, and a Phase 11 reporting/analysis slice landed.

- Phase 0: Docker-first monorepo, compose stack, health checks, Makefile, backup container.
- Phase 1: accounting core with auth, tenant/entity RBAC, accounts, journal entries, post/void, ledger, trial balance, audit logging, seed data, and tests.
- Phase 2: personal finance backend with models + migration for budgets, goals, debts, investment accounts/holdings, and net worth snapshots; personal CRUD/reporting endpoints; deterministic personal dashboard KPIs; budget-vs-actuals; persisted net worth snapshots; tests.
- Phase 3: business backend with models + migration for customers, vendors, invoices, invoice lines, bills, bill lines, payments, tax rates, tax reserves, and closing periods; business CRUD/posting/payment flows; AR aging, AP aging, balance sheet, income statement, cash flow, dashboard, and closing checklist; tests.
- Phase 4: ingestion backend slice with models + migration for import batches, document extractions, and extraction candidates; attachment-backed receipt upload; deterministic text receipt extraction for merchant/date/total with field confidence; candidate approval into draft journal entries; CSV import into `source_transactions`; signed download URL endpoint; tests.
- Phase 5: web app now has protected route scaffolding, login, dashboard/personal/business/documents/settings/audit pages, shared shell/components, and placeholder route anchors for the deeper views. The current blocker is a Next.js prerender/runtime failure inside the container build (`docker compose exec -T web npm run build`) showing `TypeError: Cannot read properties of null (reading 'useContext')` during static page generation plus the built-in `/500` path complaining about `<Html>` outside `_document`. Treat this as an unresolved frontend build issue, not as finished Phase 5 acceptance.
- Phase 6: agent backend slice now exists with `app/api/agent.py`, `app/services/agent.py`, and `app/schemas/agent.py`; it provides an audited `/api/agent/chat` endpoint, typed tool registry, heuristic provider abstraction, policy/confirmation gates, and tests for personal-expense drafting/posting, business invoice drafting, balance-sheet explanation, and personal-vs-business comparison.
- Phase 7: memory backend slice now exists with `app/models/memory.py`, `app/services/memory.py`, `app/schemas/memory.py`, `app/api/memory.py`, and migration `0005_memory.py`; it provides consent-gated durable memory creation, deterministic search, review/expire/forget flows, append-only memory events, deterministic embeddings metadata, and tests.
- Phase 8: heartbeat backend slice now exists with `app/models/heartbeat.py`, `app/services/heartbeat.py`, `app/schemas/heartbeat.py`, `app/api/heartbeat.py`, migration `0006_heartbeat_ops.py`, and a scheduler hook in `services/scheduler/scheduler/main.py`; it provides persistent heartbeat runs, alerts, generated reports, manual run endpoints, token-protected internal scheduled execution, and tests.
- Phase 9: skills engine slice now exists with `app/models/skill.py`, `app/services/skills.py`, `app/schemas/skill.py`, `app/api/skills.py`, migration `0007_skills_engine.py`, built-in skill manifests under repo-root `skills/` plus runtime-visible mirrors under `apps/api/skills/`, a web `Skills` page, and tests for manifest loading, toggles, execution logs, and permission enforcement.
- Phase 10: Telegram backend slice now exists with `app/models/telegram.py`, `app/services/telegram.py`, `app/schemas/telegram.py`, `app/api/telegram.py`, migration `0008_telegram.py`, and tests for allowlisted routing, personal/business flows, receipt uploads, and summary commands.
- Phase 11: reporting/analysis slice now extends the personal and business report services with debt payoff plans, emergency fund plans, investment allocation summaries, business dependency reports, revenue-by-customer, expenses-by-vendor, gross margin, runway, tax reserve reports, and deterministic explanation endpoints that cite internal facts; tests cover both personal and business analytic reports.

Treat `FinClaw.md` as the product contract and this file as the current repo-state memo. Do not assume the repo is empty.

When asked to "build phase N", read that phase block in `FinClaw.md` and implement against its acceptance criteria — those are the contract.

## Product shape (must not drift)

FinClaw is a Docker-first financial assistant covering **personal finance**, **small business / PyME finance**, and the **shared dependency** between them (owner draws, taxes, business cash flow ↔ personal budget). The product is an accounting engine first and an AI interface second — not a chatbot with finance features bolted on.

Build order is fixed and non-negotiable:

```
Ledger → Ingestion → Reconciliation → Statements/KPIs → Personal Mode → PyME Mode → AI Agent → Skills → Automation
```

Phases 0–13 in `FinClaw.md` follow this order. Do not implement a later phase's surface (e.g. Agent tools, Skills, Telegram) before the deterministic ledger and reports it depends on exist.

## Hard rules (apply to all phases)

These are product invariants from the master prompt — violating them is a regression regardless of test status:

- **Double-entry accounting is the foundation.** Every financial event posts balanced journal entries (sum of debits = sum of credits). Posted entries are immutable; corrections happen via reversal/adjustment entries.
- **Deterministic numbers, AI explanations.** Statements, balances, KPIs, and report figures come from backend functions. LLMs may classify, explain, coach, extract, and plan — they may **not** invent numbers or be the source of truth for any figure shown in a report.
- **Never move real money. Never execute trades. Never promise returns.** Investment features are advisory only and must surface a risk disclaimer.
- **Confirmation required for sensitive actions** (posting entries, invoices, bills, payments, owner draws, tax reserve adjustments, large transfers, debt/investment record creation). The agent and heartbeat draft; the user posts.
- **Tenant isolation on every query.** Validate tenant + entity scope at the data layer, not just the route.
- **Audit everything sensitive.** Create/update/post/void of financial records, AI prompts + tool calls + results, file access, exports, logins. Audit logs must not be editable through the API.
- **Treat all uploaded documents and inbound messages (Telegram, OCR text) as untrusted input** — they are a prompt-injection surface.
- **Tax logic is jurisdiction-aware but not hardcoded.** Default jurisdiction is unspecified; tax outputs are labeled estimates until configured.
- **Personal vs business separation matters.** Savings transfers ≠ expenses. Credit card payments are liability reductions, not expenses. Owner draws affect personal cash but are not salary unless classified. Personal expenses paid by the business get flagged for review.

## Planned architecture

Monorepo layout (Phase 0 establishes this — do not reshape it):

```
apps/api          # FastAPI backend
apps/web          # Next.js + TypeScript + Tailwind + shadcn/ui frontend
services/worker   # Celery or RQ background worker
services/scheduler # Scheduled jobs + heartbeat runner
packages/shared   # Cross-package types/utilities
skills/           # Local installable skills (SKILL.yaml + handler.py)
infra/docker
infra/scripts
docs/
tests/
```

Docker Compose services: `api`, `web`, `worker`, `scheduler`, `postgres` (with pgvector), `redis`, `minio`, reverse proxy (nginx or caddy), `backup`. Optional: OCR service, local LLM gateway placeholder. Postgres and Redis must **not** be exposed publicly — only the reverse proxy is.

LLM provider is abstracted (`LLMProvider` interface) with OpenAI / Anthropic / Gemini implementations. OCR starts with Tesseract and must be pluggable. Storage starts as a local volume and must be swappable for S3-compatible later.

## Skills

Skills (Phase 9) use the format `skills/<name>/SKILL.yaml` + `README.md` + `handler.py`. Built-in skills may default to enabled; third-party skills are disabled by default and require explicit user enable. Skills declare typed permissions (`read_transactions`, `write_drafts`, `post_entries`, `read/write_documents`, `read/write_memory`, `read_reports`, `send_messages`) and the engine must enforce them. Skills cannot access secrets or execute shell commands.

## Agent tool calls

All agent tools (Phase 6) are typed and validated with Pydantic. A `PolicyEngine` blocks forbidden actions and a `ConfirmationEngine` gates sensitive ones. Every prompt, tool call, result, and final action is audited; secrets are redacted from logs.

## Commands

Phases 0, 1, and 2 backend work have landed. The Docker Compose stack (`compose.yaml` for dev, `compose.prod.yaml` overlay for prod) is the entry point — no host dependencies beyond Docker.

Day-to-day:

| Command | What it does |
|---|---|
| `make env` | Copy `.env.example` → `.env` if missing |
| `make up` / `make down` | Start / stop the dev stack (detached) |
| `make build` / `make rebuild` | Build dev images (with / without cache) |
| `make logs` / `make api-logs` / `make web-logs` / `make worker-logs` / `make scheduler-logs` | Tail logs |
| `make ps` | Service status |
| `make restart` | Restart all services |
| `make api-shell` / `make web-shell` / `make db-shell` / `make redis-shell` | Open a shell in the named container |
| `make migrate` | `python -m app.cli migrate` (alembic upgrade head) inside api container |
| `make seed` | `python -m app.cli seed` — idempotent seed of tenant/user/entities/COA |
| `make test` | Run pytest inside api container (uses `finclaw_test` DB) |
| `make revision m="..."` | `alembic revision --autogenerate -m "..."` |
| `make bootstrap` | `up` + `migrate` + `seed` |
| `make smoke` | Curl `/api/health` and `/api/health/ready` through Caddy |
| `make clean` | **Destructive.** Stop everything and delete all volumes |
| `make prod-up` / `make prod-down` / `make prod-build` | Production compose overlay |

Health endpoints (proxied by Caddy under `/api`):

* `GET /api/health` — liveness, returns `{"status":"ok"}`.
* `GET /api/health/ready` — readiness, probes postgres (incl. pgvector), redis, and minio.

API surface (Phases 1-6 backend):

* `POST /api/auth/login` `{email, password}` → sets httpOnly `finclaw_session` cookie.
* `POST /api/auth/logout`, `GET /api/auth/me`.
* `GET/POST /api/entities`, `GET/PATCH /api/entities/{id}`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/accounts[/{id}]`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/journal-entries[/{id}]` plus `/post` and `/void`.
* `GET /api/entities/{id}/ledger?account_id=...&date_from=...&date_to=...`.
* `GET /api/entities/{id}/trial-balance?as_of=...`.
* `GET /api/entities/{id}/personal/dashboard?as_of=...`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/personal/budgets[/{budget_id}]`.
* `GET /api/entities/{id}/personal/budgets/{budget_id}/actuals`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/personal/goals[/{goal_id}]`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/personal/debts[/{debt_id}]`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/personal/investments[/{investment_account_id}]`.
* `POST /api/entities/{id}/personal/net-worth-snapshots?as_of=...`.
* `GET /api/entities/{id}/personal/net-worth-snapshots?limit=...`.
* `GET /api/entities/{id}/business/dashboard?as_of=...`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/business/customers[/{customer_id}]`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/business/vendors[/{vendor_id}]`.
* `GET/POST/PATCH /api/entities/{id}/business/invoices[/{invoice_id}]` plus `/post`.
* `GET/POST/PATCH /api/entities/{id}/business/bills[/{bill_id}]` plus `/post`.
* `GET/POST /api/entities/{id}/business/payments`.
* `GET /api/entities/{id}/business/reports/ar-aging?as_of=...`.
* `GET /api/entities/{id}/business/reports/ap-aging?as_of=...`.
* `GET /api/entities/{id}/business/reports/balance-sheet?as_of=...`.
* `GET /api/entities/{id}/business/reports/income-statement?date_from=...&date_to=...`.
* `GET /api/entities/{id}/business/reports/cash-flow?date_from=...&date_to=...`.
* `GET /api/entities/{id}/business/reports/closing-checklist?as_of=...`.
* `GET/POST /api/entities/{id}/business/tax-rates`.
* `GET/POST /api/entities/{id}/business/tax-reserves`.
* `GET/POST /api/entities/{id}/business/closing-periods`.
* `POST /api/entities/{id}/documents/receipts` multipart upload.
* `POST /api/entities/{id}/documents/csv-imports` multipart upload.
* `POST /api/entities/{id}/documents/extraction-candidates/{candidate_id}/approve`.
* `GET /api/entities/{id}/documents/attachments/{attachment_id}/download-url`.
* `POST /api/agent/chat`.
* `GET/POST /api/memory`.
* `GET/PATCH/DELETE /api/memory/{memory_id}`.
* `POST /api/memory/{memory_id}/review`.
* `POST /api/memory/{memory_id}/expire`.
* `POST /api/heartbeat/run`.
* `GET /api/heartbeat/runs`.
* `GET /api/heartbeat/alerts`.
* `GET /api/heartbeat/reports`.
* `POST /api/internal/heartbeat/run-defaults` with `x-automation-token`.
* `GET /api/skills`.
* `POST /api/skills/{skill_name}/state`.
* `POST /api/skills/{skill_name}/run`.
* `GET /api/skills/runs`.
* `GET /api/telegram/links`.
* `POST /api/telegram/links`.
* `GET /api/telegram/messages`.
* `POST /api/telegram/webhook`.
* `GET /api/entities/{id}/personal/reports/net-worth?as_of=...`.
* `GET /api/entities/{id}/personal/reports/monthly-cash-flow?as_of=...`.
* `GET /api/entities/{id}/personal/reports/debt-payoff-plan?as_of=...`.
* `GET /api/entities/{id}/personal/reports/emergency-fund-plan?as_of=...`.
* `GET /api/entities/{id}/personal/reports/investment-allocation?as_of=...`.
* `GET /api/entities/{id}/personal/reports/business-dependency?as_of=...`.
* `GET /api/entities/{id}/personal/reports/net-worth-change-explanation?date_from=...&date_to=...`.
* `GET /api/entities/{id}/personal/reports/spending-trends-explanation?as_of=...`.
* `GET /api/entities/{id}/business/reports/revenue-by-customer?date_from=...&date_to=...`.
* `GET /api/entities/{id}/business/reports/expenses-by-vendor?date_from=...&date_to=...`.
* `GET /api/entities/{id}/business/reports/gross-margin?date_from=...&date_to=...`.
* `GET /api/entities/{id}/business/reports/runway?as_of=...`.
* `GET /api/entities/{id}/business/reports/tax-reserve?as_of=...`.
* `GET /api/entities/{id}/business/reports/profitability-explanation?date_from=...&date_to=...`.
* `GET /api/entities/{id}/business/reports/cash-flow-risk-explanation?as_of=...`.

Default seed credentials (dev only): `owner@example.com` / `change-me-on-first-login`. Override via `SEED_USER_EMAIL`, `SEED_USER_PASSWORD` env vars.

Phase 1 invariants (enforced in `app/services/journal.py` and `app/api/deps.py`):
* Every posted entry balances (sum debits == sum credits, > 0).
* Each line is single-sided (DB CHECK + service-layer guard).
* Posted entries are immutable; voiding is via paired reversal entry that keeps both on the ledger (`status` becomes `voided` on the original; the reversal stays `posted`).
* All writes require an authenticated session and a per-entity role.
* Reports (`trial_balance`, `general_ledger`) include `posted` and `voided` entries; `draft` never counts.
* All sensitive actions write to `audit_logs` with a redacted before/after.

Phase 2 invariants (enforced in `app/services/personal.py`):
* Personal endpoints reject business entities (`entity.mode` must be `personal`).
* Budget lines must point to expense accounts.
* Savings transfers are excluded from expense/budget actuals because reports derive from expense-account postings only.
* Debt creation and investment-account creation require explicit `confirmed=true`.
* Personal dashboard KPIs are deterministic and ledger-derived where possible.
* Goal progress can derive from linked accounts; debt balances can derive from linked liability accounts.
* Investment tracking is advisory only and must surface a risk disclaimer.

Phase 3 status:
* Business endpoints reject personal entities (`entity.mode` must be `business`).
* Invoice posting creates accrual-basis ledger entries: debit `1200` AR, credit income accounts from invoice lines.
* Bill posting creates accrual-basis ledger entries: debit expense/asset accounts from bill lines, credit `2100` AP.
* Customer payments post `Dr 1110 / Cr 1200`; vendor payments post `Dr 2100 / Cr 1110`.
* AR/AP aging is computed from open posted/partial invoices and bills using `balance_due` and due dates.
* Balance sheet, income statement, cash flow, and dashboard are deterministic and derive from posted ledger balances.
* Tax reserve reports must still be labeled as estimates until jurisdiction-specific tax logic exists.

Phase 4 status:
* Ingestion models live in `app/models/ingestion.py`; service logic lives in `app/services/ingestion.py`; API lives in `app/api/documents.py`.
* File storage currently uses existing `attachments` as the persisted file record; the phase-specific metadata tables are `import_batches`, `document_extractions`, and `extraction_candidates`.
* Receipt extraction is currently deterministic text parsing, not full binary OCR. Tests use text receipts; future work can plug Tesseract into the same extraction model.
* Candidate approval creates a draft journal entry linked back to the `source_transaction` and updates the attachment to keep the original document attached.
* CSV import creates `source_transactions` with `kind="csv_row"` and marks batch counts in `import_batches`.
* Signed download URLs are generated through MinIO presigned URLs; audit file access through the document routes.

Phase 5 status:
* Web files live under `apps/web/app`.
* Current route coverage includes `/login`, `/dashboard`, `/personal`, `/business`, `/documents`, `/skills`, `/settings`, `/audit-log`, and placeholder anchors for budget/goals/debts/investments/accounts/ledger/invoices/bills/reports.
* The app shell includes sidebar navigation, entity switcher, and logout flow.
* `documents/page.tsx` uploads receipts and CSV files into Phase 4 endpoints.
* The Next production build is currently failing in-container during prerender. Do not claim Phase 5 complete until `docker compose exec -T web npm run build` passes.

Phase 6 status:
* Agent route lives in `app/api/agent.py`; core service lives in `app/services/agent.py`; payloads live in `app/schemas/agent.py`.
* Providers currently share a deterministic heuristic planning path through `HeuristicProvider`, `OpenAIProvider`, `AnthropicProvider`, and `GeminiProvider`. This keeps the interface in place without requiring external API calls during local development.
* The tool registry is typed with Pydantic and currently implements: `create_journal_entry_draft`, `post_journal_entry`, `create_personal_expense`, `create_invoice`, `get_personal_summary`, `get_business_summary`, `get_balance_sheet`, `get_income_statement`, `get_cash_flow`, `suggest_emergency_fund_plan`, `suggest_investment_allocation`, and `explain_transaction`.
* Memory tools are now wired: `search_memory` and `add_memory` route into the Phase 7 memory service. Remaining later-phase tools still return `status="not_implemented"` rather than pretending automation already exists.
* `PolicyEngine` blocks forbidden real-money / trade actions. `ConfirmationEngine` requires confirmation for sensitive posting/payment-style tools. Audit logs record prompts and tool calls with redaction.
* Tests for the agent core live in `apps/api/tests/test_agent_core.py`.

Phase 7 status:
* Memory models live in `app/models/memory.py`: `Memory`, `MemoryEmbedding`, `MemoryEvent`, and `MemoryReview`.
* Current memory search is deterministic text search with redacted-text embedding metadata stored in `memory_embeddings`; this is enough for correctness without depending on a live embedding provider.
* Memory writes require `consent_granted=true` and reject obvious credential-like content.
* `delete` is implemented as a "forget this" soft-delete (`is_active=false` plus event/audit trail), not as destructive row removal.
* Every memory create/update/review/expire/delete route writes normal audit logs, and the memory service itself appends `memory_events`.
* Tests for the memory slice live in `apps/api/tests/test_memory.py`.

Phase 8 status:
* Heartbeat models live in `app/models/heartbeat.py`: `HeartbeatRun`, `Alert`, and `GeneratedReport`.
* The implemented heartbeat types are currently: `daily_personal_check`, `daily_business_check`, and `weekly_business_report`. Other contract heartbeat types remain future work.
* `run_heartbeat()` persists a run record, creates alerts/reports deterministically from current finance data, and writes heartbeat audit logs for both manual and scheduler-triggered runs.
* Personal checks currently flag low emergency funds, debts due within 7 days, and current-period budget overspends.
* Business checks currently flag low cash runway, overdue invoices/bills, and tax-reserve gaps.
* Weekly business reports are stored in `generated_reports` as markdown text.
* The scheduler no longer just logs `tick`; it now POSTs to the internal heartbeat endpoint using `API_HEARTBEAT_URL` and `AUTOMATION_TOKEN`.
* Tests for the heartbeat slice live in `apps/api/tests/test_heartbeat.py`.

Phase 9 status:
* Skill models live in `app/models/skill.py`: `SkillState` and `SkillRunLog`.
* Skill service logic lives in `app/services/skills.py`; API lives in `app/api/skills.py`; payloads live in `app/schemas/skill.py`; migration is `0007_skills_engine.py`.
* Built-in skills currently registered include `receipt_reader`, `invoice_reader`, `transaction_classifier`, `personal_budget_coach`, `emergency_fund_planner`, `debt_payoff_planner`, `investment_allocator`, `business_health_advisor`, `ar_collector`, `ap_scheduler`, `tax_reserve_estimator`, `monthly_close_assistant`, `anomaly_detector`, and `weekly_reporter`.
* Skills load during API startup. The loader checks both repo-root `skills/` and `apps/api/skills/` because the dev `api` container bind-mounts only `./apps/api`.
* Built-in skills default to enabled; tenant-specific enable/disable state persists in `skill_states`.
* Skill executions are persisted in `skill_run_logs` with inputs, outputs, declared permissions, version, entity/user scope, and result status.
* Declared permissions are validated at load time and enforced by the built-in execution paths before they call finance, memory, document, or reporting services.
* The web scaffold now includes `/skills`, which lists installed skills and their permissions/triggers. The broader Next production build blocker from Phase 5 still remains unresolved.
* Tests for the skills slice live in `apps/api/tests/test_skills.py`.

Phase 10 status:
* Telegram models live in `app/models/telegram.py`: `TelegramLink` and `TelegramMessage`, plus enums for direction, type, and status.
* Telegram service logic lives in `app/services/telegram.py`; API lives in `app/api/telegram.py`; payloads live in `app/schemas/telegram.py`; migration is `0008_telegram.py`.
* Telegram access is allowlist-based: a `telegram_links` row must exist for the inbound `telegram_user_id` + `telegram_chat_id`, otherwise the webhook rejects the message and logs a rejected outbound reply.
* The link record stores both personal and business entity IDs plus an active mode so `/personal` and `/business` can switch routing deterministically without cross-tenant lookups.
* Inbound and outbound chat traffic is persisted in `telegram_messages` with direction, message type, status, text/file metadata, and raw payload JSON.
* Implemented Telegram commands are `/start`, `/personal`, `/business`, `/summary`, `/budget`, `/cash`, and `/help`.
* Known text requests fall through to the existing agent for personal chat flows; business expense phrases like `El negocio pagó $150 de internet.` are drafted directly into balanced business journal entries and left unposted pending confirmation elsewhere in the product.
* Image/PDF uploads are accepted and acknowledged as queued document-review items; voice notes are persisted and acknowledged with a transcription-placeholder reply.
* A simple per-link rate limit is enforced from the persisted message log. Authorized inbound/outbound processing writes normal audit logs with `object_type="telegram_message"`.
* Tests for the Telegram slice live in `apps/api/tests/test_telegram.py`.

Phase 11 status:
* Personal report extensions live in `app/services/personal.py` and are exposed from `app/api/personal.py`.
* Business report extensions live in `app/services/business.py` and are exposed from `app/api/business.py`.
* New personal deterministic reports include net worth statements, monthly cash-flow summaries, debt payoff plans, emergency fund plans, investment allocation summaries, and explicit business-dependency reports.
* New business deterministic reports include revenue by customer, expenses by vendor, gross margin, runway, and tax reserve reports.
* Explanation endpoints now exist for personal net-worth change, personal spending trends, business profitability, and business cash-flow risk. They return prose plus `cited_facts` built from deterministic report values; they do not call an external model.
* Debt records that are not linked to liability accounts still do not alter ledger-derived net worth. This is intentional and matches the hard rule that report figures come from deterministic accounting state.
* Tests for the Phase 11 slice live in the extended `apps/api/tests/test_personal_dashboard.py` and `apps/api/tests/test_business_reports.py`.

Before recommending or running a Make target, prefer `make help` (it prints the live target list parsed from the `Makefile`) over trusting this table — the Makefile is authoritative.
