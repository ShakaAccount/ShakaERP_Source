#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"
STANZA="shaka_db"

mkdir -p "$BACKUP_ROOT/pgbackrest" "$BACKUP_ROOT/filestore" "$BACKUP_ROOT/logs"

echo ">> Fixing ownership of $BACKUP_ROOT/pgbackrest -> postgres (uid 999) ..."
docker run --rm -v "$BACKUP_ROOT":/opt/backups busybox:1.36 \
    sh -c 'chown -R 999:999 /opt/backups/pgbackrest && chmod -R 750 /opt/backups/pgbackrest'

echo ">> Building db image (pgvector:pg16 + pgBackRest) ..."
docker compose -f "$REPO_DIR/docker-compose.yml" build db

echo ">> Starting db container ..."
docker compose -f "$REPO_DIR/docker-compose.yml" up -d db

echo ">> Waiting for db to become healthy ..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' odoo_19_db 2>/dev/null)" = "healthy" ]; do
    sleep 2
done
echo ">> db is healthy."

echo ">> Creating pgBackRest stanza '$STANZA' ..."
docker compose -f "$REPO_DIR/docker-compose.yml" exec -T -u postgres db \
    pgbackrest --stanza="$STANZA" stanza-create

echo ">> Running pgBackRest check ..."
docker compose -f "$REPO_DIR/docker-compose.yml" exec -T -u postgres db \
    pgbackrest --stanza="$STANZA" check

echo ">> Running initial full backup ..."
docker compose -f "$REPO_DIR/docker-compose.yml" exec -T -u postgres db \
    pgbackrest --stanza="$STANZA" --type=full backup

echo ">> Building filestore sync helper image ..."
docker build -f "$REPO_DIR/filestore-sync.Dockerfile" -t odoo_filestore_sync "$REPO_DIR"

echo ""
echo "Setup complete."
echo "  Backups:   $BACKUP_ROOT"
echo "  Database:  pgBackRest stanza '$STANZA' with continuous WAL archiving (RPO ~ seconds)"
echo "  Filestore: synced to $BACKUP_ROOT/filestore every 15 min (via cron)"
echo "  Next step: run backup/install_cron.sh to schedule cron jobs."