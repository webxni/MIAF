#!/usr/bin/env bash
set -euo pipefail

# Backup loop: dump once at startup, then every BACKUP_INTERVAL_SECONDS.
# Each dump is verified by restoring into a throwaway database before the
# loop sleeps; failed verifies delete the dump and exit the iteration with
# an error. See restore.sh for the operator-driven restore path.

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
