#!/bin/bash
# Philip Scraper Auto-Restarter

cd "/Volumes/Crucial X10/Decide9ja"

# Check if Philip is running
if pgrep -f "archiving.js" > /dev/null; then
  echo "[Philip] ✅ Running"
  exit 0
fi

echo "[Philip] 🔄 Restarting..."

nohup node src/scraper/archiving.js >> logs/archiving.log 2>&1 &

pid=$!
echo $pid > logs/archiving.pid

echo "$(date): Philip restarted (PID: $pid)" >> logs/agent-restarts.log
echo "[Philip] ✅ Started (PID: $pid)"
