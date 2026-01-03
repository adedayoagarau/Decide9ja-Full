-- MIGRATION 007: Constituency Projects Tracking
-- Tracks government projects at federal, state, and constituency levels
-- Sources: BudgIT, OSGF, Ministry websites, Open Treasury

-- 1. PROJECTS TABLE - Main project records
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,

    -- Classification
    project_type VARCHAR(50),           -- Constituency, MDA, UBEC, SUBEB, etc.
    sector VARCHAR(100),                -- Education, Health, Infrastructure, etc.
    category VARCHAR(100),              -- Construction, Renovation, Procurement, etc.

    -- Location
    state VARCHAR(50),
    lga VARCHAR(100),
    constituency VARCHAR(200),          -- Federal or state constituency
    location_description TEXT,          -- e.g., "Ikeja LGA, Ward 3"

    -- Financials
    budget_amount DECIMAL(15,2),
    amount_released DECIMAL(15,2),
    amount_utilized DECIMAL(15,2),
    currency VARCHAR(10) DEFAULT 'NGN',

    -- Timeline
    budget_year INTEGER,
    start_date DATE,
    expected_completion DATE,
    actual_completion DATE,

    -- Status
    status VARCHAR(50) DEFAULT 'Unknown', -- Not Started, Ongoing, Completed, Abandoned, Unknown
    completion_percentage INTEGER,

    -- Sponsor/Handler
    sponsor_politician_id INTEGER REFERENCES politicians(id),
    ministry_id INTEGER REFERENCES ministries(id),
    contractor VARCHAR(255),

    -- Source tracking
    source VARCHAR(100),                -- BudgIT, OSGF, OpenTreasury, Ministry
    source_url TEXT,
    source_id VARCHAR(100),             -- ID from original source
    last_updated DATE,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. PROJECT_UPDATES TABLE - Track project status changes
CREATE TABLE IF NOT EXISTS project_updates (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    update_date DATE,
    previous_status VARCHAR(50),
    new_status VARCHAR(50),
    notes TEXT,
    source VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. PROJECT_IMAGES TABLE - Before/during/after photos
CREATE TABLE IF NOT EXISTS project_images (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    image_type VARCHAR(50),             -- Before, During, After, Document
    caption TEXT,
    taken_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. INDEXES
CREATE INDEX IF NOT EXISTS idx_projects_state ON projects(state);
CREATE INDEX IF NOT EXISTS idx_projects_lga ON projects(lga);
CREATE INDEX IF NOT EXISTS idx_projects_constituency ON projects(constituency);
CREATE INDEX IF NOT EXISTS idx_projects_sector ON projects(sector);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_year ON projects(budget_year);
CREATE INDEX IF NOT EXISTS idx_projects_sponsor ON projects(sponsor_politician_id);
CREATE INDEX IF NOT EXISTS idx_projects_ministry ON projects(ministry_id);
CREATE INDEX IF NOT EXISTS idx_projects_source ON projects(source);

CREATE INDEX IF NOT EXISTS idx_project_updates_project ON project_updates(project_id);

-- 5. VIEWS

-- Projects by constituency with politician info
CREATE OR REPLACE VIEW constituency_projects_view AS
SELECT
    p.*,
    pol.name as sponsor_name,
    pol.party as sponsor_party,
    m.name as ministry_name
FROM projects p
LEFT JOIN politicians pol ON p.sponsor_politician_id = pol.id
LEFT JOIN ministries m ON p.ministry_id = m.id
ORDER BY p.budget_year DESC, p.state, p.constituency;

-- Project summary by state
CREATE OR REPLACE VIEW state_project_summary AS
SELECT
    state,
    COUNT(*) as total_projects,
    SUM(budget_amount) as total_budget,
    SUM(amount_released) as total_released,
    COUNT(CASE WHEN status = 'Completed' THEN 1 END) as completed,
    COUNT(CASE WHEN status = 'Ongoing' THEN 1 END) as ongoing,
    COUNT(CASE WHEN status = 'Abandoned' THEN 1 END) as abandoned,
    COUNT(CASE WHEN status = 'Not Started' THEN 1 END) as not_started
FROM projects
GROUP BY state
ORDER BY total_budget DESC NULLS LAST;

-- Verification
SELECT 'Migration 007 complete: Constituency projects schema added';
