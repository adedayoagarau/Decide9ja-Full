-- MIGRATION 005: Legislative Records
-- Tracks bills, votes, and legislative activity for Nigerian National Assembly
-- Sprint 3.1: Data Expansion Phase

-- 1. BILLS TABLE - Tracks legislation through NASS
CREATE TABLE IF NOT EXISTS bills (
    id SERIAL PRIMARY KEY,
    bill_number VARCHAR(50) UNIQUE,           -- e.g., "SB.001/2024", "HB.123/2024"
    title TEXT NOT NULL,
    short_title VARCHAR(255),
    sponsor_id INTEGER REFERENCES politicians(id),
    co_sponsors INTEGER[],                     -- Array of politician IDs
    chamber VARCHAR(20) NOT NULL,              -- 'Senate', 'House'
    status VARCHAR(50) DEFAULT 'Introduced',   -- Introduced, Committee, Second Reading, Third Reading, Passed, Signed, Rejected
    category VARCHAR(100),                     -- Finance, Health, Security, Education, etc.

    -- Timeline
    introduced_date DATE,
    committee_date DATE,
    second_reading_date DATE,
    third_reading_date DATE,
    passed_date DATE,
    signed_date DATE,

    -- Content
    summary TEXT,
    full_text_url TEXT,
    source_url TEXT,                           -- Where we got the data

    -- Metadata
    assembly_session VARCHAR(20),              -- "10th Assembly"
    legislative_year INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. VOTES TABLE - Individual politician votes on bills
CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
    politician_id INTEGER REFERENCES politicians(id) ON DELETE CASCADE,
    vote VARCHAR(10) NOT NULL,                 -- 'Yes', 'No', 'Abstain', 'Absent'
    vote_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Ensure one vote per politician per bill
    UNIQUE(bill_id, politician_id)
);

-- 3. COMMITTEE_ASSIGNMENTS TABLE - Which committees politicians belong to
CREATE TABLE IF NOT EXISTS committee_assignments (
    id SERIAL PRIMARY KEY,
    politician_id INTEGER REFERENCES politicians(id) ON DELETE CASCADE,
    committee_name VARCHAR(200) NOT NULL,
    role VARCHAR(50) DEFAULT 'Member',         -- Chair, Vice Chair, Member
    chamber VARCHAR(20) NOT NULL,              -- Senate, House
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. MOTIONS TABLE - Track floor motions and resolutions
CREATE TABLE IF NOT EXISTS motions (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    mover_id INTEGER REFERENCES politicians(id),
    chamber VARCHAR(20) NOT NULL,
    motion_type VARCHAR(50),                   -- Resolution, Point of Order, Motion, Amendment
    status VARCHAR(50),                        -- Moved, Carried, Rejected
    motion_date DATE,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. INDEXES for performance
CREATE INDEX IF NOT EXISTS idx_bills_sponsor ON bills(sponsor_id);
CREATE INDEX IF NOT EXISTS idx_bills_chamber ON bills(chamber);
CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status);
CREATE INDEX IF NOT EXISTS idx_bills_category ON bills(category);
CREATE INDEX IF NOT EXISTS idx_bills_introduced_date ON bills(introduced_date);

CREATE INDEX IF NOT EXISTS idx_votes_bill ON votes(bill_id);
CREATE INDEX IF NOT EXISTS idx_votes_politician ON votes(politician_id);
CREATE INDEX IF NOT EXISTS idx_votes_vote_date ON votes(vote_date);

CREATE INDEX IF NOT EXISTS idx_committee_politician ON committee_assignments(politician_id);
CREATE INDEX IF NOT EXISTS idx_committee_name ON committee_assignments(committee_name);

CREATE INDEX IF NOT EXISTS idx_motions_mover ON motions(mover_id);
CREATE INDEX IF NOT EXISTS idx_motions_date ON motions(motion_date);

-- 6. VIEWS for common queries

-- Bills with sponsor info
CREATE OR REPLACE VIEW bills_with_sponsors AS
SELECT
    b.*,
    p.name as sponsor_name,
    p.party as sponsor_party,
    p.state as sponsor_state
FROM bills b
LEFT JOIN politicians p ON b.sponsor_id = p.id;

-- Politician legislative activity summary
CREATE OR REPLACE VIEW politician_legislative_summary AS
SELECT
    p.id as politician_id,
    p.name,
    p.party,
    p.state,
    COUNT(DISTINCT b.id) as bills_sponsored,
    COUNT(DISTINCT CASE WHEN b.status = 'Signed' THEN b.id END) as bills_passed,
    COUNT(DISTINCT v.id) as votes_cast,
    COUNT(DISTINCT CASE WHEN v.vote = 'Yes' THEN v.id END) as yes_votes,
    COUNT(DISTINCT CASE WHEN v.vote = 'No' THEN v.id END) as no_votes,
    COUNT(DISTINCT ca.id) as committee_memberships
FROM politicians p
LEFT JOIN bills b ON p.id = b.sponsor_id
LEFT JOIN votes v ON p.id = v.politician_id
LEFT JOIN committee_assignments ca ON p.id = ca.politician_id
GROUP BY p.id, p.name, p.party, p.state;

-- Verification
SELECT 'Migration 005 complete: Legislative records schema added';
