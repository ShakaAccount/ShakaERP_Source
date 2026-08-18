#!/usr/bin/env bash
# ==============================================================================
# Odoo 19 Deployment & Initialization Script with Automated Backups
# Supports: Ubuntu, Debian, Arch Linux, Garuda Linux, Fedora, RHEL / WSL2
# Run as root or a user with docker privileges
# ==============================================================================

set -euo pipefail

# === CONFIGURATION (edit before running) ===
REPO_DIR="${REPO_DIR:-$HOME/Shaka}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/backups}"
STANZA="shaka_db"
DB_IMAGE="odoo_19_db:pg16"
PG_DATA_VOL="odoo_19_pg_data"
ODOO_DATA_VOL="odoo_19_data"
# ===========================================

# Color definitions for visual feedback
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper Functions
log_info() { echo -e "${BLUE}[INFO]${NC} [$(date '+%F %T')] $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} [$(date '+%F %T')] $1"; }
log_warn() { echo -e "${YELLOW}[WARNING]${NC} [$(date '+%F %T')] $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} [$(date '+%F %T')] $1"; }

generate_random_password() {
    if command -v openssl &> /dev/null; then
        openssl rand -base64 18 | tr -dc 'a-zA-Z0-9' | head -c 24
    else
        tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24
    fi
}

check_root_or_sudo() {
    if [ "$EUID" -ne 0 ] && ! command -v sudo &> /dev/null; then
        log_error "این اسکریپت نیاز به دسترسی root یا sudo دارد."
        exit 1
    fi
}

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO_ID=$ID
        DISTRO_LIKE=${ID_LIKE:-""}
    else
        log_error "امکان تشخیص توزیع لینوکس وجود ندارد."
        exit 1
    fi

    log_info "توزیع شناسایی شده: ${PRETTY_NAME:-$DISTRO_ID}"
}

check_docker_installed() {
    if command -v docker &> /dev/null && (docker compose version &> /dev/null || command -v docker-compose &> /dev/null); then
        return 0
    else
        return 1
    fi
}

# Distro-specific Installation Functions
install_debian_ubuntu() {
    if check_docker_installed; then
        log_warn "داکر و داکر کامپوز قبلاً نصب شده‌اند. از مراحل نصب صرف‌نظر شد."
        return
    fi

    log_info "در حال حذف نسخه‌های قدیمی احتمالی داکر..."
    sudo apt-get remove -y docker docker-engine docker.io containerd runc &> /dev/null || true

    log_info "به‌روزرسانی مخازن و نصب پیش‌نیازها..."
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg openssl gettext-base

    log_info "افزودن کلید GPG و مخزن رسمی داکر..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/${DISTRO_ID}/gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    CODENAME="${VERSION_CODENAME}"
    if [ -z "$CODENAME" ]; then
        CODENAME=$(. /etc/os-release && echo "$UBUNTU_CODENAME")
    fi

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${DISTRO_ID} \
      ${CODENAME} stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    log_info "نصب Docker Engine و Docker Compose Plugin..."
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_arch_garuda() {
    if check_docker_installed; then
        log_warn "داکر و داکر کامپوز قبلاً نصب شده‌اند. از مراحل نصب صرف‌نظر شد."
        return
    fi

    log_info "به‌روزرسانی مخازن و نصب داکر و داکر کامپوز..."
    sudo pacman -Syu --noconfirm docker docker-compose openssl gettext

    log_info "فعال‌سازی و شروع سرویس داکر..."
    sudo systemctl enable --now docker.service
}

install_fedora_rhel() {
    if check_docker_installed; then
        log_warn "داکر و داکر کامپوز قبلاً نصب شده‌اند. از مراحل نصب صرف‌نظر شد."
        return
    fi

    log_info "نصب پیش‌نیازها و افزودن مخزن رسمی داکر..."
    sudo dnf -y install dnf-plugins-core openssl gettext

    REPO_URL="https://download.docker.com/linux/fedora/docker-ce.repo"
    if [[ "$DISTRO_ID" == "rhel" || "$DISTRO_ID" == "centos" || "$DISTRO_ID" == "rocky" || "$DISTRO_ID" == "almalinux" ]]; then
        REPO_URL="https://download.docker.com/linux/centos/docker-ce.repo"
    fi

    sudo dnf config-manager --add-repo "$REPO_URL"

    log_info "نصب Docker Engine و Docker Compose Plugin..."
    sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    log_info "فعال‌سازی و شروع سرویس داکر..."
    sudo systemctl enable --now docker
}

configure_user_group() {
    TARGET_USER="${SUDO_USER:-$USER}"

    if [ "$TARGET_USER" = "root" ]; then
        log_warn "کاربر جاری root است. نیازی به افزودن به گروه docker نیست."
        return
    fi

    if id -nG "$TARGET_USER" | grep -qw "docker"; then
        log_warn "کاربر '$TARGET_USER' قبلاً عضو گروه docker بوده است."
    else
        log_info "اضافه کردن کاربر '$TARGET_USER' به گروه docker..."
        sudo groupadd docker &> /dev/null || true
        sudo usermod -aG docker "$TARGET_USER"
        log_success "کاربر '$TARGET_USER' با موفقیت به گروه docker اضافه شد."
    fi
}

# Dynamic Resource Calculation
calculate_performance_settings() {
    log_info "در حال تحلیل منابع سخت‌افزاری سرور..."

    CPU_CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)
    TOTAL_RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo 2048)

    log_info "تعداد هسته CPU: ${CYAN}${CPU_CORES}${NC}"
    log_info "میزان حافظه RAM: ${CYAN}${TOTAL_RAM_MB} MB${NC}"

    # Odoo Official Formula: workers = (CPU * 2) + 1
    CALC_WORKERS=$(( (CPU_CORES * 2) + 1 ))

    AVAILABLE_RAM_FOR_WORKERS=$(( TOTAL_RAM_MB - 1024 ))
    MAX_WORKERS_BY_RAM=$(( AVAILABLE_RAM_FOR_WORKERS / 256 ))

    if [ "$MAX_WORKERS_BY_RAM" -lt 1 ]; then
        MAX_WORKERS_BY_RAM=0
    fi

    if [ "$CALC_WORKERS" -gt "$MAX_WORKERS_BY_RAM" ] && [ "$MAX_WORKERS_BY_RAM" -gt 0 ]; then
        WORKERS=$MAX_WORKERS_BY_RAM
        log_warn "تعداد Workers به دلیل محدودیت RAM به ${WORKERS} کاهش یافت."
    elif [ "$MAX_WORKERS_BY_RAM" -eq 0 ]; then
        WORKERS=0
        log_warn "میزان RAM کمتر از حد استاندارد است. Workers روی 0 تنظیم شد (Single Process Mode)."
    else
        WORKERS=$CALC_WORKERS
    fi

    if [ "$CPU_CORES" -gt 4 ]; then
        MAX_CRON_THREADS=2
    else
        MAX_CRON_THREADS=1
    fi

    log_success "پیکربندی بهینه عملکرد محاسبه شد: Workers = ${CYAN}${WORKERS}${NC}, Max Cron Threads = ${CYAN}${MAX_CRON_THREADS}${NC}"
}

