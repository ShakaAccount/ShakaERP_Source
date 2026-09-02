<#
.SYNOPSIS
    deploy_update.ps1 — Pull latest code and redeploy Odoo 19 stack (preserves data & backups).
.DESCRIPTION
    This script updates an existing Odoo 19 installation by rebuilding images, applying database
    migrations, and restarting services without touching data volumes. It replaces the original
    Bash update script.
.NOTES
    Requires: Docker Desktop, Docker Compose v2, and administrator privileges.
    Must be run from the repository root containing .env and docker-compose.yml.
#>

# --- Strict mode & error handling ---
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSDefaultParameterValues['*:ErrorAction'] = 'Stop'

# --- Configuration (repo‑location‑aware) ---
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$REPO_DIR = if ($env:REPO_DIR) { $env:REPO_DIR } else { $SCRIPT_DIR }
$BACKUP_ROOT = if ($env:BACKUP_ROOT) {
    $env:BACKUP_ROOT
} else {
    Join-Path (Split-Path $REPO_DIR -Parent) "backups"
}
$STANZA = "shaka_db"

# --- Helper functions ---
function Log {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
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
if (-not (Get-Command "docker compose" -ErrorAction SilentlyContinue)) {
    Write-Error "Docker Compose plugin not installed. Aborting."
    exit 1
}

# --- 2. Go to repo and (optionally) pull latest ---
Log "Using repository at $REPO_DIR"
Set-Location $REPO_DIR

# Uncomment the next lines if you want to automatically git pull:
# Log "Updating repository via git pull..."
# git pull --ff-only

# --- 3. Ensure .env exists and source it ---
$envFile = Join-Path $REPO_DIR ".env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env not found — run deploy_init.ps1 first."
    exit 1
}
Set-EnvFromFile $envFile

# --- 4. Re-generate odoo.conf from template ---
Log "Regenerating odoo.conf from environment..."
$odooConfTemplate = @'
[options]
; Database
db_host = ${POSTGRES_HOST:-db}
db_port = ${POSTGRES_PORT:-5432}
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
workers = ${WORKERS:-4}
max_cron_threads = ${MAX_CRON_THREADS:-2}
gevent_port = ${GEVENT_PORT:-8072}
'@

$odooConfContent = Replace-EnvInTemplate -Template $odooConfTemplate
$odooConfPath = Join-Path $REPO_DIR "odoo.conf"
$odooConfContent | Set-Content -Path $odooConfPath -Encoding UTF8

# --- 5. Rebuild images (only if Dockerfiles changed) ---
Log "Building images (db, filestore-sync)..."
docker compose build db
docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync .

# --- 6. Stop web and nginx (keep db running) ---
Log "Stopping web and nginx..."
docker compose stop web nginx

# --- 7. Run Odoo database migrations ---
Log "Running Odoo database migrations..."
# Retrieve credentials from environment (already set)
$pgUser = [Environment]::GetEnvironmentVariable("POSTGRES_USER")
$pgPass = [Environment]::GetEnvironmentVariable("POSTGRES_PASSWORD")
if ([string]::IsNullOrEmpty($pgUser) -or [string]::IsNullOrEmpty($pgPass)) {
    Write-Error "POSTGRES_USER or POSTGRES_PASSWORD not set in environment. Aborting."
    exit 1
}

docker compose run --rm -T web `
    ./odoo-bin -c /etc/odoo/odoo.conf --db_host=db -r "$pgUser" -w "$pgPass" -u all --stop-after-init

# --- 8. Start all services ---
Log "Starting web and nginx..."
docker compose up -d web nginx

# --- 9. Verify health ---
Log "Verifying deployment..."
Start-Sleep -Seconds 5
docker compose ps

# --- 10. Quick backup health check ---
Log "Checking pgBackRest repo..."
docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

Log "Update complete."
Write-Host ""
Write-Host "=== SUMMARY ==="
Write-Host "Repository:    $REPO_DIR (updated via git pull if uncommented)"
Write-Host "Data volumes:  PRESERVED (pg_data, odoo_data)"
Write-Host "Backups:       $BACKUP_ROOT (unchanged)"
Write-Host "Services:      db, web, nginx restarted"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  - Verify Odoo accessible at http://<server-ip>"
Write-Host "  - Check logs: docker compose logs -f web"
Write-Host "  - Run manual filestore sync: .\backup\filestore_sync.ps1 (if available)"
