#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"

STANZA="shaka_db"
LOG="$BACKUP_ROOT/logs/pgbackrest_full.log"
COMPOSE="docker compose -f $REPO_DIR/docker-compose.yml"
TYPE="full"

usage() {
    cat <<EOF
Back up the whole Postgres cluster (every database + roles) with pgBackRest.
Runs daily from cron (see install_cron.sh); safe to run by hand any time,
e.g. before an upgrade or maintenance.

Usage: $(basename "$0") [--type full|diff|incr]

  --type full   complete copy (default)
  --type diff   only what changed since the last full backup (faster)
  --type incr   only what changed since the last backup of any type (fastest)
  -h, --help    this help

Retention: see pgbackrest.conf. List / restore backups with ./backup/restore.sh --list
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type) TYPE="${2:?--type needs full, diff or incr}"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option '$1'"; echo; usage; exit 2 ;;
    esac
    shift
done
[[ "$TYPE" =~ ^(full|diff|incr)$ ]] || { echo "--type must be full, diff or incr"; exit 2; }

mkdir -p "$(dirname "$LOG")"
# Interactive: show output and log it. Cron already redirects stdout into $LOG.
[[ -t 1 ]] && exec > >(tee -a "$LOG") 2>&1

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== pgbackrest $TYPE backup start ==="
log "vars: STANZA=$STANZA BACKUP_ROOT=$BACKUP_ROOT"

if ! $COMPOSE exec -T db pg_isready >/dev/null 2>&1; then
    log "FAIL: db container isn't running/ready (docker compose up -d db)"
    exit 1
fi

# Repo status before (catches a broken stanza early)
if ! $COMPOSE exec -T -u postgres db pgbackrest --stanza="$STANZA" info >/dev/null 2>&1; then
    $COMPOSE exec -T -u postgres db pgbackrest --stanza="$STANZA" info || true
    log "FAIL: 'pgbackrest info' failed before backup — check stanza/repo state above"
    exit 1
fi

START_TS=$(date +%s)
if $COMPOSE exec -T -u postgres db pgbackrest --stanza="$STANZA" --type="$TYPE" backup; then
    ELAPSED=$(( $(date +%s) - START_TS ))
    SIZE=$(du -sh "$BACKUP_ROOT/pgbackrest" 2>/dev/null | cut -f1 || echo "?")
    log "OK: $TYPE backup completed in ${ELAPSED}s, repo size now ${SIZE}"
else
    RC=$?
    log "FAIL: pgbackrest backup exited $RC (pgbackrest output above)"
    exit "$RC"
fi

# Confirm the new backup is registered, and show what's in the repo
INFO=$($COMPOSE exec -T -u postgres db pgbackrest --stanza="$STANZA" info)
if grep -q "$TYPE backup" <<<"$INFO"; then
    log "OK: repo shows the new $TYPE backup"
else
    log "WARN: no $TYPE backup visible in repo after run — investigate"
fi
[[ -t 1 ]] && echo "$INFO"
log "=== pgbackrest $TYPE backup end ==="
