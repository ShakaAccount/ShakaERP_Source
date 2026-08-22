#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"

STANZA="shaka_db"
DB_IMAGE="odoo_19_db:pg16"
PG_DATA_VOL="odoo_19_pg_data"
LOG="$BACKUP_ROOT/logs/restore.log"
TARGET=""
ASSUME_YES=""

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# --- args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes) ASSUME_YES=1 ;;
        --target) TARGET="${2:?--target needs a timestamp: 'YYYY-MM-DD HH:MM:SS'}"; shift ;;
        *) log "FAIL: unknown arg '$1'. Supported: --yes, --target 'YYYY-MM-DD HH:MM:SS'"; exit 2 ;;
    esac
    shift
done

log "=== restore start ==="
log "vars: STANZA=$STANZA VOL=$PG_DATA_VOL IMAGE=$DB_IMAGE REPO=$BACKUP_ROOT/pgbackrest TARGET=${TARGET:-latest}"

# --- preflight: repo must be readable AND contain a complete full backup
#     BEFORE we touch PGDATA. Never destroy the live cluster on a hunch.
log "preflight: reading pgBackRest repo ..."
if ! INFO=$(docker run --rm --user postgres \
        -v "$BACKUP_ROOT/pgbackrest":/var/lib/pgbackrest \
        -v "$REPO_DIR/pgbackrest.conf":/etc/pgbackrest/pgbackrest.conf:ro \
        --entrypoint pgbackrest "$DB_IMAGE" \
        --stanza="$STANZA" info 2>&1); then
    log "FAIL: cannot read repo at $BACKUP_ROOT/pgbackrest. NOT touching the database."
    echo "$INFO"
    exit 1
fi
echo "$INFO"
if ! grep -q "full backup" <<<"$INFO"; then
    log "FAIL: no complete full backup in repo. NOT touching the database."
    exit 1
fi
log "preflight OK: complete full backup present"

# --- confirmation (destructive!) ---
if [[ -z "$ASSUME_YES" ]]; then
    printf 'This WIPES volume "%s" (the live database) and restores from "%s". Type YES to continue: ' "$PG_DATA_VOL" "$STANZA"
    read -r ANSWER
    [[ "$ANSWER" == "YES" ]] || { log "aborted by user"; exit 1; }
fi

# ponytail: DB-only restore; the filestore mirror is handled separately (filestore_sync.sh / DR guide scenario 2)

cd "$REPO_DIR"

RESTORE_ARGS=(--stanza="$STANZA" restore)
if [[ -n "$TARGET" ]]; then
    # target-action=promote: auto-promote at target instead of pausing in recovery
    RESTORE_ARGS+=(--type=time --target="$TARGET" --target-action=promote)
fi

log "step 1/5: stopping web + db containers"
docker compose stop web db || true

log "step 2/5: emptying data volume (fresh restore target)"
docker run --rm \
    -v "$PG_DATA_VOL":/var/lib/postgresql/data \
    --entrypoint sh \
    "$DB_IMAGE" \
    -c 'rm -rf /var/lib/postgresql/data/* && chown -R postgres:postgres /var/lib/postgresql/data'

log "step 3/5: pgbackrest restore (${TARGET:-latest backup})"
START_TS=$(date +%s)
docker run --rm \
    --user postgres \
    -v "$PG_DATA_VOL":/var/lib/postgresql/data \
    -v "$BACKUP_ROOT/pgbackrest":/var/lib/pgbackrest \
    -v "$REPO_DIR/pgbackrest.conf":/etc/pgbackrest/pgbackrest.conf:ro \
    --entrypoint pgbackrest \
    "$DB_IMAGE" "${RESTORE_ARGS[@]}"

log "step 4/5: starting stack"
docker compose up -d

log "step 5/5: waiting for postgres (WAL replay can take minutes) ..."
for _ in $(seq 1 60); do
    if docker compose exec -T db pg_isready >/dev/null 2>&1; then
        log "OK: postgres accepting connections. Total restore time: $(( $(date +%s) - START_TS ))s"
        log "=== restore end ==="
        log "next: verify your marker data; new host? re-install cron via ./backup/install_cron.sh"
        exit 0
    fi
    sleep 2
done

log "WARN: postgres not accepting connections after 120s — investigate:"
log "  docker compose logs db | tail -50"
exit 1
