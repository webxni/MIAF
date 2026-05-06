# MIAF — Plan de Trabajo por Fases

## Master Prompt para Codex / Claude Code / Gemini CLI

```txt
You are building MIAF, a Docker-first financial AI agent for both personal finances and small business finances.

Product goal:
Create a simple but solid financial assistant that helps one user manage:
1. Personal finances.
2. A small business / PyME.
3. Shared dependency between both, when the person’s income, owner draws, taxes, business cash flow, and personal budget are connected.

The app must run fully in Docker using Docker Compose.

Core principles:
- Accounting-first, AI-second.
- Use double-entry accounting for all financial records.
- Separate personal and business modes, but allow linked transfers between them.
- Every financial event must be traceable.
- Every AI action must be auditable.
- Never move money automatically.
- Never execute investments automatically.
- Never promise guaranteed returns.
- Always require confirmation for sensitive actions.
- Use deterministic calculations for financial statements and KPIs.
- Use LLMs only for classification, explanation, coaching, extraction, and planning.
- Keep tax logic jurisdiction-aware but not hardcoded to one country.
- Default jurisdiction: unspecified.
- Docker must include all services needed for local operation.

Tech stack:
- Backend: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, pgvector, Redis, Celery or RQ.
- Frontend: Next.js, TypeScript, Tailwind, shadcn/ui, Recharts.
- AI provider abstraction: OpenAI, Anthropic, Gemini.
- OCR: Tesseract first, pluggable later.
- Audio: Whisper-compatible transcription.
- Storage: local volume first, S3-compatible later.
- Auth: local email/password first.
- Deployment: Docker Compose.

Docker services:
- api
- web
- worker
- scheduler
- postgres
- redis
- minio
- tesseract/ocr service if needed
- optional local llm gateway placeholder
- nginx or caddy reverse proxy
- backup service

Architecture:
- apps/api
- apps/web
- services/worker
- services/scheduler
- packages/shared
- skills
- infra
- docs
- tests

The system must support:
- Chart of accounts.
- Journal entries.
- Journal lines.
- General ledger.
- Personal net worth.
- Personal budget.
- Emergency fund.
- Debt payoff.
- Savings goals.
- Investment allocation suggestions.
- Business balance sheet.
- Business income statement.
- Business cash flow.
- Customers.
- Vendors.
- Invoices.
- Bills.
- Accounts receivable.
- Accounts payable.
- Owner contributions.
- Owner draws.
- Business-to-personal transfers.
- Tax reserve tracking.
- Dashboard.
- Chat.
- Telegram integration.
- OCR receipt/invoice parsing.
- Memory.
- Heartbeat.
- Skills.
- Audit logs.
- Backups.

Deliver production-quality code with tests, migrations, Docker files, documentation, and security controls.
```

---

## Phase 0 — Docker-first Monorepo

```txt
Task Phase 0: Create the Docker-first MIAF monorepo.

Create a complete monorepo with:

Structure:
- apps/api
- apps/web
- services/worker
- services/scheduler
- packages/shared
- skills
- infra/docker
- infra/scripts
- docs
- tests

Docker Compose services:
- api: FastAPI backend
- web: Next.js frontend
- worker: background job worker
- scheduler: scheduled jobs and heartbeat runner
- postgres: PostgreSQL with pgvector
- redis: queue/cache
- minio: local object storage
- nginx or caddy: reverse proxy
- backup: database backup container

Requirements:
- Everything must run with `docker compose up`.
- No service should require local host dependencies except Docker.
- Provide `.env.example`.
- Provide health checks.
- Provide persistent Docker volumes.
- Provide startup scripts.
- Provide Makefile.

Security:
- Do not run containers as root unless unavoidable.
- Use internal Docker networks.
- Do not expose Postgres or Redis publicly.
- Store secrets only in environment variables.
- Add `.gitignore` for secrets and volumes.
- Create separate dev and production compose files.

Acceptance criteria:
- `docker compose up --build` starts all services.
- API health endpoint returns OK.
- Web app loads.
- Postgres has pgvector enabled.
- Redis is reachable by worker.
- MinIO is reachable by API.
- README explains local setup.
```

---

## Phase 1 — Accounting Core

