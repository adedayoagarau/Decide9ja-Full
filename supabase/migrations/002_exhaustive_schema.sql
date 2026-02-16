-- Migration: 002_exhaustive_supabase_schema.sql
-- Optimized for 1.9M+ Nigerian newspaper documents
-- Partitioning by year for performance

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text search

-- ============================================================================
-- PARTITIONED DOCUMENTS TABLE (by year for performance)
-- ============================================================================

-- Main partitioned table
CREATE TABLE documents (
    id UUID DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,  -- newspaper, wikipedia, inec
    source_id VARCHAR(200) NOT NULL,   -- unique per source
    newspaper VARCHAR(100),            -- PM News, Guardian, etc.
    
    -- Content
    title TEXT,
    content TEXT NOT NULL,
    content_summary TEXT GENERATED ALWAYS AS (LEFT(content, 500)) STORED,
    word_count INTEGER GENERATED ALWAYS AS (ARRAY_LENGTH(REGEXP_SPLIT_TO_ARRAY(content, '\s+'), 1)) STORED,
    
    -- Temporal (partition key)
    published_date DATE NOT NULL,
    published_year INTEGER GENERATED ALWAYS AS (EXTRACT(YEAR FROM published_date)) STORED,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Source metadata
    page_number INTEGER,
    section VARCHAR(100),
    original_url TEXT,
    
    -- AI-Generated fields
    embedding VECTOR(384),  -- MiniLM for semantic search
    
    -- Processing status
    processing_status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, error
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    verified BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (id, published_year)  -- Include partition key
) PARTITION BY RANGE (published_year);

-- Create partitions by decade (1900-2030)
CREATE TABLE documents_1900s PARTITION OF documents
    FOR VALUES FROM (1900) TO (1910);
CREATE TABLE documents_1910s PARTITION OF documents
    FOR VALUES FROM (1910) TO (1920);
CREATE TABLE documents_1920s PARTITION OF documents
    FOR VALUES FROM (1920) TO (1930);
CREATE TABLE documents_1930s PARTITION OF documents
    FOR VALUES FROM (1930) TO (1940);
CREATE TABLE documents_1940s PARTITION OF documents
    FOR VALUES FROM (1940) TO (1950);
CREATE TABLE documents_1950s PARTITION OF documents
    FOR VALUES FROM (1950) TO (1960);
CREATE TABLE documents_1960s PARTITION OF documents
    FOR VALUES FROM (1960) TO (1970);
CREATE TABLE documents_1970s PARTITION OF documents
    FOR VALUES FROM (1970) TO (1980);
CREATE TABLE documents_1980s PARTITION OF documents
    FOR VALUES FROM (1980) TO (1990);
CREATE TABLE documents_1990s PARTITION OF documents
    FOR VALUES FROM (1990) TO (2000);
CREATE TABLE documents_2000s PARTITION OF documents
    FOR VALUES FROM (2000) TO (2010);
CREATE TABLE documents_2010s PARTITION OF documents
    FOR VALUES FROM (2010) TO (2020);
CREATE TABLE documents_2020s PARTITION OF documents
    FOR VALUES FROM (2020) TO (2030);

-- Indexes on partitioned table
CREATE INDEX idx_docs_newspaper ON documents(newspaper);
CREATE INDEX idx_docs_date ON documents(published_date DESC);
CREATE INDEX idx_docs_status ON documents(processing_status);
CREATE INDEX idx_docs_source ON documents(source_type, source_id);

-- Full-text search (per partition for performance)
CREATE INDEX idx_docs_fts ON documents USING gin(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(content, '')));

-- Trigram index for fuzzy search
CREATE INDEX idx_docs_trgm ON documents USING gin(title gin_trgm_ops);

-- Vector index for semantic search
CREATE INDEX idx_docs_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- DOCUMENT CHUNKS (for fine-grained RAG)
-- ============================================================================

CREATE TABLE document_chunks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    document_id UUID NOT NULL,
    document_year INTEGER NOT NULL,  -- Partition key reference
    content TEXT NOT NULL,
    embedding VECTOR(384),
    chunk_position INTEGER NOT NULL,  -- Order in document
    token_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    FOREIGN KEY (document_id, document_year) REFERENCES documents(id, published_year)
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);

