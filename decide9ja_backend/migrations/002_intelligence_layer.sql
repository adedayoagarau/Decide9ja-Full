-- Intelligence Layer Database Migrations
-- Run this migration to enable fuzzy search and RAG capabilities

-- =============================================
-- PART 1: Enable Required Extensions
-- =============================================

-- Enable trigram extension for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable vector extension for embeddings (pgvector)
-- Note: This requires pgvector to be installed on the database
-- Railway PostgreSQL includes this by default
CREATE EXTENSION IF NOT EXISTS vector;


-- =============================================
-- PART 2: Documents Table for RAG
-- =============================================

-- Create documents table for storing embeddings
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    source TEXT UNIQUE NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Vector similarity index for fast semantic search
CREATE INDEX IF NOT EXISTS idx_documents_embedding 
ON documents 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Metadata indexes for filtering
CREATE INDEX IF NOT EXISTS idx_documents_metadata_type 
ON documents ((metadata->>'type'));

CREATE INDEX IF NOT EXISTS idx_documents_metadata_politician 
ON documents ((metadata->>'politician_id'));

-- Source index for upserts
CREATE INDEX IF NOT EXISTS idx_documents_source
ON documents (source);


-- =============================================
-- PART 3: Politician Table Enhancements
-- =============================================

-- Add bio column if missing
ALTER TABLE politicians 
ADD COLUMN IF NOT EXISTS bio TEXT;

-- Add constituency column if missing
ALTER TABLE politicians 
ADD COLUMN IF NOT EXISTS constituency TEXT;

-- Create trigram index on politician names for fuzzy search
CREATE INDEX IF NOT EXISTS idx_politicians_name_trgm 
ON politicians 
USING gin(name gin_trgm_ops);

-- Create trigram index on state for fuzzy matching
CREATE INDEX IF NOT EXISTS idx_politicians_state_trgm 
ON politicians 
USING gin(state gin_trgm_ops);

-- Create full text search vector column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'politicians' 
        AND column_name = 'search_vector'
    ) THEN
        ALTER TABLE politicians
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(position, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(state, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(bio, '')), 'D')
        ) STORED;
    END IF;
END $$;

-- Create GIN index on search vector
CREATE INDEX IF NOT EXISTS idx_politicians_search 
ON politicians 
USING gin(search_vector);


-- =============================================
-- PART 4: Representatives Mapping Table
-- =============================================

-- Create representatives table to map politicians to constituencies
CREATE TABLE IF NOT EXISTS representatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    politician_id INTEGER REFERENCES politicians(id),
    state VARCHAR(100) NOT NULL,
    lga VARCHAR(200),
    position VARCHAR(100) NOT NULL,  -- Governor, Senator, House Rep
    district VARCHAR(200),           -- Senatorial district, Federal constituency
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_representatives_state_lga 
ON representatives (state, lga);

CREATE INDEX IF NOT EXISTS idx_representatives_politician 
ON representatives (politician_id);


-- =============================================
-- PART 5: News Cache Table
-- =============================================

-- Create news cache table for storing fetched news
CREATE TABLE IF NOT EXISTS news_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT,
    url TEXT UNIQUE NOT NULL,
    source VARCHAR(100),
    published_at TIMESTAMP,
    topics JSONB DEFAULT '[]',
    politician_ids JSONB DEFAULT '[]',
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for topic filtering
CREATE INDEX IF NOT EXISTS idx_news_cache_topics
ON news_cache USING gin(topics);

-- Index for recent news
CREATE INDEX IF NOT EXISTS idx_news_cache_published
ON news_cache (published_at DESC);


-- =============================================
-- PART 6: Helper Functions
-- =============================================

-- Function to calculate similarity between two strings
CREATE OR REPLACE FUNCTION fuzzy_similarity(text1 TEXT, text2 TEXT)
RETURNS FLOAT AS $$
BEGIN
    RETURN similarity(LOWER(text1), LOWER(text2));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to find politician by fuzzy name match
CREATE OR REPLACE FUNCTION find_politician_fuzzy(search_name TEXT, min_similarity FLOAT DEFAULT 0.3)
RETURNS TABLE (
    id INTEGER,
    name TEXT,
    party TEXT,
    position TEXT,
    state TEXT,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.name,
        p.party,
        p.position,
        p.state,
        similarity(LOWER(p.name), LOWER(search_name)) as similarity_score
    FROM politicians p
    WHERE similarity(LOWER(p.name), LOWER(search_name)) > min_similarity
    ORDER BY similarity_score DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;


-- =============================================
-- MIGRATION COMPLETE
-- =============================================
