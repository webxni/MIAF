# MIAF — Mayordomo IA Financiero

Administra con sabiduría.

MIAF is a local-first financial operations app and AI agent for people who want one place to manage personal finances, owner finances, and small-business bookkeeping. It combines a deterministic accounting backend with an AI chat interface, document ingestion, draft journal workflows, heartbeat monitoring, and built-in analytical skill packs.

The product position in the codebase is simple:

- Deterministic numbers first.
- AI explanations and suggestions second.
- Human confirmation before sensitive write actions.
- No money movement, no trading, no tax filing.

The full build spec lives in [MIAF.md](./MIAF.md). Contributor guardrails live in [CLAUDE.md](./CLAUDE.md).
The ingestion pipeline, supported file types, review flow, and safety model are documented in [docs/INGESTION.md](./docs/INGESTION.md).

## What MIAF Is

MIAF gives a single owner a workspace with:

- A personal entity and a business entity.
- Double-entry bookkeeping with draft and posted journal entries.
- AI-assisted chat for summaries, analysis, and guided actions.
- CSV and receipt ingestion into a review queue.
- Alerts and generated reports from scheduled heartbeat runs.
- Local Docker infrastructure for the full stack.

Today, MIAF is best suited for:

- Solo operators managing personal and business finances together.
- Small business owners who want AI-assisted bookkeeping support without handing control to an autonomous system.
- Developers who want a self-hosted financial app with a clear backend, audit trail, and conservative execution model.

## What Works Today

The current repo ships a working monorepo with:

- FastAPI backend in `apps/api`.
- Next.js frontend in `apps/web`.
- Postgres + pgvector, Redis, MinIO, Caddy, worker, scheduler, and backup services in Docker Compose.
- Owner account creation through `/onboarding`.
- Session-based login.
- Tenant, user, entity, account, journal, audit-log, memory, settings, skills, heartbeat, and document APIs.
- Personal and business dashboards.
- Agent chat in `/agent`.
- Dedicated memory management in `/memory`.
- Settings page in `/settings` for accounting defaults and AI provider credentials.
- Team invite management in `/settings` for owner/admin users.
- Document upload and review queue in `/documents`.
- Telegram link and message management in `/telegram`.
- Built-in skill packs for accounting, personal finance, and Python-based finance calculations.
- Scheduler-driven heartbeat runs that create alerts and reports.
- Automated database backups in Docker.

## Planned Or Still In Progress

These areas are present only partially or are explicitly not finished yet:

- PDF OCR for receipt parsing is not supported yet. PDF receipts upload, but parsing can fall back to a review-only path.
- Email alerts are not implemented yet. Current alerting is in-product, with Telegram integration also present in the backend.
- Broader multi-tenant collaboration is still limited. Team invites exist, but the product is still optimized around an owner-led workspace.
- Skill proposal review is not implemented yet.
- Some agent tools are intentionally registered as reserved or not implemented for later phases, even if the tool names already exist in code.
- Production hardening still depends on your own operations choices for off-host backups, secret rotation, and infrastructure monitoring.

## Product Flow

### 1. Create the first account with `/onboarding`

On a fresh install, visit `/onboarding`.

- This route is available only before the first user exists.
- Submitting the form creates the owner account, tenant, session, and default personal and business entities.
- The onboarding page currently asks for:
  - name
  - email
  - password
- Password minimum is 12 characters.

If MIAF is already set up, `/onboarding` redirects you back toward login.

### 2. Configure AI providers in `/settings`

After login, open `/settings`.

Current settings UI supports:

- Jurisdiction
- Base currency
- Fiscal year start month
- AI provider
- AI model
- AI API key

Supported provider choices in the current code:

- `heuristic`
- `anthropic`
- `openai`
- `gemini`

Important behavior:

- The heuristic provider works without an external API key.
- Provider API keys are stored server-side as encrypted ciphertext.
- The UI only receives a last-four-character hint for an already stored key.
- If no external key is configured, `/agent` can still fall back to deterministic heuristic behavior for supported prompts.

### 2.1 Manage team invites in `/settings`

Owner and admin users can invite teammates from the `Team invites` section in `/settings`.

- Create an invite by entering the teammate email and role.
- Copy the one-time `/accept-invite` link immediately after creation and send it through your own secure channel.
- Revoke any pending invite before it is accepted.

