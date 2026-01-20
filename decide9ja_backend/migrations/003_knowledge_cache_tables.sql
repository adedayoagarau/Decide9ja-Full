-- Migration: 003_knowledge_cache_tables
-- Description: Create tables for the autonomous research knowledge cache
-- Date: 2026-01-20
--
-- This migration creates the storage layer for the research system:
-- - knowledge_cache: Main entity storage (politicians, parties, etc.)
-- - promises_cache: Denormalized promises for fast lookup
-- - news_cache: Recent news articles
-- - cache_misses: Tracks queries that had no cached data (for research prioritization)

-- ============================================
-- 1. KNOWLEDGE CACHE (Main Entity Storage)
-- ============================================
-- Stores structured data extracted from news sources
-- Entity types: politician, party, bill, etc.

CREATE TABLE IF NOT EXISTS knowledge_cache (
    id SERIAL PRIMARY KEY,

    -- Entity identification
    entity_type VARCHAR(50) NOT NULL,      -- 'politician', 'party', 'bill'
    entity_name VARCHAR(255) NOT NULL,     -- Searchable name

    -- Extracted data (JSONB for flexibility)
    data JSONB NOT NULL DEFAULT '{}',

    -- Source tracking
    sources TEXT[] DEFAULT '{}',           -- Array of source URLs

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint on entity
    UNIQUE(entity_type, entity_name)
);

-- Indexes for knowledge_cache
CREATE INDEX IF NOT EXISTS idx_knowledge_cache_entity
    ON knowledge_cache(entity_type, entity_name);

CREATE INDEX IF NOT EXISTS idx_knowledge_cache_updated
    ON knowledge_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_knowledge_cache_name_search
    ON knowledge_cache(entity_name varchar_pattern_ops);

-- GIN index for JSONB queries (e.g., searching by party)
CREATE INDEX IF NOT EXISTS idx_knowledge_cache_data
    ON knowledge_cache USING GIN (data);

COMMENT ON TABLE knowledge_cache IS
    'Main storage for researched political entities';


-- ============================================
-- 2. PROMISES CACHE (Denormalized Promises)
-- ============================================
-- Separate table for fast promise lookups and status tracking

CREATE TABLE IF NOT EXISTS promises_cache (
    id SERIAL PRIMARY KEY,

    -- Who made the promise
    politician_name VARCHAR(255) NOT NULL,

    -- The promise itself
    promise_text TEXT NOT NULL,

    -- Categorization
    topic VARCHAR(100),                    -- education, healthcare, security, etc.

    -- Status tracking
    status VARCHAR(50) DEFAULT 'unknown',  -- pending, in_progress, kept, broken, unknown
    status_evidence TEXT,                  -- Why we assigned this status
    status_updated_at TIMESTAMP WITH TIME ZONE,

    -- Source
    source_url TEXT,
    date_made DATE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(politician_name, promise_text)
);

-- Indexes for promises_cache
CREATE INDEX IF NOT EXISTS idx_promises_politician
    ON promises_cache(politician_name);

CREATE INDEX IF NOT EXISTS idx_promises_topic
    ON promises_cache(topic);

CREATE INDEX IF NOT EXISTS idx_promises_status
    ON promises_cache(status);

CREATE INDEX IF NOT EXISTS idx_promises_date
    ON promises_cache(date_made DESC NULLS LAST);

COMMENT ON TABLE promises_cache IS
    'Denormalized promise tracking for fast lookups';


-- ============================================
-- 3. NEWS CACHE (Recent Articles)
-- ============================================
-- Stores news article summaries, deduplicated by URL