generate_env_and_config() {
    echo
    echo -e "${CYAN}----------------------------------------------------${NC}"
    echo -e "${CYAN}  تنظیم اطلاعات پایگاه داده و امنیت Odoo            ${NC}"
    echo -e "${CYAN}----------------------------------------------------${NC}"

    if [ -f .env ] || [ -f odoo.conf ]; then
        log_warn "فایل‌های .env یا odoo.conf قبلاً وجود دارند."
        read -p "آیا می‌خواهید آن‌ها را بازنویسی (Overwrite) کنید؟ (y/N): " overwrite_files
        if [[ ! "$overwrite_files" =~ ^[Yy]$ ]]; then
            log_info "ساخت فایل‌های پیکربندی لغو شد. فایل‌های موجود حفظ شدند."
            return
        fi
    fi

    RANDOM_PG_PASS=$(generate_random_password)
    RANDOM_ODOO_PASS=$(generate_random_password)

    read -p "نام کاربر دیتابیس (پیش‌فرض: shaka): " INPUT_PG_USER
    POSTGRES_USER=${INPUT_PG_USER:-shaka}

    read -p "رمز عبور دیتابیس [پیش‌فرض (تصادفی)]: " INPUT_PG_PASS
    POSTGRES_PASSWORD=${INPUT_PG_PASS:-$RANDOM_PG_PASS}

    read -p "نام دیتابیس اصلی (پیش‌فرض: postgres): " INPUT_PG_DB
    POSTGRES_DB=${INPUT_PG_DB:-postgres}

    read -p "رمز عبور مستر اودوو [پیش‌فرض (تصادفی)]: " INPUT_ODOO_PASS
    SHAKA_MASTER_PASSWORD=${INPUT_ODOO_PASS:-$RANDOM_ODOO_PASS}

    # Generate .env file
    log_info "در حال ایجاد فایل .env..."
    cat <<EOF > .env
# Database Credentials
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}

# Shaka Settings
SHAKA_MASTER_PASSWORD=${SHAKA_MASTER_PASSWORD}
EOF
    chmod 600 .env
    log_success "فایل .env با موفقیت ساخته شد."

    # Generate odoo.conf file matching exact clean structure
    log_info "در حال ایجاد فایل odoo.conf با تنظیمات اختصاصی سرور..."
    cat <<EOF > odoo.conf
[options]

db_host = db
db_port = 5432
db_user = ${POSTGRES_USER}
db_password = ${POSTGRES_PASSWORD}

admin_passwd = ${SHAKA_MASTER_PASSWORD}

proxy_mode = True

addons_path = /opt/odoo/addons,/opt/odoo/custom_addons
data_dir = /var/lib/odoo

log_level = info

workers = ${WORKERS:-4}
max_cron_threads = ${MAX_CRON_THREADS:-2}
gevent_port = 8072
EOF
    log_success "فایل odoo.conf با موفقیت ساخته شد."
}

