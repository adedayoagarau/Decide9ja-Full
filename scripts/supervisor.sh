#!/bin/bash
# Philip Supervisor - Auto-restart on crash
# Monitors the archivi.ng scraper and restarts if it fails

set -e

# Configuration
PROJECT_DIR="/Volumes/Crucial X10/Decide9ja"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="/tmp/philip-supervisor.pid"
SCRAPER_PID_FILE="/tmp/philip-scraper.pid"
MAX_RESTARTS=10
RESTART_WINDOW=3600  # 1 hour
HEALTH_CHECK_INTERVAL=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo -e "${timestamp} [SUPERVISOR] [$level] $message"
    
    # Also log to file
    echo "${timestamp} [SUPERVISOR] [$level] $message" >> "$LOG_DIR/supervisor.log"
}

# Check if scraper is running
check_scraper() {
    if [ -f "$SCRAPER_PID_FILE" ]; then
        local pid=$(cat "$SCRAPER_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Running
        fi
    fi
    return 1  # Not running
}

# Get scraper health from health.json
get_scraper_health() {
    local health_file="$PROJECT_DIR/memory/health.json"
    if [ -f "$health_file" ]; then
        local age=$(($(date +%s) - $(stat -f %m "$health_file")))
        if [ $age -lt 300 ]; then  # Updated in last 5 minutes
            cat "$health_file"
            return 0
        fi
    fi
    return 1
}

# Start the scraper
start_scraper() {
    log "INFO" "Starting Philip scraper..."
    
    cd "$PROJECT_DIR"
    
    # Start scraper in background
    nohup node src/scraper/archiving.js > "$LOG_DIR/scraper-output.log" 2>&1 &
    local pid=$!
    
    echo $pid > "$SCRAPER_PID_FILE"
    
    log "INFO" "Scraper started with PID: $pid"
    
    # Wait a bit and check if it's still running
    sleep 5
    
    if ps -p "$pid" > /dev/null 2>&1; then
        log "SUCCESS" "${GREEN}Scraper is running successfully${NC}"
        return 0
    else
        log "ERROR" "${RED}Scraper failed to start${NC}"
        return 1
    fi
}

# Stop the scraper
stop_scraper() {
    if [ -f "$SCRAPER_PID_FILE" ]; then
        local pid=$(cat "$SCRAPER_PID_FILE")
        log "INFO" "Stopping scraper (PID: $pid)..."
        
        # Try graceful shutdown first
        kill -TERM "$pid" 2>/dev/null || true
        
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$pid" > /dev/null 2>&1; then
                log "INFO" "Scraper stopped gracefully"
                rm -f "$SCRAPER_PID_FILE"
                return 0
            fi
            sleep 1
        done
        
        # Force kill if still running
        log "WARN" "Force killing scraper..."
        kill -KILL "$pid" 2>/dev/null || true
        rm -f "$SCRAPER_PID_FILE"
    fi
}

# Restart the scraper
restart_scraper() {
    log "WARN" "${YELLOW}Restarting scraper...${NC}"
    stop_scraper
    sleep 2
    start_scraper
}

# Check error rate
check_error_rate() {
    local error_file="$PROJECT_DIR/logs/detailed-errors.jsonl"
    
    if [ -f "$error_file" ]; then
        # Count errors in last 10 minutes
        local cutoff=$(($(date +%s) - 600))
        local recent_errors=$(grep -c "$(date -r $cutoff '+%Y-%m-%d')" "$error_file" 2>/dev/null || echo "0")
        
        if [ "$recent_errors" -gt 20 ]; then
            log "ERROR" "${RED}High error rate detected: $recent_errors errors in last 10 minutes${NC}"
            return 1
        fi
    fi
    return 0
}

# Check disk space
check_disk_space() {
    local available=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $4}')
    
    # Convert to GB for comparison (handle Ti/Gi/Mi)
    local available_gb=0
    if [[ "$available" =~ ([0-9.]+)Ti ]]; then
        available_gb=$(echo "${BASH_REMATCH[1]} * 1024" | bc)
    elif [[ "$available" =~ ([0-9.]+)Gi ]]; then
        available_gb=${BASH_REMATCH[1]}
    elif [[ "$available" =~ ([0-9.]+)Mi ]]; then
        available_gb=$(echo "${BASH_REMATCH[1]} / 1024" | bc -l)
    fi
    
    # Require at least 10GB free
    if (( $(echo "$available_gb < 10" | bc -l) )); then
        log "ERROR" "${RED}Low disk space: ${available} available${NC}"
        return 1
    fi
    
    return 0
}