CREATE TABLE IF NOT EXISTS news_cache (
    id SERIAL PRIMARY KEY,

    -- What the news is about
    politician_name VARCHAR(255),          -- Can be NULL for general news

    -- Article content
    headline TEXT NOT NULL,
    summary TEXT,

    -- Source info
    source VARCHAR(100),                   -- News outlet name
    url TEXT UNIQUE,                       -- Unique for deduplication

    -- Metadata
    published_date DATE,
    sentiment VARCHAR(20),                 -- positive, negative, neutral
    topic VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for news_cache
CREATE INDEX IF NOT EXISTS idx_news_politician
    ON news_cache(politician_name);

CREATE INDEX IF NOT EXISTS idx_news_date
    ON news_cache(published_date DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_news_topic
    ON news_cache(topic);

CREATE INDEX IF NOT EXISTS idx_news_source
    ON news_cache(source);

CREATE INDEX IF NOT EXISTS idx_news_created
    ON news_cache(created_at DESC);

COMMENT ON TABLE news_cache IS
    'Cached news articles with summaries';


-- ============================================
-- 4. CACHE MISSES (Research Prioritization)
-- ============================================
-- Tracks queries that couldn't be answered from cache
-- Used to prioritize what to research next

CREATE TABLE IF NOT EXISTS cache_misses (
    id SERIAL PRIMARY KEY,

    -- What was asked
    query_text TEXT,                       -- User's query (truncated)
    intent_topic VARCHAR(100),             -- Classified intent
    query_entity VARCHAR(255),             -- Specific entity if identified

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for cache_misses
CREATE INDEX IF NOT EXISTS idx_cache_misses_topic
    ON cache_misses(intent_topic);

CREATE INDEX IF NOT EXISTS idx_cache_misses_created
    ON cache_misses(created_at);

CREATE INDEX IF NOT EXISTS idx_cache_misses_entity
    ON cache_misses(query_entity);

-- Partial index for recent misses (most queried)
CREATE INDEX IF NOT EXISTS idx_cache_misses_recent
    ON cache_misses(intent_topic, created_at)
    WHERE created_at > (NOW() - INTERVAL '7 days');

COMMENT ON TABLE cache_misses IS
    'Tracks cache misses for research prioritization';


-- ============================================
-- 5. RESEARCH JOB LOG
-- ============================================
-- Logs research job runs for debugging

CREATE TABLE IF NOT EXISTS research_job_log (
    id SERIAL PRIMARY KEY,

    job_type VARCHAR(50) NOT NULL,         -- 'cycle', 'single_entity', 'refresh'

    -- Results
    tasks_processed INT DEFAULT 0,
    profiles_cached INT DEFAULT 0,
    promises_cached INT DEFAULT 0,
    articles_crawled INT DEFAULT 0,
    errors INT DEFAULT 0,

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds FLOAT,

    -- Details
    details JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_research_log_started
    ON research_job_log(started_at DESC);

COMMENT ON TABLE research_job_log IS
    'Logs research job executions';


-- ============================================
-- 6. HELPER FUNCTIONS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_knowledge_cache_updated_at ON knowledge_cache;
CREATE TRIGGER update_knowledge_cache_updated_at
    BEFORE UPDATE ON knowledge_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_promises_cache_updated_at ON promises_cache;
CREATE TRIGGER update_promises_cache_updated_at
    BEFORE UPDATE ON promises_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_news_cache_updated_at ON news_cache;
CREATE TRIGGER update_news_cache_updated_at
    BEFORE UPDATE ON news_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================
-- 7. CLEANUP FUNCTION
-- ============================================
-- Call periodically to clean up old data

CREATE OR REPLACE FUNCTION cleanup_old_cache_data(days_to_keep INT DEFAULT 30)
RETURNS TABLE(
    news_deleted BIGINT,
    cache_misses_deleted BIGINT
) AS $$
DECLARE
    cutoff_date TIMESTAMP WITH TIME ZONE;
    news_count BIGINT;
    misses_count BIGINT;
BEGIN
    cutoff_date := NOW() - (days_to_keep || ' days')::INTERVAL;

    -- Delete old news
    DELETE FROM news_cache WHERE created_at < cutoff_date;
    GET DIAGNOSTICS news_count = ROW_COUNT;

    -- Delete old cache misses
    DELETE FROM cache_misses WHERE created_at < cutoff_date;
    GET DIAGNOSTICS misses_count = ROW_COUNT;

    RETURN QUERY SELECT news_count, misses_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_cache_data IS
    'Cleans up old news and cache miss records';


-- ============================================
-- DONE
-- ============================================
-- Run with: psql $DATABASE_URL -f migrations/003_knowledge_cache_tables.sql
