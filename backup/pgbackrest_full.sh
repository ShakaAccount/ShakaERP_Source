#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
STANZA="shaka_db"

docker compose -f "$REPO_DIR/docker-compose.yml" exec -T -u postgres db \
    pgbackrest --stanza="$STANZA" --type=full backup