# Exhaustive Supabase Database Strategy

## Goal
Load **ALL 1.9M+ Nigerian newspaper documents** into Supabase with intelligent organization for querying.

## Storage Requirements

| Documents | Estimated Size | Supabase Tier | Cost |
|-----------|---------------|---------------|------|
| 3,974 (current) | 42 MB | Free (500MB) | FREE ✅ |
| 100,000 | ~1 GB | Free (500MB) | EXCEEDED ❌ |
| 500,000 | ~5 GB | Pro (8GB) | $25/mo |
| 1,900,000 | ~20 GB | Team (40GB) | $60/mo ✅ |
| 1,900,000 + embeddings | ~50 GB | Enterprise | Custom 💰 |

**Recommendation:** Start with **Team tier ($60/mo)** for full 1.9M document capacity.

---

## Database Architecture

### 1. Partitioned Documents Table

```sql
-- Partitioned by decade for performance
CREATE TABLE documents PARTITION BY RANGE (published_year);

-- Partitions:
documents_1900s  -- 1900-1910
documents_1910s  -- 1910-1920
...              -- ...
documents_2020s  -- 2020-2030
```

**Benefits:**
- Query specific decades quickly
- Archive old partitions if needed
- Parallel query execution

### 2. Entity Graph (Knowledge Base)

```
entities (people, orgs, locations)
    ↓
entity_relationships (who knows who, who opposes who)
    ↓
document_entities (mentions in articles)
```

**Example Query:**
```sql
-- Find all articles mentioning Tinubu and Atiku together
SELECT d.* FROM documents d
JOIN document_entities de1 ON d.id = de1.document_id
JOIN entities e1 ON de1.entity_id = e1.id AND e1.slug = 'bola_tinubu'
JOIN document_entities de2 ON d.id = de2.document_id
JOIN entities e2 ON de2.entity_id = e2.id AND e2.slug = 'atiku_abubakar'
WHERE d.published_date BETWEEN '2022-01-01' AND '2023-12-31';
```

### 3. Sentiment Tracking

Time-series sentiment per entity:
```sql
SELECT 
  date,
  sentiment_score,
  positive_mentions - negative_mentions as net_sentiment
FROM sentiment_snapshots
WHERE entity_id = 'tinubu_id'
ORDER BY date;
```

### 4. Full-Text + Semantic Search

| Search Type | Method | Use Case |
|-------------|--------|----------|
| **Full-text** | PostgreSQL FTS | Exact phrases, keywords |
| **Fuzzy** | pg_trgm | Misspellings, variations |
| **Semantic** | pgvector | Conceptual similarity |

---

## Implementation Plan

### Phase 1: Schema Setup (1 hour)
```bash
# Run the comprehensive migration
psql $SUPABASE_URL -f supabase/migrations/002_exhaustive_schema.sql
```

### Phase 2: Initial Load (Days 1-3)
```bash
# Start exhaustive sync
npm run supabase:sync

# This will:
# - Load 3,974 existing documents first
# - Sync in batches of 500
# - Save progress every 5,000 docs
# - Resume if interrupted
```

**Progress Tracking:**
```
[Batch 1] Processing 500 documents...
  ↳ Synced 500 docs, 45 entities

[Batch 10] Processing 500 documents...
📊 PROGRESS REPORT
  Processed: 5,000
  Synced: 5,000
  Failed: 0
  Rate: 45.2 docs/sec
  ETA: 11.7 hours
  Progress: 0.26%
```

### Phase 3: Continuous Loading (Ongoing)

As Philip/Fleet/Judas add new data:
```bash
# Auto-sync new documents (cron job every hour)
0 * * * * cd /Volumes/Crucial\ X10/Decide9ja && npm run supabase:sync
```

---

## Query Examples

### 1. Search by Entity
```javascript
// Find all articles about Tinubu
const { data } = await supabase
  .from('document_entities')
  .select(`
    documents (*),
    entities (name, type)
  `)
  .eq('entities.slug', 'bola_tinubu')
  .order('documents.published_date', { ascending: false });
```

