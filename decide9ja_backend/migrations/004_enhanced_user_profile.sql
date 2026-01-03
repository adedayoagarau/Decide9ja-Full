-- MIGRATION 004: Enhanced User Profile Schema
-- Adds comprehensive user profiling for progressive data collection and personalization
-- Sprint 2.1: User Intelligence Phase

-- 1. ADD LOCATION FIELDS (origin, residence, registration)
-- Origin: Where user is originally from
ALTER TABLE users ADD COLUMN IF NOT EXISTS origin_state VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS origin_lga VARCHAR(100);

-- Residence: Where user currently lives
ALTER TABLE users ADD COLUMN IF NOT EXISTS residence_state VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS residence_lga VARCHAR(100);

-- Registration: Where user is registered to vote
ALTER TABLE users ADD COLUMN IF NOT EXISTS registered_state VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS registered_lga VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS ward VARCHAR(100);

-- 2. ADD POLITICAL GEOGRAPHY (auto-derived from LGA)
ALTER TABLE users ADD COLUMN IF NOT EXISTS senatorial_district VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS federal_constituency VARCHAR(200);
ALTER TABLE users ADD COLUMN IF NOT EXISTS state_constituency VARCHAR(200);

-- 3. ADD DEMOGRAPHIC FIELDS
ALTER TABLE users ADD COLUMN IF NOT EXISTS age_range VARCHAR(20); -- '18-24', '25-34', '35-44', '45-54', '55-64', '65+'
ALTER TABLE users ADD COLUMN IF NOT EXISTS gender VARCHAR(20);    -- 'male', 'female', 'other', 'prefer_not_to_say'

-- 4. ADD VOTER STATUS
ALTER TABLE users ADD COLUMN IF NOT EXISTS has_pvc BOOLEAN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS pvc_collected_at TIMESTAMP;

-- 5. ADD ENGAGEMENT TRACKING
ALTER TABLE users ADD COLUMN IF NOT EXISTS message_count INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS topics_asked TEXT[];   -- Array of topics user has asked about
ALTER TABLE users ADD COLUMN IF NOT EXISTS interests TEXT[];      -- Inferred interests

-- 6. ADD PROFILE METADATA
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_completeness INTEGER DEFAULT 0; -- 0-100 score
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_version INTEGER DEFAULT 1;      -- For schema evolution
ALTER TABLE users ADD COLUMN IF NOT EXISTS data_consent BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_date TIMESTAMP;

-- 7. ADD INDEXES FOR NEW COLUMNS
CREATE INDEX IF NOT EXISTS idx_users_origin_state ON users(origin_state);
CREATE INDEX IF NOT EXISTS idx_users_residence_state ON users(residence_state);
CREATE INDEX IF NOT EXISTS idx_users_registered_state ON users(registered_state);
CREATE INDEX IF NOT EXISTS idx_users_senatorial_district ON users(senatorial_district);
CREATE INDEX IF NOT EXISTS idx_users_federal_constituency ON users(federal_constituency);
CREATE INDEX IF NOT EXISTS idx_users_has_pvc ON users(has_pvc);
CREATE INDEX IF NOT EXISTS idx_users_profile_completeness ON users(profile_completeness);

-- 8. CREATE USER SEGMENTS VIEW
CREATE OR REPLACE VIEW user_segments AS
SELECT
    phone_hash,
    name,
    state,
    lga,
    CASE
        WHEN message_count >= 100 THEN 'power_user'
        WHEN message_count >= 50 THEN 'regular'
        WHEN message_count >= 10 THEN 'engaged'
        WHEN message_count >= 1 THEN 'new'
        ELSE 'inactive'
    END as engagement_tier,
    CASE
        WHEN has_pvc = TRUE THEN 'registered_voter'
        WHEN has_pvc = FALSE THEN 'unregistered'
        ELSE 'unknown'
    END as voter_status,
    profile_completeness,
    CASE
        WHEN profile_completeness >= 80 THEN 'complete'
        WHEN profile_completeness >= 50 THEN 'partial'
        WHEN profile_completeness >= 20 THEN 'minimal'
        ELSE 'new'
    END as profile_tier,
    created_at,
    last_interaction
FROM users;

-- Verification
SELECT 'Migration 004 complete: Enhanced user profile schema added';
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'users'
ORDER BY ordinal_position;
