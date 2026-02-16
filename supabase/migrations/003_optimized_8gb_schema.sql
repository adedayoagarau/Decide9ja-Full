-- Migration: 003_optimized_supabase_schema.sql
-- Optimized for $25/mo Pro tier (8GB storage)
-- Strategy: Metadata + Summaries in Supabase, Full Content in SQLite

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- OPTIMIZED DOCUMENTS TABLE (Compact)
-- Store only essential metadata + summary (not full content)
-- Full content queried from local SQLite via document_id
-- ============================================================================

CREATE TABLE documents (
    id TEXT PRIMARY KEY,  -- Use deterministic ID: "newspaper_YYYY-MM-DD"
    
    -- Minimal metadata
    source_type VARCHAR(20) NOT NULL,      -- newspaper
    newspaper VARCHAR(50) NOT NULL,         -- PM News, Guardian
    published_date DATE NOT NULL,
    published_year INTEGER GENERATED ALWAYS AS (EXTRACT(YEAR FROM published_date)) STORED,
    
    -- Searchable content (summary only ~500 chars vs full ~10KB)
    title VARCHAR(300),
    content_summary TEXT,                  -- First 500 chars only
    
    -- Extracted data (compact JSON)
    entities JSONB,                        -- {people: [], orgs: [], locations: []}
    topics JSONB,                          -- ["politics", "economy"]
    sentiment JSONB,                       -- {label: "negative", score: -0.5}
    
    -- Statistics (pre-calculated)
    word_count INTEGER,
    entity_count INTEGER GENERATED ALWAYS AS (
        COALESCE(jsonb_array_length(entities->'people'), 0) +
        COALESCE(jsonb_array_length(entities->'organizations'), 0)
    ) STORED,
    
    -- Quality signals
    confidence_score FLOAT,
    has_full_content BOOLEAN DEFAULT TRUE,  -- Reference to local SQLite
    
    -- Timestamps
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Create index-friendly newspaper slug
    newspaper_slug VARCHAR(50) GENERATED ALWAYS AS (
        LOWER(REGEXP_REPLACE(newspaper, '\s+', '_', 'g'))
    ) STORED
);

-- Indexes for fast queries
CREATE INDEX idx_docs_newspaper ON documents(newspaper);
CREATE INDEX idx_docs_date ON documents(published_date DESC);
CREATE INDEX idx_docs_year ON documents(published_year);
CREATE INDEX idx_docs_gin ON documents USING GIN(entities);
CREATE INDEX idx_docs_topics ON documents USING GIN(topics);

-- Full-text search on summary (much smaller than full content)
CREATE INDEX idx_docs_fts ON documents 
    USING gin(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(content_summary, '')));

-- Trigram for fuzzy title search
CREATE INDEX idx_docs_trgm ON documents USING gin(title gin_trgm_ops);

-- ============================================================================
-- LIGHTWEIGHT ENTITIES TABLE
-- Only most-mentioned entities (not every single mention)
-- ============================================================================

CREATE TABLE entities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    normalized_name VARCHAR(200) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('person', 'organization', 'location')),
    slug VARCHAR(200) UNIQUE NOT NULL,
    
    -- Key metrics only
    mention_count INTEGER DEFAULT 0,
    first_mentioned DATE,
    last_mentioned DATE,
    
    -- Optional external link
    wikidata_id VARCHAR(50),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_entities_slug ON entities(slug);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_mentions ON entities(mention_count DESC) WHERE mention_count > 10;

-- ============================================================================
-- DOCUMENT-ENTITY MAPPING (Lightweight)
-- Only for entities mentioned 3+ times (reduce noise)
-- ============================================================================

CREATE TABLE document_entities (
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    entity_slug TEXT REFERENCES entities(slug) ON DELETE CASCADE,
    mention_count INTEGER DEFAULT 1,
    PRIMARY KEY (document_id, entity_slug)
);

CREATE INDEX idx_de_entity ON document_entities(entity_slug);
CREATE INDEX idx_de_doc ON document_entities(document_id);

-- ============================================================================
-- TOPICS (Minimal)
-- ============================================================================

CREATE TABLE topics (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    document_count INTEGER DEFAULT 0
);

CREATE TABLE document_topics (
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    topic_id VARCHAR(50) REFERENCES topics(id) ON DELETE CASCADE,
    confidence FLOAT,
    PRIMARY KEY (document_id, topic_id)
);

CREATE INDEX idx_dt_topic ON document_topics(topic_id);

-- Insert core topics
INSERT INTO topics (id, name) VALUES
    ('politics', 'Politics'),
    ('economy', 'Economy'),
    ('security', 'Security'),
    ('infrastructure', 'Infrastructure'),
    ('health', 'Health'),
    ('education', 'Education'),
    ('sports', 'Sports'),
    ('entertainment', 'Entertainment'),
    ('corruption', 'Corruption'),
    ('election', 'Election')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- SENTIMENT SNAPSHOTS (Aggregated, not per-document)