```txt
Task Phase 1: Build the accounting core.

Implement double-entry accounting as the foundation.

Database models:
- tenants
- users
- entities
- entity_members
- accounts
- journal_entries
- journal_lines
- source_transactions
- attachments
- audit_logs

Entity modes:
- personal
- business

Rules:
- Every posted journal entry must balance.
- Total debits must equal total credits.
- Accounts must have type:
  - asset
  - liability
  - equity
  - income
  - expense
- Accounts must have normal side:
  - debit
  - credit
- Support hierarchical chart of accounts.
- Support personal chart of accounts.
- Support business chart of accounts.
- Support linked personal/business transfer entries.

Required APIs:
- CRUD accounts
- CRUD journal entries
- post journal entry
- void journal entry
- get general ledger
- get trial balance

Security:
- All write operations require authenticated user.
- Posted entries cannot be edited directly.
- Corrections must use reversal or adjustment entries.
- Every create/update/post/void action must create audit log.
- Validate tenant isolation on every query.
- Add permission middleware.

Acceptance criteria:
- Migration runs.
- Seed creates one personal entity and one business entity.
- Seed creates default charts of accounts.
- Tests prove balanced entries can post.
- Tests prove unbalanced entries cannot post.
- Tests prove posted entries are immutable.
```

---

## Phase 2 — Personal Finance Mode

```txt
Task Phase 2: Build personal finance mode.

Implement personal finance features on top of the accounting core.

Features:
- Personal dashboard.
- Personal net worth.
- Monthly budget.
- Emergency fund.
- Savings goals.
- Debt tracking.
- Basic investment tracking.
- Cash flow summary.
- Spending by category.
- Personal-to-business dependency tracking.

Models:
- budgets
- budget_lines
- goals
- debts
- investment_accounts
- investment_holdings
- net_worth_snapshots

Personal KPIs:
- net worth
- monthly income
- monthly expenses
- monthly savings
- savings rate
- emergency fund months
- debt-to-income ratio
- total debt
- investment allocation
- goal progress

Rules:
- Savings transfers are not expenses.
- Credit card payments are transfers/liability reductions, not expenses.
- Business owner draws affect personal cash but are not salary unless classified.
- Personal expenses paid by business must be flagged for review.

Security:
- Investment module must be advisory only.
- No investment execution.
- No guarantees of returns.
- Display risk disclaimer for investment suggestions.
- Require confirmation before creating debt, investment, or large transfer records.

Acceptance criteria:
- User can create budget and goals.
- Dashboard calculates personal KPIs deterministically.
- User can track emergency fund.
- User can track debts.
- User can track investment allocation manually.
- Tests verify savings rate, net worth, and emergency fund months.
```

---

## Phase 3 — Business / PyME Finance Mode

```txt
Task Phase 3: Build small business finance mode.

Implement business accounting and financial statements.

Features:
- Business dashboard.
- Customers.
- Vendors.
- Invoices.
- Bills.
- Accounts receivable.
- Accounts payable.
- Business income statement.
- Balance sheet.
- Cash flow statement.
- Owner contributions.
- Owner draws.
- Tax reserve tracking.
- Simple closing checklist.

Models:
- customers
- vendors
- invoices
- invoice_lines
- bills
- bill_lines
- payments
- tax_rates
- tax_reserves
- closing_periods

Business statements:
- Balance Sheet
- Income Statement / Profit and Loss
- Cash Flow Statement
- Trial Balance
- General Ledger
- AR Aging
- AP Aging

Rules:
- Invoice issued on accrual basis:
  Debit Accounts Receivable.
  Credit Revenue.
- Customer payment:
  Debit Cash.
  Credit Accounts Receivable.
- Vendor bill:
  Debit Expense or Asset.
  Credit Accounts Payable.
- Vendor payment:
  Debit Accounts Payable.
  Credit Cash.
- Owner contribution:
  Debit Cash.
  Credit Owner Equity.
- Owner draw:
  Debit Owner Draws.
  Credit Cash.

Security:
- Business reports must be deterministic.
- Tax calculations must be labeled as estimates unless jurisdiction is configured.
- Require confirmation for posting invoices, bills, payments, owner draws, and tax reserve adjustments.
- Maintain audit trail for all financial statement source records.

Acceptance criteria:
- User can create customer and invoice.
- User can record payment.
- AR aging updates.
- User can create vendor bill.
- AP aging updates.
- Balance sheet balances.
- Income statement matches posted ledger.
- Cash flow derives from ledger.
```

---

## Phase 4 — Ingestion, Documents, OCR, and Files

