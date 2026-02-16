# EZEKIEL - Unified Data Ingestion Pipeline

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES (Multiple)                              │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│  Philip/Fleet   │  Judas OCR      │  Wikipedia      │  INEC/External APIs   │
│  (Newspapers)   │  (Text/Images)  │  (Knowledge)    │  (Structured Data)    │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────┬───────────┘
         │                 │                 │                    │
         ▼                 ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EZEKIEL INGESTION ORCHESTRATOR                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Parser     │  │  Chunker    │  │  Embedder   │  │  Entity Extractor   │ │
│  │  (Multi-    │  │  (Smart     │  │  (Vector    │  │  (People, Places,   │ │
│  │   format)   │  │   split)    │  │   Gen)      │  │   Orgs, Topics)     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         └─────────────────┴─────────────────┴────────────────────┘           │
│                                    │                                         │
│                         ┌──────────▼──────────┐                              │
│                         │  Unified Schema     │                              │
│                         │  (Canonical Format) │                              │
│                         └──────────┬──────────┘                              │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HOT TIER - SUPABASE (PRIMARY)                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL + pgvector                                                  │ │
│  │  • Real-time queries (<100ms)                                           │ │
│  │  • Full-text + semantic search                                          │ │ │
│  │  • 2020-2026 data (most relevant)                                       │ │
│  │  • All entity relationships                                             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │  RAG API     │  │  Analytics   │  │  Dashboard   │
         │  (/ask)      │  │  Engine      │  │  (Visual)    │
         └──────────────┘  └──────────────┘  └──────────────┘
```

## Unified Data Schema

```typescript
// Core Entity - Everything becomes this
interface UnifiedDocument {
  // Identity
  id: string;                    // UUID v4
  source_type: 'newspaper' | 'wikipedia' | 'inec' | 'government' | 'user_report';
  source_id: string;             // Original ID from source
  
  // Content
  title: string;
  content: string;               // Full text
  content_chunks: ContentChunk[]; // For RAG retrieval
  
  // Temporal
  published_date: Date;          // When it happened
  scraped_date: Date;            // When we got it
  
  // Source Attribution
  source_metadata: {
    newspaper?: string;          // Punch, Guardian, etc.
    author?: string;
    url?: string;
    page_number?: number;
    section?: string;
  };
  
  // AI-Generated
  embedding: number[];           // Vector for semantic search
  entities: {
    people: Entity[];            // [{name: "Tinubu", role: "President", confidence: 0.95}]
    organizations: Entity[];     // [{name: "APC", type: "political_party"}]
    locations: Entity[];         // [{name: "Abuja", type: "city", state: "FCT"}]
    events: Entity[];            // [{name: "2023 Election", date: "2023-02-25"}]
  };
  topics: Topic[];               // [{topic: "election", confidence: 0.92}, ...]
  sentiment: Sentiment;          // {score: 0.7, label: "positive", emotions: ["hope"]}
  
  // Relationships (Graph)
  related_documents: string[];   // IDs of related articles
  mentions: string[];            // Politician slugs mentioned
  
  // Verification
  confidence: number;            // 0-1 data quality score
  verified: boolean;             // Human verified?
  
  // Timestamps
  created_at: Date;
  updated_at: Date;
}

interface ContentChunk {
  id: string;
  content: string;
  embedding: number[];
  position: number;              // Order in document
  entities: Entity[];            // Entities in this chunk
}
```

## Async Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EZEKIEL AGENT FLEET                         │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│  Parser      │  Chunker     │  Embedder    │  Entity          │
│  Agents      │  Agents      │  Agents      │  Extractor       │
│  (3 agents)  │  (2 agents)  │  (4 agents)  │  (3 agents)      │
├──────────────┼──────────────┼──────────────┼──────────────────┤
│ Parse JSON   │ Split into   │ Generate     │ Extract people,  │
│ Parse HTML   │ chunks       │ embeddings   │ places, orgs     │
│ Parse PDF    │ 512 tokens   │ OpenAI/HF    │ SpaCy/LLM        │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬─────────┘
       │              │              │                │
       └──────────────┴──────────────┴────────────────┘
                          │
                          ▼
              ┌─────────────────────┐
              │   Message Queue     │
              │   (Bull/Redis)      │
              └─────────────────────┘
```

## Implementation Priority

### Phase 1: Foundation (Days 1-3)
- [ ] Supabase schema migration
- [ ] Message queue setup (Redis)
- [ ] Base Ezekiel orchestrator

### Phase 2: Pipeline (Days 4-7)
- [ ] Parser agents (async)
- [ ] Chunker agents (async)
- [ ] Embedder agents (async)
- [ ] Entity extractor agents (async)

### Phase 3: Integration (Days 8-10)
- [ ] Judas OCR connector
- [ ] Wikipedia data migration
- [ ] Backfill existing data

### Phase 4: API (Days 11-14)
- [ ] Unified search endpoint
- [ ] GraphQL API
- [ ] Real-time sync

