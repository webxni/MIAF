# MIAF Install Guide

This guide covers local installation, updates, backups, restore, uninstall, Tailscale access, and pointers to production deployment.

## Quick Install With Curl

Recommended local install:

```bash
curl -fsSL https://raw.githubusercontent.com/webxni/MIAF/main/install-cli.sh | bash
```

Custom install directory:

```bash
MIAF_HOME=~/.miaf curl -fsSL https://raw.githubusercontent.com/webxni/MIAF/main/install-cli.sh | bash
```

Default layout:

- `~/.miaf/repo`: git checkout
- `~/.miaf/bin/miaf`: local wrapper

The installer:

- Detects Linux or macOS.
- Verifies `git`, `docker`, `docker compose`, `curl`, and `openssl` or `python`.
- Clones the repo if missing.
- Pulls the latest `main` if the repo already exists.
- Creates `.env` from `.env.example` if needed.
- Generates secure local secrets for a new `.env`.
- Preserves an existing `.env` unless you explicitly approve placeholder replacement.
- Builds the dev images.
- Starts the stack.
- Runs `python -m app.cli migrate`.
- Runs the same health checks as `make smoke`.

The installer does not:

- use `sudo`
- install Docker, Node, or Python system-wide
- delete volumes
- print generated secrets
- deploy production

If you want to finish first-run onboarding from the terminal instead of the browser, run:

```bash
~/.miaf/bin/miaf setup
```

That command creates the owner account, saves the basic settings, and can configure Tailscale using the actual host port selected in `.env`.

## Manual Local Install

Use this if you prefer working directly from the repo:

```bash
git clone https://github.com/webxni/MIAF.git
cd MIAF
make env
# edit .env
make build
make up
docker compose exec -T api python -m app.cli migrate
make smoke
```

Open:

- `http://localhost`
- `http://localhost/onboarding`
- `http://localhost/api/health`
- `http://127.0.0.1:9001` for the MinIO dev console

Important:

- Do not run `make seed` on a normal first install if you want to complete `/onboarding` yourself.
- The app does not auto-run migrations on boot.

## First Run Checklist

After the stack is healthy:

1. Open `http://localhost/onboarding`.
2. Create the owner account.
3. Optionally configure Tailscale access in `/onboarding/tailscale`.
4. Open `/settings`.
5. Set jurisdiction, base currency, fiscal year start month, and AI provider.
6. Add an AI provider key if you want OpenAI, Anthropic, or Gemini. If not, keep `heuristic`.
7. If you want external document extraction, enable `AI document reading` and grant consent in `/settings`.
8. Upload a CSV or source document in `/documents`.
9. Use `/agent`, `/dashboard`, `/business/reports`, `/alerts`, and `/audit-log`.

## Update

### If You Installed With Curl

Run:

```bash
~/.miaf/bin/miaf update
```

That reruns the installer with your existing `MIAF_HOME`. Current behavior:

- `git fetch`
- `git pull --ff-only`
- keep the existing `.env`
- rebuild images
- `docker compose up -d`
- `python -m app.cli migrate`
- rerun HTTP health checks

No local data or volumes are deleted.

### If You Installed Manually

Run:

```bash
git pull
make build
make up
docker compose exec -T api python -m app.cli migrate
make smoke
```

## Local CLI Wrapper

The curl installer installs `~/.miaf/bin/miaf`.

Supported commands:

```bash
~/.miaf/bin/miaf setup
~/.miaf/bin/miaf start
~/.miaf/bin/miaf stop
~/.miaf/bin/miaf restart
~/.miaf/bin/miaf logs
~/.miaf/bin/miaf status
~/.miaf/bin/miaf smoke
~/.miaf/bin/miaf update
~/.miaf/bin/miaf shell api
~/.miaf/bin/miaf shell web
```

If you want `miaf` on your PATH:

```bash
export PATH="$HOME/.miaf/bin:$PATH"
```