```txt
Task Phase 4: Build ingestion and document processing.

Implement ingestion for receipts, invoices, PDFs, images, CSVs, and manual entries.

Features:
- Upload file.
- Store file in MinIO.
- OCR image/PDF.
- Parse receipt.
- Parse invoice.
- Import CSV bank transactions.
- Create source transaction records.
- Suggest journal entries.
- Attach source documents to journal entries.

Models:
- files
- import_batches
- source_transactions
- document_extractions
- extraction_candidates

OCR pipeline:
File upload → storage → OCR → structured extraction → confidence score → suggested accounting treatment → review queue.

Rules:
- OCR never posts directly unless user setting allows and confidence is very high.
- Low confidence requires user review.
- Every document must keep original file hash.
- Every extracted field must include confidence.
- Duplicate detection by file hash, amount, date, merchant, invoice number.

Security:
- Limit file types.
- Limit file size.
- Scan file MIME type.
- Never execute uploaded files.
- Store files outside web root.
- Use signed URLs for downloads.
- Audit all file access.

Acceptance criteria:
- User can upload receipt.
- OCR extracts merchant, date, total.
- System suggests expense entry.
- User can approve suggested entry.
- Original receipt remains attached.
- CSV import creates source transactions.
```

---

## Phase 5 — Web Dashboard

```txt
Task Phase 5: Build the dashboard UI.

Implement a clean dashboard for both personal and business modes.

Pages:
- /login
- /dashboard
- /personal
- /personal/budget
- /personal/goals
- /personal/debts
- /personal/investments
- /business
- /business/accounts
- /business/ledger
- /business/invoices
- /business/bills
- /business/reports
- /documents
- /chat
- /skills
- /memory
- /settings
- /audit-log

Components:
- Sidebar
- Entity switcher
- Mode switcher
- Stat cards
- Charts
- Tables
- Review queue
- Journal entry viewer
- Financial statement viewer
- Document preview
- Confirmation modal
- Risk warning banner

Personal widgets:
- Net worth
- Income
- Expenses
- Savings rate
- Emergency fund months
- Debt progress
- Goal progress
- Investment allocation

Business widgets:
- Cash
- Revenue
- Expenses
- Net income
- AR
- AP
- Runway
- Gross margin
- Balance sheet summary
- Cash flow summary

Security:
- Protect all routes.
- Hide sensitive values by toggle.
- Add session timeout.
- Add audit view for user.
- Never expose raw secrets to frontend.
- Validate all inputs with schemas.

Acceptance criteria:
- User can switch between personal and business views.
- Reports display correctly.
- Charts load from API.
- Review queue works.
- Sensitive actions require confirmation.
```

---

## Phase 6 — AI Agent Core and Financial Tools

```txt
Task Phase 6: Build the AI agent core.

Create a financial agent that can chat with the user and call typed tools.

Core components:
- AgentService
- LLMProvider interface
- OpenAIProvider
- AnthropicProvider
- GeminiProvider
- ToolRegistry
- PolicyEngine
- ConfirmationEngine
- AgentMemoryContextBuilder
- AgentAuditLogger

Tools:
- create_journal_entry_draft
- post_journal_entry
- create_personal_expense
- create_business_expense
- create_invoice
- record_invoice_payment
- create_bill
- record_bill_payment
- get_personal_summary
- get_business_summary
- get_balance_sheet
- get_income_statement
- get_cash_flow
- create_budget
- create_goal
- create_debt_plan
- suggest_emergency_fund_plan
- suggest_investment_allocation
- classify_transaction
- explain_transaction
- search_memory
- add_memory

Agent behavior:
- The agent can explain finances.
- The agent can suggest actions.
- The agent can draft records.
- The agent cannot post sensitive records without confirmation.
- The agent cannot move real money.
- The agent cannot execute trades.
- The agent must say when advice is educational, not legal/tax/investment advice.

Security:
- Tool calls must be typed.
- Validate all tool inputs with Pydantic.
- Policy engine blocks forbidden actions.
- Confirmation required for sensitive actions.
- Audit every prompt, tool call, result, and final action.
- Redact secrets from logs.
- Add prompt injection defenses for documents and messages.
- Uploaded documents are untrusted input.

Acceptance criteria:
- User can say: "Gasté $35 en gasolina personal."
- Agent drafts and posts only after allowed confirmation.
- User can say: "Mi negocio vendió $1,200 a Cliente X."
- Agent creates invoice draft.
- Agent can explain balance sheet.
- Agent can compare personal and business cash flow.
```

---

## Phase 7 — Financial Memory

