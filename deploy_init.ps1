<#
.SYNOPSIS
    deploy_init.ps1 — Windows counterpart of deploy_init.sh (same steps, same names).
.DESCRIPTION
    Sets up Odoo 19 using Docker, configures pgBackRest for continuous WAL archiving
    and daily full backups, and creates scheduled tasks for filestore sync and DB backups.
.NOTES
    Requires: Docker Desktop, Docker Compose v2. Run from an elevated PowerShell so
    Register-ScheduledTask can create tasks. Paths auto-locate.
#>

# --- Strict mode & error handling ---
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# NOTE: unlike the bash script (set -euo pipefail), native commands here do NOT
# stop the script on non-zero exit codes. We check $LASTEXITCODE via Invoke-Native.

# --- Configuration (defaults are repo-location-aware) ---
$SCRIPT_DIR  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$REPO_DIR    = if ($env:REPO_DIR)    { $env:REPO_DIR }    else { $SCRIPT_DIR }
$BACKUP_ROOT = if ($env:BACKUP_ROOT) { $env:BACKUP_ROOT } else { Join-Path (Split-Path $REPO_DIR -Parent) "backups" }
$STANZA = "shaka_db"
$DB_CONTAINER = "odoo_19_db"

# Helper: run a native command; abort on non-zero exit (mimics bash set -e).
function Invoke-Native {
    param([scriptblock]$Block, [string]$What)
    & $Block
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$What failed (exit code $LASTEXITCODE). Aborting."
        exit $LASTEXITCODE
    }
}

# --- Helper functions ---
function Log {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
}

function Gen-Password {
    # 32-char random password from base64 (no '/', '+', '='), like openssl|tr|cut
    $bytes  = New-Object Byte[] 32
    $rng    = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $clean = ([Convert]::ToBase64String($bytes)) -replace '[/+=]', ''
    if ($clean.Length -ge 32) { return $clean.Substring(0, 32) }
    return $clean
}

function Set-EnvFromFile {
    param([string]$FilePath)
    if (Test-Path $FilePath) {
        Get-Content $FilePath | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
            }
        }
    }
}

function Replace-EnvInTemplate {
    param([string]$Template)
    # Replace ${VAR} with the current process environment variable value
    return [regex]::Replace($Template, '\$\{([^}]+)\}', {
        param($m)
        $v = [Environment]::GetEnvironmentVariable($m.Groups[1].Value, 'Process')
        if ($null -eq $v) { $v = '' }
        $v
    })
}

function Get-HealthStatus {
    # Health of $DB_CONTAINER; 'starting' if container not found yet (like the bash fallback).
    # PS 5.1 gotcha: with $ErrorActionPreference='Stop', redirecting native stderr (2>$null)
    # turns stderr lines into ErrorRecords and can throw — relax EAP around the redirect.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = docker inspect --format '{{.State.Health.Status}}' $DB_CONTAINER 2>$null
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($LASTEXITCODE -ne 0) { return "starting" }
    return "$out".Trim()
}

function Restrict-FileToUser {
    param([string]$Path)
    # chmod 600 equivalent: strip inheritance, keep only current user
    icacls $Path /inheritance:r /grant:r "${env:USERNAME}:F" | Out-Null
}

# --- 1. Prerequisites ---
Log "Checking prerequisites..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not installed. Aborting."
    exit 1
}
Invoke-Native { docker compose version } "Docker Compose v2 check" | Out-Null

# --- 2. Use repository location ---
Log "Using project at $REPO_DIR"
Set-Location $REPO_DIR

# --- 3. Create .env if missing ---
$envFile = Join-Path $REPO_DIR ".env"
if (-not (Test-Path $envFile)) {
    Log "Generating .env with random passwords..."
    $POSTGRES_USER        = "shaka"
    $POSTGRES_PASSWORD    = Gen-Password
    $POSTGRES_DB          = "postgres"
    $POSTGRES_HOST        = "db"
    $POSTGRES_PORT        = "5432"
    $SHAKA_MASTER_PASSWORD = Gen-Password
    $ADMIN_PASSWORD       = $SHAKA_MASTER_PASSWORD
    $WORKERS              = "4"
    $MAX_CRON_THREADS     = "2"
    $GEVENT_PORT          = "8072"

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
    # ascii => ANSI, writes CRLF line endings (UTF8 with BOM confuses docker compose variable parsing)
    $envContent | Set-Content -Path $envFile -Encoding ascii
    Restrict-FileToUser $envFile
    Log "Created .env (keep it safe!)"
} else {
    Log ".env already exists, using existing credentials."
}

# Load .env into process environment
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
# ascii => CRLF on disk; PowerShell 5.1 writes UTF16 (not UTF8) for -Encoding UTF8
$odooConfContent | Set-Content -Path $odooConfPath -Encoding ascii

