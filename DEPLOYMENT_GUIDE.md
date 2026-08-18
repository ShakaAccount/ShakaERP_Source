# Odoo 19 Deployment with Automated Backups

This guide explains how to deploy the Odoo 19 stack on a fresh server with **continuous WAL archiving** (RPO ~seconds) and **filestore mirroring every 15 minutes** (RPO 15 min).

---

## Prerequisites on Target Server

| Requirement | Version / Notes |
|-------------|-----------------|
| Docker Engine | 24+ |
| Docker Compose plugin | v2 (`docker compose version`) |
| Git (or scp/rsync) | to fetch the repository |
| Network access | to your off‑site backup storage (NAS, S3, remote rsync) |
| User with docker privileges | e.g. `usermod -aG docker $USER` |

---

## 1. Get the Project on the Server

```bash
# Option A: clone from git (recommended)
git clone <your-private-repo> /opt/odoo-19
cd /opt/odoo-19

# Option B: copy the whole directory via scp/rsync from your workstation
# scp -r odoo-19.0+e.20260223 user@server:/opt/odoo-19
```

---

## 2. Provide Production Secrets (`.env`)

Create `/opt/odoo-19/.env` **manually** – do **not** commit it.

```ini
# Database Credentials
POSTGRES_USER=shaka
POSTGRES_PASSWORD=<strong-random-password>
POSTGRES_DB=postgres

# Shaka Settings
SHAKA_MASTER_PASSWORD=<another-strong-password>
```

> **Tip:** Generate passwords with `openssl rand -base64 32`.

---

## 3. Restore Backup Storage from Off‑Site

The backup directory (`/opt/backups` by default) must contain two sub‑trees:

```
/opt/backups/
├── pgbackrest/      # pgBackRest repository (WAL + base backups)
└── filestore/       # rsync mirror of /var/lib/odoo/filestore
```

Sync from your backup server (adjust source):

```bash
mkdir -p /opt/backups
rsync -avz --progress backup-user@backup-server:/backups/ /opt/backups/
```

If this is a **brand‑new** deployment with no prior backups, you can skip this step – the init script will create an empty repo and take an initial full backup.

---

## 4. Run the Initialization Script

```bash
cd /opt/odoo-19
chmod +x deploy_init.sh
sudo ./deploy_init.sh
```

The script performs, in order:

1. Verifies Docker & Compose.
2. Fixes pgBackRest directory ownership (`uid 999`).
3. Builds the `db` image (pgvector + pgBackRest) and the `odoo_filestore_sync` helper image.
4. Starts the database container and waits for healthcheck.
5. Creates the pgBackRest stanza `shaka_db` and runs `check`.
6. Takes an **initial full backup** if the repo is empty.
7. Starts `web` and `nginx`.
8. Runs an initial filestore sync.
9. Installs two cron jobs (see below).
10. Final health verification.

### What the Cron Jobs Do

| Schedule | Command | Purpose |
|----------|---------|---------|
| `*/15 * * * *` | `/opt/odoo-19/backup/filestore_sync.sh` | Incremental rsync mirror of the filestore (RPO ≤ 15 min). |
| `15 2 * * *` | `/opt/odoo-19/backup/pgbackrest_full.sh` | Daily full base backup at 02:15 (retention: 2 full + 7 days WAL). |

Both write logs to `/opt/backups/logs/`.

---

## 5. Verify the Deployment

```bash
# All containers healthy?
docker compose ps

# pgBackRest repo OK?
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db check

# Latest backup info
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db info

# Filestore sync log
tail /opt/backups/logs/filestore_sync.log

# Odoo reachable
curl -I http://<server-ip>
```

You should see:
- `db` and `web` containers `Up (healthy)`.
- `pgbackrest check` → `completed successfully`.
- Filestore log shows `rsync` transferred bytes (or “nothing to do” on first run).

---

## 6. (Optional) Enable Off‑Site Replication for the Backup Repo

Add a second repository in `pgbackrest.conf` (e.g. S3, GCS, Azure, SFTP) and set `repo2-type=...`.  
Then pgBackRest will automatically push WAL segments and full backups to the remote target.

```ini
[global]
repo2-type=s3
repo2-path=your-bucket/odoo-pgbackrest
repo2-host=...
repo2-host-user=...
```

Run `pgbackrest --stanza=shaka_db check` again to validate the new repo.

---

## 7. Disaster Recovery Reference

See **`DISASTER_RECOVERY.md`** in this repository for step‑by‑step restore procedures covering:

1. Database corruption / point‑in‑time recovery.
2. Filestore corruption / deleted attachments.
3. Complete host failure / new server provisioning.
4. Bad migration / module upgrade rollback.
5. Partial data loss (single table).

---

## 8. Maintenance Cheatsheet

```bash
# Manual full backup (before major upgrade)
/opt/odoo-19/backup/pgbackrest_full.sh

# Manual filestore sync
/opt/odoo-19/backup/filestore_sync.sh

# List backups
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db info

# Force retention expiry
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db expire

# Full repo integrity scan (run off‑peak)
docker compose exec -T -u postgres db pgbackrest --stanza=shaka_db check --checksum
```

---

## 9. Security Notes

- **`.env`** contains secrets – restrict permissions (`chmod 600 .env`).
- Backup directory `/opt/backups/pgbackrest` owned by `uid 999` (postgres) mode `750`.
- Consider enabling pgBackRest encryption (`repo1-cipher-type=aes-256-cbc`) and storing the passphrase in a vault.
- Off‑site replication is **essential** – a single server loss must not lose both primary and backup data.

---

## 10. File Inventory (for audit)

```
/opt/odoo-19/
├── docker-compose.yml
├── pgbackrest.conf
├── db.Dockerfile
├── filestore-sync.Dockerfile
├── deploy_init.sh          # ← run once on new server
├── DISASTER_RECOVERY.md
├── backup/
│   ├── setup.sh
│   ├── install_cron.sh
│   ├── filestore_sync.sh
│   ├── pgbackrest_full.sh
│   └── restore.sh
└── .env                    # ← you create this
```

---

**You are now ready.** Run `deploy_init.sh`, verify, and schedule a quarterly restore drill on a staging environment.