## Environment Notes

Use [`.env.example`](../.env.example) for local development and [`.env.production.example`](../.env.production.example) for production.

Variables to set carefully:

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- `AUTOMATION_TOKEN`
- optional provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
- OpenAI document reading defaults:
  - `OPENAI_DOCUMENT_AI_REQUIRES_CONSENT`
  - `OPENAI_VISION_MODEL`
  - `OPENAI_PDF_MODEL`
  - `OPENAI_TRANSCRIPTION_MODEL`
  - `OPENAI_DOCUMENT_MAX_FILE_MB`
  - `OPENAI_DOCUMENT_TIMEOUT_SECONDS`
- optional `TELEGRAM_WEBHOOK_SECRET`
- optional Tailscale settings

The local installer auto-generates secure values for a new local `.env`.

## Local Extraction vs OpenAI Extraction

Local by default:

- CSV parsing and row import
- text note parsing
- image OCR with Tesseract
- PDF embedded-text extraction with `pypdf`

Optional OpenAI path when enabled in `/settings`:

- low-confidence image extraction
- scanned or low-text PDF extraction
- ambiguous text note extraction
- audio transcription and extraction
- CSV column mapping suggestions only

OpenAI is never allowed to:

- post journal entries directly
- invent totals
- bypass review for uncertain accounting
- replace the deterministic CSV row parser

## Backup

The dev and prod stacks both include the `backup` container. It writes compressed database dumps into the `backup_data` Docker volume and verifies restores automatically.

For a local copy of the backups:

```bash
docker compose cp backup:/backups ./backups
```

For production, the same approach is documented in [docs/DEPLOY.md](./DEPLOY.md).

Current limitation:

- There is no built-in off-host backup transport. Copy backups off the machine yourself.

## Restore

Use the existing restore script:

```bash
docker compose exec -T backup restore.sh /backups/<backup-file.sql.gz> <target_database>
```

The script is [infra/docker/backup/restore.sh](../infra/docker/backup/restore.sh).

Behavior to know:

- It expects `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.
- `DROP_EXISTING=1` drops the target DB first.
- It refuses to drop the live DB unless `ALLOW_DROP_LIVE=1`.
- `CREATE_DB=1` creates the target DB before restore.

For example, restoring into a scratch database:

```bash
docker compose exec -T \
  -e CREATE_DB=1 \
  backup restore.sh /backups/<backup-file.sql.gz> miaf_restore_test
```

## Uninstall

Stop the app:

```bash
make down
```

Remove containers and volumes:

```bash
make clean
```

Remove the local install folder:

```bash
rm -rf ~/.miaf
```

Warnings:

- `make clean` is destructive because it deletes Docker volumes.
- Those volumes contain the Postgres database, MinIO object storage, and backup files.

## Tailscale Access

MIAF supports private phone access with Tailscale Serve. Use Serve, not Funnel.

Typical host-side flow:

```bash
sudo tailscale up
sudo tailscale serve --bg http://127.0.0.1:80
tailscale serve status
```

Repo helpers:

```bash
make tailscale-status
make tailscale-ip
make tailscale-serve
make tailscale-serve-status
make tailscale-serve-reset
```

Full details are in [docs/TAILSCALE.md](./TAILSCALE.md).

## Production

Do not use the curl installer for production.

Use:

- [docs/DEPLOY.md](./DEPLOY.md)
- `.env.production.example`
- `docker compose -f compose.yaml -f compose.prod.yaml up -d --build`

Production setup also requires:

- a real domain
- `CADDY_ADMIN_EMAIL`
- explicit migrations
- `miaf_app` role hardening
- backup export planning

## Validation Commands

Useful checks after setup or updates:

```bash
bash -n install-cli.sh
docker compose config
docker compose exec -T api python -m pytest -q
docker compose exec -T web npx tsc --noEmit
make smoke
```
