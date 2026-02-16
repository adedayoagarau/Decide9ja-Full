# Decide9ja Hybrid RAG Architecture

**Local (SQLite) + Cloud (Supabase) = Unlimited Storage + Always Online**

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HYBRID RAG ARCHITECTURE                              │
├─────────────────────────────────────┬───────────────────────────────────────┤
│           LOCAL (Mac Mini)          │           CLOUD (Supabase)            │
│           2TB External Drive        │           Hot Tier ($25/mo)           │
├─────────────────────────────────────┼───────────────────────────────────────┤
│                                     │                                       │
│  ┌─────────────────────────────┐    │    ┌─────────────────────────────┐   │
│  │  SQLite Database            │    │    │  PostgreSQL + pgvector      │   │
│  │  • All 1.9M+ documents      │    │    │  • Recent 2 years only      │   │
│  │  • Full-text search (FTS5)  │    │    │  • Embeddings for semantic  │   │
│  │  • 2TB storage capacity     │    │    │  • Public API endpoint      │   │
│  │  • Zero cost                │    │    │  • Always online            │   │
│  └─────────────┬───────────────┘    │    └─────────────┬───────────────┘   │
│                │                    │                  │                   │
│  ┌─────────────▼───────────────┐    │    ┌─────────────▼───────────────┐   │
│  │  Express API Server         │◄───┼────┤  Sync Service (async)       │   │
│  │  • Local access: localhost  │    │    │  • Pushes recent data       │   │
│  │  • Can expose via ngrok     │    │    │  • Keeps both in sync       │   │
│  │  • Fast <10ms queries       │    │    │  • Configurable window      │   │
│  └─────────────┬───────────────┘    │    └─────────────────────────────┘   │
│                │                    │                                       │
│  ┌─────────────▼───────────────┐    │                                       │
│  │  Data Pipeline              │    │                                       │
│  │  • Philip/Fleet scrape      │    │                                       │
│  │  • Judas OCR                │    │                                       │
│  │  • Ezekiel ingest → SQLite  │    │                                       │
│  └─────────────────────────────┘    │                                       │
│                                     │                                       │
└─────────────────────────────────────┴───────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   User Access   │
                    │                 │
                    │  Option A: Local│
                    │  http://localhost:3000
                    │  (Mac must be on)      │
                    │                 │
                    │  Option B: Cloud│
                    │  https://your-app.supabase.co
                    │  (Always online)       │
                    │                 │
                    │  Option C: Ngrok│
                    │  https://abc123.ngrok.io
                    │  (Temporary public)    │
                    └─────────────────┘
```

## Cost Breakdown

| Component | Cost | Storage | Always Online |
|-----------|------|---------|---------------|
| **Local SQLite** | FREE | 2TB | ❌ (Mac must be on) |
| **Supabase Pro** | $25/mo | 8GB | ✅ |
| **Ngrok (free)** | FREE | - | ⚠️ (URL changes) |
| **Ngrok (paid)** | $5/mo | - | ✅ (Static domain) |
| **VPS (alternative)** | $10/mo | 100GB | ✅ |

**Recommended:** Local + Supabase = $25/mo for always-online recent data

## Quick Start

### 1. Setup
```bash
cd "/Volumes/Crucial X10/Decide9ja"
./scripts/setup-hybrid.sh
```

### 2. Ingest Existing Data
```bash
# Process all OCR output into SQLite
npm run rag:ingest

# Check stats
npm run rag:stats
```

### 3. Start API Server
```bash
# Terminal 1: Start API
npm run rag:api

# Server runs on http://localhost:3000
```

### 4. Expose to Internet (Optional)
```bash
# Terminal 2: Create tunnel (free, temporary URL)
npm run tunnel

# Or use paid ngrok for static domain
ngrok http 3000 --domain=your-domain.ngrok.io
```

### 5. Sync Recent Data to Supabase (Optional)
```bash
# Push last 2 years to Supabase for always-online access
npm run rag:sync

# Check sync status
npm run rag:sync:status
```

## API Endpoints

### Local SQLite API (Fast, Unlimited)
```bash
# Search
GET http://localhost:3000/api/search?q=Nigerian+election&limit=10

# Get document
GET http://localhost:3000/api/documents/judas_pmnews_2021-10-23

# Get by date range
GET http://localhost:3000/api/documents?from=2021-01-01&to=2021-12-31

# Get by newspaper
GET http://localhost:3000/api/documents?newspaper=pmnews&limit=50

# Stats
GET http://localhost:3000/api/stats

# Advanced query
POST http://localhost:3000/api/query
Content-Type: application/json