-- ============================================================================
-- ENTITIES (Normalized People, Orgs, Locations)
-- ============================================================================

CREATE TABLE entities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(300) NOT NULL,
    normalized_name VARCHAR(300) NOT NULL,  -- Lowercase, no titles
    type VARCHAR(50) NOT NULL CHECK (type IN ('person', 'organization', 'location', 'event', 'topic')),
    slug VARCHAR(200) UNIQUE NOT NULL,
    
    -- Aliases and variations
    aliases TEXT[],  -- ["Bola Tinubu", "BAT", "Asiwaju"]
    
    -- External IDs
    wikidata_id VARCHAR(50),
    google_kg_id VARCHAR(100),
    
    -- Metadata
    description TEXT,
    image_url TEXT,
    birth_date DATE,
    death_date DATE,
    
    -- Statistics
    mention_count INTEGER DEFAULT 0,
    first_mentioned_date DATE,
    last_mentioned_date DATE,
    
    -- Verification
    verified BOOLEAN DEFAULT FALSE,
    verified_by UUID REFERENCES auth.users(id),
    verified_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_entities_slug ON entities(slug);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_name ON entities USING gin(name gin_trgm_ops);
CREATE INDEX idx_entities_wikidata ON entities(wikidata_id) WHERE wikidata_id IS NOT NULL;

-- Entity relationships (graph structure)
CREATE TABLE entity_relationships (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    from_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    to_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL,  -- "colleague", "opponent", "member_of"
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    source_document_id UUID,
    evidence_text TEXT,
    first_seen_date DATE,
    last_seen_date DATE,
    mention_count INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(from_entity_id, to_entity_id, relationship_type)
);

CREATE INDEX idx_rel_from ON entity_relationships(from_entity_id);
CREATE INDEX idx_rel_to ON entity_relationships(to_entity_id);
CREATE INDEX idx_rel_type ON entity_relationships(relationship_type);

-- ============================================================================
-- DOCUMENT-ENTITY MENTIONS (Many-to-many with context)
-- ============================================================================

CREATE TABLE document_entities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    document_id UUID NOT NULL,
    document_year INTEGER NOT NULL,
    entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    
    -- Mention details
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    context_snippet TEXT,  -- Text surrounding the mention
    context_position INTEGER,  -- Character position in document
    mention_count_in_doc INTEGER DEFAULT 1,
    
    -- Sentiment toward this entity in this document
    sentiment_label VARCHAR(20),  -- positive, negative, neutral
    sentiment_score FLOAT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    FOREIGN KEY (document_id, document_year) REFERENCES documents(id, published_year),
    UNIQUE(document_id, entity_id)
);

CREATE INDEX idx_de_doc ON document_entities(document_id);
CREATE INDEX idx_de_entity ON document_entities(entity_id);
CREATE INDEX idx_de_sentiment ON document_entities(sentiment_label);

-- ============================================================================
-- TOPICS (Hierarchical Taxonomy)
-- ============================================================================

CREATE TABLE topics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    parent_id UUID REFERENCES topics(id),  -- Hierarchical
    
    -- Classification
    keywords TEXT[],  -- For auto-tagging
    description TEXT,
    
    -- Statistics
    document_count INTEGER DEFAULT 0,
    total_mentions INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_topics_parent ON topics(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX idx_topics_slug ON topics(slug);

-- Document-topic assignments
CREATE TABLE document_topics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    document_id UUID NOT NULL,
    document_year INTEGER NOT NULL,
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    
    FOREIGN KEY (document_id, document_year) REFERENCES documents(id, published_year),
    UNIQUE(document_id, topic_id)
);

CREATE INDEX idx_dt_topic ON document_topics(topic_id);

-- ============================================================================
-- SENTIMENT ANALYSIS (Time-series tracking)
-- ============================================================================

