# FinClaw — Production deployment

Target: single VM (1 vCPU / 2 GB RAM minimum), single user, single tenant, Docker + Docker Compose v2, real domain pointed at the VM.

## 1. Prerequisites

- VM with Docker + Docker Compose v2 installed.
- DNS A record for your domain (for example `finclaw.example.com`) pointing at the VM's public IP.
- Ports `80` and `443` open in the VM firewall.
- About 1 GB free disk for Postgres + MinIO + backups.

## 2. Clone and configure

```bash
git clone <repo> /opt/finclaw
cd /opt/finclaw
cp .env.production.example .env
```

Edit `.env`:

- Generate `SECRET_KEY`: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Generate strong values for `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AUTOMATION_TOKEN`, and `FINCLAW_APP_ROLE_PASSWORD` (32+ chars each).
- Set `CADDY_DOMAIN=<your-domain>`.
- Set `CADDY_ADMIN_EMAIL=<your-ops-email>` so Let's Encrypt can warn you about cert issues.
- Set `CORS_ALLOW_ORIGINS=https://<your-domain>`.

## 3. First-time start

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

- First boot creates the database and runs the mounted Postgres init script.
- If the schema is not current, run:

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec -T api python -m app.cli migrate
```

- Caddy obtains a Let's Encrypt certificate automatically the first time it serves traffic on the configured domain.

## 4. Lock down the Postgres app role

The init script creates a non-super `finclaw_app` role with a deliberately bad placeholder password. Override it after first boot:

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "ALTER ROLE finclaw_app PASSWORD '$FINCLAW_APP_ROLE_PASSWORD'; \
   GRANT INSERT, SELECT ON ALL TABLES IN SCHEMA public TO finclaw_app; \
   GRANT UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO finclaw_app; \
   REVOKE UPDATE, DELETE ON TABLE audit_logs FROM finclaw_app;"
```

Then update `.env` so the running app uses `finclaw_app` instead of the bootstrap admin:

```dotenv
DATABASE_URL=postgresql+asyncpg://finclaw_app:<your-finclaw-app-role-password>@postgres:5432/<your-postgres-db>
```

Restart the long-running app processes:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d api worker scheduler
```

Leave the `POSTGRES_USER` admin role for migrations, backup, and ad-hoc DBA work. After switching the app to `finclaw_app`, run migrations with the admin URL as a one-off override:

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec -T \
  -e DATABASE_URL="postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/$POSTGRES_DB" \
  api python -m app.cli migrate
```

If a later migration creates new tables, re-run the grant command so `finclaw_app` can access them.

## 5. Create the owner account

Visit `https://<your-domain>/onboarding` in a browser. First-run registration is gated to the "no users exist yet" state. Submitting it creates your tenant, personal and business entities with default charts of accounts, and your owner session.

## 6. Configure AI provider

Once logged in, go to `/settings`:

- Pick a provider. Anthropic is the current recommended default.
- Paste your API key. It is encrypted at rest with Fernet keyed from `SECRET_KEY`.
- Default model: `claude-sonnet-4-6`.

## 7. Backups

The `backup` service dumps the live DB every `BACKUP_INTERVAL_SECONDS` seconds (default `86400`, once per day) into the `backup_data` volume and verifies each dump by restoring it into a throwaway database. To pull backups off the VM:

```bash
docker compose -f compose.yaml -f compose.prod.yaml cp backup:/backups ./backups
```

Use `infra/docker/backup/restore.sh` for restore. Test a restore at least once before you need it.

## 8. Updates

```bash
cd /opt/finclaw
git pull
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml exec -T \
  -e DATABASE_URL="postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/$POSTGRES_DB" \
  api python -m app.cli migrate
```

If the update adds tables, sequences, or other new schema objects the app role needs, re-run the grant command from step 4.

## 9. Operational checks

- `https://<your-domain>/api/health` returns `{"status":"ok"}`.
- `https://<your-domain>/api/health/ready` returns `{"status":"ok","checks":{"postgres":"ok","redis":"ok","minio":"ok"}}`.
- Caddy has issued a valid TLS certificate for your domain.
- The audit log at `/audit-log` shows your recent actions.

## 10. Limitations to know

- Single user / single tenant. There is no invitation flow yet.
- Postgres, MinIO, and backups all live on the VM's disk. There is no built-in off-host backup yet, so the VM disk is still a single point of failure.
- Stored provider API keys are encrypted from `SECRET_KEY`. If you rotate `SECRET_KEY`, existing stored API keys become unreadable and must be re-entered in `/settings`.

## 11. Going further

- Off-host backups: copy the `backup_data` volume off-host nightly with `rsync`, `restic`, or similar.
- Email alerts are not implemented yet; current alerting is in-product plus Telegram.
- Skill proposal review is not implemented yet.
