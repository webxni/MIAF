#!/usr/bin/env bash
set -euo pipefail

: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${BACKUP_RETENTION_DAYS:=7}"
: "${BACKUP_VERIFY:=1}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="/backups/miaf_${ts}.sql.gz"

echo "[backup] dumping ${POSTGRES_DB}@${POSTGRES_HOST}:${POSTGRES_PORT} -> ${out}"

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner --no-privileges --format=plain \
  | gzip -9 > "$out"

bytes="$(stat -c '%s' "$out")"
echo "[backup] wrote ${bytes} bytes"

if [ "$BACKUP_VERIFY" = "1" ]; then
  verify_db="miaf_verify_${ts}"
  echo "[backup] verifying restore into temporary database ${verify_db}"

  cleanup() {
    PGPASSWORD="$POSTGRES_PASSWORD" psql \
      -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
      -d postgres -X -q -v ON_ERROR_STOP=1 \
      -c "DROP DATABASE IF EXISTS \"${verify_db}\";" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT

  PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
    -d postgres -X -q -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"${verify_db}\";"

  if ! gunzip -c "$out" | PGPASSWORD="$POSTGRES_PASSWORD" psql \
        -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -d "${verify_db}" -X -q -v ON_ERROR_STOP=1 >/dev/null; then
    echo "[backup] VERIFY FAILED: restore raised an error" >&2
    rm -f "$out"
    exit 1
  fi

  # Sanity-check that a core table is present and queryable. journal_entries is
  # the ledger spine; if it's missing or unreadable the dump is useless.
  table_count="$(PGPASSWORD="$POSTGRES_PASSWORD" psql \
        -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -d "${verify_db}" -X -q -t -A -v ON_ERROR_STOP=1 \
        -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='journal_entries';" \
        2>/dev/null || echo "0")"
  if [ "$table_count" != "1" ]; then
    echo "[backup] VERIFY FAILED: journal_entries table missing in restored dump" >&2
    rm -f "$out"
    exit 1
  fi

  echo "[backup] verify ok (journal_entries present)"
fi

echo "[backup] pruning backups older than ${BACKUP_RETENTION_DAYS} days"
find /backups -maxdepth 1 -type f -name 'miaf_*.sql.gz' \
  -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete || true