CREATE TABLE sentiment_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    
    -- Sentiment metrics
    positive_mentions INTEGER DEFAULT 0,
    negative_mentions INTEGER DEFAULT 0,
    neutral_mentions INTEGER DEFAULT 0,
    
    -- Calculated score (-1 to +1)
    sentiment_score FLOAT GENERATED ALWAYS AS (
        (positive_mentions - negative_mentions)::FLOAT / 
        NULLIF(positive_mentions + negative_mentions + neutral_mentions, 0)
    ) STORED,
    
    -- Sources
    document_ids UUID[],
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(entity_id, date)
);

CREATE INDEX idx_sentiment_entity ON sentiment_snapshots(entity_id);
CREATE INDEX idx_sentiment_date ON sentiment_snapshots(date DESC);

-- ============================================================================
-- EVENTS (Detected from documents)
-- ============================================================================

CREATE TABLE events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,  -- election, protest, scandal, etc.
    
    title VARCHAR(500) NOT NULL,
    description TEXT,
    
    -- Temporal
    start_date DATE,
    end_date DATE,
    
    -- Location
    location_text VARCHAR(200),
    state VARCHAR(50),
    lga VARCHAR(100),
    
    -- Entities involved
    primary_entity_id UUID REFERENCES entities(id),
    related_entity_ids UUID[],
    
    -- Sources
    source_document_ids UUID[],
    
    -- Verification
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    verified BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_date ON events(start_date DESC);
CREATE INDEX idx_events_entity ON events(primary_entity_id);

-- ============================================================================
-- SEARCH QUERIES (Analytics)
-- ============================================================================

CREATE TABLE search_queries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_normalized TEXT GENERATED ALWAYS AS (LOWER(REGEXP_REPLACE(query_text, '\s+', ' ', 'g'))) STORED,
    
    -- Filters used
    filters JSONB DEFAULT '{}',
    
    -- Results
    results_count INTEGER,
    response_time_ms INTEGER,
    
    -- User context
    user_id UUID,
    session_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_search_queries_text ON search_queries(query_normalized);
CREATE INDEX idx_search_queries_date ON search_queries(created_at DESC);

-- Search query results cache (for performance)
CREATE TABLE search_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query_hash VARCHAR(64) UNIQUE NOT NULL,  -- MD5 of query + filters
    query_text TEXT NOT NULL,
    filters JSONB DEFAULT '{}',
    
    results JSONB NOT NULL,
    results_count INTEGER,
    
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_cache_hash ON search_cache(query_hash);
CREATE INDEX idx_cache_expires ON search_cache(expires_at);

-- ============================================================================
-- SYNC TRACKING (for ETL pipeline)
-- ============================================================================

