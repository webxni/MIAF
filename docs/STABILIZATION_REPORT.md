# Stabilization Report

Reviewed commit: `f5229a1` as the starting point.

Latest stabilization commit should be read from `git log -1` after this report lands.

## Docker build status

- `docker compose down`: passed
- `docker compose build --no-cache`: passed
- `docker compose up -d`: passed
- `docker compose ps`: all services came up
- `make smoke`: passed against the rebuilt stack

## Container health status

Healthy containers observed:

- `miaf-api`
- `miaf-web`
- `miaf-postgres`
- `miaf-redis`
- `miaf-minio`

Running containers observed:

- `miaf-caddy`
- `miaf-backup`
- `miaf-scheduler`
- `miaf-worker`

## Migrations status

- Migrations are not automatic on API startup.
- Verified command: `docker compose exec -T api python -m app.cli migrate`
- Verified current Alembic revision: `0013_invite_tokens`
- Verified head revision: `0013_invite_tokens`

## Routes checked

The following routes returned successful responses through the live stack:

- `/`
- `/onboarding`
- `/onboarding/tailscale`
- `/login`
- `/settings`
- `/accept-invite`
- `/dashboard`
- `/agent`
- `/documents`
- `/skills`
- `/alerts`
- `/audit-log`
- `/personal/budget`
- `/personal/debts`
- `/personal/goals`
- `/personal/investments`
- `/business`
- `/business/reports`
- `/business/ledger`
- `/business/invoices`
- `/business/bills`
- `/api/health`
- `/api/health/ready`
- `/api/docs`

## End-to-end flows checked

### New owner flow

- Verified unauthenticated `GET /api/auth/me` returns `401`
- Created owner account through the live onboarding backend: `POST /api/auth/register-owner`
- Verified owner session cookie works with `GET /api/auth/me`
- Verified entities were created for Personal and My Business
- Verified settings fetch and save through `GET/PUT /api/settings`

### Agent flow

- Called `POST /api/agent/chat` with `How am I doing financially?`
- Result: graceful heuristic fallback, no crash

### Documents flow

- Uploaded a sample CSV through `POST /api/documents/upload`
- Verified source transactions and pending draft journal entries were created
- Reviewed/corrected one draft journal entry via `PATCH /api/entities/{entity_id}/journal-entries/{entry_id}`
- Posted the corrected draft via `POST /api/entities/{entity_id}/journal-entries/{entry_id}/post`

### Accounting flow

- Verified personal trial balance after posting a document-created entry
- Created a live business draft journal entry
- Posted the business draft journal entry
- Verified business trial balance, balance sheet, and income statement endpoints on posted data

### Invite flow

- Created invite through `POST /api/auth/invites`
- Verified pending invite list through `GET /api/auth/invites`
- Accepted invite through public `POST /api/auth/accept-invite`
- Verified invited user session with `GET /api/auth/me`
- Verified invited viewer role is denied `GET /api/auth/invites` with `403`

### Security flow

- Changed owner password through `PUT /api/auth/password`
- Verified old password login fails
- Verified new password login succeeds
- Revoked all sessions through `POST /api/auth/revoke-all-sessions`
- Verified revoked session cookie fails `GET /api/auth/me`
- Verified login succeeds again after revocation

## Tests run

- `docker compose exec -T api python -m pytest -q`
- `docker compose exec -T web npx tsc --noEmit`
- `docker compose config`
- `make smoke`
- `docker compose logs --tail=200 api`
- `docker compose logs --tail=200 web`
- `docker compose logs --tail=200 caddy`
- `docker compose logs --tail=200 scheduler`
- `docker compose logs --tail=200 worker`

Observed result during stabilization:

- Backend tests: `251 passed, 1 skipped`
- TypeScript compile: passed
- Compose config: passed
- Smoke checks: passed

## Issues found

- Migrations are still manual rather than automatic on API startup.
- `.env.example` was missing several currently used variables and overrides.
- `docs/DEPLOY.md` still claimed there was no invitation flow.
- `docs/INGESTION.md` described pre-`pypdf` PDF behavior.
- README quickstart and CSV review wording needed alignment with the working runtime flow.

## Issues fixed

- Updated `.env.example` with the current app/runtime variables.
- Updated README quickstart and troubleshooting notes.
- Updated deploy docs to reflect the current invite flow and owner-led collaboration model.
- Updated ingestion docs to mention `pypdf` first-pass extraction.
- Added this stabilization report with exact commands and observed results.

## Remaining limitations

- Migrations still require an explicit manual command: `make migrate`.
- The heuristic agent provider still returns graceful fallback text for unsupported prompts rather than deep financial analysis.
- The product remains owner-led. Team invites work, but broader collaboration is intentionally limited.
- PDF ingestion is improved with `pypdf`, but scanned-PDF OCR fallback is still not implemented.

## Exact commands to run the app

```bash
make env
$EDITOR .env
make build
make up
make ps
make migrate
make smoke
```

Then open:

- `http://localhost`
- `http://localhost/onboarding`

Optional operational checks:

```bash
docker compose ps
docker compose exec -T api python -m pytest -q
docker compose exec -T web npx tsc --noEmit
docker compose logs --tail=200 api
docker compose logs --tail=200 web
```