# Main supervisor loop
supervise() {
    log "INFO" "=== PHILIP SUPERVISOR STARTED ==="
    log "INFO" "Project: $PROJECT_DIR"
    log "INFO" "Max restarts: $MAX_RESTARTS per hour"
    log "INFO" "Health check interval: ${HEALTH_CHECK_INTERVAL}s"
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    
    # Initialize restart tracking
    local restart_count=0
    local restart_window_start=$(date +%s)
    
    # Start scraper initially
    if ! start_scraper; then
        log "ERROR" "${RED}Failed to start scraper initially${NC}"
        exit 1
    fi
    
    # Main loop
    while true; do
        sleep $HEALTH_CHECK_INTERVAL
        
        # Check if we need to reset restart counter
        local current_time=$(date +%s)
        if [ $((current_time - restart_window_start)) -gt $RESTART_WINDOW ]; then
            if [ $restart_count -gt 0 ]; then
                log "INFO" "Resetting restart counter (was $restart_count)"
                restart_count=0
                restart_window_start=$current_time
            fi
        fi
        
        # Check if scraper is running
        if ! check_scraper; then
            log "ERROR" "${RED}Scraper is not running!${NC}"
            
            # Check restart limit
            if [ $restart_count -ge $MAX_RESTARTS ]; then
                log "ERROR" "${RED}Maximum restarts ($MAX_RESTARTS) reached in last hour. Giving up.${NC}"
                log "ERROR" "Please check logs at: $LOG_DIR"
                exit 1
            fi
            
            # Check error rate
            if ! check_error_rate; then
                log "WARN" "${YELLOW}High error rate detected, waiting 60s before restart...${NC}"
                sleep 60
            fi
            
            # Check disk space
            if ! check_disk_space; then
                log "ERROR" "${RED}Critical: Low disk space. Stopping supervisor.${NC}"
                exit 1
            fi
            
            # Restart scraper
            restart_count=$((restart_count + 1))
            log "INFO" "Restart attempt $restart_count/$MAX_RESTARTS"
            
            if restart_scraper; then
                log "SUCCESS" "${GREEN}Scraper restarted successfully${NC}"
            else
                log "ERROR" "${RED}Failed to restart scraper${NC}"
            fi
        else
            # Scraper is running, check health
            local health=$(get_scraper_health)
            if [ $? -eq 0 ]; then
                log "DEBUG" "Scraper health check: OK"
            else
                log "WARN" "No recent health update from scraper"
            fi
        fi
        
        # Log status periodically
        if [ $((current_time % 300)) -lt $HEALTH_CHECK_INTERVAL ]; then
            local uptime=$(ps -o etime= -p $(cat "$SCRAPER_PID_FILE") 2>/dev/null || echo "unknown")
            log "INFO" "Status check - Scraper uptime: $uptime, Restarts: $restart_count"
        fi
    done
}

# Handle shutdown
cleanup() {
    log "INFO" "Supervisor shutting down..."
    stop_scraper
    rm -f "$PID_FILE"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Write supervisor PID
echo $$ > "$PID_FILE"

# Parse command line arguments
case "${1:-}" in
    start)
        supervise
        ;;
    stop)
        log "INFO" "Stopping supervisor..."
        if [ -f "$PID_FILE" ]; then
            kill -TERM $(cat "$PID_FILE") 2>/dev/null || true
        fi
        stop_scraper
        ;;
    restart)
        log "INFO" "Restarting supervisor..."
        if [ -f "$PID_FILE" ]; then
            kill -TERM $(cat "$PID_FILE") 2>/dev/null || true
            sleep 2
        fi
        stop_scraper
        supervise
        ;;
    status)
        if check_scraper; then
            _pid=$(cat "$SCRAPER_PID_FILE")
            _uptime=$(ps -o etime= -p "$_pid" 2>/dev/null || echo "unknown")
            echo -e "${GREEN}Scraper is running${NC} (PID: $_pid, Uptime: $_uptime)"
        else
            echo -e "${RED}Scraper is not running${NC}"
        fi
        
        if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
            echo -e "${GREEN}Supervisor is running${NC} (PID: $(cat "$PID_FILE"))"
        else
            echo -e "${RED}Supervisor is not running${NC}"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the supervisor and scraper"
        echo "  stop    - Stop the supervisor and scraper"
        echo "  restart - Restart the supervisor and scraper"
        echo "  status  - Check status of supervisor and scraper"
        exit 1
        ;;
esac
