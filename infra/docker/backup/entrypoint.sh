#!/usr/bin/env bash
set -euo pipefail

# Phase 0 backup loop: dump once at startup, then every 24h.
# Phase 12 will replace this with a proper cron schedule and restore tooling.

INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"

echo "[backup] entrypoint starting; interval=${INTERVAL_SECONDS}s"

# Initial backup gives us a recovery point as soon as the stack is up.
# Sleep briefly so postgres has finished its initdb on first boot.
sleep 10

while true; do
  if /usr/local/bin/backup.sh; then
    echo "[backup] success at $(date -u)"
  else
    echo "[backup] FAILED at $(date -u)" >&2
  fi
  sleep "$INTERVAL_SECONDS"
done
