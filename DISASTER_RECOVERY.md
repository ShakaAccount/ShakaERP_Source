# Odoo 19 Disaster Recovery Guide

## Overview

This document describes the backup architecture and step-by-step disaster recovery procedures for the Odoo 19 deployment.

### Backup Architecture

| Component | Technology | RPO | Retention | Location |
|-----------|------------|-----|-----------|----------|
| PostgreSQL Database | pgBackRest (continuous WAL archiving + daily full) | **~seconds** (well under 15 min target) | 2 full backups + 7 days WAL | `$BACKUPS/pgbackrest/` |
| Odoo Filestore (attachments) | rsync incremental mirror | **15 minutes** (cron) | Rolling mirror (--delete) | `$BACKUPS/filestore/` |

### Key Properties

- **Database RPO**: Continuous WAL archiving (`archive_timeout=30s`) → near-zero data loss
- **Filestore RPO**: Cron runs every 15 minutes (`*/15 * * * *`)
- **Backup Storage**: Host directory `$BACKUPS/` survives container rebuilds
- **Encryption**: Not enabled (add `--repo1-cipher-type=aes-256-cbc` if required)

---

## Quick Reference

```bash
# Repository root
REPO=~/Shaka
BACKUPS=~/backups

# Verify backups are healthy
docker compose -f $REPO/docker-compose.yml exec -T -u postgres db pgbackrest --stanza=shaka_db check

# List available backups
docker compose -f $REPO/docker-compose.yml exec -T -u postgres db pgbackrest --stanza=shaka_db info

# Manual full backup (run before maintenance)
$REPO/backup/pgbackrest_full.sh

# Manual filestore sync
$REPO/backup/filestore_sync.sh
```

---

## Disaster Scenarios & Recovery Procedures

### Scenario 1: Database Corruption / Accidental DROP / Point-in-Time Recovery

**When to use**: Data corruption, accidental `DROP TABLE`, need to recover to specific timestamp.

**RPO**: Seconds (WAL archiving)

#### Step-by-Step Recovery

```bash
cd ~/Shaka

# 1. Stop application (web) to prevent new writes
docker compose stop web

# 2. Stop database
docker compose stop db

# 3. Empty the PostgreSQL data volume (fresh restore target)
docker run --rm \
    -v odoo_19_pg_data:/var/lib/postgresql/data \
    --entrypoint sh \
    odoo_19_db:pg16 \
    -c 'rm -rf /var/lib/postgresql/data/* && chown -R postgres:postgres /var/lib/postgresql/data'

# 4A. Full restore (latest backup)
docker run --rm \
    --user postgres \
    -v odoo_19_pg_data:/var/lib/postgresql/data \
    -v ~/backups/pgbackrest:/var/lib/pgbackrest \
    -v ~/Shaka/pgbackrest.conf:/etc/pgbackrest/pgbackrest.conf:ro \
    --entrypoint pgbackrest \
    odoo_19_db:pg16 \
    --stanza=shaka_db restore

# 4B. Point-in-time restore (replace timestamp as needed)
# docker run --rm ... pgbackrest --stanza=shaka_db --type=time --target='2026-08-18 14:30:00' restore

# 5. Start database
docker compose up -d db

# 6. Verify database health
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db check

# 7. Start application
docker compose up -d web
```

**Verification**:
```bash
# Check Odoo can connect
docker compose logs web | tail -20

# Verify data integrity
docker compose exec -T -u postgres db psql -U shaka -d postgres -c "SELECT count(*) FROM ir_module_module WHERE state='installed';"
```

---

### Scenario 2: Filestore Corruption / Deleted Attachments

**When to use**: Missing attachments, corrupted filestore, accidental file deletion.

**RPO**: Up to 15 minutes (last cron run)

#### Step-by-Step Recovery

```bash
cd ~/Shaka

# 1. Stop application (prevents new file writes during restore)
docker compose stop web

# 2. Restore filestore from backup mirror (--delete removes extra files)
docker run --rm \
    -v odoo_19_data:/dst \
    -v ~/backups/filestore:/src:ro \
    odoo_filestore_sync -a --delete /src/ /dst/filestore/

# 3. Fix ownership (Odoo runs as uid 1000)
docker run --rm \
    -v odoo_19_data:/var/lib/odoo \
    --entrypoint sh \
    busybox:1.36 \
    -c 'chown -R 1000:1000 /var/lib/odoo/filestore'

# 4. Start application
docker compose up -d web
```

**Verification**:
```bash
# Check attachment count
docker compose exec -T -u postgres db psql -U shaka -d postgres -c "SELECT count(*) FROM ir_attachment WHERE store_fname IS NOT NULL;"

# Spot-check a few attachments via Odoo UI
```

---

### Scenario 3: Complete Host Failure / New Server Provisioning

