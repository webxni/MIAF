# MIAF — Mayordomo IA Financiero

Administra con sabiduría.

MIAF helps you manage personal finances, small business accounting, and owner finances with AI-assisted bookkeeping and financial guidance.

> Accounting engine first, AI interface second.
> Deterministic numbers, AI explanations.
> Never moves real money. Never executes trades.

The full product spec, build phases, and acceptance criteria live in [`MIAF.md`](./MIAF.md). Engineering guardrails for contributors and AI agents are in [`CLAUDE.md`](./CLAUDE.md).

---

## Status

* **Phase 0 — Docker-first monorepo:** complete. Working `docker compose up` stack (api, web, worker, scheduler, postgres+pgvector, redis, minio, caddy, backup); health endpoints; non-root containers; dev/prod compose overlays.
* **Phase 1 — Accounting Core:** complete. SQLAlchemy models for tenants, users, sessions, entities, entity_members, accounts, journal_entries, journal_lines, source_transactions, attachments, audit_logs. Alembic migrations. Argon2 sessions. CRUD for entities/accounts/journal entries. Post + void (via reversal) with full immutability of posted entries. General ledger and trial balance. Per-entity RBAC (owner/admin/accountant/viewer/agent). Append-only audit logs with secret redaction. Seed creates one personal + one business entity with default charts of accounts (26 / 30 accounts). 21 pytest cases covering balance checks, immutability, void semantics, and trial balance correctness.

Next: **Phase 2 — Personal Finance Mode** (budgets, goals, debts, net-worth snapshots, personal KPIs).

## Repo layout

```
apps/
  api/            FastAPI backend
  web/            Next.js + TS + Tailwind frontend
services/
  worker/         RQ background worker
  scheduler/      APScheduler + heartbeat runner
packages/
  shared/         Cross-package types/utilities (placeholder)
skills/           Local installable skills (Phase 9)
infra/
  docker/         Caddy, postgres init, backup container
  scripts/        Operational scripts
docs/
tests/
compose.yaml      Dev compose
compose.prod.yaml Production overrides
Makefile
.env.example
```

## Local setup

**Prerequisite:** Docker + Docker Compose v2. No Python, no Node, no other host dependencies.

```bash
# 1. Create your local .env from the template
make env

# 2. Edit .env and replace every "change-me-..." placeholder with real secrets
$EDITOR .env

# 3. Build and start the stack
make build
make up

# 4. Tail logs (optional)
make logs

# 5. Smoke test the API health endpoints (proxied through Caddy)
make smoke
```

The web UI lives at <http://localhost> and the API at <http://localhost/api>. The MinIO console is at <http://127.0.0.1:9001> in dev only.

### Production deploy

For a single-VM production deployment with Caddy TLS on a real domain, see [`docs/DEPLOY.md`](./docs/DEPLOY.md).

### Key Make targets

| Target | What it does |
|---|---|
| `make env` | Copy `.env.example` → `.env` if missing |
| `make up` / `make down` | Start / stop the dev stack |
| `make build` / `make rebuild` | Build images (with / without cache) |
| `make logs` / `make api-logs` / `make web-logs` | Tail logs |
| `make ps` | Service status |
| `make api-shell` / `make web-shell` / `make db-shell` / `make redis-shell` | Open a shell in the named container |
| `make smoke` | Curl `/api/health` and `/api/health/ready` through Caddy |
| `make clean` | **Destructive.** Stop everything and delete all volumes |
| `make prod-up` / `make prod-down` | Production compose overrides |

Run `make help` for the full list.

## Network model

* Only **caddy** is published on host ports (`HTTP_PORT`, `HTTPS_PORT`).
* `postgres`, `redis`, `minio`, `api`, `web`, `worker`, `scheduler`, `backup` are reachable only on the internal `miaf_internal` Docker network.
* In dev only, the MinIO **console** (port 9001) is bound to `127.0.0.1` for convenience. In prod it is internal-only.
* All containers run as a non-root user.
* Secrets are never baked into images — they're injected via environment variables sourced from `.env`.

## Health checks

| Service | Check |
|---|---|
| api | `GET /health` (liveness), `GET /health/ready` (deps: postgres, redis, minio) |
| postgres | `pg_isready` |
| redis | `redis-cli ping` (auth) |
| minio | `GET /minio/health/live` |
| web | `GET /` |

`docker compose ps` shows the per-service health column.

## What's intentionally **not** here yet

* Database models and migrations (Phase 1).
* Auth, sessions, RBAC (Phase 12 finalizes; lightweight stubs land earlier).
* Real worker jobs and scheduler actions (later phases).
* shadcn/ui component setup (Phase 5 will run `shadcn init`).

See [`MIAF.md`](./MIAF.md) for the phase-by-phase contract.

## Production notes

`compose.prod.yaml` is an overlay, not a replacement:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
# or
make prod-up
```

The overlay removes dev source mounts, removes the MinIO console host binding, switches Caddy to a real domain (`CADDY_DOMAIN`) with auto HTTPS, and runs api/web in production mode (no `--reload`, Next.js prebuilt).

Backups are written to the `backup_data` volume as `miaf_<timestamp>.sql.gz` and pruned per `BACKUP_RETENTION_DAYS`. Use `infra/docker/backup/restore.sh` to restore a dump.
