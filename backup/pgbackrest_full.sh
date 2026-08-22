#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"

STANZA="shaka_db"
LOG="$BACKUP_ROOT/logs/pgbackrest_full.log"
COMPOSE="docker compose -f $REPO_DIR/docker-compose.yml"

mkdir -p "$(dirname "$LOG")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== pgbackrest full backup start ==="
log "vars: STANZA=$STANZA BACKUP_ROOT=$BACKUP_ROOT IMAGE=$(docker compose -f "$REPO_DIR/docker-compose.yml" images db --format '{{.Repository}}:{{.Tag}}' 2>/dev/null || echo unknown)"

# Repo status before (catches a broken stanza early)
if ! $COMPOSE exec -T -u postgres db pgbackrest --stanza="$STANZA" info >>"$LOG" 2>&1; then
    log "FAIL: 'pgbackrest info' failed before backup — check stanza/repo state above"
    exit 1
fi

START_TS=$(date +%s)
if $COMPOSE exec -T -u postgres db \
    pgbackrest --stanza="$STANZA" --type=full backup >>"$LOG" 2>&1
then
    ELAPSED=$(( $(date +%s) - START_TS ))
    SIZE=$(du -sh "$BACKUP_ROOT/pgbackrest" | cut -f1)
    log "OK: full backup completed in ${ELAPSED}s, repo size now ${SIZE}"
else
    RC=$?
    log "FAIL: pgbackrest backup exited $RC (pgbackrest output above)"
    exit "$RC"
fi

# Confirm the new backup is registered as complete
if $COMPOSE exec -T -u postgres db pgbackrest --stanza="$STANZA" info | grep -q "full.*complete"; then
    log "OK: repo shows a complete full backup"
else
    log "WARN: no complete full backup visible in repo after run — investigate"
fi
log "=== pgbackrest full backup end ==="
