<#
.SYNOPSIS
    deploy_init.ps1 — Initialize Odoo 19 stack with automated backups on a fresh Windows server.
.DESCRIPTION
    This script sets up Odoo 19 using Docker, configures pgBackRest for continuous WAL archiving
    and daily full backups, and creates scheduled tasks for filestore sync and database backups.
    It replaces the original Bash script with PowerShell equivalents.
.NOTES
    Requires: Docker Desktop, Docker Compose v2, and administrator privileges.
    The script auto‑locates its repository folder – no hardcoded paths.
#>

# --- Strict mode & error handling ---
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSDefaultParameterValues['*:ErrorAction'] = 'Stop'

# --- Configuration (defaults are repo‑location‑aware) ---
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$REPO_DIR = if ($env:REPO_DIR) { $env:REPO_DIR } else { $SCRIPT_DIR }
$BACKUP_ROOT = if ($env:BACKUP_ROOT) {
    $env:BACKUP_ROOT
} else {
    Join-Path (Split-Path $REPO_DIR -Parent) "backups"
}
$STANZA = "shaka_db"
$DB_IMAGE = "odoo_19_db:pg16"
$PG_DATA_VOL = "odoo_19_pg_data"
$ODOO_DATA_VOL = "odoo_19_data"

# --- Helper functions ---
function Log {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
}

function Gen-Password {
    # Generate a 32‑character random password (alphanumeric + safe symbols, no /+=)
    $bytes = New-Object Byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()

    $base64 = [Convert]::ToBase64String($bytes)
    # Remove '/', '+', '=' and take first 32 characters
    $clean = $base64 -replace '[/+=]', ''
    if ($clean.Length -ge 32) { $clean.Substring(0, 32) } else { $clean }
}

function Set-EnvFromFile {
    param([string]$FilePath)
    if (Test-Path $FilePath) {
        Get-Content $FilePath | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                $key = $Matches[1].Trim()
                $value = $Matches[2].Trim()
                [Environment]::SetEnvironmentVariable($key, $value, 'Process')
            }
        }
    }
}

function Replace-EnvInTemplate {
    param([string]$Template)
    # Replace ${VAR} with the current environment variable value
    $result = $Template
    [regex]::Matches($Template, '\$\{([^}]+)\}') | ForEach-Object {
        $varName = $_.Groups[1].Value
        $value = [Environment]::GetEnvironmentVariable($varName)
        if ($null -eq $value) { $value = '' }
        $result = $result -replace [regex]::Escape($_.Value), $value
    }
    return $result
}

# --- 1. Prerequisites ---
Log "Checking prerequisites..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not installed. Aborting."
    exit 1
}
#if (-not (Get-Command "docker compose" -ErrorAction SilentlyContinue)) {
#    Write-Error "Docker Compose plugin not installed. Aborting."
#    exit 1
#}
# Optionally check version: docker compose version | Select-String v2

# --- 2. Use repository location ---
Log "Using project at $REPO_DIR"
Set-Location $REPO_DIR

# --- 3. Create .env if missing ---
$envFile = Join-Path $REPO_DIR ".env"
if (-not (Test-Path $envFile)) {
    Log "Generating .env with random passwords..."
    $POSTGRES_USER = "shaka"
    $POSTGRES_PASSWORD = Gen-Password
    $POSTGRES_DB = "postgres"
    $POSTGRES_HOST = "db"
    $POSTGRES_PORT = "5432"
    $SHAKA_MASTER_PASSWORD = Gen-Password
    $ADMIN_PASSWORD = $SHAKA_MASTER_PASSWORD
    $WORKERS = "4"
    $MAX_CRON_THREADS = "2"
    $GEVENT_PORT = "8072"

    $envContent = @"
# Database Credentials
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB
POSTGRES_HOST=$POSTGRES_HOST
POSTGRES_PORT=$POSTGRES_PORT

# Shaka Settings
SHAKA_MASTER_PASSWORD=$SHAKA_MASTER_PASSWORD
ADMIN_PASSWORD=$ADMIN_PASSWORD
WORKERS=$WORKERS
MAX_CRON_THREADS=$MAX_CRON_THREADS
GEVENT_PORT=$GEVENT_PORT
"@
    $envContent | Set-Content -Path $envFile -Encoding UTF8
    # Set permissions on Windows: restrict to current user only (equivalent to chmod 600)
    icacls $envFile /inheritance:r /grant "$env:USERNAME`:F" | Out-Null
    Log "Created .env (keep it safe!)"
} else {
    Log ".env already exists, using existing credentials."
}

# Source .env into process environment
Set-EnvFromFile $envFile

# --- 4. Generate odoo.conf from embedded template ---
Log "Generating odoo.conf from template..."
$odooConfTemplate = @'
[options]
; Database
db_host = ${POSTGRES_HOST}
db_port = ${POSTGRES_PORT}
db_user = ${POSTGRES_USER}
db_password = ${POSTGRES_PASSWORD}

; Security
admin_passwd = ${SHAKA_MASTER_PASSWORD}

; Proxy
proxy_mode = True

; Paths
addons_path = /opt/odoo/addons,/opt/odoo/custom_addons
data_dir = /var/lib/odoo

; Logging
log_level = info

; Performance
workers = ${WORKERS}
max_cron_threads = ${MAX_CRON_THREADS}
gevent_port = ${GEVENT_PORT}
'@

