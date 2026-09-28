#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"

STANZA="shaka_db"
DB_IMAGE="odoo_19_db:pg16"
PG_DATA_VOL="odoo_19_pg_data"
ODOO_DATA_VOL="odoo_19_data"
TMP_VOL="odoo_19_restore_tmp"
TMP_CT="odoo_19_restore_tmp"
DUMP_DIR="$BACKUP_ROOT/restore_dumps"
LOG="$BACKUP_ROOT/logs/restore.log"
STAMP="$(date '+%Y%m%d_%H%M%S')"

usage() {
    cat <<EOF
Restore Postgres from the pgBackRest repo ($BACKUP_ROOT/pgbackrest).

Usage:
  ./backup/restore_tui.py
      Interactive: pick a database and a time on a backup timeline.

  $(basename "$0") --list
      Show available backups, the databases in each, and the PITR time window.

  $(basename "$0") --db NAME [--as NEWNAME] [--target 'YYYY-MM-DD HH:MM:SS'] [--yes]
      Restore ONE database. Other databases are not touched and the server
      stays up. The backup is restored into a temporary side container, NAME
      is dumped from it and loaded into the live server.
        (default)     replaces NAME; the current copy is kept as
                      NAME_before_restore_<timestamp> (drop it when happy).
                      Odoo (web) is stopped during the swap.
        --as NEWNAME  restores next to it as NEWNAME instead (Odoo keeps
                      running; the filestore folder is copied too).

  $(basename "$0") --all [--target 'YYYY-MM-DD HH:MM:SS'] [--yes]
      Restore the WHOLE cluster (every database + roles). Wipes the live
      data volume. Use for disaster recovery / new host.

Options:
  --target TS   point-in-time: state of the data at TS (db server time zone,
                or add an offset: '2026-08-18 14:30:00+03:30').
                Omit for the latest data available.
  --yes         don't ask for confirmation.
  -h, --help    this help.

Examples:
  $(basename "$0") --list
  $(basename "$0") --db shaka --target '2026-08-18 14:30:00'
  $(basename "$0") --db shaka --as shaka_yesterday --target '2026-08-17 18:00:00'
  $(basename "$0") --all --yes
EOF
}

# --- output helpers ---
if [[ -t 1 ]]; then B=$'\e[1m'; R=$'\e[31m'; G=$'\e[32m'; Y=$'\e[33m'; N=$'\e[0m'; else B= R= G= Y= N=; fi
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
ok()   { log "${G}OK${N}: $*"; }
warn() { log "${Y}WARN${N}: $*"; }
die()  { log "${R}FAIL${N}: $*"; exit 1; }
confirm() {
    [[ -n "$ASSUME_YES" ]] && return
    printf '\n%s%s%s\nType YES to continue: ' "$B" "$1" "$N"
    read -r ANSWER
    [[ "$ANSWER" == "YES" ]] || { log "aborted, nothing changed"; exit 1; }
}

# pgbackrest against the host repo, independent of the live db container
pgbr() {
    docker run --rm --user postgres \
        -v "$BACKUP_ROOT/pgbackrest":/var/lib/pgbackrest \
        -v "$REPO_DIR/pgbackrest.conf":/etc/pgbackrest/pgbackrest.conf:ro \
        "$@"
}

# --- args ---
MODE="" DB="" AS="" TARGET="" ASSUME_YES=""
[[ $# -eq 0 ]] && { usage; exit 2; }
while [[ $# -gt 0 ]]; do
    case "$1" in
        --list) MODE=list ;;
        --all) MODE=all ;;
        --db) MODE=db; DB="${2:?--db needs a database name}"; shift ;;
        --as) AS="${2:?--as needs a new database name}"; shift ;;
        --target) TARGET="${2:?--target needs a timestamp: 'YYYY-MM-DD HH:MM:SS'}"; shift ;;
        --yes) ASSUME_YES=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option '$1'"; echo; usage; exit 2 ;;
    esac
    shift
done
[[ -z "$MODE" ]] && { echo "pick one of --list, --db NAME, --all"; echo; usage; exit 2; }
[[ -n "$AS" && "$MODE" != db ]] && die "--as only works together with --db"
[[ -n "$TARGET" && ! "$TARGET" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}(:[0-9]{2})?([+-][0-9]{2}(:[0-9]{2})?)?$ ]] \
    && die "--target must look like 'YYYY-MM-DD HH:MM:SS', got '$TARGET'"

cd "$REPO_DIR"
PGUSER="$(grep -E '^POSTGRES_USER=' .env 2>/dev/null | cut -d= -f2- | tr -d "\"'")"
PGUSER="${PGUSER:-shaka}"

