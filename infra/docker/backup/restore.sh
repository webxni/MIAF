#!/usr/bin/env bash
set -euo pipefail

# Restore a MIAF backup dump into a target database.
#
# Usage:
#   restore.sh <backup-file.sql.gz> [target_database]
#
# Required env: POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD.
# Default target database: $POSTGRES_DB (the live database). To restore into
# a clean database safely, pass an explicit target name and pre-create it
# (or set CREATE_DB=1 to have this script create it for you).
#
# Set DROP_EXISTING=1 to drop the target database before restoring. Refuses
# to drop the live POSTGRES_DB unless ALLOW_DROP_LIVE=1 — restoring over the
# live database is destructive and should be a deliberate operator action.

: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <backup-file.sql.gz> [target_database]" >&2
  exit 2
fi

src="$1"
target="${2:-$POSTGRES_DB}"

if [ ! -f "$src" ]; then
  echo "[restore] backup file not found: $src" >&2
  exit 1
fi

if [ "${DROP_EXISTING:-0}" = "1" ]; then
  if [ "$target" = "$POSTGRES_DB" ] && [ "${ALLOW_DROP_LIVE:-0}" != "1" ]; then
    echo "[restore] refusing to drop live database '$target'." >&2
    echo "          Set ALLOW_DROP_LIVE=1 to override (this is destructive)." >&2
    exit 1
  fi
  echo "[restore] dropping target database '$target'"
  PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
    -d postgres -X -q -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS \"${target}\";"
fi

if [ "${CREATE_DB:-0}" = "1" ]; then
  echo "[restore] creating target database '$target'"
  PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
    -d postgres -X -q -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"${target}\";"
fi

echo "[restore] restoring $src -> $target"
gunzip -c "$src" | PGPASSWORD="$POSTGRES_PASSWORD" psql \
  -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
  -d "$target" -X -q -v ON_ERROR_STOP=1 >/dev/null
echo "[restore] restore complete"