# Main Execution Flow
main() {
    clear
    echo -e "${GREEN}====================================================${NC}"
    echo -e "${GREEN}  آماده‌سازی پیش‌نیازها و کانفیگ Odoo 19 (Docker & Nginx) ${NC}"
    echo -e "${GREEN}====================================================${NC}"
    echo

    check_root_or_sudo
    detect_distro

    echo
    case "$DISTRO_ID" in
        ubuntu|debian)
            install_debian_ubuntu
            ;;
        arch|garuda)
            install_arch_garuda
            ;;
        fedora|rhel|centos|rocky|almalinux)
            install_fedora_rhel
            ;;
        *)
            if [[ "$DISTRO_LIKE" == *"debian"* || "$DISTRO_LIKE" == *"ubuntu"* ]]; then
                install_debian_ubuntu
            elif [[ "$DISTRO_LIKE" == *"arch"* ]]; then
                install_arch_garuda
            elif [[ "$DISTRO_LIKE" == *"fedora"* || "$DISTRO_LIKE" == *"rhel"* ]]; then
                install_fedora_rhel
            else
                log_error "توزیع لینوکس شما به صورت خودکار پشتیبانی نمی‌شود."
                exit 1
            fi
            ;;
    esac

    configure_user_group
    calculate_performance_settings
    generate_env_and_config

    echo
    log_info "Using project at $REPO_DIR"
    cd "$REPO_DIR"

    # Source .env for later use
    set -a
    source .env
    set +a

    # 5. Restore backup storage from off-site (rsync from your backup server)
    #    Uncomment and adjust the source:
    # log_info "Syncing backup storage from remote..."
    # rsync -avz --progress backup-user@backup-server:/backups/ "$BACKUP_ROOT/"

    # 6. Ensure backup directories exist
    log_info "Ensuring backup directories exist..."
    mkdir -p "$BACKUP_ROOT/pgbackrest" "$BACKUP_ROOT/filestore" "$BACKUP_ROOT/logs"

    # 7. Fix pgBackRest ownership (postgres uid 999 inside container)
    log_info "Fixing pgBackRest directory ownership..."
    docker run --rm -v "$BACKUP_ROOT":/opt/backups busybox:1.36 \
        sh -c 'chown -R 999:999 /opt/backups/pgbackrest && chmod -R 750 /opt/backups/pgbackrest'

    # 8. Build images
    log_info "Building database image (pgvector + pgBackRest)..."
    docker compose build db

    log_info "Building filestore sync helper image..."
    docker build -f filestore-sync.Dockerfile -t odoo_filestore_sync .

    # 9. Start database
    log_info "Starting database container..."
    docker compose up -d db

    # Wait for healthcheck
    log_info "Waiting for database to become healthy..."
    until [[ "$(docker inspect -f '{{.State.Health.Status}}' odoo_19_db 2>/dev/null)" == "healthy" ]]; do
        sleep 2
    done
    log_success "Database healthy."

    # 10. Initialize pgBackRest stanza
    log_info "Creating pgBackRest stanza '$STANZA'..."
    docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" stanza-create || true

    log_info "Running pgBackRest check..."
    docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

    # 11. Run initial full backup (if repo is empty)
    if ! docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" info 2>/dev/null | grep -q "full backup:"; then
        log_info "No existing backups found. Running initial full backup..."
        docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" --type=full backup
    else
        log_info "Existing backups detected. Skipping initial full backup."
    fi

    # 12. Start Odoo web + nginx
    log_info "Starting web and nginx..."
    docker compose up -d web nginx

    # 13. Initial filestore sync (creates mirror)
    log_info "Running initial filestore sync..."
    if [ -f "./backup/filestore_sync.sh" ]; then
        ./backup/filestore_sync.sh
    else
        log_warn "./backup/filestore_sync.sh not found, skipping initial sync."
    fi

    # 14. Install cron jobs for automated backups
    log_info "Installing cron jobs (filestore every 15 min, full DB daily at 02:15)..."
    if [ -f "./backup/install_cron.sh" ]; then
        ./backup/install_cron.sh
    else
        log_warn "./backup/install_cron.sh not found, skipping cron installation."
    fi

    # 15. Final verification
    log_info "Verifying backup health..."
    docker compose exec -T -u postgres db pgbackrest --stanza="$STANZA" check

    log_success "Deployment initialization complete."
    echo ""
    echo "=== SUMMARY ==="
    echo "Project:       $REPO_DIR"
    echo "Backups:       $BACKUP_ROOT"
    echo "Database:      pgBackRest stanza '$STANZA' (continuous WAL, daily full)"
    echo "Filestore:     rsync mirror every 15 min"
    echo "Cron:          Installed (run 'crontab -l' to verify)"
    echo ""
    echo "Next steps:"
    echo "  - Verify Odoo accessible at http://<server-ip>"
    echo "  - Test a restore on staging: ./backup/restore.sh"
    echo "  - Configure off-site replication for $BACKUP_ROOT"
}

main "$@"