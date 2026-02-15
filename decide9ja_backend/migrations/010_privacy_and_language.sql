-- Migration: Add Language Support and Privacy Logs
-- Description: Renames legacy documents table, adds language columns, and creates privacy_logs table.

-- 1. Rename legacy 'documents' table to 'rag_documents' (matches app/database.py)
ALTER TABLE documents RENAME TO rag_documents;

-- 2. Add language column to rag_documents (default 'en')
ALTER TABLE rag_documents ADD COLUMN language VARCHAR(10) DEFAULT 'en';
CREATE INDEX idx_rag_documents_language ON rag_documents(language);

-- 3. Add language column to news_articles (default 'en')
-- Note: Check if column exists or handle duplication error if re-running
ALTER TABLE news_articles ADD COLUMN language VARCHAR(10) DEFAULT 'en';
CREATE INDEX idx_news_articles_language ON news_articles(language);

-- 4. Create privacy_logs table (IF NOT EXISTS to be safe)
CREATE TABLE IF NOT EXISTS privacy_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id VARCHAR(50) UNIQUE NOT NULL,
    
    -- Anonymized content (PII stripped)
    anonymized_query TEXT NOT NULL,
    intent_category VARCHAR(50),
    cluster_id INTEGER, -- For DP clustering
    
    -- Metadata (No user ID)
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    language VARCHAR(10) DEFAULT 'en'
);

CREATE INDEX IF NOT EXISTS idx_privacy_logs_intent ON privacy_logs(intent_category);
CREATE INDEX IF NOT EXISTS idx_privacy_logs_cluster ON privacy_logs(cluster_id);
