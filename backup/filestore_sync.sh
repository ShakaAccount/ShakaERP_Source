#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"

mkdir -p "$BACKUP_ROOT/filestore"

# Incremental sync of the Odoo filestore (attachments) to the host backup dir.
# Runs every 15 min (see install_cron.sh); --delete keeps the mirror clean.
docker run --rm \
    -v odoo_19_data:/src:ro \
    -v "$BACKUP_ROOT/filestore":/dst \
    odoo_filestore_sync -a --delete /src/filestore/ /dst/