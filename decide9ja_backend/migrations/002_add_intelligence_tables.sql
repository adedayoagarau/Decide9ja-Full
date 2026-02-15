-- Migration: Add tables for Gap 7 (Financial Intelligence)
-- Up
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    risk_score INTEGER,
    title TEXT,
    description TEXT,
    jurisdiction TEXT,
    year INTEGER,
    mda TEXT,
    amount REAL,
    project_name TEXT,
    anomaly_type TEXT,
    enriched_analysis TEXT, -- JSON blob of AI analysis
    source_file TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts USING fts5(
    title,
    description,
    enriched_analysis,
    jurisdiction,
    mda,
    content=findings,
    content_rowid=id
);

-- Triggers to keep FTS updated
CREATE TRIGGER IF NOT EXISTS findings_ai AFTER INSERT ON findings BEGIN
  INSERT INTO findings_fts(rowid, title, description, enriched_analysis, jurisdiction, mda) 
  VALUES (new.rowid, new.title, new.description, new.enriched_analysis, new.jurisdiction, new.mda);
END;

CREATE TRIGGER IF NOT EXISTS findings_ad AFTER DELETE ON findings BEGIN
  INSERT INTO findings_fts(findings_fts, rowid, title, description, enriched_analysis, jurisdiction, mda) 
  VALUES('delete', old.rowid, old.title, old.description, old.enriched_analysis, old.jurisdiction, old.mda);
END;

CREATE TRIGGER IF NOT EXISTS findings_au AFTER UPDATE ON findings BEGIN
  INSERT INTO findings_fts(findings_fts, rowid, title, description, enriched_analysis, jurisdiction, mda) 
  VALUES('delete', old.rowid, old.title, old.description, old.enriched_analysis, old.jurisdiction, old.mda);
  INSERT INTO findings_fts(rowid, title, description, enriched_analysis, jurisdiction, mda) 
  VALUES (new.rowid, new.title, new.description, new.enriched_analysis, new.jurisdiction, new.mda);
END;

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    payment_date DATE,
    payer TEXT, -- e.g., "Federal Ministry of Works"
    receiver TEXT, -- e.g., "Contractor X Ltd"
    amount REAL,
    description TEXT,
    source_url TEXT,
    state TEXT, -- 'Federal' or State Name
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_payer ON transactions(payer);
CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions(receiver);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(payment_date);

CREATE TABLE IF NOT EXISTS context_registry (
    key TEXT PRIMARY KEY, -- e.g., "corruption_patterns"
    category TEXT, -- "fraud_detection", "benchmark"
    content_json TEXT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);
