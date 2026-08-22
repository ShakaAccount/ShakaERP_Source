#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"

SRC_VOL="odoo_19_data"
SRC_FS="/src/filestore/"
DST_DIR="$BACKUP_ROOT/filestore"
IMAGE="odoo_filestore_sync"
LOG="$BACKUP_ROOT/logs/filestore_sync.log"

mkdir -p "$DST_DIR" "$(dirname "$LOG")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== filestore sync start ==="
log "vars: SRC_VOL=$SRC_VOL SRC_FS=$SRC_FS DST_DIR=$DST_DIR IMAGE=$IMAGE"

# Incremental sync of the Odoo filestore (attachments) to the host backup dir.
# Runs every 15 min (see install_cron.sh); --delete keeps the mirror clean.
START_TS=$(date +%s)
if docker run --rm \
    -v "$SRC_VOL":/src:ro \
    -v "$DST_DIR":/dst \
    "$IMAGE" -a --delete "$SRC_FS" /dst/ >>"$LOG" 2>&1
then
    ELAPSED=$(( $(date +%s) - START_TS ))
    FILES=$(find "$DST_DIR" -type f | wc -l)
    SIZE=$(du -sh "$DST_DIR" | cut -f1)
    log "OK: sync completed in ${ELAPSED}s, mirror now ${FILES} files, ${SIZE}"
else
    RC=$?
    log "FAIL: docker run exited $RC (see rsync output above)"
    exit "$RC"
fi
log "=== filestore sync end ==="