$odooConfContent = Replace-EnvInTemplate -Template $odooConfTemplate
$odooConfPath = Join-Path $REPO_DIR "odoo.conf"
$odooConfContent | Set-Content -Path $odooConfPath -Encoding UTF8

# --- 5. (Optional) Restore backup storage from off‑site ---
# Uncomment and adjust if you have a remote backup server:
# Log "Syncing backup storage from remote..."
# rsync -avz --progress backup-user@backup-server:/backups/ "$BACKUP_ROOT/"

# --- 6. Ensure backup directories exist ---
Log "Creating backup directories..."
$dirs = @(
    "$BACKUP_ROOT\pgbackrest",
    "$BACKUP_ROOT\filestore",
    "$BACKUP_ROOT\logs",
    "$BACKUP_ROOT\config"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

# 6b. Back up .env and odoo.conf to config/ (first time only)
$configEnv = "$BACKUP_ROOT\config\.env"
if (-not (Test-Path $configEnv)) {
    Log "Backing up .env and odoo.conf to $BACKUP_ROOT\config\ ..."
    Copy-Item $envFile $configEnv -Force
    Copy-Item $odooConfPath "$BACKUP_ROOT\config\odoo.conf" -Force
    icacls $configEnv /inheritance:r /grant "$env:USERNAME`:F" | Out-Null
}

# --- 7. Fix pgBackRest directory ownership (postgres uid 999 inside container) ---
Log "Fixing pgBackRest directory ownership..."
$backupRootUnix = $BACKUP_ROOT -replace '\\','/'    # Convert to Unix‑style for Docker
docker run --rm -v "${backupRootUnix}:/opt/backups" busybox:1.36 sh -c "chown -R 999:999 /opt/backups/pgbackrest && chmod -R 750 /opt/backups/pgbackrest"

# --- 8. Build images ---
Log "Building database image (pgvector + pgBackRest)..."
docker compose build db

Log "Building filestore sync helper image..."
docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync .

# --- 9. Start database and wait for health ---
Log "Starting database container..."
docker compose up -d db

Log "Waiting for database to become healthy..."
do {
    Start-Sleep -Seconds 2
    $status = docker inspect --format '{{.State.Health.Status}}' odoo_19_db 2>$null
} while ($status -ne "healthy")
Log "Database healthy."

# --- 10. Initialize pgBackRest stanza ---
Log "Creating pgBackRest stanza '$STANZA'..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" stanza-create

Log "Running pgBackRest check..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

# --- 11. Run initial full backup if no existing backups ---
$infoOutput = docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" info 2>$null
if ($LASTEXITCODE -ne 0 -or $infoOutput -notmatch "full backup:") {
    Log "No existing backups found. Running initial full backup..."
    docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" --type=full backup
} else {
    Log "Existing backups detected. Skipping initial full backup."
}

# --- 12. Start Odoo web + nginx ---
Log "Starting web and nginx..."
docker compose up -d web nginx

# --- 13. Initial filestore sync (creates mirror) ---
Log "Running initial filestore sync..."
# Use the built image. The container must be able to mount both the data volume and the backup folder.
# We assume the filestore-sync container accepts source and dest as volumes.
docker run --rm -v odoo_19_data:/data -v "${backupRootUnix}/filestore:/backup" odoo_filestore_sync

# --- 14. Install scheduled tasks (replaces cron) ---
Log "Installing scheduled tasks (filestore every 15 min, full DB daily at 02:15)..."

# Helper to create a scheduled task that runs a PowerShell command
function New-OdooTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [string]$Command,
        [string]$TriggerType  # Changed from $Trigger to avoid variable collision
    )
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$Command`""

    if ($TriggerType -eq "15Minute") {
        $taskTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)
    } elseif ($TriggerType -eq "DailyAt0215") {
        $taskTrigger = New-ScheduledTaskTrigger -Daily -At "02:15"
    } else {
        throw "Unknown trigger type"
    }

    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    # Pass $taskTrigger instead of $trigger
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $taskTrigger -Settings $settings -Description $Description -Force
}
$syncCmd = "docker run --rm -v odoo_19_data:/data -v `"${backupRootUnix}/filestore:/backup`" odoo_filestore_sync"
New-OdooTask -TaskName "OdooFilestoreSync" -Description "Sync Odoo filestore to backup every 15 min" -Command $syncCmd -TriggerType "15Minute"

# Task 2: Full DB backup daily at 02:15
$backupCmd = "docker compose -f `"$REPO_DIR\docker-compose.yml`" exec -T -u postgres db pgbackrest --stanza=$STANZA --type=full backup"
New-OdooTask -TaskName "OdooDBBackup" -Description "Full pgBackRest backup daily at 02:15" -Command $backupCmd -TriggerType "DailyAt0215"
# --- 15. Final verification ---
Log "Verifying backup health..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

Log "Deployment initialization complete."
Write-Host ""
Write-Host "=== SUMMARY ==="
Write-Host "Project:       $REPO_DIR"
Write-Host "Backups:       $BACKUP_ROOT"
Write-Host "Database:      pgBackRest stanza '$STANZA' (continuous WAL, daily full)"
Write-Host "Filestore:     rsync mirror every 15 min (via scheduled task)"
Write-Host "Scheduled tasks:  Installed (run 'taskschd.msc' to verify)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  - Verify Odoo accessible at http://<server-ip>"
Write-Host "  - Test a restore on staging: ./backup/restore.sh (requires bash)"
Write-Host "  - Configure off-site replication for $BACKUP_ROOT"