# --- list: read-only ---
if [[ "$MODE" == list ]]; then
    INFO=$(pgbr --entrypoint pgbackrest "$DB_IMAGE" --stanza="$STANZA" info) || die "cannot read repo at $BACKUP_ROOT/pgbackrest"
    echo "$INFO"
    echo
    echo "${B}Databases per backup:${N}"
    for SET in $(grep -oE '[0-9]{8}-[0-9]{6}F(_[0-9]{8}-[0-9]{6}[DI])?' <<<"$INFO"); do
        printf '  %s: ' "$SET"
        pgbr --entrypoint pgbackrest "$DB_IMAGE" --stanza="$STANZA" --set="$SET" info \
            | sed -n 's/.*database list: //p' | sed -E 's/ \([0-9]+\)//g'
    done
    echo
    echo "Point-in-time --target can be anything between the oldest backup's"
    echo "start time and the 'wal archive max' shown above."
    exit 0
fi

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1
log "=== restore start: mode=$MODE db=${DB:-*} as=${AS:--} target=${TARGET:-latest} ==="

# --- preflight: repo must be readable AND contain a complete full backup
#     BEFORE we touch anything. Never destroy data on a hunch.
log "checking the backup repo ..."
INFO=$(pgbr --entrypoint pgbackrest "$DB_IMAGE" --stanza="$STANZA" info 2>&1) \
    || { echo "$INFO"; die "cannot read repo at $BACKUP_ROOT/pgbackrest. Nothing was changed."; }
grep -q "full backup" <<<"$INFO" || { echo "$INFO"; die "no complete full backup in repo. Nothing was changed."; }
ok "repo readable, full backup present"

RESTORE_ARGS=(--stanza="$STANZA" restore)
if [[ -n "$TARGET" ]]; then
    # target-action=promote: auto-promote at target instead of pausing in recovery
    RESTORE_ARGS+=(--type=time --target="$TARGET" --target-action=promote)
fi

# ======================================================================
# --all: whole-cluster restore (disaster recovery)
# ======================================================================
if [[ "$MODE" == all ]]; then
    confirm "This WIPES the live database volume \"$PG_DATA_VOL\" (ALL databases) and restores it from backup (${TARGET:-latest})."

    # ponytail: DB-only restore; the filestore mirror is handled separately (filestore_sync.sh / DR guide scenario 2)

    log "step 1/5: stopping web + db containers"
    docker compose stop web db || true

    log "step 2/5: emptying data volume"
    docker run --rm -v "$PG_DATA_VOL":/var/lib/postgresql/data --entrypoint sh "$DB_IMAGE" \
        -c 'rm -rf /var/lib/postgresql/data/* && chown -R postgres:postgres /var/lib/postgresql/data'

    log "step 3/5: pgbackrest restore (${TARGET:-latest backup})"
    START_TS=$(date +%s)
    pgbr -v "$PG_DATA_VOL":/var/lib/postgresql/data --entrypoint pgbackrest "$DB_IMAGE" "${RESTORE_ARGS[@]}"

    log "step 4/5: starting stack"
    docker compose up -d

    log "step 5/5: waiting for postgres (WAL replay can take minutes) ..."
    for _ in $(seq 1 60); do
        if docker compose exec -T db pg_isready >/dev/null 2>&1; then
            ok "postgres accepting connections. Total restore time: $(( $(date +%s) - START_TS ))s"
            log "next: check your data; new host? re-install cron via ./backup/install_cron.sh"
            log "=== restore end ==="
            exit 0
        fi
        sleep 2
    done
    warn "postgres not accepting connections after 120s — investigate: docker compose logs db | tail -50"
    exit 1
fi

# ======================================================================
# --db: single-database restore via a temporary side cluster
# ======================================================================
DEST="${AS:-$DB}"
OLD="${DB}_before_restore_${STAMP}"
DUMP="$DUMP_DIR/${DB}_${STAMP}.dump"
live_psql() { docker compose exec -T db psql -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 -qtA "$@"; }
tmp_psql()  { docker exec "$TMP_CT" psql -U "$PGUSER" -d postgres -qtA "$@"; }

docker compose exec -T db pg_isready >/dev/null 2>&1 \
    || die "the live db container isn't running. Start it (docker compose up -d db), or use --all for a full rebuild."

LIVE_HAS_DEST=$(live_psql -c "SELECT 1 FROM pg_database WHERE datname = '$DEST'")
if [[ -n "$AS" && -n "$LIVE_HAS_DEST" ]]; then
    die "database '$AS' already exists on the live server. Pick another --as name or drop it first."
fi

if [[ -n "$AS" ]]; then
    confirm "Restore '$DB' (${TARGET:-latest}) as NEW database '$AS'. Nothing existing is changed."
elif [[ -n "$LIVE_HAS_DEST" ]]; then
    confirm "Replace live database '$DB' with its backup (${TARGET:-latest}). Odoo will be stopped briefly; the current '$DB' is kept as '$OLD'."
