# BEAST MODE CRAWLER — Unstoppable Archivi.ng Scraper

**Philosophy:** Crawl forever. Never stop. Handle everything. Store everything.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    BEAST CRAWLER                        │
│                  (Never Stops Edition)                  │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   QUEUE     │  │   WORKER    │  │   STORE     │     │
│  │  (SQLite)   │→ │ (Async)     │→ │  (SQLite)   │     │
│  │             │  │             │  │             │     │
│  │ • Pending   │  │ • Retry     │  │ • Raw       │     │
│  │ • Active    │  │ • Rotate UA │  │ • Parsed    │     │
│  │ • Failed    │  │ • Circuit   │  │ • Indexed   │     │
│  │ • Completed │  │ • Resume    │  │ • Embeddings│     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│  RESILIENCE LAYERS:                                     │
│  1. Exponential backoff (up to 1 hour)                  │
│  2. User agent rotation (50+ agents)                    │
│  3. Proxy support (optional)                            │
│  4. Circuit breaker (5 min cooldown after 10 fails)     │
│  5. Checkpointing (resume from exact spot)              │
│  6. Self-healing (auto-restart on crash)                │
│  7. Resource monitoring (pause if CPU/memory high)      │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Infinite Retry Logic
```python
# No max retries. Ever.
# Backoff: 1s, 2s, 4s, 8s, 16s, 32s, 64s, 128s, 256s, 512s, 1024s, 1800s (30 min cap)
# Then retry every 30 minutes forever until success
```

### 2. State Persistence
```python
# SQLite queue tracks every URL:
- url: The target
- status: pending | active | failed | completed
- attempts: Count
- last_attempt: Timestamp
- error: Last error message
- resume_point: Byte offset for partial downloads
```

### 3. Aggressive Concurrency
```python
# 50 concurrent requests (configurable)
# Rate limit: 10 req/sec per domain (polite but fast)
# Async throughout for max throughput
```

### 4. Content Extraction
```python
# Multiple strategies:
1. Direct OCR from archivi.ng (if available)
2. Image download + local OCR (Tesseract)
3. Claude Vision API (expensive but accurate)
4. Human-in-the-loop for critical pages

# Extract:
- Full text
- Politicians mentioned
- Topics/themes
- Sentiment
- Embeddings for RAG
```

### 5. Checkpointing
```python
# Every 100 pages:
- Save state to disk
- Log progress
- Rotate logs
- Update metrics

# On restart:
- Load queue state
- Resume from last completed
- No duplicate work
```

## Configuration

```python
# config.py
BEAST_CONFIG = {
    # Crawling
    "max_concurrent": 50,
    "rate_limit_per_domain": 10,  # req/sec
    "retry_backoff_base": 2,
    "retry_max_delay": 1800,  # 30 min cap
    "retry_forever": True,
    
    # Resilience
    "circuit_breaker_threshold": 10,
    "circuit_breaker_timeout": 300,  # 5 min
    "user_agent_rotation": True,
    "proxy_rotation": False,  # Enable if needed
    
    # Storage
    "checkpoint_interval": 100,
    "db_path": "beast_crawler.db",
    "raw_storage": "./raw_pages/",
    
    # Extraction
    "ocr_engine": "tesseract",  # or "claude" or "auto"
    "extract_entities": True,
    "generate_embeddings": True,
    
    # Monitoring
    "log_level": "INFO",
    "metrics_endpoint": None,  # Prometheus if needed
    "alert_on_stall": True,  # Alert if no progress for 1 hour
}
```

## Database Schema

```sql
-- Queue table
CREATE TABLE crawl_queue (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    status TEXT CHECK(status IN ('pending', 'active', 'failed', 'completed')),
    priority INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    last_attempt TIMESTAMP,
    error TEXT,
    resume_point INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Results table
CREATE TABLE crawl_results (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    source TEXT,  -- pm-news, etc.
    date TEXT,
    page_number INTEGER,
    title TEXT,
    raw_html BLOB,
    extracted_text TEXT,
    ocr_text TEXT,
    politicians TEXT,  -- JSON array
    topics TEXT,  -- JSON array
    sentiment TEXT,
    embedding BLOB,  -- Vector
    downloaded_at TIMESTAMP,
    processed_at TIMESTAMP
);

-- Metrics table
CREATE TABLE crawl_metrics (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pages_queued INTEGER,
    pages_active INTEGER,
    pages_completed INTEGER,
    pages_failed INTEGER,
    avg_time_per_page REAL,
    errors_last_hour INTEGER
);

-- Create indexes
CREATE INDEX idx_queue_status ON crawl_queue(status);
CREATE INDEX idx_queue_priority ON crawl_queue(priority DESC);
CREATE INDEX idx_results_source ON crawl_results(source);
CREATE INDEX idx_results_date ON crawl_results(date);
```