**When to use**: Server hardware failure, migrating to new infrastructure.

**RPO**: Database ~seconds, Filestore ≤15 min

#### Prerequisites on New Host

```bash
# Install Docker & Docker Compose
curl -fsSL https://get.docker.com | sh
# Ensure docker compose plugin is available
docker compose version

# Clone repository (or copy project files)
git clone <your-repo> ~/Shaka
cd ~/Shaka

# Restore .env file (database credentials, master password)
# IMPORTANT: Keep .env secure and out of version control
cp /path/to/backup/.env .
```

#### Recovery Procedure

```bash
cd ~/Shaka

# 1. Restore backup storage from off-site / NAS / cloud
#    Ensure directory structure matches:
#    ~/backups/pgbackrest/
#    ~/backups/filestore/
rsync -avz backup-server:/backups/ ~/backups/

# 2. Fix pgbackrest ownership (postgres uid 999)
docker run --rm -v ~/backups:/opt/backups busybox:1.36 \
    sh -c 'chown -R 999:999 /opt/backups/pgbackrest && chmod -R 750 /opt/backups/pgbackrest'

# 3. Build images
docker compose build db
docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync .

# 4. Restore database
#    Initialize a fresh cluster first (this creates the odoo_19_pg_data
#    volume and finishes initdb), then STOP postgres before restoring.
docker compose up -d db
# wait until db shows "healthy" (initdb must complete):
docker compose ps
docker compose stop db

#    Wipe the freshly-initialized data directory.
#    pgBackRest refuses to restore into a non-empty PGDATA — skipping this
#    step is the usual cause of "restore" errors on a new host.
docker run --rm \
    -v odoo_19_pg_data:/var/lib/postgresql/data \
    --entrypoint sh \
    odoo_19_db:pg16 \
    -c 'rm -rf /var/lib/postgresql/data/* && chown -R postgres:postgres /var/lib/postgresql/data'

#    Run the restore (database stopped)
docker run --rm --user postgres \
    -v odoo_19_pg_data:/var/lib/postgresql/data \
    -v ~/backups/pgbackrest:/var/lib/pgbackrest \
    -v ~/Shaka/pgbackrest.conf:/etc/pgbackrest/pgbackrest.conf:ro \
    --entrypoint pgbackrest odoo_19_db:pg16 \
    --stanza=shaka_db restore

#    Start database and verify it recovered from the restored data
docker compose up -d db
docker compose exec -T -u postgres db pg_isready

# 5. Restore filestore (Scenario 2, step 2)
docker run --rm \
    -v odoo_19_data:/dst \
    -v ~/backups/filestore:/src:ro \
    odoo_filestore_sync -a --delete /src/ /dst/filestore/
docker run --rm -v odoo_19_data:/var/lib/odoo --entrypoint sh busybox:1.36 \
    -c 'chown -R 1000:1000 /var/lib/odoo/filestore'

# 6. Start full stack
docker compose up -d

# 7. Re-install cron jobs
./backup/install_cron.sh
```

**Verification**:
```bash
# All services healthy?
docker compose ps

# Database backup check
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db check

# Filestore sync test
./backup/filestore_sync.sh

# Odoo accessible?
curl -I http://localhost
```

---

### Scenario 4: Accidental Schema Migration / Bad Module Upgrade

**When to use**: Failed Odoo module upgrade, broken migration script.

**Approach**: Point-in-time recovery to just before the migration.

```bash
# Find the timestamp before migration started
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db info

# Restore to that timestamp (see Scenario 1, step 4B)
# --target='2026-08-18 10:00:00'
```

---

### Scenario 5: Partial Data Loss (Single Table / Record)

**When to use**: Accidental `DELETE FROM res_partner WHERE ...` without WHERE clause.

**Approach**: Restore to temporary database, extract data, copy back.

```bash
# 1. Create temporary restore on same host (different stanza name)
docker run --rm --user postgres \
    -v odoo_19_pg_data:/var/lib/postgresql/data \
    -v ~/backups/pgbackrest:/var/lib/pgbackrest \
    -v ~/Shaka/pgbackrest.conf:/etc/pgbackrest/pgbackrest.conf:ro \
    --entrypoint pgbackrest odoo_19_db:pg16 \
    --stanza=shaka_db --type=full --delta restore --target-action=promote --pg1-path=/var/lib/postgresql/data_temp

# 2. Start temporary PostgreSQL on different port
# (simpler: use pg_dump from restored data directory)

# 3. Dump specific table
docker run --rm \
    -v odoo_19_pg_data:/var/lib/postgresql/data \
    --entrypoint pg_dump odoo_19_db:pg16 \
    -U shaka -d postgres -t res_partner > /tmp/res_partner.sql

# 4. Restore into production
docker compose exec -T -u postgres db psql -U shaka -d postgres < /tmp/res_partner.sql
```

