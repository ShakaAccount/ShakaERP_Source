#!/usr/bin/env bash
# deploy_init.sh — Linux counterpart of deploy_init.ps1 (same steps, same names).
# Requires: docker + docker compose v2. Run from anywhere; paths auto-locate.
set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$SCRIPT_DIR}"
BACKUP_ROOT="${BACKUP_ROOT:-$(dirname "$REPO_DIR")/backups}"
STANZA="shaka_db"
DB_CONTAINER="odoo_19_db"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

gen_password() { openssl rand -base64 32 | tr -d '/+=' | cut -c1-32; }

# --- 1. Prerequisites ---
log "Checking prerequisites..."
command -v docker >/dev/null || { echo "Docker not installed. Aborting." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 plugin not installed. Aborting." >&2; exit 1; }

# --- 2. Use repository location ---
log "Using project at $REPO_DIR"
cd "$REPO_DIR"

# --- 3. Create .env if missing ---
ENV_FILE="$REPO_DIR/.env"
if [[ ! -f $ENV_FILE ]]; then
    log "Generating .env with random passwords..."
    POSTGRES_USER="shaka"
    POSTGRES_PASSWORD="$(gen_password)"
    POSTGRES_DB="postgres"
    POSTGRES_HOST="db"
    POSTGRES_PORT="5432"
    SHAKA_MASTER_PASSWORD="$(gen_password)"
    ADMIN_PASSWORD="$SHAKA_MASTER_PASSWORD"
    WORKERS="4"
    MAX_CRON_THREADS="2"
    GEVENT_PORT="8072"
    cat > "$ENV_FILE" <<EOF
# Database Credentials
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB
POSTGRES_HOST=$POSTGRES_HOST
POSTGRES_PORT=$POSTGRES_PORT

# Shaka Settings
SHAKA_MASTER_PASSWORD=$SHAKA_MASTER_PASSWORD
ADMIN_PASSWORD=$ADMIN_PASSWORD
WORKERS=$WORKERS
MAX_CRON_THREADS=$MAX_CRON_THREADS
GEVENT_PORT=$GEVENT_PORT
EOF
    chmod 600 "$ENV_FILE"
    log "Created .env (keep it safe!)"
else
    log ".env already exists, using existing credentials."
fi
set -a; . "$ENV_FILE"; set +a

# --- 4. Generate odoo.conf ---
log "Generating odoo.conf from template..."
cat > "$REPO_DIR/odoo.conf" <<EOF
[options]
; Database
db_host = ${POSTGRES_HOST}
db_port = ${POSTGRES_PORT}
db_user = ${POSTGRES_USER}
db_password = ${POSTGRES_PASSWORD}

; Security
admin_passwd = ${SHAKA_MASTER_PASSWORD}

; Proxy
proxy_mode = True

; Paths
addons_path = /opt/odoo/addons,/opt/odoo/custom_addons
data_dir = /var/lib/odoo

; Logging
log_level = info

; Performance
workers = ${WORKERS}
max_cron_threads = ${MAX_CRON_THREADS}
gevent_port = ${GEVENT_PORT}
EOF

# --- 5. Ensure backup directories exist ---
log "Creating backup directories..."
mkdir -p "$BACKUP_ROOT"/{pgbackrest,filestore,logs,config}

# 5b. Back up .env and odoo.conf to config/ (first time only)
if [[ ! -f "$BACKUP_ROOT/config/.env" ]]; then
    log "Backing up .env and odoo.conf to $BACKUP_ROOT/config/ ..."
    cp -f "$ENV_FILE" "$BACKUP_ROOT/config/.env"
    cp -f "$REPO_DIR/odoo.conf" "$BACKUP_ROOT/config/odoo.conf"
    chmod 600 "$BACKUP_ROOT/config/.env"
fi

# --- 6. Fix pgBackRest directory ownership (postgres uid 999 inside container) ---
log "Fixing pgBackRest directory ownership..."
docker run --rm -v "$BACKUP_ROOT:/opt/backups" busybox:1.36 \
    sh -c "chown -R 999:999 /opt/backups/pgbackrest && chmod -R 750 /opt/backups/pgbackrest"

# --- 7. Build images ---
log "Building database image (pgvector + pgBackRest)..."
docker compose build db

log "Building filestore sync helper image..."
docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync .

# --- 8. Start database and wait for health ---
log "Starting database container..."
docker compose up -d db

log "Waiting for database to become healthy..."
until [[ "$(docker inspect -f '{{.State.Health.Status}}' "$DB_CONTAINER" 2>/dev/null || echo starting)" == "healthy" ]]; do
    sleep 2
done
log "Database healthy."

# --- 9. Initialize pgBackRest stanza ---
log "Creating pgBackRest stanza '$STANZA'..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" stanza-create

log "Running pgBackRest check..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

# --- 10. Initial full backup if none exist ---
if ! docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" info 2>/dev/null | grep -q "full backup:"; then
    log "No existing backups found. Running initial full backup..."
    docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" --type=full backup
else
    log "Existing backups detected. Skipping initial full backup."
fi

# --- 11. Start Odoo web + nginx ---
log "Starting web and nginx..."
docker compose up -d web nginx

# --- 12. Initial filestore sync ---
log "Running initial filestore sync..."
docker run --rm -v odoo_19_data:/data -v "$BACKUP_ROOT/filestore:/backup" odoo_filestore_sync

# --- 13. Schedule recurring jobs (cron replaces Windows scheduled tasks) ---
log "Installing cron entries (filestore every 15 min, full DB daily at 02:15)..."
SYNC_LINE="*/15 * * * * docker run --rm -v odoo_19_data:/data -v $BACKUP_ROOT/filestore:/backup odoo_filestore_sync >> $BACKUP_ROOT/logs/filestore_sync.log 2>&1"
BACKUP_LINE="15 2 * * * docker compose -f $REPO_DIR/docker-compose.yml exec -T -u postgres db pgbackrest --stanza=$STANZA --type=full backup >> $BACKUP_ROOT/logs/db_backup.log 2>&1"
existing_crontab="$(crontab -l 2>/dev/null || true)"
new_crontab="$(echo "$existing_crontab" | grep -vF -e 'odoo_filestore_sync' -e 'pgbackrest --stanza' || true)"
printf '%s\n%s\n%s\n' "$new_crontab" "$SYNC_LINE" "$BACKUP_LINE" | sed '/^$/d' | crontab -

# --- 14. Final verification ---
log "Verifying backup health..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

log "Deployment initialization complete."
echo ""
echo "=== SUMMARY ==="
echo "Project:       $REPO_DIR"
echo "Backups:       $BACKUP_ROOT"
echo "Database:      pgBackRest stanza '$STANZA' (continuous WAL, daily full)"
echo "Filestore:     rsync mirror every 15 min (via cron)"
echo "Cron entries:  installed (run 'crontab -l' to verify)"
echo ""
echo "Next steps:"
echo "  - Verify Odoo accessible at http://<server-ip>"
echo "  - Test a restore on staging: ./backup/restore.sh"
echo "  - Configure off-site replication for $BACKUP_ROOT"