## Usage

### Start Crawling (Background)
```bash
# Terminal 1: Start the beast
python beast_crawler.py --source pm-news --start-year 1960 --end-year 2010

# It runs forever. Literally.
# Ctrl+C to pause (resumable)
# Kill -9 to stop (resumable)
# Power outage (resumable)
```

### Monitor Progress
```bash
# Terminal 2: Watch stats
python beast_crawler.py --stats

# Output:
# Queue: 45,230 pending | 47 active | 12,847 completed | 3 failed (retrying)
# Rate: 4.2 pages/sec | ETA: 3 days, 7 hours
# Last error: Connection timeout (retry #5 in 180s)
```

### Emergency Commands
```bash
# Force retry all failed
python beast_crawler.py --retry-failed

# Reset specific range
python beast_crawler.py --reset --year 1999 --month 6

# Export data
python beast_crawler.py --export --format jsonl --output archive.jsonl

# Import queue (for seeding)
python beast_crawler.py --import-urls urls.txt
```

## Deployment Options

### Option 1: Local Machine (Dev)
```bash
# Just run it
python beast_crawler.py
```

### Option 2: VPS/Cloud (Production)
```bash
# Systemd service
sudo systemctl enable beast-crawler
sudo systemctl start beast-crawler

# Auto-restart on crash
# Logs to journald
# Metrics to cloudwatch (optional)
```

### Option 3: Docker (Containerized)
```dockerfile
FROM python:3.11-slim
COPY . /app
RUN pip install -r requirements.txt
CMD ["python", "beast_crawler.py", "--daemon"]
```

### Option 4: Railway (Your Current Setup, Fixed)
```yaml
# railway.yaml
services:
  beast-crawler:
    build: .
    restart: always  # KEY: Always restart
    env:
      - DATABASE_URL=${{Postgres.DATABASE_URL}}
      - REDIS_URL=${{Redis.REDIS_URL}}
    resources:
      memory: 2GB
      cpu: 1
    healthcheck:
      path: /health
      interval: 60
```

## Integration with Tade

```python
# After crawling, automatically:
1. Generate embeddings (OpenAI)
2. Index in QMD or vector DB
3. Update Tade's knowledge base
4. Trigger re-training (if using ML)
5. Notify admin (Slack/email)
```

## Cost Estimation

### Archivi.ng (PM News: 50,000 pages)
- **Time:** ~3-5 days at 4 pages/sec
- **Storage:** ~50GB (raw) + 5GB (processed)
- **Compute:** $20-50 (VPS for a week)
- **OCR (Tesseract):** Free
- **OCR (Claude Vision):** $500-1000 (if used)

### Current News (Daily)
- **Time:** Continuous
- **Storage:** ~1GB/month
- **Compute:** $10/month
- **API costs:** Minimal

## Why This Won't Fail Like Before

| Issue | Old Crawler | Beast Mode |
|-------|-------------|------------|
| Crash on error | ✅ Dies | 🚫 Catches, logs, retries |
| No persistence | ✅ Loses progress | 🚫 SQLite queue, resume anywhere |
| Rate limited | ✅ Gives up | 🚫 Exponential backoff, forever |
| Memory leaks | ✅ Crashes | 🚫 Monitored, auto-restart |
| Network blips | ✅ Fails | 🚫 Retries with backoff |
| No observability | ✅ Blind | 🚫 Metrics, logs, alerts |

## Deliverables

1. `beast_crawler.py` — Main crawler (1,000+ lines)
2. `models.py` — Database models
3. `extractors.py` — OCR + entity extraction
4. `resilience.py` — Retry, circuit breaker, rotation
5. `monitoring.py` — Stats, metrics, alerts
6. `config.py` — Configuration
7. `requirements.txt` — Dependencies
8. `Dockerfile` — Containerization
9. `railway.yaml` — Railway deployment
10. `README.md` — Documentation

## Next Steps

1. **Review this design** — Does it match your "doesn't care, crawls nonstop" requirement?
2. **Choose deployment** — Local, VPS, Railway, or Docker?
3. **Prioritize sources** — Archivi.ng first, or current news too?
4. **OCR strategy** — Tesseract (free) or Claude Vision (expensive but better)?

**Ready to build this beast?** 🦉🐍

