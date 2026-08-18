#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$(cd "$REPO_DIR/.." && pwd)/backups"

mkdir -p "$BACKUP_ROOT/logs"

INSTALL_MARK="# odoo-19 backup (RPO 15min)"
CRON_LINE_FS="*/15 * * * * $SCRIPT_DIR/filestore_sync.sh >> $BACKUP_ROOT/logs/filestore_sync.log 2>&1"
CRON_LINE_FULL="15 2 * * * $SCRIPT_DIR/pgbackrest_full.sh >> $BACKUP_ROOT/logs/pgbackrest_full.log 2>&1"

TMP=$(mktemp)
crontab -l > "$TMP" 2>/dev/null || true

if ! grep -qF "$INSTALL_MARK" "$TMP"; then
    printf '\n%s\n' "$INSTALL_MARK" >> "$TMP"
fi

if grep -qF "filestore_sync.sh" "$TMP"; then
    echo ">> filestore cron already installed, skipping."
else
    echo ">> Installing filestore sync every 15 min."
    printf '%s\n' "$CRON_LINE_FS" >> "$TMP"
fi

if grep -qF "pgbackrest_full.sh" "$TMP"; then
    echo ">> pgbackrest daily cron already installed, skipping."
else
    echo ">> Installing daily full backup at 02:15."
    printf '%s\n' "$CRON_LINE_FULL" >> "$TMP"
fi

crontab "$TMP"
rm -f "$TMP"

echo ">> Current crontab:"
crontab -l | grep -A3 "$INSTALL_MARK"