# MIAF — Mayordomo IA Financiero

Administra con sabiduría.

MIAF is an AI-assisted financial steward for personal finances, small-business accounting, and owner/operator finances. It combines a deterministic accounting core with guided AI chat, document ingestion, draft journal workflows, heartbeat monitoring, and an audit trail.

MIAF is designed around a few hard rules:

- Deterministic numbers first.
- AI explanations and drafts second.
- Human confirmation before sensitive writes.
- No money movement, no trading, no tax filing.

The full product spec lives in [MIAF.md](./MIAF.md). Ingestion details live in [docs/INGESTION.md](./docs/INGESTION.md). Production deployment is documented in [docs/DEPLOY.md](./docs/DEPLOY.md).

## Quick Install

Recommended local install:

```bash
curl -fsSL https://raw.githubusercontent.com/webxni/MIAF/main/install-cli.sh | bash
```

Custom install prefix:

```bash
MIAF_HOME=~/.miaf curl -fsSL https://raw.githubusercontent.com/webxni/MIAF/main/install-cli.sh | bash
```

What the installer does:

- Verifies `git`, `docker`, `docker compose`, `curl`, and `openssl` or `python`.
- Clones or updates MIAF under `~/.miaf/repo` by default.
- Creates `.env` from `.env.example` if needed.
- Generates fresh local secrets for a new `.env`.
- Preserves an existing `.env` unless you explicitly approve placeholder replacement.
- Builds the Docker images, starts the dev stack, runs migrations, and runs smoke checks.
- Installs a local helper at `~/.miaf/bin/miaf`.

The curl installer is for local development and self-hosted local use. It does not perform a production deployment.

## After Install

Once the stack is up:

