#!/usr/bin/env bash
# deploy_update.sh — Pull latest code and redeploy Odoo 19 stack (preserves data & backups)
# Run as root or a user with docker privileges

set -euo pipefail

# === CONFIGURATION (defaults are repo-location-aware — no hardcoded folder) ===
# Script auto-locates itself, so it works wherever the repo is cloned.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$SCRIPT_DIR}"
# Backups live next to the repo (sibling dir) unless overridden.
BACKUP_ROOT="${BACKUP_ROOT:-$(cd "$REPO_DIR/.." && pwd)/backups}"
STANZA="shaka_db"
DB_IMAGE="odoo_19_db:pg16"
# ===========================================

log() { echo "[$(date '+%F %T')] $*"; }

# 1. Prerequisites
log "Checking prerequisites..."
command -v docker >/dev/null || { echo "Docker not installed"; exit 1; }
command -v docker compose >/dev/null || { echo "Docker Compose plugin not installed"; exit 1; }

# 2. Go to repo and pull latest
log "Updating repository at $REPO_DIR..."
cd "$REPO_DIR"
git pull --ff-only

# 3. Re-generate odoo.conf from template (in case template changed)
if [[ -f .env ]]; then
    log "Regenerating odoo.conf from environment..."
    set -a
    source .env
    set +a
    envsubst < odoo.conf > /tmp/odoo.conf.generated && mv /tmp/odoo.conf.generated odoo.conf
else
    log "WARNING: .env not found — run deploy_init.sh first"
    exit 1
fi

# 4. Rebuild images (only if Dockerfiles changed)
log "Building images (db, filestore-sync)..."
docker compose build db
docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync .

# 5. Stop web/nginx (keep db running for zero-downtime DB migrations)
log "Stopping web and nginx..."
docker compose stop web nginx

# 6. Run Odoo migrations (if any) — starts web briefly with --update=all
log "Running Odoo database migrations..."
docker compose run --rm -T web \
    ./odoo-bin -c /etc/odoo/odoo.conf --db_host=db -r "${POSTGRES_USER}" -w "${POSTGRES_PASSWORD}" -u all --stop-after-init

# 7. Start all services
log "Starting web and nginx..."
docker compose up -d web nginx

# 8. Verify health
log "Verifying deployment..."
sleep 5
docker compose ps

# 9. Quick backup health check
log "Checking pgBackRest repo..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

log "Update complete."
echo ""
echo "=== SUMMARY ==="
echo "Repository:    $REPO_DIR (updated via git pull)"
echo "Data volumes:  PRESERVED (pg_data, odoo_data)"
echo "Backups:       $BACKUP_ROOT (unchanged)"
echo "Services:      db, web, nginx restarted"
echo ""
echo "Next steps:"
echo "  - Verify Odoo accessible at http://<server-ip>"
echo "  - Check logs: docker compose logs -f web"
echo "  - Run manual filestore sync: $REPO_DIR/backup/filestore_sync.sh"