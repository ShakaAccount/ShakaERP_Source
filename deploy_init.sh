#!/usr/bin/env bash
# deploy_init.sh — Initialize Odoo 19 stack with automated backups on a fresh server
# Run as root or a user with docker privileges

set -euo pipefail

# === CONFIGURATION (edit before running) ===
REPO_DIR="${REPO_DIR:-/opt/odoo-19}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/backups}"
STANZA="shaka_db"
DB_IMAGE="odoo_19_db:pg16"
PG_DATA_VOL="odoo_19_pg_data"
ODOO_DATA_VOL="odoo_19_data"
# ===========================================

log() { echo "[$(date '+%F %T')] $*"; }

# 1. Prerequisites
log "Checking prerequisites..."
command -v docker >/dev/null || { echo "Docker not installed"; exit 1; }
command -v docker compose >/dev/null || { echo "Docker Compose plugin not installed"; exit 1; }
docker compose version | grep -q "v2" || { echo "Docker Compose v2 required"; exit 1; }

# 2. Clone / copy project (assumes you already have the repo at $REPO_DIR)
log "Using project at $REPO_DIR"
cd "$REPO_DIR"

# 3. Restore .env from secure location (you must provide this)
if [[ ! -f .env ]]; then
    log "ERROR: .env not found. Copy your production .env to $REPO_DIR/.env"
    echo "Required variables: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, SHAKA_MASTER_PASSWORD"
    exit 1
fi

# 4. Restore backup storage from off-site (rsync from your backup server)
#    Uncomment and adjust the source:
# log "Syncing backup storage from remote..."
# rsync -avz --progress backup-user@backup-server:/backups/ "$BACKUP_ROOT/"

# 5. Ensure backup directories exist
mkdir -p "$BACKUP_ROOT/pgbackrest" "$BACKUP_ROOT/filestore" "$BACKUP_ROOT/logs"

# 6. Fix pgBackRest ownership (postgres uid 999 inside container)
log "Fixing pgBackRest directory ownership..."
docker run --rm -v "$BACKUP_ROOT":/opt/backups busybox:1.36 \
    sh -c 'chown -R 999:999 /opt/backups/pgbackrest && chmod -R 750 /opt/backups/pgbackrest'

# 7. Build images
log "Building database image (pgvector + pgBackRest)..."
docker compose build db

log "Building filestore sync helper image..."
docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync .

# 8. Start database
log "Starting database container..."
docker compose up -d db

# Wait for healthcheck
log "Waiting for database to become healthy..."
until [[ "$(docker inspect -f '{{.State.Health.Status}}' odoo_19_db 2>/dev/null)" == "healthy" ]]; do
    sleep 2
done
log "Database healthy."

# 9. Initialize pgBackRest stanza
log "Creating pgBackRest stanza '$STANZA'..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" stanza-create

log "Running pgBackRest check..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

# 10. Run initial full backup (if repo is empty)
if ! docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" info 2>/dev/null | grep -q "full backup:"; then
    log "No existing backups found. Running initial full backup..."
    docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" --type=full backup
else
    log "Existing backups detected. Skipping initial full backup."
fi

# 11. Start Odoo web + nginx
log "Starting web and nginx..."
docker compose up -d web nginx

# 12. Initial filestore sync (creates mirror)
log "Running initial filestore sync..."
./backup/filestore_sync.sh

# 13. Install cron jobs for automated backups
log "Installing cron jobs (filestore every 15 min, full DB daily at 02:15)..."
./backup/install_cron.sh

# 14. Final verification
log "Verifying backup health..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

log "Deployment initialization complete."
echo ""
echo "=== SUMMARY ==="
echo "Project:       $REPO_DIR"
echo "Backups:       $BACKUP_ROOT"
echo "Database:      pgBackRest stanza '$STANZA' (continuous WAL, daily full)"
echo "Filestore:     rsync mirror every 15 min"
echo "Cron:          Installed (run 'crontab -l' to verify)"
echo ""
echo "Next steps:"
echo "  - Verify Odoo accessible at http://<server-ip>"
echo "  - Test a restore on staging: ./backup/restore.sh"
echo "  - Configure off-site replication for $BACKUP_ROOT"