-- Migration: Fix Schema Drift
-- 1. Add language to rag_documents
ALTER TABLE rag_documents ADD COLUMN language VARCHAR(10) DEFAULT 'en';

-- 2. Add language to news_articles (try/catch in execution or just run)
-- Note: If this fails, it might already exist, but we assume it's missing based on previous failure
ALTER TABLE news_articles ADD COLUMN language VARCHAR(10) DEFAULT 'en';

-- 3. Create privacy_logs table
CREATE TABLE privacy_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id VARCHAR(50) NOT NULL UNIQUE,
    anonymized_query TEXT NOT NULL,
    intent_category VARCHAR(50),
    cluster_id INTEGER,
    language VARCHAR(10) DEFAULT 'en',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_privacy_logs_log_id ON privacy_logs (log_id);
CREATE INDEX ix_privacy_logs_intent_category ON privacy_logs (intent_category);