> **Note**: For single-table recovery, consider using `pg_dump`/`pg_restore` from a logical backup instead. The current setup only does physical backups. Add a nightly `pg_dump` cron if this scenario is likely.

---

## Monitoring & Alerting

### Daily Checks (Automate via Cron)

```bash
#!/usr/bin/env bash
# /etc/cron.daily/odoo-backup-check

REPO=~/Shaka
LOG=~/backups/logs/health_check.log

{
  echo "=== $(date) ==="
  # 1. pgBackRest repo check
  docker compose -f $REPO/docker-compose.yml exec -T -u postgres db pgbackrest --stanza=shaka_db check
  
  # 2. Verify latest backup age < 25 hours
  docker compose -f $REPO/docker-compose.yml exec -T -u postgres db pgbackrest --stanza=shaka_db info | grep "backup.*complete"
  
  # 3. Filestore sync log (last run)
  tail -5 ~/backups/logs/filestore_sync.log
  
  # 4. Disk space
  df -h ~/backups
} >> $LOG 2>&1
```

### Key Metrics to Alert On

| Metric | Warning | Critical |
|--------|---------|----------|
| Last full backup age | > 26 hours | > 48 hours |
| WAL archive lag | > 5 min | > 15 min |
| Backup disk usage | > 80% | > 90% |
| Filestore sync failures (cron) | 1 failure | 3 consecutive |

---

## Maintenance Operations

### Rotate / Expire Old Backups Manually

```bash
# pgBackRest handles retention automatically (repo1-retention-full=2)
# To force expire now:
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db expire
```

### Verify Backup Integrity (Full Scan)

```bash
# Runs checksums on all files in repo (IO intensive, run off-peak)
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db check --checksum
```

### Add a Logical Backup (pg_dump) for Table-Level Recovery

```bash
# Add to crontab (weekly):
# 0 3 * * 0 docker compose exec -T -u postgres db pg_dump -U shaka -d postgres -Fc > /backups/logical/odoo_$(date +\%Y\%m\%d).dump
```

---

## Security Considerations

1. **Backup Encryption**: Not currently enabled. Enable with:
   ```ini
   # pgbackrest.conf
   [global]
   repo1-cipher-type=aes-256-cbc
   repo1-cipher-pass=<strong-passphrase>
   ```
   Store passphrase in password manager, not in repo.

2. **Access Control**: 
   - `$BACKUPS/pgbackrest/` owned by uid 999 (postgres), mode 750
   - `$BACKUPS/filestore/` owned by host user
   - Restrict SSH/NFS access to backup directory

3. **Off-Site Replication**: 
   - Configure `repo2-type=s3` (or `gcs`, `azure`) in pgbackrest.conf
   - Or rsync `$BACKUPS/` to remote server nightly

4. **Test Restores**: Schedule quarterly full restore drills to staging environment.

---

## Troubleshooting

### pgBackRest "role postgres does not exist"
```bash
# Ensure pg1-user=shaka is set in pgbackrest.conf [shaka_db] section
# Restart db container after config change
docker compose restart db
```

### "repo1-type=path not allowed"
```bash
# Use repo1-type=posix (fixed in pgbackrest.conf)
```

### Filestore rsync "No such file or directory"
```bash
# Filestore doesn't exist until Odoo creates it on first run
docker compose up -d web
# Then run filestore_sync.sh
```

### Cron Jobs Not Running
```bash
# Check cron daemon
systemctl status cron
# Check crontab
crontab -l
# Check logs
tail -f ~/backups/logs/filestore_sync.log
```

---

## Contact & Escalation

- **Primary**: Platform team
- **Backup Storage**: NAS at `backup-server:/backups/`
- **Runbook Version**: 1.0 (2026-08-18)
- **Next Review**: 2026-11-18

---

## Appendix: File Inventory

```
~/Shaka/
├── docker-compose.yml          # Stack definition
├── pgbackrest.conf             # pgBackRest configuration
├── db.Dockerfile               # PostgreSQL + pgBackRest image
├── filestore-sync.Dockerfile   # rsync helper image
├── deploy_init.sh              # ← run once on new server
├── DISASTER_RECOVERY.md        # This file
├── DEPLOYMENT_GUIDE.md
├── backup/
│   ├── install_cron.sh         # Installs 15-min filestore + daily full backup cron
│   ├── filestore_sync.sh       # Incremental rsync mirror (RPO 15min)
│   ├── pgbackrest_full.sh      # Daily full backup trigger
│   └── restore.sh              # Full disaster restore (database only)
└── .env                        # Credentials (NOT in git)
```

**Backup Root**: `~/backups/`
- `pgbackrest/` — pgBackRest repository (WAL + base backups)
- `filestore/` — rsync mirror of `/var/lib/odoo/filestore`
- `logs/` — Cron job output logs