else
    confirm "Database '$DB' does not exist on the live server; it will be created from backup (${TARGET:-latest})."
fi

cleanup() {
    docker rm -f "$TMP_CT" >/dev/null 2>&1 || true
    docker volume rm "$TMP_VOL" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup  # leftovers from an interrupted run

START_TS=$(date +%s)
log "step 1/5: restoring backup into a temporary volume (only '$DB' gets real data)"
docker volume create "$TMP_VOL" >/dev/null
docker run --rm -v "$TMP_VOL":/var/lib/postgresql/data --entrypoint sh "$DB_IMAGE" \
    -c 'chown -R postgres:postgres /var/lib/postgresql/data'
pgbr -v "$TMP_VOL":/var/lib/postgresql/data --entrypoint pgbackrest "$DB_IMAGE" \
    "${RESTORE_ARGS[@]}" --db-include="$DB" \
    || die "pgbackrest restore failed. Does '$DB' exist in that backup? Check with --list. Live server untouched."

log "step 2/5: starting temporary postgres and replaying WAL (can take minutes) ..."
# archive_mode off: the side cluster must never push WAL into the real repo
docker run -d --name "$TMP_CT" --user postgres \
    -v "$TMP_VOL":/var/lib/postgresql/data \
    -v "$BACKUP_ROOT/pgbackrest":/var/lib/pgbackrest \
    -v "$REPO_DIR/pgbackrest.conf":/etc/pgbackrest/pgbackrest.conf:ro \
    "$DB_IMAGE" postgres -c archive_mode=off -c listen_addresses='' \
    -c unix_socket_directories=/var/run/postgresql >/dev/null
READY=""
for _ in $(seq 1 300); do
    if [[ "$(tmp_psql -c 'SELECT pg_is_in_recovery()' 2>/dev/null)" == "f" ]]; then READY=1; break; fi
    docker ps -q -f name="^${TMP_CT}$" | grep -q . || break
    sleep 2
done
[[ -n "$READY" ]] || { docker logs --tail 30 "$TMP_CT" || true; die "temporary postgres did not finish recovery. Live server untouched."; }
ok "temporary copy of '$DB' is up"

log "step 3/5: dumping '$DB' from the temporary copy"
mkdir -p "$DUMP_DIR"
OWNER=$(tmp_psql -c "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '$DB'")
[[ -n "$OWNER" ]] || die "'$DB' not found in the restored backup. Live server untouched."
docker exec "$TMP_CT" pg_dump -U "$PGUSER" -Fc -d "$DB" > "$DUMP"
ok "dump saved: $DUMP ($(du -h "$DUMP" | cut -f1))"
cleanup

log "step 4/5: loading into the live server as '$DEST'"
if [[ -z "$AS" && -n "$LIVE_HAS_DEST" ]]; then
    log "  stopping Odoo and moving current '$DB' aside to '$OLD'"
    docker compose stop web
    live_psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB' AND pid <> pg_backend_pid()" >/dev/null
    live_psql -c "ALTER DATABASE \"$DB\" RENAME TO \"$OLD\""
fi
live_psql -c "CREATE DATABASE \"$DEST\" OWNER \"$OWNER\" TEMPLATE template0"
if ! docker compose exec -T db pg_restore -U "$PGUSER" -d "$DEST" --exit-on-error < "$DUMP"; then
    warn "loading failed, rolling back"
    live_psql -c "DROP DATABASE IF EXISTS \"$DEST\"" || true
    if [[ -z "$AS" && -n "$LIVE_HAS_DEST" ]]; then
        live_psql -c "ALTER DATABASE \"$OLD\" RENAME TO \"$DB\"" && docker compose start web
    fi
    die "restore of '$DEST' failed; live data is as before. Dump kept at $DUMP"
fi

if [[ -n "$AS" ]]; then
    # Odoo keys the filestore by db name: give the copy its own attachments
    docker run --rm -v "$ODOO_DATA_VOL":/d --entrypoint sh "$DB_IMAGE" -c \
        "[ -d /d/filestore/$DB ] && cp -a /d/filestore/$DB /d/filestore/$AS || true"
elif [[ -n "$LIVE_HAS_DEST" ]]; then
    docker compose start web
fi

log "step 5/5: done in $(( $(date +%s) - START_TS ))s"
ok "'$DEST' restored from backup (${TARGET:-latest})"
[[ -z "$AS" && -n "$LIVE_HAS_DEST" ]] && log "the previous '$DB' is kept as '$OLD'. When you're happy:
    docker compose exec db psql -U $PGUSER -d postgres -c 'DROP DATABASE \"$OLD\"'"
log "the dump in $DUMP can be deleted once you've checked the data"
log "=== restore end ==="