## Database Schema (Supabase)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Main documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(200) NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    published_date DATE,
    scraped_date TIMESTAMP DEFAULT NOW(),
    source_metadata JSONB DEFAULT '{}',
    embedding VECTOR(384),  -- MiniLM-L6-v2
    entities JSONB DEFAULT '{}',
    topics JSONB DEFAULT '[]',
    sentiment JSONB DEFAULT '{}',
    related_documents UUID[] DEFAULT '{}',
    mentions VARCHAR(100)[] DEFAULT '{}',
    confidence FLOAT DEFAULT 0.5,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(source_type, source_id)
);

-- Chunks for RAG
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    position INTEGER,
    entities JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Entity registry (normalized)
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(300) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- person, organization, location, event
    slug VARCHAR(200) UNIQUE NOT NULL,
    aliases VARCHAR(200)[],
    metadata JSONB DEFAULT '{}',
    mention_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Many-to-many: documents <> entities
CREATE TABLE document_entities (
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    confidence FLOAT,
    context TEXT,  -- Snippet where mentioned
    PRIMARY KEY (document_id, entity_id)
);

-- Topics taxonomy
CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    parent_id UUID REFERENCES topics(id),
    keywords VARCHAR(100)[],
    description TEXT
);

-- Many-to-many: documents <> topics
CREATE TABLE document_topics (
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    confidence FLOAT,
    PRIMARY KEY (document_id, topic_id)
);

-- Sync tracking (for backfills)
CREATE TABLE sync_status (
    source_type VARCHAR(50) PRIMARY KEY,
    last_synced_id VARCHAR(200),
    last_synced_at TIMESTAMP,
    total_processed INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'idle'  -- idle, running, error
);

-- Indexes for performance
CREATE INDEX idx_docs_date ON documents(published_date DESC);
CREATE INDEX idx_docs_source ON documents(source_type, source_id);
CREATE INDEX idx_docs_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_entities_slug ON entities(slug);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_doc_entities ON document_entities(entity_id);

-- Full-text search
CREATE INDEX idx_docs_fts ON documents USING gin(to_tsvector('english', content));

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_docs_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

## Agent Deployment Plan

```yaml
# ezekiel-agents.yaml
agents:
  # Parsers - Convert raw to unified format
  parser_json:
    count: 2
    queue: "parse:json"
    handler: "parsers.json_parser"
    
  parser_html:
    count: 2
    queue: "parse:html"
    handler: "parsers.html_parser"
    
  parser_wikipedia:
    count: 1
    queue: "parse:wikipedia"
    handler: "parsers.wikipedia_parser"
  
  # Chunkers - Split content intelligently
  chunker_standard:
    count: 2
    queue: "chunk:standard"
    config:
      chunk_size: 512
      overlap: 128
      
  # Embedders - Generate vectors
  embedder_openai:
    count: 3
    queue: "embed:openai"
    rate_limit: "3000/minute"
    
  embedder_local:
    count: 2
    queue: "embed:local"
    model: "sentence-transformers/all-MiniLM-L6-v2"
  
  # Entity Extractors
  entity_spacy:
    count: 2
    queue: "entity:spacy"
    handler: "extractors.spacy_ner"
    
  entity_llm:
    count: 1
    queue: "entity:llm"
    handler: "extractors.llm_extractor"
    
  # Ingestors - Write to Supabase
  ingestor_batch:
    count: 2
    queue: "ingest:batch"
    batch_size: 100
    retry_policy: "exponential_backoff"
```

## Hot Tier Recommendation

**YES - Hot tier is correct for Supabase:**

| Tier | Storage | Query Speed | Use Case |
|------|---------|-------------|----------|
| **Hot** | Supabase PostgreSQL | <100ms | 2020-2026 (active queries) |
| **Warm** | Supabase + Files | 1-2s | 2000-2019 (on-demand load) |
| **Cold** | Files only | 5-10s | 1900-1999 (batch queries) |

**Hot Tier Capacity:**
- Supabase free tier: 500MB database
- Pro tier ($25/mo): 8GB database + 100GB storage
- Team tier ($60/mo): 40GB database + 1TB storage

**Recommendation: Start with Pro tier**
- 8GB fits ~2M documents with embeddings
- Upgrade to Team when you hit 5M+ docs

## Unified Source of Truth Strategy

```
SUPABASE = Single Source of Truth

┌─────────────────────────────────────────────┐
│           SUPABASE (PostgreSQL)             │
│  ┌───────────────────────────────────────┐  │
│  │  documents table                      │  │
│  │  • All text content                   │  │
│  │  • All embeddings                     │  │
│  │  • All entities                       │  │
│  │  • All relationships                  │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐
│Search │ │Analytics│ │Export │
│  API   │ │ Engine  │ │Tools  │
└───────┘ └───────┘ └───────┘

Raw files (data/archiving/) = Backup only
Don't query files directly - always go through Supabase
```

## Success Metrics

- [ ] 10K documents ingested in first week
- [ ] <100ms query response time
- [ ] 95% entity extraction accuracy
- [ ] Zero data loss (idempotent ingestion)
- [ ] Real-time sync from Judas OCR
- [ ] GraphQL API serving frontend

## Next Action

**I need to build:**
1. Supabase migration files
2. Ezekiel orchestrator (Node.js + Bull queue)
3. Async agent workers
4. Connector to existing Judas pipeline
5. GraphQL API layer

**Ready to start?** I'll create the foundation first (schema + orchestrator), then deploy agents.