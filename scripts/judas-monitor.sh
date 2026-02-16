#!/bin/bash
# Judas OCR Auto-Restarter

cd "/Volumes/Crucial X10/Decide9ja"

# Check if Judas is running
if pgrep -f "judas.js" > /dev/null; then
  echo "[Judas] ✅ Running"
  exit 0
fi

echo "[Judas] 🔄 Restarting..."

nohup node src/processor/judas.js >> logs/judas.log 2>&1 &

pid=$!
echo $pid > logs/judas.pid

echo "$(date): Judas restarted (PID: $pid)" >> logs/agent-restarts.log
echo "[Judas] ✅ Started (PID: $pid)"
