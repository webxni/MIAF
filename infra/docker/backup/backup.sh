#!/usr/bin/env bash
set -euo pipefail

: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${BACKUP_RETENTION_DAYS:=7}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="/backups/finclaw_${ts}.sql.gz"

echo "[backup] dumping ${POSTGRES_DB}@${POSTGRES_HOST}:${POSTGRES_PORT} -> ${out}"

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner --no-privileges --format=plain \
  | gzip -9 > "$out"

echo "[backup] wrote $(stat -c '%s' "$out") bytes"

echo "[backup] pruning backups older than ${BACKUP_RETENTION_DAYS} days"
find /backups -maxdepth 1 -type f -name 'finclaw_*.sql.gz' \
  -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete || true
