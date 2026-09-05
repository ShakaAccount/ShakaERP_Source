<#
.SYNOPSIS
    deploy_update.ps1 — Windows counterpart of deploy_update.sh (same steps, same names).
.DESCRIPTION
    Updates an existing Odoo 19 installation: rebuilds images, applies DB migrations,
    restarts services without touching data volumes or backups.
.NOTES
    Requires: Docker Desktop, Docker Compose v2. Run from anywhere; paths auto-locate.
    .env must already exist (run deploy_init.ps1 first).
#>

# --- Strict mode & error handling ---
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# NOTE: native commands do NOT stop the script on non-zero exit codes;
# Invoke-Native checks $LASTEXITCODE (bash set -e equivalent).

# --- Configuration (defaults are repo-location-aware) ---
$SCRIPT_DIR  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$REPO_DIR    = if ($env:REPO_DIR)    { $env:REPO_DIR }    else { $SCRIPT_DIR }
$BACKUP_ROOT = if ($env:BACKUP_ROOT) { $env:BACKUP_ROOT } else { Join-Path (Split-Path $REPO_DIR -Parent) "backups" }
$STANZA   = "shaka_db"
$DB_IMAGE = "odoo_19_db:pg16"

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
    # envsubst semantics: ${VAR} and ${VAR:-default} (default used when unset or empty)
    return [regex]::Replace($Template, '\$\{([^}]+)\}', {
        param($m)
        $spec    = $m.Groups[1].Value
        $name    = $spec
        $default = $null
        $idx = $spec.IndexOf(':-')
        if ($idx -ge 0) {
            $name    = $spec.Substring(0, $idx)
            $default = $spec.Substring($idx + 2)
        }
        $v = [Environment]::GetEnvironmentVariable($name, 'Process')
        if (-not [string]::IsNullOrEmpty($v)) { return $v }
        if ($null -ne $default) { return $default }
        return ''
    })
}

# --- 1. Prerequisites ---
Log "Checking prerequisites..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not installed. Aborting."
    exit 1
}
Invoke-Native { docker compose version } "Docker Compose v2 check" | Out-Null

# --- 2. Go to repo and (optionally) pull latest ---
Log "Using repository at $REPO_DIR"
Set-Location $REPO_DIR

# Uncomment the next lines if you want to automatically git pull:
# Log "Updating repository via git pull..."
# Invoke-Native { git pull --ff-only } "git pull"

# --- 3. Ensure .env exists and source it ---
$envFile = Join-Path $REPO_DIR ".env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env not found — run deploy_init.ps1 first."
    exit 1
}
Set-EnvFromFile $envFile

# --- 4. Re-generate odoo.conf from embedded template ---
# (bash version runs envsubst over the existing odoo.conf, which is already
#  fully substituted — a no-op. Regenerating from template + .env actually
#  picks up changed credentials. Defaults match deploy_init.ps1.)
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
# ascii => ANSI with CRLF (PS 5.1 -Encoding UTF8 writes UTF-16 + BOM, which breaks odoo)
$odooConfContent | Set-Content -Path $odooConfPath -Encoding ascii

# --- 5. Rebuild images (only if Dockerfiles changed) ---
Log "Building images (db, filestore-sync)..."
Invoke-Native { docker compose build db } "docker compose build db"
Invoke-Native { docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync . } "docker build filestore-sync"

# --- 6. Stop web and nginx (keep db running for zero-downtime migrations) ---
Log "Stopping web and nginx..."
Invoke-Native { docker compose stop web nginx } "docker compose stop web nginx"

# --- 7. Run Odoo database migrations ---
Log "Running Odoo database migrations..."
$pgUser = [Environment]::GetEnvironmentVariable("POSTGRES_USER", 'Process')
$pgPass = [Environment]::GetEnvironmentVariable("POSTGRES_PASSWORD", 'Process')
if ([string]::IsNullOrEmpty($pgUser) -or [string]::IsNullOrEmpty($pgPass)) {
    Write-Error "POSTGRES_USER or POSTGRES_PASSWORD not set in .env. Aborting."
    exit 1
}
Invoke-Native {
    docker compose run --rm -T web `
        ./odoo-bin -c /etc/odoo/odoo.conf --db_host=db -r "$pgUser" -w "$pgPass" -u all --stop-after-init
} "Odoo migration (-u all)"

# --- 8. Start all services ---
Log "Starting web and nginx..."
Invoke-Native { docker compose up -d web nginx } "docker compose up web nginx"

# --- 9. Verify health ---
Log "Verifying deployment..."
Start-Sleep -Seconds 5
docker compose ps

# --- 10. Quick backup health check ---
Log "Checking pgBackRest repo..."
Invoke-Native { docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check } "pgbackrest check"

Log "Update complete."
Write-Host ""
Write-Host "=== SUMMARY ==="
Write-Host "Repository:    $REPO_DIR (git pull optional, commented out)"
Write-Host "Data volumes:  PRESERVED (pg_data, odoo_data)"
Write-Host "Backups:       $BACKUP_ROOT (unchanged)"
Write-Host "Services:      db, web, nginx restarted"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  - Verify Odoo accessible at http://<server-ip>"
Write-Host "  - Check logs: docker compose logs -f web"
Write-Host "  - Run manual filestore sync: .\backup\filestore_sync.ps1 (if available)"