1. Open [http://localhost](http://localhost).
2. Visit [http://localhost/onboarding](http://localhost/onboarding).
3. Create the owner account.
4. Optionally configure private phone access in `/onboarding/tailscale`.
5. Open `/settings` and configure jurisdiction, base currency, fiscal year start, and AI provider.
6. Add an AI provider key in `/settings` if you want OpenAI, Anthropic, or Gemini. The `heuristic` provider works without an external key.
7. Use `/documents` to upload CSVs and source files.
8. Use `/agent` for guided bookkeeping, summaries, and draft actions.
9. Use `/dashboard`, `/business/reports`, `/alerts`, and `/audit-log` for ongoing review.

## Manual Docker Setup

The existing Docker/manual path remains supported and is the fallback for users who do not want the curl installer.

```bash
git clone https://github.com/webxni/MIAF.git
cd MIAF
make env
# edit .env before first run
make build
make up
docker compose exec -T api python -m app.cli migrate
make smoke
```

Notes:

- `make env` copies `.env.example` to `.env` only if `.env` is missing.
- Migrations are not run automatically by the app container; run them explicitly after boot and after updates.
- Do not run `make seed` for a normal fresh install if you want to use `/onboarding`, because onboarding is only available before the first user exists.

Deep install, update, backup, restore, and uninstall details are in [docs/INSTALL.md](./docs/INSTALL.md).

## Environment Variables

The main local template is [`.env.example`](./.env.example). Production-oriented defaults live in [`.env.production.example`](./.env.production.example). Do not commit real secrets.

Important local variables:

- App secrets
  - `SECRET_KEY`: required for sessions and encrypted stored provider keys.
  - `AUTOMATION_TOKEN`: required for internal scheduler-to-API heartbeat calls.
- Database
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_DB`
  - `DATABASE_URL`: optional override; Compose derives it from `POSTGRES_*` by default.
- Redis
  - `REDIS_PASSWORD`
  - `REDIS_URL`: optional override; Compose derives it by default.
- MinIO
  - `MINIO_ROOT_USER`
  - `MINIO_ROOT_PASSWORD`
  - `MINIO_BUCKET`
  - `MINIO_ENDPOINT`
  - `MINIO_ACCESS_KEY`
  - `MINIO_SECRET_KEY`
  - `MINIO_SECURE`
- Web and reverse proxy
  - `NEXT_PUBLIC_API_URL`
  - `CORS_ALLOW_ORIGINS`
  - `HTTP_PORT`
  - `HTTPS_PORT`
  - `CADDY_DOMAIN`
  - `CADDY_ADMIN_EMAIL` in production
- AI provider keys
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GEMINI_API_KEY`
  - These are optional because the UI also supports encrypted per-user provider setup in `/settings`.
- Integrations and automation
  - `TELEGRAM_WEBHOOK_SECRET`
  - `BACKUP_RETENTION_DAYS`
  - `HEARTBEAT_INTERVAL_SECONDS`
- Tailscale
  - `TAILSCALE_BINARY_PATH`
  - `TAILSCALE_COMMAND_TIMEOUT`
  - `TAILSCALE_ALLOWED_PORTS`
- Rate limiting and proxy trust
  - `IP_RATE_LIMIT_WINDOW_SECONDS`
  - `IP_RATE_LIMIT_REQUESTS`
  - `UVICORN_FORWARDED_IPS`

Production-only values in `.env.production.example` also include:

- `MIAF_APP_ROLE_PASSWORD`
- `BACKUP_INTERVAL_SECONDS`

## Access MIAF From Phone With Tailscale

MIAF supports private phone access through Tailscale. Use Tailscale Serve, not Funnel. The short version is:

- Run MIAF locally on port `80`.
- Install Tailscale on the host machine.
- Use `tailscale serve --bg http://127.0.0.1:80` or `make tailscale-serve`.
- Open the resulting `https://*.ts.net` URL from a device in the same tailnet.

See [docs/TAILSCALE.md](./docs/TAILSCALE.md) for the full flow and troubleshooting.

## Common Commands

Make targets:

```bash
make up
make down
make logs
make smoke
make ps
make clean
make prod-up
make prod-down
```

Local CLI wrapper from the curl installer:

```bash
~/.miaf/bin/miaf start
~/.miaf/bin/miaf stop
~/.miaf/bin/miaf logs
~/.miaf/bin/miaf status
~/.miaf/bin/miaf update
~/.miaf/bin/miaf smoke
```

Additional helper commands already present in the repo:

```bash
make build
docker compose exec -T api python -m app.cli migrate
make api-shell
make web-shell
make tailscale-serve
make tailscale-serve-status
```

## What Works Today

Accurate to the current codebase:

- Onboarding
  - `/onboarding` creates the first owner account, session, tenant, and default personal and business entities.
- Settings
  - `/settings` supports jurisdiction, base currency, fiscal year start month, AI provider, AI model, encrypted API key storage, password change, team invites, and Tailscale settings.
- AI provider configuration
  - Current provider choices are `heuristic`, `anthropic`, `openai`, and `gemini`.
- Agent chat
  - `/agent` supports chat, tool planning, report explanations, memory access, and draft-oriented accounting actions with explicit confirmation for sensitive steps.
- Document and CSV ingestion
  - `/documents` supports file upload, text ingestion, CSV import, review questions, reclassification, draft creation, and rejection.
- File-type ingestion status
  - CSV: implemented.
  - Text notes: implemented.
  - Image OCR: implemented with Tesseract.
  - PDF: initial support with embedded-text extraction and safe fallback scraping; scanned-PDF OCR is not implemented yet.
  - Audio: initial support for storage and review, but transcription is still placeholder behavior.
- Draft journal entries
  - CSV imports and document workflows can create draft journal entries for human review.
- Corrections and learning
  - Merchant/account corrections feed conservative memory updates for future CSV classification.
- Accounting core
  - Double-entry accounts, ledger, journal validation, trial balance, business reports, personal/business dashboards, and report endpoints are present.
- Heartbeat
  - Scheduler-driven heartbeat runs create alerts and reports and call the internal heartbeat endpoint with `AUTOMATION_TOKEN`.
- Team invites
  - `/settings` supports invite creation, copyable accept links, acceptance, and revocation.
- Audit log
  - `/audit-log` and backend audit services are present, with immutability tests in the API suite.
- Tailscale setup
  - `/onboarding/tailscale`, `/settings/tailscale`, API checks, and host-command helpers exist today.
- Telegram
  - Telegram link and message management routes exist, with webhook secret support in the environment.

Still partial or planned:

- Scanned-PDF OCR fallback is not implemented yet.
- Audio transcription is not implemented yet.
- Broader multi-tenant collaboration is still limited; the product is optimized for an owner-led workspace.
- Production hardening, off-host backups, and operator monitoring remain an ops responsibility.

## Troubleshooting

- Docker is not running
  - Start Docker Desktop on macOS or the Docker daemon on Linux, then rerun `make up` or the installer.
- Port `80` is already in use
  - Change `HTTP_PORT` in `.env`, then run `docker compose up -d` again. If you change the port, open `http://localhost:<new-port>`.
- API unhealthy
  - Run `make logs` and `docker compose logs api --tail=100`. Confirm `.env` exists and that `SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `MINIO_ROOT_PASSWORD`, and `AUTOMATION_TOKEN` are not placeholder values.
- Database unhealthy
  - Check `docker compose logs postgres --tail=100`. If the schema is behind, run `docker compose exec -T api python -m app.cli migrate`.
- Redis unhealthy
  - Check `docker compose logs redis --tail=100`. Confirm `REDIS_PASSWORD` matches the derived `REDIS_URL` configuration.
- MinIO unhealthy
  - Check `docker compose logs minio --tail=100`. Confirm `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, and `MINIO_SECRET_KEY` line up. In dev, the console is at `http://127.0.0.1:9001`.
- AI provider not working
  - Confirm the provider and model in `/settings`, then re-enter the API key. If you want local deterministic behavior only, switch to `heuristic`.
- CSV upload problems
  - MIAF expects date and amount-style columns. Check [docs/INGESTION.md](./docs/INGESTION.md) and review the pending drafts queue after import.
- `pypdf` missing after an old build
  - Rebuild the API image with `make build` or rerun the installer so the current `apps/api/requirements.txt` is installed.
- Migration errors
  - Bring the stack up first, then run `docker compose exec -T api python -m app.cli migrate`. For production, follow the admin-URL migration notes in [docs/DEPLOY.md](./docs/DEPLOY.md).
- Tailscale is not reachable
  - Confirm the host is in your tailnet, use Serve instead of Funnel, and check `make tailscale-serve-status`. Full guidance is in [docs/TAILSCALE.md](./docs/TAILSCALE.md).

## Uninstall And Cleanup

Do not remove data unless you mean to.

Stop the app:

```bash
make down
```

Destructive full cleanup, including Docker volumes:

```bash
make clean
```

Remove the local install folder manually:

```bash
rm -rf ~/.miaf
```

Warning:

- Docker volumes contain the database, object storage, and backups.
- `make clean` deletes those volumes for the local dev stack.

## Production Notes

The curl installer is not a production deploy path.

For production:

- Use [docs/DEPLOY.md](./docs/DEPLOY.md).
- Use `.env.production.example` as the starting point.
- Run `docker compose -f compose.yaml -f compose.prod.yaml up -d --build`.
- Apply migrations explicitly.
- Keep the `miaf_app` role hardening and backup steps from the deployment guide.

## More Documentation

- [docs/INSTALL.md](./docs/INSTALL.md)
- [docs/DEPLOY.md](./docs/DEPLOY.md)
- [docs/TAILSCALE.md](./docs/TAILSCALE.md)
- [docs/INGESTION.md](./docs/INGESTION.md)
