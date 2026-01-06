-- MIGRATION 006: Ministers & Historical Elections
-- Sprint 3.2: Ministers & Cabinet
-- Sprint 3.3: Historical Election Data

-- ============================================
-- PART 1: MINISTERS & CABINET (Sprint 3.2)
-- ============================================

-- 1. MINISTRIES TABLE - Federal ministries
CREATE TABLE IF NOT EXISTS ministries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    short_name VARCHAR(50),
    description TEXT,
    sector VARCHAR(100),               -- Economy, Social, Infrastructure, etc.
    website_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. MINISTER_APPOINTMENTS TABLE - Track who holds which ministry
CREATE TABLE IF NOT EXISTS minister_appointments (
    id SERIAL PRIMARY KEY,
    politician_id INTEGER REFERENCES politicians(id),
    ministry_id INTEGER REFERENCES ministries(id),
    position VARCHAR(100) DEFAULT 'Minister',  -- Minister, Minister of State
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Index for current ministers
    UNIQUE(ministry_id, is_current) WHERE is_current = TRUE
);

-- 3. SEED MINISTRIES (current Federal Executive Council structure)
INSERT INTO ministries (name, short_name, sector) VALUES
('Ministry of Finance', 'Finance', 'Economy'),
('Ministry of Budget and Economic Planning', 'Budget', 'Economy'),
('Ministry of Trade and Investment', 'Trade', 'Economy'),
('Ministry of Industry', 'Industry', 'Economy'),
('Ministry of Petroleum Resources', 'Petroleum', 'Economy'),
('Ministry of Solid Minerals Development', 'Solid Minerals', 'Economy'),
('Ministry of Agriculture and Food Security', 'Agriculture', 'Economy'),

('Ministry of Health', 'Health', 'Social'),
('Ministry of Education', 'Education', 'Social'),
('Ministry of Labour and Employment', 'Labour', 'Social'),
('Ministry of Women Affairs', 'Women Affairs', 'Social'),
('Ministry of Youth Development', 'Youth', 'Social'),
('Ministry of Humanitarian Affairs', 'Humanitarian', 'Social'),
('Ministry of Sports Development', 'Sports', 'Social'),

('Ministry of Works', 'Works', 'Infrastructure'),
('Ministry of Housing and Urban Development', 'Housing', 'Infrastructure'),
('Ministry of Transportation', 'Transportation', 'Infrastructure'),
('Ministry of Aviation and Aerospace Development', 'Aviation', 'Infrastructure'),
('Ministry of Power', 'Power', 'Infrastructure'),
('Ministry of Water Resources and Sanitation', 'Water Resources', 'Infrastructure'),

('Ministry of Defence', 'Defence', 'Security'),
('Ministry of Interior', 'Interior', 'Security'),
('Ministry of Police Affairs', 'Police Affairs', 'Security'),

('Ministry of Justice', 'Justice', 'Governance'),
('Ministry of Foreign Affairs', 'Foreign Affairs', 'Governance'),
('Ministry of Information and National Orientation', 'Information', 'Governance'),
('Ministry of Federal Capital Territory', 'FCT', 'Governance'),

('Ministry of Communications and Digital Economy', 'Communications', 'Technology'),
('Ministry of Science, Technology and Innovation', 'Science', 'Technology'),

('Ministry of Environment', 'Environment', 'Environment'),
('Ministry of Marine and Blue Economy', 'Marine', 'Environment'),

('Ministry of Arts, Culture and Creative Economy', 'Arts & Culture', 'Culture'),
('Ministry of Tourism', 'Tourism', 'Culture')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- PART 2: HISTORICAL ELECTIONS (Sprint 3.3)
-- ============================================

-- 4. ELECTIONS TABLE - Election events
CREATE TABLE IF NOT EXISTS elections (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    election_type VARCHAR(50) NOT NULL,  -- Presidential, Governorship, Senate, House, State Assembly
    election_date DATE,
    state VARCHAR(50),                    -- NULL for presidential
    constituency VARCHAR(200),            -- Senatorial district, federal constituency, etc.
    total_registered_voters INTEGER,
    total_votes_cast INTEGER,
    valid_votes INTEGER,
    invalid_votes INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. ELECTION_RESULTS TABLE - Candidate results per election
CREATE TABLE IF NOT EXISTS election_results (
    id SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    candidate_name VARCHAR(200) NOT NULL,
    party VARCHAR(50) NOT NULL,
    votes INTEGER NOT NULL,
    vote_percentage DECIMAL(5,2),
    position INTEGER,                     -- 1st, 2nd, 3rd place
    is_winner BOOLEAN DEFAULT FALSE,
    politician_id INTEGER REFERENCES politicians(id),  -- Link if in our DB
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. INDEXES
CREATE INDEX IF NOT EXISTS idx_minister_appointments_politician ON minister_appointments(politician_id);
CREATE INDEX IF NOT EXISTS idx_minister_appointments_ministry ON minister_appointments(ministry_id);
CREATE INDEX IF NOT EXISTS idx_minister_appointments_current ON minister_appointments(is_current) WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_elections_year ON elections(year);
CREATE INDEX IF NOT EXISTS idx_elections_type ON elections(election_type);
CREATE INDEX IF NOT EXISTS idx_elections_state ON elections(state);

CREATE INDEX IF NOT EXISTS idx_election_results_election ON election_results(election_id);
CREATE INDEX IF NOT EXISTS idx_election_results_party ON election_results(party);
CREATE INDEX IF NOT EXISTS idx_election_results_winner ON election_results(is_winner) WHERE is_winner = TRUE;

-- 7. VIEWS

-- Current ministers view
CREATE OR REPLACE VIEW current_ministers AS
SELECT
    p.id as politician_id,
    p.name,
    p.party,
    p.state as state_of_origin,
    m.name as ministry,
    m.short_name as ministry_short,
    m.sector,
    ma.position,
    ma.start_date
FROM minister_appointments ma
JOIN politicians p ON ma.politician_id = p.id
JOIN ministries m ON ma.ministry_id = m.id
WHERE ma.is_current = TRUE
ORDER BY m.name;

-- Election results summary view
CREATE OR REPLACE VIEW election_results_summary AS
SELECT
    e.year,
    e.election_type,
    e.state,
    e.constituency,
    e.total_votes_cast,
    er.candidate_name as winner_name,
    er.party as winner_party,
    er.votes as winner_votes,
    er.vote_percentage as winner_percentage
FROM elections e
JOIN election_results er ON e.id = er.election_id
WHERE er.is_winner = TRUE
ORDER BY e.year DESC, e.state;

-- Verification
SELECT 'Migration 006 complete: Ministers and Elections schema added';
SELECT COUNT(*) as ministries_count FROM ministries;