-- Monthly aggregation to save space
-- ============================================================================

CREATE TABLE sentiment_monthly (
    entity_slug TEXT,
    year_month VARCHAR(7),  -- "2023-01"
    
    positive_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    
    avg_sentiment_score FLOAT,
    
    PRIMARY KEY (entity_slug, year_month)
);

CREATE INDEX idx_sentiment_entity ON sentiment_monthly(entity_slug);
CREATE INDEX idx_sentiment_month ON sentiment_monthly(year_month DESC);

-- ============================================================================
-- SEARCH QUERIES (Analytics only - small)
-- ============================================================================

CREATE TABLE search_queries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query_text VARCHAR(200) NOT NULL,
    filters JSONB DEFAULT '{}',
    results_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_search_queries_date ON search_queries(created_at DESC);

-- ============================================================================
-- SYNC TRACKING
-- ============================================================================

CREATE TABLE sync_status (
    source_type VARCHAR(50) PRIMARY KEY,
    last_synced_id TEXT,
    last_synced_at TIMESTAMP WITH TIME ZONE,
    total_synced INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'idle'
);

INSERT INTO sync_status (source_type, status) VALUES
    ('newspaper', 'idle')
ON CONFLICT (source_type) DO NOTHING;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Document search view (denormalized for speed)
CREATE VIEW document_search_view AS
SELECT 
    d.id,
    d.title,
    d.content_summary,
    d.published_date,
    d.newspaper,
    d.sentiment->>'label' as sentiment_label,
    d.entities,
    d.topics,
    -- Count of related entities
    (SELECT COUNT(*) FROM document_entities de WHERE de.document_id = d.id) as entity_count
FROM documents d
ORDER BY d.published_date DESC;

-- Entity timeline view
CREATE VIEW entity_timeline AS
SELECT 
    e.slug,
    e.name,
    e.type,
    e.mention_count,
    sm.year_month,
    sm.avg_sentiment_score,
    sm.positive_count,
    sm.negative_count
FROM entities e
LEFT JOIN sentiment_monthly sm ON e.slug = sm.entity_slug
WHERE e.mention_count > 5  -- Only significant entities
ORDER BY e.mention_count DESC, sm.year_month DESC;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Search function combining FTS + filters
CREATE OR REPLACE FUNCTION search_documents(
    query_text TEXT,
    p_newspaper TEXT DEFAULT NULL,
    p_from_date DATE DEFAULT NULL,
    p_to_date DATE DEFAULT NULL,
    p_limit INTEGER DEFAULT 50
)
RETURNS TABLE (
    id TEXT,
    title VARCHAR(300),
    content_summary TEXT,
    published_date DATE,
    newspaper VARCHAR(50),
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id,
        d.title,
        d.content_summary,
        d.published_date,
        d.newspaper,
        ts_rank(
            to_tsvector('english', COALESCE(d.title, '') || ' ' || COALESCE(d.content_summary, '')),
            plainto_tsquery('english', query_text)
        ) as rank
    FROM documents d
    WHERE 
        -- Full-text search
        to_tsvector('english', COALESCE(d.title, '') || ' ' || COALESCE(d.content_summary, ''))
            @@ plainto_tsquery('english', query_text)
        -- Optional filters
        AND (p_newspaper IS NULL OR d.newspaper = p_newspaper)
        AND (p_from_date IS NULL OR d.published_date >= p_from_date)
        AND (p_to_date IS NULL OR d.published_date <= p_to_date)
    ORDER BY rank DESC, d.published_date DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Get entity mentions over time
CREATE OR REPLACE FUNCTION get_entity_mentions(
    p_entity_slug TEXT,
    p_from_date DATE DEFAULT NULL,
    p_to_date DATE DEFAULT NULL
)
RETURNS TABLE (
    document_id TEXT,
    title VARCHAR(300),
    published_date DATE,
    newspaper VARCHAR(50),
    context_snippet TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id,
        d.title,
        d.published_date,
        d.newspaper,
        d.content_summary as context_snippet
    FROM documents d
    JOIN document_entities de ON d.id = de.document_id
    WHERE 
        de.entity_slug = p_entity_slug
        AND (p_from_date IS NULL OR d.published_date >= p_from_date)
        AND (p_to_date IS NULL OR d.published_date <= p_to_date)
    ORDER BY d.published_date DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;

CREATE POLICY allow_read_all ON documents FOR SELECT USING (true);
CREATE POLICY allow_read_all ON entities FOR SELECT USING (true);

CREATE POLICY service_write ON documents 
    FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE documents IS 'Optimized: Only metadata + summary. Full content in local SQLite.';
COMMENT ON TABLE entities IS 'Key entities only (mention_count > 5)';
COMMENT ON TABLE sentiment_monthly IS 'Aggregated monthly sentiment to save space';