### 2. Timeline Analysis
```javascript
// Sentiment trend for APC over time
const { data } = await supabase
  .from('sentiment_snapshots')
  .select('*')
  .eq('entity_id', 'apc_id')
  .order('date');
```

### 3. Relationship Graph
```javascript
// Who is connected to Obasanjo?
const { data } = await supabase
  .from('entity_relationships')
  .select(`
    to_entity:entities!entity_relationships_to_entity_id_fkey (*),
    relationship_type,
    confidence
  `)
  .eq('from_entity_id', 'obasanjo_id')
  .order('confidence', { ascending: false });
```

### 4. Full-Text + Filters
```javascript
// Search "corruption" in 2023, specific newspapers
const { data } = await supabase
  .from('documents')
  .select('*')
  .textSearch('content', 'corruption')
  .eq('newspaper', 'The Guardian')
  .gte('published_date', '2023-01-01')
  .lte('published_date', '2023-12-31')
  .order('published_date', { ascending: false });
```

---

## Intelligent Sorting Strategy

### 1. Primary Sort: Recency
```sql
ORDER BY published_date DESC
```
Default - users usually want latest news first.

### 2. Secondary Sort: Relevance Score
```sql
ORDER BY 
  ts_rank(search_vector, query) DESC,  -- Text relevance
  confidence_score DESC,                -- Data quality
  published_date DESC
```

### 3. Tertiary Sort: Entity Prominence
```sql
ORDER BY
  entity.mention_count DESC,  -- More mentioned = more important
  published_date DESC
```

### 4. Custom Sorts

**By Sentiment:**
```sql
-- Most negative articles first
ORDER BY sentiment->>'score' ASC
```

**By Document Length:**
```sql
-- Longest/most detailed articles
ORDER BY word_count DESC
```

**By Source Credibility:**
```sql
-- Tier 1 newspapers first
ORDER BY 
  CASE newspaper
    WHEN 'The Guardian' THEN 1
    WHEN 'Vanguard' THEN 1
    WHEN 'Punch' THEN 2
    ELSE 3
  END,
  published_date DESC
```

---

## Cost Optimization

### Option A: Full Team Tier ($60/mo)
- ✅ All 1.9M documents
- ✅ Full-text search
- ✅ Embeddings (semantic search)
- ✅ Always online

### Option B: Hybrid (Recommended)
- **Local SQLite:** All 1.9M docs (processing, heavy queries)
- **Supabase Pro ($25/mo):** Recent 2 years (400K docs) - public API
- **Sync:** Recent data auto-synced

### Option C: Enterprise (When Ready)
- Custom pricing for >40GB
- Dedicated support
- SLA guarantees

---

## Migration Steps

### 1. Upgrade Supabase
```
1. Go to https://supabase.com/dashboard
2. Select project: liosugqvfvubmqaqzrro
3. Settings → Billing
4. Upgrade to Team tier ($60/mo)
```

### 2. Run Migration
```bash
cd "/Volumes/Crucial X10/Decide9ja"

# Run comprehensive schema
psql $SUPABASE_URL -f supabase/migrations/002_exhaustive_schema.sql
```

### 3. Start Sync
```bash
# Check current status
npm run supabase:status

# Start full sync
npm run supabase:sync

# Monitor in real-time
tail -f logs/supabase-sync.log
```

### 4. Verify
```bash
# Check document count
npm run supabase:status

# Test search
curl "https://liosugqvfvubmqaqzrro.supabase.co/rest/v1/documents?select=count"
```

---

## Performance Expectations

| Metric | Expected | Notes |
|--------|----------|-------|
| **Sync Rate** | 50-100 docs/sec | With rate limiting |
| **Full Load Time** | 5-10 hours | For 1.9M documents |
| **Query Time** | <100ms | With proper indexes |
| **Search Time** | <500ms | FTS + filters |
| **Storage** | 20-50GB | Depending on embeddings |

---

## Next Steps

1. **Upgrade Supabase to Team tier** ($60/mo)
2. **Run schema migration**
3. **Start exhaustive sync**
4. **Build frontend/API on top**

**Ready to proceed?** Run:
```bash
npm run supabase:sync
```
