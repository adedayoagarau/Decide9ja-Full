#!/bin/bash
# Cron Job Setup for Political Data Agent
# Run this script to install the cron jobs

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_PATH="${PYTHON_PATH:-python3}"

echo "Setting up cron jobs for Decide9ja Political Data Agent"
echo "Backend directory: $BACKEND_DIR"

# Create cron entries
CRON_FILE="/tmp/decide9ja_cron"

cat > "$CRON_FILE" << EOF
# Decide9ja Political Data Agent Cron Jobs
# =========================================

# Full agent run - Daily at 6 AM (collects, processes, updates candidates)
0 6 * * * cd $BACKEND_DIR && $PYTHON_PATH scripts/run_political_agent.py >> /var/log/decide9ja/agent.log 2>&1

# Quick update - Every 4 hours (just RSS feeds)
0 */4 * * * cd $BACKEND_DIR && $PYTHON_PATH scripts/run_political_agent.py --quick >> /var/log/decide9ja/agent_quick.log 2>&1

# Database backup - Daily at 2 AM
0 2 * * * pg_dump decide9ja > /var/backups/decide9ja/db_\$(date +\%Y\%m\%d).sql 2>&1
EOF

echo ""
echo "The following cron entries will be added:"
echo "-------------------------------------------"
cat "$CRON_FILE"
echo "-------------------------------------------"

# Ask for confirmation
read -p "Install these cron jobs? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create log directory
    sudo mkdir -p /var/log/decide9ja
    sudo chmod 777 /var/log/decide9ja

    # Install crontab
    crontab -l 2>/dev/null | cat - "$CRON_FILE" | crontab -

    echo "✅ Cron jobs installed!"
    echo ""
    echo "View current cron jobs with: crontab -l"
    echo "View logs in: /var/log/decide9ja/"
else
    echo "Cancelled."
fi

rm "$CRON_FILE"
