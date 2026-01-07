#!/bin/bash
#
# Decide9ja Scheduler & News Worker Installation Script
# This script sets up systemd services for background processing
#
# Usage: sudo ./install.sh [--uninstall]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/etc/systemd/system"
INSTALL_DIR="/opt/decide9ja"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

create_user() {
    if ! id "decide9ja" &>/dev/null; then
        log_info "Creating decide9ja user..."
        useradd --system --home-dir "$INSTALL_DIR" --shell /bin/false decide9ja
    else
        log_info "User decide9ja already exists"
    fi
}

setup_directories() {
    log_info "Setting up directories..."

    mkdir -p "$INSTALL_DIR"/{data,logs}

    # Copy application if not already there
    if [[ ! -d "$INSTALL_DIR/decide9ja_backend" ]]; then
        log_warn "Application not found at $INSTALL_DIR/decide9ja_backend"
        log_warn "Please copy the application first:"
        log_warn "  cp -r /path/to/decide9ja_backend $INSTALL_DIR/"
    fi

    # Set ownership
    chown -R decide9ja:decide9ja "$INSTALL_DIR"
}

setup_venv() {
    if [[ ! -d "$INSTALL_DIR/venv" ]]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv "$INSTALL_DIR/venv"
        "$INSTALL_DIR/venv/bin/pip" install --upgrade pip

        if [[ -f "$INSTALL_DIR/decide9ja_backend/requirements.txt" ]]; then
            "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/decide9ja_backend/requirements.txt"
        fi
    else
        log_info "Virtual environment already exists"
    fi
}

setup_env() {
    if [[ ! -f "$INSTALL_DIR/.env" ]]; then
        log_warn "Environment file not found at $INSTALL_DIR/.env"
        log_warn "Please create .env file with required variables:"
        cat << 'EOF'
# Required environment variables:
ANTHROPIC_API_KEY=your_api_key
OPENAI_API_KEY=your_openai_key
DATABASE_URL=postgresql://user:pass@localhost:5432/decide9ja
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
REDIS_URL=redis://localhost:6379/0
EOF
    fi
}

install_services() {
    log_info "Installing systemd services..."

    # Copy service files
    cp "$SCRIPT_DIR/decide9ja-scheduler.service" "$SERVICE_DIR/"
    cp "$SCRIPT_DIR/decide9ja-news-worker.service" "$SERVICE_DIR/"

    # Reload systemd
    systemctl daemon-reload

    log_info "Services installed successfully"
}

enable_services() {
    log_info "Enabling services to start on boot..."

    systemctl enable decide9ja-scheduler.service
    systemctl enable decide9ja-news-worker.service
}

start_services() {
    log_info "Starting services..."

    systemctl start decide9ja-scheduler.service
    sleep 2
    systemctl start decide9ja-news-worker.service

    # Check status
    log_info "Service status:"
    systemctl status decide9ja-scheduler.service --no-pager || true
    systemctl status decide9ja-news-worker.service --no-pager || true
}

uninstall() {
    log_info "Uninstalling Decide9ja services..."

    # Stop services
    systemctl stop decide9ja-scheduler.service 2>/dev/null || true
    systemctl stop decide9ja-news-worker.service 2>/dev/null || true

    # Disable services
    systemctl disable decide9ja-scheduler.service 2>/dev/null || true
    systemctl disable decide9ja-news-worker.service 2>/dev/null || true

    # Remove service files
    rm -f "$SERVICE_DIR/decide9ja-scheduler.service"
    rm -f "$SERVICE_DIR/decide9ja-news-worker.service"

    # Reload systemd
    systemctl daemon-reload

    log_info "Services uninstalled"
    log_info "Note: User and data directories were not removed"
}

show_status() {
    echo ""
    echo "=== Decide9ja Services Status ==="
    echo ""

    echo "Scheduler:"
    systemctl is-active decide9ja-scheduler.service || echo "Not running"

    echo ""
    echo "News Worker:"
    systemctl is-active decide9ja-news-worker.service || echo "Not running"

    echo ""
    echo "=== Useful Commands ==="
    echo "  View scheduler logs:     journalctl -u decide9ja-scheduler -f"
    echo "  View news worker logs:   journalctl -u decide9ja-news-worker -f"
    echo "  Restart scheduler:       systemctl restart decide9ja-scheduler"
    echo "  Restart news worker:     systemctl restart decide9ja-news-worker"
    echo "  Stop all:                systemctl stop decide9ja-{scheduler,news-worker}"
    echo ""
}

# Main
main() {
    check_root

    if [[ "${1:-}" == "--uninstall" ]]; then
        uninstall
        exit 0
    fi

    if [[ "${1:-}" == "--status" ]]; then
        show_status
        exit 0
    fi

    echo "========================================"
    echo "Decide9ja Scheduler Installation"
    echo "========================================"
    echo ""

    create_user
    setup_directories
    setup_venv
    setup_env
    install_services
    enable_services
    start_services
    show_status

    log_info "Installation complete!"
}

main "$@"
