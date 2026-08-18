#!/usr/bin/env bash
set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/lib/local_backups"

mkdir -p ${BACKUP_DIR}/database ${BACKUP_DIR}/filestore

echo "Starting logical database backup..."
pg_dump -h db -U ${POSTGRES_USER} -d ${POSTGRES_DB} -Fc -f ${BACKUP_DIR}/database/odoo_${DATE}.dump

echo "Starting Odoo filestore archive..."
tar -czf ${BACKUP_DIR}/filestore/filestore_${DATE}.tar.gz -C /var/lib/odoo filestore

echo "Local backup complete! Output directory: ${BACKUP_DIR}"
