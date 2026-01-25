# Railway Workers

Background workers for long-running tasks on Railway.

## Archiving Worker

Scrapes historical Nigerian newspapers from archivi.ng (1960-2010).

### Deploy to Railway

1. **Create a new service** in your Railway project:
   ```bash
   railway link  # Link to your project
   railway add --service archiving-worker
   ```

2. **Set environment variables** in Railway dashboard or CLI:
   ```bash
   railway variables set DATABASE_URL="your-postgres-url"
   railway variables set ANTHROPIC_API_KEY="your-key"  # Optional, for OCR

   # Optional configuration
   railway variables set ARCHIVING_SOURCE="pm-news"
   railway variables set ARCHIVING_START_YEAR="1960"
   railway variables set ARCHIVING_END_YEAR="2010"
   railway variables set ARCHIVING_LIMIT_PER_YEAR="100"
   railway variables set ARCHIVING_USE_OCR="false"
   railway variables set ARCHIVING_SLEEP_SECONDS="5"
   ```

3. **Set the start command** in Railway:
   ```
   python workers/archiving_worker.py
   ```

4. **Deploy**:
   ```bash
   railway up
   ```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | required | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | optional | For Claude Vision OCR |
| `ARCHIVING_SOURCE` | `pm-news` | Source to scrape |
| `ARCHIVING_START_YEAR` | `1960` | First year to scrape |
| `ARCHIVING_END_YEAR` | `2010` | Last year to scrape |
| `ARCHIVING_LIMIT_PER_YEAR` | `100` | Max pages per year |
| `ARCHIVING_USE_OCR` | `false` | Enable Claude Vision OCR |
| `ARCHIVING_SLEEP_SECONDS` | `5` | Pause between years |

### Features

- **Auto-resume**: Tracks progress using the database (checks for existing articles).
- **Continuous**: Runs until all years are complete.
- **No timeout**: Railway has no execution time limits.
- **Logs**: All progress logged to Railway's log viewer.

### Monitoring

View logs in Railway dashboard or:
```bash
railway logs -f
```

### Cost Estimate

Railway charges ~$0.000463/minute for compute. For the full 1960-2010 scrape:
- Without OCR: ~8-12 hours = $0.22-$0.33
- With OCR: ~24-48 hours = $0.67-$1.34

### Splitting Into Chunks

If you want to run multiple workers in parallel:

```bash
# Worker 1: 1960-1980
railway variables set ARCHIVING_START_YEAR="1960"
railway variables set ARCHIVING_END_YEAR="1980"

# Worker 2: 1981-2000 (in separate service)
railway variables set ARCHIVING_START_YEAR="1981"
railway variables set ARCHIVING_END_YEAR="2000"

# Worker 3: 2001-2010 (in separate service)
railway variables set ARCHIVING_START_YEAR="2001"
railway variables set ARCHIVING_END_YEAR="2010"
```
