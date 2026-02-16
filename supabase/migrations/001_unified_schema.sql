-- Migration: 001_unified_schema.sql
-- Create unified data schema for Ezekiel ingestion pipeline
-- Hot tier: Supabase PostgreSQL with pgvector

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom types
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_type') THEN
        CREATE TYPE source_type AS ENUM ('newspaper', 'wikipedia', 'inec', 'government', 'user_report', 'external_api');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type') THEN
        CREATE TYPE entity_type AS ENUM ('person', 'organization', 'location', 'event', 'topic');
    END IF;
END$$;

-- Main documents table (unified source of truth)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type source_type NOT NULL,
    source_id VARCHAR(200) NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    content_summary TEXT,  -- AI-generated summary
    published_date DATE,
    scraped_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_metadata JSONB DEFAULT '{}'::jsonb,
    embedding VECTOR(384),  -- MiniLM-L6-v2 dimensions
    entities JSONB DEFAULT '{}'::jsonb,  -- {people: [], organizations: [], locations: [], events: []}
    topics JSONB DEFAULT '[]'::jsonb,  -- [{topic: "election", confidence: 0.92}]
    sentiment JSONB DEFAULT '{}'::jsonb,  -- {score: 0.7, label: "positive", emotions: []}
    related_documents UUID[] DEFAULT '{}',
    mentions TEXT[] DEFAULT '{}',  -- Array of entity slugs
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    verified BOOLEAN DEFAULT FALSE,
    processing_status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, error
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(source_type, source_id)
);

-- Document chunks for fine-grained RAG
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    position INTEGER NOT NULL,  -- Order in document
    entities JSONB DEFAULT '{}'::jsonb,  -- Entities found in this chunk
    token_count INTEGER,  -- For tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Entity registry (normalized, reusable)
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,
    type entity_type NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    aliases TEXT[],  -- Alternative names
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,  -- Flexible attributes
    wikidata_id VARCHAR(50),  -- Link to Wikidata
    image_url TEXT,
    mention_count INTEGER DEFAULT 0,
    first_mentioned DATE,
    last_mentioned DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Many-to-many: documents <-> entities
CREATE TABLE IF NOT EXISTS document_entities (
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    context TEXT,  -- Snippet where entity appears
    mention_count INTEGER DEFAULT 1,
    PRIMARY KEY (document_id, entity_id)
);

-- Topics taxonomy (hierarchical)
CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    parent_id UUID REFERENCES topics(id),
    keywords TEXT[],  -- For auto-classification
    description TEXT,
    document_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Many-to-many: documents <-> topics
CREATE TABLE IF NOT EXISTS document_topics (
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    PRIMARY KEY (document_id, topic_id)
);

