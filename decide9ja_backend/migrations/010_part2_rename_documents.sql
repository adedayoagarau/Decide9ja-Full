-- Migration: Part 2 - Rename Documents and Add Language
-- Description: Renames 'documents' to 'rag_documents' and adds language column. 
-- Note: 'news_articles' and 'privacy_logs' were already updated in previous run.

-- 1. Rename legacy 'documents' table to 'rag_documents'
ALTER TABLE documents RENAME TO rag_documents;

-- 2. Add language column to rag_documents (default 'en')
ALTER TABLE rag_documents ADD COLUMN language VARCHAR(10) DEFAULT 'en';
CREATE INDEX idx_rag_documents_language ON rag_documents(language);
