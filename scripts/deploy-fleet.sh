#!/bin/bash
# Archivi.ng Fleet Deployment Script
# Deploys multiple agents to scrape in parallel from OLDEST to NEWEST

cd "/Volumes/Crucial X10/Decide9ja"

# Fleet configuration
NEWSPAPERS=("PM News" "The Guardian" "Vanguard" "Punch" "Daily Trust" "ThisDay" "Tribune" "The Sun" "The Nation" "Leadership")

# Time ranges for each agent (oldest → newest)
# Agent Alpha: 1900-1930
# Agent Beta: 1931-1960
# Agent Gamma: 1961-1980
# Agent Delta: 1981-1990
# Agent Epsilon: 1991-2000
# Agent Zeta: 2001-2010
# Agent Eta: 2011-2020
# Agent Theta: 2021-2026

echo "🚀 DEPLOYING ARCHIVI.NG FLEET"
echo "=============================="
echo ""

# Create fleet directories
mkdir -p logs/memory
mkdir -p data/bulk-archive

# Function to start an agent
start_agent() {
    local name=$1
    local start_year=$2
    local end_year=$3
    local newspapers=$4
    
    echo "[$name] Deploying: $start_year → $end_year"
    
    START_YEAR=$start_year \
    END_YEAR=$end_year \
    NEWSPAPERS="$newspapers" \
    AGENT_ID=$name \
    node src/fleet/scraper.js >> "logs/fleet-$name.log" 2>&1 &
    
    echo $! > "logs/fleet-$name.pid"
    echo "[$name] PID: $!"
}

# Stop any existing fleet
pkill -f "fleet-" 2>/dev/null
sleep 2

# Deploy the fleet
# Each agent handles 30 years (except modern ones)
echo "📡 Launching agents..."
echo ""

start_agent "alpha" 1900 1930 "${NEWSPAPERS[*]}"
sleep 5

start_agent "beta" 1931 1960 "${NEWSPAPERS[*]}"
sleep 5

start_agent "gamma" 1961 1980 "${NEWSPAPERS[*]}"
sleep 5

start_agent "delta" 1981 1990 "${NEWSPAPERS[*]}"
sleep 5

start_agent "epsilon" 1991 2000 "${NEWSPAPERS[*]}"
sleep 5

start_agent "zeta" 2001 2010 "${NEWSPAPERS[*]}"
sleep 5

start_agent "eta" 2011 2020 "${NEWSPAPERS[*]}"
sleep 5

start_agent "theta" 2021 2026 "${NEWSPAPERS[*]}"

echo ""
echo "✅ FLEET DEPLOYED"
echo ""
echo "Active agents:"
ps aux | grep "fleet-" | grep -v grep | wc -l
echo ""
echo "Monitor with:"
echo "  tail -f logs/fleet-alpha.log"
echo "  tail -f logs/fleet-beta.log"
echo "  ..."
echo ""
echo "Check progress:"
echo "  ls logs/memory/FLEET_*.json"