```txt
Task Phase 7: Build financial memory.

Implement durable memory for preferences, rules, goals, business context, and recurring patterns.

Models:
- memories
- memory_embeddings
- memory_events
- memory_reviews

Memory types:
- user_profile
- personal_preference
- business_profile
- financial_rule
- merchant_rule
- tax_context
- goal_context
- risk_preference
- recurring_pattern
- advisor_note

Features:
- Add memory.
- Search memory.
- Review memory.
- Delete memory.
- Expire memory.
- Promote observation to durable memory.
- Show memory in dashboard.

Rules:
- Do not store sensitive credentials in memory.
- Do not store bank passwords.
- Store only useful financial context.
- Allow user to edit/delete memory.
- Every memory write must be audited.

Security:
- Memory is tenant-isolated.
- Embeddings must not include secrets.
- Redact sensitive fields before embedding.
- Add memory consent setting.
- Add "forget this" endpoint.

Acceptance criteria:
- Agent remembers preferred budget method.
- Agent remembers business tax reserve percentage.
- Agent remembers recurring vendors.
- User can inspect and delete memories.
```

---

## Phase 8 — Heartbeat, Scheduler, and Alerts

```txt
Task Phase 8: Build heartbeat and scheduled financial checks.

Implement proactive financial review.

Services:
- scheduler
- heartbeat runner
- alert engine
- report generator

Heartbeat types:
- daily_personal_check
- weekly_personal_report
- monthly_personal_close
- daily_business_check
- weekly_business_report
- monthly_business_close
- tax_reserve_check
- cash_runway_check
- budget_overspend_check
- AR/AP aging check

Daily personal check:
- Budget overspending.
- Unusual spending.
- Emergency fund progress.
- Large transactions.
- Debt due dates.
- Missing categories.

Daily business check:
- Cash balance.
- Upcoming bills.
- Overdue invoices.
- Unusual expenses.
- Low runway.
- Tax reserve gaps.
- Unreconciled transactions.

Security:
- Heartbeat cannot post entries unless explicitly configured.
- Default heartbeat can only create alerts and drafts.
- Heartbeat must respect quiet hours.
- Heartbeat must log start, decisions, and result.
- Heartbeat must avoid repeated spam alerts.

Acceptance criteria:
- Heartbeat runs manually.
- Heartbeat runs on schedule.
- Alerts appear in dashboard.
- Weekly report is generated.
- All heartbeat actions are audited.
```

---

## Phase 9 — Skills Engine

```txt
Task Phase 9: Build skills engine.

Create local installable skills inspired by OpenClaw-style skills, but focused on finance.

Skill format:
- skills/<skill_name>/SKILL.yaml
- skills/<skill_name>/README.md
- skills/<skill_name>/handler.py

SKILL.yaml fields:
- name
- version
- description
- mode: personal, business, both
- permissions
- triggers
- tools_used
- requires_confirmation
- risk_level
- entrypoint

Built-in skills:
- receipt_reader
- invoice_reader
- transaction_classifier
- personal_budget_coach
- emergency_fund_planner
- debt_payoff_planner
- investment_allocator
- business_health_advisor
- ar_collector
- ap_scheduler
- tax_reserve_estimator
- monthly_close_assistant
- anomaly_detector
- weekly_reporter

Permissions:
- read_transactions
- write_drafts
- post_entries
- read_documents
- write_documents
- read_memory
- write_memory
- read_reports
- send_messages

Security:
- Skills are disabled by default if third-party.
- Built-in skills can be enabled by default.
- Third-party skills require explicit enable.
- Skill permissions must be enforced.
- Skill execution must be logged.
- No skill can access secrets directly.
- No skill can execute shell commands by default.
- Add sandbox placeholder for future isolation.

Acceptance criteria:
- Skills load at startup.
- Skills appear in dashboard.
- User can enable/disable skills.
- Skill run logs show inputs, outputs, permissions, and result.
```

---

## Phase 10 — Telegram Integration

```txt
Task Phase 10: Add Telegram integration.

Implement Telegram bot as the first external chat channel.

Features:
- Receive text.
- Receive images.
- Receive PDFs.
- Receive voice notes.
- Send replies.
- Link Telegram user to MIAF user.
- Route message to personal or business entity.
- Create events and messages.
- Send agent responses.

Commands:
- /start
- /personal
- /business
- /summary
- /budget
- /cash
- /help

Examples:
- "Gasté $20 en comida personal."
- "El negocio pagó $150 de internet."
- "Cliente Juan pagó la factura 0003."
- "Muéstrame mi flujo de caja."

Security:
- Verify Telegram user allowlist.
- Do not allow unknown users.
- Rate limit inbound messages.
- Treat all messages and files as untrusted.
- Audit every inbound and outbound message.
- Require confirmation for posting sensitive entries.

Acceptance criteria:
- User can send personal expense.
- User can send business expense.
- User can upload receipt.
- User can ask for summary.
- Unknown users are rejected.
```

---

