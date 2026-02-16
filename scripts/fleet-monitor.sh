#!/bin/bash
# Fleet Auto-Restarter & Monitor
# Restarts any fleet agent that crashes or stops

cd "/Volumes/Crucial X10/Decide9ja"

NEWSPAPERS="PM News,The Guardian,Vanguard,Punch,Daily Trust,ThisDay,Tribune,The Sun,The Nation,Leadership"

# Agent configurations
agents=(
  "alpha:1900:1930"
  "beta:1931:1960"
  "gamma:1961:1980"
  "delta:1981:1990"
  "epsilon:1991:2000"
  "zeta:2001:2010"
  "eta:2011:2020"
  "theta:2021:2026"
)

# Function to check and restart agent
check_and_restart() {
  local name=$1
  local start_year=$2
  local end_year=$3
  
  # Check if process is running
  local pid_file="logs/fleet-${name}.pid"
  local log_file="logs/fleet-${name}.log"
  
  if [ -f "$pid_file" ]; then
    local pid=$(cat "$pid_file")
    if ps -p "$pid" > /dev/null 2>&1; then
      echo "[$name] ✅ Running (PID: $pid)"
      return 0
    fi
  fi
  
  # Process not running - restart it
  echo "[$name] 🔄 Restarting..."
  
  START_YEAR=$start_year \
  END_YEAR=$end_year \
  AGENT_ID=$name \
  NEWSPAPERS="$NEWSPAPERS" \
  nohup node src/fleet/scraper.js >> "$log_file" 2>&1 &
  
  local new_pid=$!
  echo $new_pid > "$pid_file"
  echo "[$name] ✅ Started (PID: $new_pid)"
  
  # Log restart
  echo "$(date): $name restarted (PID: $new_pid)" >> logs/fleet-restarts.log
}

# Main loop
echo "🚀 FLEET AUTO-RESTARTER"
echo "======================="
echo "Checking all agents..."
echo ""

for agent in "${agents[@]}"; do
  IFS=':' read -r name start end <<< "$agent"
  check_and_restart "$name" "$start" "$end"
  sleep 2
done

echo ""
echo "✅ Fleet check complete"
echo ""
echo "Active agents:"
ps aux | grep "fleet-" | grep -v grep | wc -l
echo ""