# --- 5. Ensure backup directories exist ---
Log "Creating backup directories..."
$dirs = @(
    (Join-Path $BACKUP_ROOT "pgbackrest"),
    (Join-Path $BACKUP_ROOT "filestore"),
    (Join-Path $BACKUP_ROOT "logs"),
    (Join-Path $BACKUP_ROOT "config")
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

# 5b. Back up .env and odoo.conf to config/ (first time only)
$configEnv = Join-Path $BACKUP_ROOT "config\.env"
if (-not (Test-Path $configEnv)) {
    Log "Backing up .env and odoo.conf to $BACKUP_ROOT\config\ ..."
    Copy-Item $envFile      $configEnv -Force
    Copy-Item $odooConfPath (Join-Path $BACKUP_ROOT "config\odoo.conf") -Force
    Restrict-FileToUser $configEnv
}

# --- 6. Fix pgBackRest directory ownership (postgres uid 999 inside container) ---
Log "Fixing pgBackRest directory ownership..."
# Docker on Windows requires the mount path in Linux form: /c/Users/...
$drive   = ($BACKUP_ROOT.Substring(0, 1)).ToLower()          # 'C'
$rest    = $BACKUP_ROOT.Substring(2) -replace '\\', '/'       # '/Users/.../backups'
$backupRootUnix = "/$drive$rest"
docker run --rm -v "${backupRootUnix}:/opt/backups" busybox:1.36 sh -c "chown -R 999:999 /opt/backups/pgbackrest && chmod -R 750 /opt/backups/pgbackrest"
if ($LASTEXITCODE -ne 0) {
    Write-Error "pgBackRest ownership fix failed (exit code $LASTEXITCODE). Aborting."
    exit $LASTEXITCODE
}

# --- 7. Build images ---
Log "Building database image (pgvector + pgBackRest)..."
Invoke-Native { docker compose build db } "docker compose build db"

Log "Building filestore sync helper image..."
Invoke-Native { docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync . } "docker build filestore-sync"

# --- 8. Start database and wait for health ---
Log "Starting database container..."
Invoke-Native { docker compose up -d db } "docker compose up db"

Log "Waiting for database to become healthy..."
do {
    Start-Sleep -Seconds 2
    $status = Get-HealthStatus
} while ($status -ne "healthy")
Log "Database healthy."

# 8b. Re-run safety: POSTGRES_PASSWORD only takes effect on FIRST volume init.
# If the role password drifted from .env (re-runs with a regenerated .env), resync it.
Log "Checking database password matches .env..."
$pgUser = [Environment]::GetEnvironmentVariable("POSTGRES_USER", 'Process')
if (-not $pgUser) { $pgUser = "shaka" }
$prev = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    docker compose exec -T -e PGPASSWORD="$env:POSTGRES_PASSWORD" db psql -h db -U $pgUser -d postgres -tAc 'SELECT 1' 2>$null | Out-Null
    $checkExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $prev
}
if ($checkExit -ne 0) {
    Log "Role password differs from .env — resyncing..."
    Invoke-Native { docker compose exec -T -u postgres db psql -U $pgUser -d postgres -c "ALTER USER $pgUser WITH PASSWORD '$env:POSTGRES_PASSWORD';" } "password resync"
}

# --- 9. Initialize pgBackRest stanza ---
Log "Creating pgBackRest stanza '$STANZA'..."
Invoke-Native { docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" stanza-create } "pgbackrest stanza-create"

Log "Running pgBackRest check..."
Invoke-Native { docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check } "pgbackrest check"

# --- 10. Initial full backup if none exist ---
# (relax EAP around 2>$null redirect — PS 5.1 NativeCommandError, see Get-HealthStatus)
$prev = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $infoOutput = docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" info 2>$null
} finally {
    $ErrorActionPreference = $prev
}
if ($LASTEXITCODE -ne 0 -or $infoOutput -notmatch "full backup:") {
    Log "No existing backups found. Running initial full backup..."
    Invoke-Native { docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" --type=full backup } "initial full backup"
} else {
    Log "Existing backups detected. Skipping initial full backup."
}

# --- 11. Start Odoo web + nginx ---
Log "Starting web and nginx..."
Invoke-Native { docker compose up -d web nginx } "docker compose up web nginx"

# --- 12. Initial filestore sync ---
Log "Running initial filestore sync..."
Invoke-Native { docker run --rm -v odoo_19_data:/data -v "${backupRootUnix}/filestore:/backup" odoo_filestore_sync } "initial filestore sync"

# --- 13. Schedule recurring jobs (scheduled tasks replace cron) ---
Log "Installing scheduled tasks (filestore every 15 min, full DB daily at 02:15)..."

function New-OdooTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [string]$Command,
        [string]$TriggerType  # '15Minute' | 'DailyAt0215'
    )
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$Command`""

    if ($TriggerType -eq "15Minute") {
        $taskTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
            -RepetitionInterval (New-TimeSpan -Minutes 15) `
            -RepetitionDuration ([TimeSpan]::MaxValue)
    } elseif ($TriggerType -eq "DailyAt0215") {
        $taskTrigger = New-ScheduledTaskTrigger -Daily -At "02:15"
    } else {
        throw "Unknown trigger type: $TriggerType"
    }

    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $taskTrigger -Settings $settings -Description $Description -Force | Out-Null
}

# NOTE: scheduled tasks run under the SYSTEM/invoking account; docker CLI must be
# on that account's PATH (Docker Desktop's default install location is System32-linked).
$syncCmd = "docker run --rm -v odoo_19_data:/data -v `"${backupRootUnix}/filestore:/backup`" odoo_filestore_sync"
New-OdooTask -TaskName "OdooFilestoreSync" -Description "Sync Odoo filestore to backup every 15 min" -Command $syncCmd -TriggerType "15Minute"

$backupCmd = "docker compose -f `"$REPO_DIR\docker-compose.yml`" exec -T -u postgres db pgbackrest --stanza=$STANZA --type=full backup"
New-OdooTask -TaskName "OdooDBBackup" -Description "Full pgBackRest backup daily at 02:15" -Command $backupCmd -TriggerType "DailyAt0215"

# --- 14. Final verification ---
Log "Verifying backup health..."
Invoke-Native { docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check } "final pgbackrest check"

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
