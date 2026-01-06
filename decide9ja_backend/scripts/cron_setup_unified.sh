#!/bin/bash
# ============================================================================
# Decide9ja Unified Scheduler Setup Script
# ============================================================================
# This script sets up the production deployment for the Decide9ja scheduler.
#
# Options:
#   --cron     Install cron jobs (for systems without systemd)
#   --systemd  Install systemd service (recommended for production)
#   --both     Install both cron jobs and systemd service
#   --status   Check current status
#   --remove   Remove all installed services
#
# Usage:
#   ./cron_setup_unified.sh --systemd
#   ./cron_setup_unified.sh --cron
#   ./cron_setup_unified.sh --status
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_PATH="${PYTHON_PATH:-python3}"
SERVICE_NAME="decide9ja-scheduler"
LOG_DIR="/var/log/decide9ja"
VENV_PATH="${VENV_PATH:-$BACKEND_DIR/venv}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Decide9ja Unified Scheduler Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Backend directory: $BACKEND_DIR"
echo "Python path: $PYTHON_PATH"
echo ""

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Error: This script must be run as root (for systemd/cron setup)${NC}"
        echo "Try: sudo $0 $@"
        exit 1
    fi
}

# Function to create log directory
create_log_dir() {
    if [[ ! -d "$LOG_DIR" ]]; then
        mkdir -p "$LOG_DIR"
        chmod 755 "$LOG_DIR"
        echo -e "${GREEN}✓ Created log directory: $LOG_DIR${NC}"
    fi
}

# Function to install systemd service
install_systemd() {
    check_root
    create_log_dir

    echo ""
    echo -e "${YELLOW}Installing systemd service...${NC}"

    # Create systemd service file
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Decide9ja Unified Scheduler
Documentation=https://github.com/adedayoagarau/Decide9ja-Full
After=network.target postgresql.service redis.service
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$BACKEND_DIR"
ExecStart=$VENV_PATH/bin/python -m app.scheduler_unified
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/scheduler.log
StandardError=append:$LOG_DIR/scheduler_error.log

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$LOG_DIR $BACKEND_DIR/data
PrivateTmp=yes

# Resource limits
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"

    echo -e "${GREEN}✓ Systemd service installed${NC}"
    echo ""
    echo "To start the service:"
    echo "  sudo systemctl start $SERVICE_NAME"
    echo ""
    echo "To check status:"
    echo "  sudo systemctl status $SERVICE_NAME"
    echo ""
    echo "To view logs:"
    echo "  sudo journalctl -u $SERVICE_NAME -f"
    echo "  tail -f $LOG_DIR/scheduler.log"
}

# Function to install cron jobs
install_cron() {
    check_root
    create_log_dir

    echo ""
    echo -e "${YELLOW}Installing cron jobs...${NC}"

    # Create cron file
    CRON_FILE="/etc/cron.d/decide9ja-scheduler"

    cat > "$CRON_FILE" << EOF
# Decide9ja Scheduler Cron Jobs
# ============================================================================
# These are BACKUP cron jobs in case the main scheduler service fails.
# The main scheduler (systemd service) handles most jobs internally.
# ============================================================================

SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
PYTHONPATH=$BACKEND_DIR

# Backup: Run full scheduler check every 6 hours (in case service died)
0 */6 * * * root cd $BACKEND_DIR && $PYTHON_PATH -m app.scheduler_unified --job health >> $LOG_DIR/cron_health.log 2>&1

# Backup: Political Data Agent - Daily at 6 AM
0 6 * * * root cd $BACKEND_DIR && $PYTHON_PATH scripts/run_political_agent.py >> $LOG_DIR/agent.log 2>&1

# Backup: Quick RSS update - Every 4 hours (lightweight)
0 */4 * * * root cd $BACKEND_DIR && $PYTHON_PATH scripts/run_political_agent.py --quick >> $LOG_DIR/agent_quick.log 2>&1

# Database backup - Daily at 2 AM
0 2 * * * root pg_dump decide9ja > /var/backups/decide9ja/db_\$(date +\%Y\%m\%d).sql 2>&1 || echo "DB backup failed" >> $LOG_DIR/backup_error.log

# Log rotation check - Weekly
0 0 * * 0 root find $LOG_DIR -name "*.log" -mtime +30 -delete
EOF

    chmod 644 "$CRON_FILE"

    echo -e "${GREEN}✓ Cron jobs installed at $CRON_FILE${NC}"
    echo ""
    echo "View cron jobs:"
    echo "  cat $CRON_FILE"
}

# Function to show status
show_status() {
    echo ""
    echo -e "${YELLOW}Current Status:${NC}"
    echo "----------------------------------------"

    # Check systemd service
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "Systemd service: ${GREEN}RUNNING${NC}"
        systemctl status "$SERVICE_NAME" --no-pager | head -10
    elif systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "Systemd service: ${YELLOW}INSTALLED (not running)${NC}"
    else
        echo -e "Systemd service: ${RED}NOT INSTALLED${NC}"
    fi

    echo ""

    # Check cron jobs
    if [[ -f "/etc/cron.d/decide9ja-scheduler" ]]; then
        echo -e "Cron jobs: ${GREEN}INSTALLED${NC}"
    else
        echo -e "Cron jobs: ${RED}NOT INSTALLED${NC}"
    fi

    echo ""

    # Check logs
    if [[ -d "$LOG_DIR" ]]; then
        echo "Recent log entries:"
        if [[ -f "$LOG_DIR/scheduler.log" ]]; then
            tail -5 "$LOG_DIR/scheduler.log" 2>/dev/null || echo "  (no logs yet)"
        else
            echo "  (no logs yet)"
        fi
    fi
}

# Function to remove installations
remove_all() {
    check_root

    echo ""
    echo -e "${YELLOW}Removing Decide9ja scheduler installations...${NC}"

    # Stop and disable systemd service
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl stop "$SERVICE_NAME"
    fi
    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl disable "$SERVICE_NAME"
    fi
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload

    # Remove cron file
    rm -f "/etc/cron.d/decide9ja-scheduler"

    echo -e "${GREEN}✓ All installations removed${NC}"
}

# Function to test scheduler
test_scheduler() {
    echo ""
    echo -e "${YELLOW}Testing scheduler...${NC}"
    cd "$BACKEND_DIR"
    $PYTHON_PATH -m app.scheduler_unified --job health
    echo ""
    echo -e "${GREEN}✓ Scheduler test complete${NC}"
}

# Main logic
case "${1:-}" in
    --systemd)
        install_systemd
        ;;
    --cron)
        install_cron
        ;;
    --both)
        install_systemd
        install_cron
        ;;
    --status)
        show_status
        ;;
    --remove)
        remove_all
        ;;
    --test)
        test_scheduler
        ;;
    *)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  --systemd  Install systemd service (recommended)"
        echo "  --cron     Install backup cron jobs"
        echo "  --both     Install both systemd and cron"
        echo "  --status   Show current installation status"
        echo "  --remove   Remove all installations"
        echo "  --test     Test scheduler health check"
        echo ""
        echo "Example:"
        echo "  sudo $0 --systemd"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Done!${NC}"