-- Sync tracking for each data source
CREATE TABLE IF NOT EXISTS sync_status (
    source_type source_type PRIMARY KEY,
    last_synced_id VARCHAR(200),
    last_synced_at TIMESTAMP WITH TIME ZONE,
    total_processed INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'idle',  -- idle, running, error, paused
    config JSONB DEFAULT '{}'::jsonb,  -- Source-specific config
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ingestion queue (for tracking async jobs)
CREATE TABLE IF NOT EXISTS ingestion_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type source_type NOT NULL,
    source_id VARCHAR(200) NOT NULL,
    file_path TEXT,  -- Path to raw file
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, error
    priority INTEGER DEFAULT 5,  -- 1-10, lower = higher priority
    worker_id VARCHAR(100),  -- Which agent is processing
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Search logs (for analytics)
CREATE TABLE IF NOT EXISTS search_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    query_embedding VECTOR(384),
    filters JSONB DEFAULT '{}'::jsonb,
    results_count INTEGER,
    response_time_ms INTEGER,
    user_id UUID,  -- If authenticated
    session_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_docs_source ON documents(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_docs_date ON documents(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_docs_fts ON documents USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')));
CREATE INDEX IF NOT EXISTS idx_docs_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_entities_slug ON entities(slug);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_wikidata ON entities(wikidata_id) WHERE wikidata_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_doc_entities_entity ON document_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_doc_entities_doc ON document_entities(document_id);

CREATE INDEX IF NOT EXISTS idx_topics_parent ON topics(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_doc_topics_topic ON document_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_doc_topics_doc ON document_topics(document_id);

CREATE INDEX IF NOT EXISTS idx_queue_status ON ingestion_queue(status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_queue_source ON ingestion_queue(source_type, source_id);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_docs_updated_at ON documents;
CREATE TRIGGER update_docs_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_entities_updated_at ON entities;
CREATE TRIGGER update_entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to increment entity mention count
CREATE OR REPLACE FUNCTION increment_entity_mention()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE entities 
    SET mention_count = mention_count + NEW.mention_count,
        last_mentioned = GREATEST(last_mentioned, (SELECT published_date FROM documents WHERE id = NEW.document_id))
    WHERE id = NEW.entity_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_increment_mention ON document_entities;
CREATE TRIGGER trigger_increment_mention
    AFTER INSERT ON document_entities
    FOR EACH ROW EXECUTE FUNCTION increment_entity_mention();

-- Row Level Security (RLS) policies
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

-- Allow all reads for now (can be restricted later)
CREATE POLICY allow_all_reads ON documents FOR SELECT USING (true);
CREATE POLICY allow_all_reads ON entities FOR SELECT USING (true);
CREATE POLICY allow_all_reads ON document_chunks FOR SELECT USING (true);

-- Only service role can write
CREATE POLICY service_role_insert ON documents FOR INSERT WITH CHECK (true);
CREATE POLICY service_role_update ON documents FOR UPDATE USING (true) WITH CHECK (true);

-- Insert default topics
INSERT INTO topics (name, slug, keywords, description) VALUES
('Politics', 'politics', ARRAY['election', 'vote', 'government', 'party', 'senate', 'president', 'governor'], 'Political news and elections'),
('Economy', 'economy', ARRAY['budget', 'naira', 'dollar', 'trade', 'market', 'finance', 'bank'], 'Economic and financial news'),
('Security', 'security', ARRAY['police', 'army', 'crime', 'terrorism', 'banditry', 'violence'], 'Security and crime-related news'),
('Infrastructure', 'infrastructure', ARRAY['road', 'power', 'electricity', 'water', 'bridge', 'construction'], 'Infrastructure projects and development'),
('Health', 'health', ARRAY['hospital', 'doctor', 'disease', 'covid', 'medicine', 'healthcare'], 'Health and medical news'),
('Education', 'education', ARRAY['school', 'university', 'student', 'exam', 'academic'], 'Education-related news'),
('Sports', 'sports', ARRAY['football', 'soccer', 'match', 'team', 'player', 'super eagles'], 'Sports news'),
('Entertainment', 'entertainment', ARRAY['music', 'movie', 'nollywood', 'celebrity', 'actor'], 'Entertainment and culture'),
('International', 'international', ARRAY['foreign', 'international', 'global', 'world'], 'International relations and foreign news')
ON CONFLICT (slug) DO NOTHING;

-- Insert sync status records
INSERT INTO sync_status (source_type, status) VALUES
('newspaper', 'idle'),
('wikipedia', 'idle'),
('inec', 'idle'),
('government', 'idle')
ON CONFLICT (source_type) DO NOTHING;

-- Create view for easy querying
CREATE OR REPLACE VIEW document_search_view AS
SELECT 
    d.id,
    d.title,
    d.content_summary,
    d.published_date,
    d.source_type,
    d.source_metadata->>'newspaper' as newspaper,
    d.sentiment->>'label' as sentiment,
    d.embedding,
    array_agg(DISTINCT e.name) FILTER (WHERE e.type = 'person') as people,
    array_agg(DISTINCT e.name) FILTER (WHERE e.type = 'location') as locations,
    array_agg(DISTINCT t.name) as topics
FROM documents d
LEFT JOIN document_entities de ON d.id = de.document_id
LEFT JOIN entities e ON de.entity_id = e.id
LEFT JOIN document_topics dt ON d.id = dt.document_id
LEFT JOIN topics t ON dt.topic_id = t.id
WHERE d.processing_status = 'completed'
GROUP BY d.id;

-- Comments for documentation
COMMENT ON TABLE documents IS 'Unified source of truth for all ingested content';
COMMENT ON TABLE entities IS 'Normalized entity registry for people, organizations, locations, events';
COMMENT ON TABLE document_chunks IS 'Chunked content with embeddings for fine-grained RAG retrieval';
COMMENT ON TABLE ingestion_queue IS 'Async processing queue for Ezekiel agents';