Invite acceptance flow:

- The invited user opens `/accept-invite?token=...`.
- They enter their name and a password with at least 12 characters.
- MIAF creates the user, grants workspace memberships, creates a session, and redirects them to `/dashboard`.

Role notes:

- `admin` can manage most workspace operations.
- `accountant` can work on accounting flows without owner-level administration.
- `viewer` has read-oriented access.

### 3. Use `/agent`

The agent introduces itself as:

`MIAF, tu Mayordomo IA Financiero.`

The `/agent` page supports:

- freeform prompts
- tool planning
- deterministic summaries
- draft creation flows
- explicit confirmation for sensitive actions

Examples already reflected in the UI and backend:

- explain the balance sheet
- compare personal and business cash flow
- draft a personal expense entry from a natural-language message
- draft a business invoice from a sale description
- search or add memory when consent is provided

The agent does not silently finalize risky accounting writes. Sensitive tools surface confirmation prompts in the chat before execution.

### 4. Upload receipts and CSVs in `/documents`

The `/documents` page has two ingestion paths:

- receipt uploads
- CSV imports

Receipt behavior today:

- files are uploaded into document storage
- supported extractions can be parsed
- unsupported PDF OCR cases are accepted and queued for review

CSV behavior today:

- a CSV import is uploaded against an entity
- imported rows create draft journal entries
- the page then reloads the pending draft queue

### 5. Review draft journal entries and corrections

The review queue in `/documents` is the current human-in-the-loop accounting workflow.

What happens after CSV import:

- MIAF creates pending draft journal entries.
- Each draft is shown with source context, amount, and proposed lines.
- You can change the debit-side expense account before approval.
- Approving a draft can first update the selected account, then post the journal entry.
- Declining a draft deletes it from the queue.

This is one of the core safety boundaries in the product: ingestion and agent logic can prepare accounting work, but a human still reviews and approves it.

## Built-In Skill Packs

MIAF currently ships three built-in skill packs:

- `python_finance`
- `accounting`
- `personal_finance`

They are loaded from the backend skill system and used by agent tools and heartbeat jobs.

### `python_finance`

Current scope in the codebase:

- Monte Carlo simulation
- portfolio allocation helpers
- Value at Risk and drawdown calculations
- anomaly detection
- chart-ready data generation

### `accounting`

Current scope in the codebase:

- journal validation
- trial balance generation
- income statement generation
- balance sheet generation
- AR/AP aging helpers
- depreciation helpers
- bank reconciliation helpers

### `personal_finance`

Current scope in the codebase:

- budget variance
- personal cashflow analysis
- emergency fund planning
- debt strategy
- room-for-error scoring
- spending habit analysis
- weekly money meeting planning

Developer details for the skill engine are in [docs/developer-guide-skills.md](./docs/developer-guide-skills.md).

## Memory And Learning

MIAF has memory support, but it is intentionally conservative.

What memory does today:

- stores user-approved notes and contextual finance memories
- supports search by title, content, or summary
- tracks memory events such as creation, access, update, review, deletion, and expiration
- stores a deterministic redacted embedding representation for retrieval support
- can learn merchant classification rules from corrected import drafts

Important constraints:

- memory writes require explicit consent
- obvious credentials and secrets are blocked from storage
- memory can be reviewed, expired, or deleted through the API

How the correction loop works today:

- CSV imports classify outflows into draft journal entries.
- If you change the suggested expense account and then post the corrected draft, MIAF records a merchant rule memory for that merchant.
- Future imports for that merchant can use the remembered account instead of the default keyword classifier.

Current UI surface:

- `/memory` lets you create consented memories, search active memories, review them, expire them, and delete them.

## Heartbeat And Alerts

MIAF includes a scheduler and heartbeat pipeline for recurring checks.

Heartbeat runs currently support daily, weekly, and monthly checks across personal and business entities, including:

- daily personal checks
- weekly personal reports
- monthly personal close checks
- daily business checks
- weekly business reports
- monthly business close checks
- tax reserve checks
- cash runway checks
- budget overspend checks
- AR/AP aging checks

User-facing heartbeat surfaces today:

- `/alerts` for open or resolved alerts
- dashboard widgets for recent alerts
- `/business/reports` for deterministic balance sheet, income statement, AR aging, and AP aging views
- `/api/heartbeat/reports` and related endpoints for generated reports

