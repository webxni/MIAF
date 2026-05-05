# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This repo currently contains only `FinClaw.md` — a phased build specification. There is no source code, no `package.json`/`pyproject.toml`, no Dockerfiles, and no git history yet. Treat `FinClaw.md` as the source of truth for architecture, scope, and acceptance criteria. Do not invent additional features, files, or services that the spec does not define.

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

Phases 0 (Docker monorepo) and 1 (Accounting Core) have landed. The Docker Compose stack (`compose.yaml` for dev, `compose.prod.yaml` overlay for prod) is the entry point — no host dependencies beyond Docker.

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

API surface (Phase 1):

* `POST /api/auth/login` `{email, password}` → sets httpOnly `finclaw_session` cookie.
* `POST /api/auth/logout`, `GET /api/auth/me`.
* `GET/POST /api/entities`, `GET/PATCH /api/entities/{id}`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/accounts[/{id}]`.
* `GET/POST/PATCH/DELETE /api/entities/{id}/journal-entries[/{id}]` plus `/post` and `/void`.
* `GET /api/entities/{id}/ledger?account_id=...&date_from=...&date_to=...`.
* `GET /api/entities/{id}/trial-balance?as_of=...`.

Default seed credentials (dev only): `owner@example.com` / `change-me-on-first-login`. Override via `SEED_USER_EMAIL`, `SEED_USER_PASSWORD` env vars.

Phase 1 invariants (enforced in `app/services/journal.py` and `app/api/deps.py`):
* Every posted entry balances (sum debits == sum credits, > 0).
* Each line is single-sided (DB CHECK + service-layer guard).
* Posted entries are immutable; voiding is via paired reversal entry that keeps both on the ledger (`status` becomes `voided` on the original; the reversal stays `posted`).
* All writes require an authenticated session and a per-entity role.
* Reports (`trial_balance`, `general_ledger`) include `posted` and `voided` entries; `draft` never counts.
* All sensitive actions write to `audit_logs` with a redacted before/after.

Before recommending or running a Make target, prefer `make help` (it prints the live target list parsed from the `Makefile`) over trusting this table — the Makefile is authoritative.