CREATE TABLE sync_status (
    source_type VARCHAR(50) PRIMARY KEY,
    last_synced_id VARCHAR(200),
    last_synced_at TIMESTAMP WITH TIME ZONE,
    
    -- Statistics
    total_documents INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    total_entities INTEGER DEFAULT 0,
    
    -- Status
    status VARCHAR(20) DEFAULT 'idle',  -- idle, running, error, paused
    error_message TEXT,
    
    -- Configuration
    config JSONB DEFAULT '{}',
    
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Increment entity mention count
CREATE OR REPLACE FUNCTION increment_entity_mention()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE entities 
    SET mention_count = mention_count + 1,
        last_mentioned_date = GREATEST(last_mentioned_date, CURRENT_DATE)
    WHERE id = NEW.entity_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_increment_mention
    AFTER INSERT ON document_entities
    FOR EACH ROW EXECUTE FUNCTION increment_entity_mention();

-- Update topic document count
CREATE OR REPLACE FUNCTION update_topic_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE topics SET document_count = document_count + 1 WHERE id = NEW.topic_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE topics SET document_count = document_count - 1 WHERE id = OLD.topic_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_topic_count
    AFTER INSERT OR DELETE ON document_topics
    FOR EACH ROW EXECUTE FUNCTION update_topic_count();

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Document search view (denormalized for fast queries)
CREATE VIEW document_search_view AS
SELECT 
    d.id,
    d.title,
    d.content_summary,
    d.published_date,
    d.published_year,
    d.newspaper,
    d.source_type,
    d.confidence_score,
    d.embedding,
    -- Aggregated entities
    (SELECT json_agg(json_build_object('name', e.name, 'type', e.type))
     FROM document_entities de
     JOIN entities e ON de.entity_id = e.id
     WHERE de.document_id = d.id
    ) AS entities,
    -- Aggregated topics
    (SELECT json_agg(t.name)
     FROM document_topics dt
     JOIN topics t ON dt.topic_id = t.id
     WHERE dt.document_id = d.id
    ) AS topics
FROM documents d
WHERE d.processing_status = 'completed';

-- Entity timeline view
CREATE VIEW entity_timeline_view AS
SELECT 
    e.id AS entity_id,
    e.name AS entity_name,
    e.type AS entity_type,
    d.published_date,
    d.title AS document_title,
    de.sentiment_label,
    de.sentiment_score,
    de.context_snippet
FROM entities e
JOIN document_entities de ON e.id = de.entity_id
JOIN documents d ON de.document_id = d.id AND de.document_year = d.published_year
ORDER BY e.id, d.published_date DESC;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

-- Allow read access to all authenticated users
CREATE POLICY allow_read_documents ON documents FOR SELECT USING (true);
CREATE POLICY allow_read_entities ON entities FOR SELECT USING (true);
CREATE POLICY allow_read_chunks ON document_chunks FOR SELECT USING (true);

-- Only service role can write
CREATE POLICY service_role_write_documents ON documents 
    FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- INITIAL DATA SEED
-- ============================================================================

INSERT INTO topics (id, name, slug, keywords, description) VALUES
    ('politics', 'Politics', 'politics', 
     ARRAY['election', 'vote', 'government', 'party', 'senate', 'president', 'governor', 'campaign', 'ballot'],
     'Political news, elections, governance'),
    ('economy', 'Economy', 'economy',
     ARRAY['budget', 'naira', 'dollar', 'finance', 'market', 'trade', 'business', 'economy', 'revenue'],
     'Economic and financial news'),
    ('security', 'Security', 'security',
     ARRAY['security', 'police', 'crime', 'terrorism', 'violence', 'banditry', 'army', 'military'],
     'Security, crime, military operations'),
    ('infrastructure', 'Infrastructure', 'infrastructure',
     ARRAY['road', 'power', 'electricity', 'water', 'bridge', 'construction', 'project'],
     'Infrastructure and development projects'),
    ('health', 'Health', 'health',
     ARRAY['health', 'hospital', 'doctor', 'disease', 'covid', 'medicine', 'healthcare'],
     'Health and medical news'),
    ('education', 'Education', 'education',
     ARRAY['education', 'school', 'university', 'student', 'exam', 'academic'],
     'Education-related news'),
    ('sports', 'Sports', 'sports',
     ARRAY['football', 'match', 'team', 'player', 'soccer', 'super eagles', 'premier league'],
     'Sports news'),
    ('entertainment', 'Entertainment', 'entertainment',
     ARRAY['music', 'movie', 'nollywood', 'celebrity', 'actor', 'film', 'entertainment'],
     'Entertainment and culture'),
    ('international', 'International', 'international',
     ARRAY['foreign', 'international', 'global', 'world', 'diplomacy', 'foreign affairs'],
     'International relations'),
    ('corruption', 'Corruption', 'corruption',
     ARRAY['corruption', 'fraud', 'embezzlement', 'scandal', 'probe', 'investigation', 'EFCC', 'ICPC'],
     'Corruption and fraud cases')
ON CONFLICT (id) DO NOTHING;

INSERT INTO sync_status (source_type, status) VALUES
    ('newspaper', 'idle'),
    ('wikipedia', 'idle'),
    ('inec', 'idle'),
    ('government', 'idle')
ON CONFLICT (source_type) DO NOTHING;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE documents IS 'Main partitioned table for all ingested documents by year';
COMMENT ON TABLE entities IS 'Normalized entity registry with aliases and external IDs';
COMMENT ON TABLE entity_relationships IS 'Graph relationships between entities';
COMMENT ON TABLE sentiment_snapshots IS 'Time-series sentiment tracking per entity';
COMMENT ON TABLE search_cache IS 'Query result cache for performance';