Internal automation path:

- the scheduler calls `/internal/heartbeat/run-defaults`
- that endpoint requires `AUTOMATION_TOKEN`

The scheduler frequency is controlled with `HEARTBEAT_INTERVAL_SECONDS`.

## Access MIAF from Your Phone with Tailscale

MIAF supports private remote access via [Tailscale Serve](https://tailscale.com/kb/1242/tailscale-serve) — a private link inside your tailnet. This is **not** public internet exposure.

**Quickstart:**

```bash
# On the host machine running MIAF
sudo tailscale up
make tailscale-serve        # sudo tailscale serve --bg http://127.0.0.1:80
make tailscale-serve-status # copy the https://*.ts.net URL and open on your phone
```

Install Tailscale on your phone and sign in to the same tailnet. Then open the URL.

The UI also guides you through setup at **Onboarding → Tailscale** (after account creation) and **Settings → Tailscale private access**.

Full documentation: [docs/TAILSCALE.md](./docs/TAILSCALE.md)

## Telegram

MIAF includes a Telegram integration backend and a frontend setup screen in `/telegram`.

What works today:

- save or update a Telegram link for a workspace user
- map personal mode and business mode to specific entities
- switch active routing mode
- review recent inbound and outbound Telegram message logs

Current command support in the backend:

- `/start`
- `/personal`
- `/business`
- `/summary`
- `/budget`
- `/cash`
- `/help`

Current limitations:

- the app does not create or host a full Telegram bot setup wizard for you
- you still need an external bot or webhook sender to post inbound events to the backend webhook
- voice-note handling is still placeholder behavior

## Safety Limits

MIAF is deliberately narrow about what it will do autonomously.

- No money movement.
- No banking actions.
- No trading execution.
- No tax filing.
- No silent posting of sensitive actions from chat when confirmation is required.
- Human approval is required for risky actions such as sensitive accounting writes.

The system is designed to help with bookkeeping, analysis, and operator review, not to act as an unbounded autonomous finance bot.

## Docker Setup

The default development stack runs with Docker Compose and creates one internal bridge network:

- network name: `miaf_internal`

Services in `compose.yaml`:

- `postgres`
- `redis`
- `minio`
- `api`
- `web`
- `worker`
- `scheduler`
- `caddy`
- `backup`

Host exposure model in development:

- `caddy` publishes `HTTP_PORT` and `HTTPS_PORT`
- MinIO console publishes `127.0.0.1:9001`
- the MinIO S3 API remains internal-only
- API, web, Postgres, Redis, worker, scheduler, and backup stay on the internal Docker network

## Required Environment Variables

For local development, start from `.env.example`.

Core required values:

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`

Frequently used local variables:

- `ENVIRONMENT`
- `LOG_LEVEL`
- `POSTGRES_USER`
- `POSTGRES_DB`
- `MINIO_BUCKET`
- `NEXT_PUBLIC_API_URL`
- `HTTP_PORT`
- `HTTPS_PORT`
- `CADDY_DOMAIN`
- `BACKUP_RETENTION_DAYS`
- `HEARTBEAT_INTERVAL_SECONDS`
- `AUTOMATION_TOKEN`

Additional production-oriented variables are documented in [docs/DEPLOY.md](./docs/DEPLOY.md) and `.env.production.example`.

## How To Run Locally

Prerequisite: Docker and Docker Compose v2.

```bash
make env
$EDITOR .env
make build
make up
make migrate
make smoke
```

Then open:

- app: `http://localhost`
- API through Caddy: `http://localhost/api`
- MinIO console in dev: `http://127.0.0.1:9001`

Notes:

- `make up` starts containers, but you should still run `make migrate` on a fresh database.
- `make seed` is available, but the current seed command is driven by backend seed configuration and is not the main first-user path for normal app setup.
- The intended real first-run flow for users is `/onboarding`.

## Make Commands

Common commands from the current `Makefile`:

| Command | Purpose |
|---|---|
| `make env` | Create `.env` from `.env.example` if missing |
| `make up` | Start the development stack |
| `make down` | Stop the development stack |
| `make build` | Build images |
| `make rebuild` | Rebuild images without cache |
| `make logs` | Tail all logs |
| `make ps` | Show service status |
| `make migrate` | Run Alembic migrations in the API container |
| `make seed` | Run backend seed command |
| `make smoke` | Check health endpoints through Caddy |
| `make test` | Run API tests inside the API container |
| `make api-shell` | Open a shell in the API container |
| `make web-shell` | Open a shell in the web container |
| `make db-shell` | Open a shell in the Postgres container |
| `make redis-shell` | Open a shell in the Redis container |
| `make clean` | Destructive cleanup of containers and volumes |
| `make prod-up` | Start with production compose overlay |
| `make prod-down` | Stop the production overlay stack |

Run `make help` for the full list.

## Network Model

MIAF is designed so the app stack talks mostly over Docker-internal networking.

- Caddy is the main public entrypoint.
- The app stack uses service-to-service communication on `miaf_internal`.
- Health checks and internal automation hit container-local or internal service URLs.
- Production should keep internal services unexposed unless you intentionally add ingress.

This is a local-first deployment model, not a managed SaaS architecture.

## Health Checks

Current health checks in the stack:

- API liveness: `GET /api/health`
- API readiness: `GET /api/health/ready`
- Postgres: `pg_isready`
- Redis: authenticated `redis-cli ping`
- MinIO: `GET /minio/health/live`
- Web: HTTP fetch of `/`

Useful commands:

```bash
make smoke
make ps
docker compose logs --tail=80 api
docker compose logs --tail=80 web
```

## Production Notes

Production deployment is documented in [docs/DEPLOY.md](./docs/DEPLOY.md).

Current production model:

- single VM
- Docker Compose
- Caddy for TLS termination
- internal Docker networking
- local persistent volumes for Postgres, MinIO, and backups

Important notes from the actual deployment docs:

- `/onboarding` is the first-run owner setup path
- API keys configured in `/settings` are encrypted from `SECRET_KEY`
- rotating `SECRET_KEY` makes previously stored provider keys unreadable
- the Postgres app role should be tightened after initial bootstrap
- off-host backups are still your responsibility

## Backups

The `backup` service runs automatically in Docker.

Current behavior:

- dumps the live Postgres database on an interval
- writes dumps into the `backup_data` volume
- uses `BACKUP_INTERVAL_SECONDS`
- prunes old dumps using `BACKUP_RETENTION_DAYS`
- production docs describe restore using `infra/docker/backup/restore.sh`

Operationally, you should still copy backups off-host if you care about recovery beyond single-VM disk failure.

## Troubleshooting

### `/onboarding` does not work

- If an owner already exists, onboarding is intentionally disabled.
- Use `/login` instead.

### The stack starts but the app is broken

- Run `make migrate` against a fresh or updated database.
- Check `make ps` for unhealthy services.
- Check `make logs`, `make api-logs`, or `make web-logs`.

### `/agent` is not using my preferred model

- Check `/settings` and confirm the provider and model are saved.
- If no valid provider key is stored, the app can fall back to heuristic behavior.

### CSV import succeeded but I do not see final entries

- CSV imports create draft journal entries first.
- Open `/documents` and review the pending drafts.
- Approve drafts to post them, or decline them to remove them.

### Receipt upload worked but parsing did not

- PDF OCR is not fully implemented yet.
- The current flow may accept the upload while leaving it queued for review.

### Web container is unhealthy in development

- Check for stale `.next` cache issues in the `web` volume if the dev server fails after route or dependency changes.
- Recreating the `web` container and its cache volume may be necessary in that case.

## Developer Notes

Repo structure:

```text
apps/
  api/      FastAPI application
  web/      Next.js application
services/
  worker/   background worker
  scheduler/ recurring automation and heartbeat runner
infra/
  docker/   Caddy, Postgres init, backup container
docs/
```

Useful developer guidance:

- [docs/local-development.md](./docs/local-development.md)
- [docs/developer-guide-skills.md](./docs/developer-guide-skills.md)
- [docs/DEPLOY.md](./docs/DEPLOY.md)
- [docs/user-guide.md](./docs/user-guide.md)

Conservative naming rule in this repo:

- user-facing branding should say `MIAF`
- internal identifiers should only be renamed when safe

That is why some low-level infrastructure or implementation details may still follow existing technical conventions instead of turning every internal name into a branding exercise.