## Phase 11 — Reports and Advanced Analysis

```txt
Task Phase 11: Build reports and analysis.

Implement deterministic reports plus AI explanations.

Reports:
Personal:
- Net worth statement.
- Monthly cash flow.
- Budget vs actual.
- Debt payoff plan.
- Emergency fund plan.
- Investment allocation summary.
- Personal/business dependency report.

Business:
- Balance sheet.
- Income statement.
- Cash flow statement.
- Trial balance.
- General ledger.
- AR aging.
- AP aging.
- Revenue by customer.
- Expenses by vendor.
- Gross margin.
- Runway.
- Tax reserve report.

AI explanations:
- Explain why net worth changed.
- Explain spending trends.
- Explain business profitability.
- Explain cash flow risk.
- Suggest next actions.

Rules:
- Numbers must come from deterministic functions.
- AI can only explain numbers, not invent them.
- Every report must include date range and entity.
- Every report must be exportable to PDF/CSV later.

Security:
- Reports respect tenant and entity permissions.
- Sensitive reports require authenticated session.
- Export actions are audited.

Acceptance criteria:
- Reports match ledger.
- Balance sheet balances.
- Income statement ties to ledger.
- Cash flow is reproducible.
- AI explanation cites report data internally.
```

---

## Phase 12 — Security Hardening, Backups, and Production Readiness

```txt
Task Phase 12: Security hardening, backups, and production readiness.

Implement security controls across the system.

Authentication:
- Local email/password.
- Password hashing with Argon2 or bcrypt.
- Session cookies httpOnly and secure.
- Optional MFA placeholder.

Authorization:
- Tenant isolation.
- Entity-level permissions.
- Role-based access:
  - owner
  - admin
  - accountant
  - viewer
  - agent

Audit:
- Log all sensitive actions.
- Log login attempts.
- Log exports.
- Log AI tool calls.
- Log financial postings.
- Protect audit logs from modification.

Data protection:
- Encrypt secrets.
- Redact logs.
- Add backup service.
- Daily Postgres backup.
- Backup retention policy.
- Restore script.
- MinIO backup plan.

Network:
- Internal Docker networks.
- Only expose reverse proxy.
- Do not expose DB/Redis.
- Add CORS allowlist.
- Add rate limits.

AI safety:
- Prompt injection defenses.
- Treat documents as untrusted.
- Tool permission enforcement.
- Confirmation for sensitive actions.
- No autonomous money movement.
- No autonomous investment execution.

Acceptance criteria:
- Security checklist documented.
- Backups run.
- Restore script tested.
- Audit logs cannot be edited through API.
- Sensitive endpoints require auth.
- Rate limits active.
```

---

## Phase 13 — End-to-End Integration Test

```txt
Task Phase 13: End-to-end integration test.

Create a complete demo flow.

Scenario:
A user owns a small business and also depends on that business for personal income.

Demo data:
- Personal checking account.
- Personal credit card.
- Emergency fund.
- Business operating bank account.
- Customer.
- Vendor.
- Invoice.
- Bill.
- Owner draw.
- Tax reserve.
- Personal budget.

Test flow:
1. User logs in.
2. User creates personal and business entities.
3. User imports bank CSV.
4. User uploads receipt.
5. OCR suggests transaction.
6. User approves.
7. User creates customer invoice.
8. Customer payment is recorded.
9. User records owner draw from business to personal.
10. Personal budget updates.
11. Business balance sheet updates.
12. Business income statement updates.
13. Personal net worth updates.
14. Heartbeat detects low tax reserve or budget issue.
15. Weekly report is generated.
16. Audit log shows full trace.

Acceptance criteria:
- Full flow works in Docker.
- No manual DB edits.
- All tests pass.
- Dashboard reflects correct numbers.
- Reports are consistent.
- Audit trail is complete.
```

---

## Recommended Build Order

```txt
0 Docker/monorepo
1 Accounting core
2 Personal finance mode
3 Business finance mode
4 OCR/ingestion
5 Dashboard
6 Agent core
7 Memory
8 Heartbeat
9 Skills
10 Telegram
11 Reports
12 Security
13 E2E
```

## Final Product Direction

MIAF should not start as a chatbot with finance features. It should start as a reliable accounting and finance engine with an AI interface.

The correct product sequence is:

```txt
Ledger → Ingestion → Reconciliation → Statements/KPIs → Personal Mode → PyME Mode → AI Agent → Skills → Automation
```

The agent should classify, explain, coach, extract, and recommend. The ledger, reports, KPIs, balances, and statements must be produced by deterministic backend logic.
