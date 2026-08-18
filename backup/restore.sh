#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"
STANZA="shaka_db"
DB_IMAGE="odoo_19_db:pg16"
PG_DATA_VOL="odoo_19_pg_data"

cd "$REPO_DIR"

echo ">> Stopping db container ..."
docker compose stop db || true

echo ">> Emptying the data volume (fresh restore target) ..."
docker run --rm \
    -v "$PG_DATA_VOL":/var/lib/postgresql/data \
    --entrypoint sh \
    "$DB_IMAGE" \
    -c 'rm -rf /var/lib/postgresql/data/* && chown -R postgres:postgres /var/lib/postgresql/data'

echo ">> Restoring latest backup from pgBackRest ..."
docker run --rm \
    --user postgres \
    -v "$PG_DATA_VOL":/var/lib/postgresql/data \
    -v "$BACKUP_ROOT/pgbackrest":/var/lib/pgbackrest \
    -v "$REPO_DIR/pgbackrest.conf":/etc/pgbackrest/pgbackrest.conf:ro \
    --entrypoint pgbackrest \
    "$DB_IMAGE" \
    --stanza="$STANZA" restore

echo ">> Starting db container with restored data ..."
docker compose up -d db

echo ">> Done. Verify with: docker compose exec -T -u postgres db pgbackrest --stanza=$STANZA check"
echo ">> For a point-in-time restore add:  --type=time --target='YYYY-MM-DD HH:MM:SS'"