{
  "entities": ["Tinubu", "Buhari"],
  "topics": ["election"],
  "dateRange": {
    "from": "2021-01-01",
    "to": "2023-12-31"
  },
  "sentiment": "negative"
}
```

### Supabase API (Always Online, Limited Storage)
```bash
# If you sync to Supabase, use their REST API:
GET https://liosugqvfvubmqaqzrro.supabase.co/rest/v1/documents?select=*&title=ilike.*election*
```

## Data Flow

```
1. SCRAPING (Philip/Fleet)
   archivi.ng → data/archiving/ (images + metadata)

2. OCR (Judas)
   images → data/processed/ (extracted text)

3. UNIFICATION (Ezekiel Lite)
   processed → data/unified/ (structured JSON)

4. INDEXING (SQLite RAG)
   unified → data/catalog.db (searchable database)

5. SYNC (to Supabase - optional)
   recent 2 years → Supabase PostgreSQL (always online)

6. SERVE (API)
   SQLite → Express API → Client
```

## Configuration

### Environment Variables (.env)
```bash
# Local
NODE_ENV=development
PORT=3000

# Supabase (for sync)
SUPABASE_URL=https://liosugqvfvubmqaqzrro.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# Redis (for job queue)
REDIS_URL=redis://localhost:6379

# OpenAI (optional)
OPENAI_API_KEY=your-key
```

### Hot Tier Configuration
Edit `src/ezekiel/sync.js`:
```javascript
const CONFIG = {
  hotTierYears: 2,  // Change to 1 or 3 as needed
  batchSize: 100
};
```

## Scripts Reference

```bash
# Data Processing
npm run rag:ingest           # Ingest unified files to SQLite
npm run rag:search "query"   # Search local database
npm run rag:stats            # Show database statistics
npm run rag:date 2021-01-01 2021-12-31  # Get by date range

# API Server
npm run rag:api              # Start API server
npm run rag:api:dev          # Start with nodemon (dev)

# Cloud Sync
npm run rag:sync             # Sync recent data to Supabase
npm run rag:sync:status      # Check sync status

# Tunnel (expose local to internet)
npm run tunnel               # Free ngrok tunnel

# Original scrapers
npm run scrape               # Philip scraper
npm run judas:highmem        # Judas OCR (16GB RAM)
```

## Storage Capacity Planning

| Documents | SQLite Size | Query Speed |
|-----------|-------------|-------------|
| 1,000     | ~10 MB      | <10ms       |
| 10,000    | ~100 MB     | <50ms       |
| 100,000   | ~1 GB       | <100ms      |
| 1,000,000 | ~10 GB      | <500ms      |
| 1,900,000 | ~19 GB      | <1s         |

**Your 2TB drive can handle:**
- ~200 million documents (with SQLite)
- Or ~100 million with full content + embeddings

## Troubleshooting

### Mac must stay on for local access
**Solution:** Use Supabase sync for critical recent data, or deploy to VPS

### Ngrok URL changes on restart
**Solution:** Buy ngrok paid plan ($5/mo) for static domain, or use Supabase

### SQLite database locked
**Solution:** Only one process can write at a time. Ezekiel handles this with queue.

### Out of memory during OCR
**Solution:** Judas already configured with 16GB limit and batch processing

## Scaling Options

### Phase 1: Local Only (Current)
- ✅ Free
- ✅ Unlimited storage
- ❌ Mac must stay on

### Phase 2: Hybrid (Recommended)
- Local: All 1.9M+ documents
- Supabase: Recent 2 years ($25/mo)
- ✅ Recent data always online
- ✅ Full archive locally searchable

### Phase 3: Full Cloud
- VPS: $10-50/mo for 100GB-500GB
- Or Supabase Team: $60/mo for 40GB
- ✅ Everything always online
- ❌ Expensive at scale

## Next Steps

1. ✅ Ingest all current OCR data: `npm run rag:ingest`
2. ✅ Start API server: `npm run rag:api`
3. ✅ Test search: `npm run rag:search "Boko Haram"`
4. 🔄 Sync to Supabase: `npm run rag:sync`
5. 🔄 Expose via ngrok: `npm run tunnel`
6. 🚀 Build frontend or integrate with Decide9ja backend

## Support

All data is in `/Volumes/Crucial X10/Decide9ja/data/`:
- `archiving/` - Raw scraped images
- `processed/` - OCR output
- `unified/` - Structured JSON
- `catalog.db` - Searchable SQLite database

Logs in `/Volumes/Crucial X10/Decide9ja/logs/`:
- `ezekiel-lite.log` - Ingestion logs
- `sqlite-rag.log` - Search logs
- `api.log` - API server logs
