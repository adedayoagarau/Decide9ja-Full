# Philip Scraper - Bulletproof Edition v2.0

## ✅ DEPLOYED ENHANCEMENTS

### 1. Auto-Restart on Crash
- **Supervisor**: `/Volumes/Crucial X10/Decide9ja/scripts/supervisor.sh`
- **Max Restarts**: 10 per hour
- **Health Checks**: Every 30 seconds
- **Commands**:
  ```bash
  npm run scrape:supervised  # Start with supervisor
  npm run scrape:stop        # Stop
  npm run scrape:restart     # Restart
  npm run scrape:status      # Check status
  ```

### 2. Detailed Error Logging
**Files**:
- `logs/archiving.log` - Main log (100MB rotation, 10 files)
- `logs/archiving-error.log` - Error log (50MB rotation, 5 files)
- `logs/detailed-errors.jsonl` - Structured JSON errors
- `logs/supervisor.log` - Supervisor activity
- `logs/exceptions.log` - Uncaught exceptions
- `logs/rejections.log` - Unhandled rejections

**Each Error Includes**:
```json
{
  "context": "scrape-PM News-2026-02-05",
  "message": "Error details",
  "stack": "Full stack trace",
  "code": "Error code",
  "type": "Error name",
  "attempt": 3,
  "maxRetries": 5,
  "url": "https://archivi.ng/...",
  "newspaper": "PM News",
  "date": "2026-02-05",
  "selectorsTried": ["selector1", "selector2", ...],
  "timestamp": "2026-02-05T10:00:00Z"
}
```

### 3. Fallback Mechanisms

#### Selector Fallbacks (9 patterns tried in order)
1. `[data-testid="result-item"]`
2. `.result-item`
3. `.archive-item`
4. `.search-result`
5. `article`
6. `.issue-card`
7. `.newspaper-item`
8. `[class*="result"]`
9. `[class*="item"]`

#### Field Fallbacks
- **Title**: h2 → h3 → .title → [data-title] → .headline → a
- **Date**: .date → [data-date] → time → [datetime] → .published
- **Image**: img[src*="archive"] → img[src*="newspaper"] → img

#### Final Fallback
If all selectors fail, extracts any links containing "archive" or "newspaper"

### 4. Retry Logic
- **Max Retries**: 5 attempts
- **Backoff**: Exponential (5s, 10s, 20s, 40s, 80s)
- **Per-Date**: Each date scraped independently
- **Consecutive Errors**: Skip to next newspaper after 10 consecutive failures

### 5. Health Monitoring
- **File**: `memory/health.json`
- **Updated**: Every 50 issues processed
- **Includes**: PID, memory usage, uptime, directory status

### 6. Graceful Shutdown
- Handles SIGTERM and SIGINT
- Saves progress before exiting
- Closes browser properly

## 🎯 Current Status

```bash
$ npm run scrape:status

🟢 Scraper is running (PID: 30006, Uptime: 00:05)
🟢 Supervisor is running (PID: 29995)
```

## 📊 Log Viewing Commands

```bash
# Watch main scraper log
npm run logs:view

# Watch error log
npm run logs:errors

# Watch supervisor log
npm run logs:supervisor

# Check health
npm run health

# Check progress
cat memory/SCRAPING_PROGRESS.json | jq
```

## 🚨 Alert Conditions (Supervisor)

Supervisor will alert if:
- Scraper crashes (auto-restarts)
- Error rate > 20 errors in 10 minutes
- Disk space < 10GB
- 10 consecutive restarts in 1 hour

## 🔄 Recovery Procedures

### If Scraper Keeps Crashing:
```bash
# Check detailed errors
cat logs/detailed-errors.jsonl | jq -s '.[-10]'

# Check what's happening
tail -100 logs/archiving-error.log

# Manual restart
npm run scrape:restart

# Check screenshots (if DEBUG_SCRAPER=1)
ls logs/screenshots/
```

### If Disk Space Low:
```bash
# Check usage
du -sh data/archiving/*

# Clear old logs
find logs -name "*.log" -mtime +7 -delete
```

## 📈 Performance Stats

- **Issues Archived**: Check `memory/SCRAPING_PROGRESS.json`
- **Total Errors**: Tracked in progress file
- **Uptime**: Check `memory/health.json`
- **Storage**: Monitored automatically

---

**DEPLOYED**: 2026-02-05 10:35 PST
**VERSION**: 2.0.1 Bulletproof Edition
**STATUS**: 🟢 OPERATIONAL
