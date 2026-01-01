-- PRIORITY 0 FIX: Create users and representatives tables
-- Run this on the production PostgreSQL database

-- 1. USERS TABLE - stores user profiles (persists between sessions)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    phone_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100),
    state VARCHAR(50),
    lga VARCHAR(100),
    language_preference VARCHAR(10) DEFAULT 'en',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    preferences_json JSONB,
    flow_state TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_interaction TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_phone_hash ON users(phone_hash);

-- 2. REPRESENTATIVES TABLE - maps LGA to politicians
CREATE TABLE IF NOT EXISTS representatives (
    id SERIAL PRIMARY KEY,
    state VARCHAR(50) NOT NULL,
    lga VARCHAR(100),
    position VARCHAR(50) NOT NULL,
    senatorial_district VARCHAR(100),
    federal_constituency VARCHAR(200),
    politician_id INTEGER REFERENCES politicians(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reps_state_lga ON representatives(state, lga);
CREATE INDEX IF NOT EXISTS idx_reps_politician ON representatives(politician_id);

-- 3. CHAT_HISTORY TABLE - stores conversation history
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    phone_hash VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    intent VARCHAR(50),
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_phone ON chat_history(phone_hash);

-- Verification queries
SELECT 'Created tables:';
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('users', 'representatives', 'chat_history');
