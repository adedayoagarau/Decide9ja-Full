-- Supabase schema for Decide9ja Optimized Sync (Pro Tier)
-- Run this in Supabase SQL Editor

-- Main documents table (compressed for 8GB limit)
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source_type TEXT,
    newspaper TEXT,
    published_date DATE,
    title TEXT,
    content_summary TEXT,
    word_count INTEGER,
    entities JSONB,
    topics JSONB,
    sentiment JSONB,
    confidence_score REAL,
    has_full_content BOOLEAN DEFAULT true,
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(published_date);
CREATE INDEX IF NOT EXISTS idx_documents_newspaper ON documents(newspaper);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_type);

-- Full-text search index
ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector;
CREATE INDEX IF NOT EXISTS idx_documents_search ON documents USING GIN(search_vector);

-- Update search vector trigger
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content_summary, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS documents_search_update ON documents;
CREATE TRIGGER documents_search_update
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- Entities table (aggregated mentions)
CREATE TABLE IF NOT EXISTS entities (
    slug TEXT PRIMARY KEY,
    name TEXT,
    normalized_name TEXT,
    type TEXT,
    mention_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_count ON entities(mention_count DESC);

-- Enable Row Level Security (RLS) - allow anonymous read
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;

-- Allow read access to all
CREATE POLICY "Allow read access" ON documents FOR SELECT USING (true);
CREATE POLICY "Allow read access" ON entities FOR SELECT USING (true);

-- Allow insert/update from service role (sync script)
CREATE POLICY "Allow service writes" ON documents 
    FOR ALL 
    USING (current_user = 'supabase_admin' OR current_user LIKE 'service_role%')
    WITH CHECK (current_user = 'supabase_admin' OR current_user LIKE 'service_role%');

CREATE POLICY "Allow service writes" ON entities 
    FOR ALL 
    USING (current_user = 'supabase_admin' OR current_user LIKE 'service_role%')
    WITH CHECK (current_user = 'supabase_admin' OR current_user LIKE 'service_role%');
