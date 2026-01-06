-- Migration 008: Polling Infrastructure
-- Sprint 4.1: Foundation for polls and user responses
-- Sprint 4.2: Results and analytics support

-- =====================================================
-- POLLS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS polls (
    id SERIAL PRIMARY KEY,

    -- Poll content
    question TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]',  -- ["Yes", "No", "Undecided"]
    description TEXT,
    category VARCHAR(50),  -- 'governance', 'election', 'policy', 'opinion'

    -- Targeting criteria (all optional - null means no filter)
    target_state VARCHAR(50),
    target_senatorial_district VARCHAR(100),
    target_federal_constituency VARCHAR(150),
    target_lga VARCHAR(100),
    target_age_range VARCHAR(20),  -- '18-25', '26-35', '36-45', '46-55', '56+'
    target_gender VARCHAR(10),  -- 'male', 'female', 'all'
    target_has_pvc BOOLEAN,  -- Only registered voters

    -- Timing
    starts_at TIMESTAMP DEFAULT NOW(),
    ends_at TIMESTAMP,

    -- Delivery settings
    max_responses INTEGER,  -- Optional cap
    priority INTEGER DEFAULT 0,  -- Higher = more urgent

    -- Status
    status VARCHAR(20) DEFAULT 'active',  -- 'draft', 'active', 'paused', 'completed', 'archived'

    -- Metadata
    created_by VARCHAR(100),
    source VARCHAR(100),  -- 'admin', 'partner', 'research'
    tags JSONB DEFAULT '[]',

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- POLL RESPONSES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS poll_responses (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    phone_hash VARCHAR(64),  -- Fallback if user not in users table

    -- Response
    response VARCHAR(200) NOT NULL,  -- The selected option
    response_index INTEGER,  -- Index in options array (0-based)

    -- Demographics snapshot at time of response
    user_state VARCHAR(50),
    user_lga VARCHAR(100),
    user_senatorial_district VARCHAR(100),
    user_federal_constituency VARCHAR(150),
    user_age_range VARCHAR(20),
    user_gender VARCHAR(10),
    user_has_pvc BOOLEAN,

    -- Metadata
    responded_at TIMESTAMP DEFAULT NOW(),
    response_channel VARCHAR(20) DEFAULT 'whatsapp',  -- 'whatsapp', 'web', 'voice'
    response_time_seconds INTEGER,  -- How long they took to answer

    -- Ensure one response per user per poll
    CONSTRAINT unique_poll_user UNIQUE (poll_id, phone_hash)
);

-- =====================================================
-- POLL DELIVERY QUEUE
-- =====================================================
CREATE TABLE IF NOT EXISTS poll_queue (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    phone_hash VARCHAR(64) NOT NULL,

    -- Status
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'sent', 'responded', 'expired', 'failed'

    -- Timing
    queued_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    responded_at TIMESTAMP,
    expires_at TIMESTAMP,

    -- Retry tracking
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP,

    CONSTRAINT unique_poll_queue UNIQUE (poll_id, phone_hash)
);

-- =====================================================
-- ANALYTICS TABLES
-- =====================================================

-- Daily aggregated metrics
CREATE TABLE IF NOT EXISTS daily_metrics (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,

    -- User metrics
    total_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,  -- DAU
    returning_users INTEGER DEFAULT 0,

    -- Message metrics
    total_messages INTEGER DEFAULT 0,
    inbound_messages INTEGER DEFAULT 0,
    outbound_messages INTEGER DEFAULT 0,

    -- Query metrics
    total_queries INTEGER DEFAULT 0,
    successful_queries INTEGER DEFAULT 0,
    fallback_queries INTEGER DEFAULT 0,  -- Bot didn't understand

    -- Poll metrics
    polls_sent INTEGER DEFAULT 0,
    polls_responded INTEGER DEFAULT 0,

    -- Breakdown by state (top 10)
    users_by_state JSONB DEFAULT '{}',
    queries_by_state JSONB DEFAULT '{}',

    -- Breakdown by intent
    queries_by_intent JSONB DEFAULT '{}',

    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_metric_date UNIQUE (metric_date)
);

-- Hourly metrics for real-time monitoring
CREATE TABLE IF NOT EXISTS hourly_metrics (
    id SERIAL PRIMARY KEY,
    metric_hour TIMESTAMP NOT NULL,

    active_users INTEGER DEFAULT 0,
    messages INTEGER DEFAULT 0,
    queries INTEGER DEFAULT 0,
    polls_responded INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_metric_hour UNIQUE (metric_hour)
);

-- Query log for analytics (anonymized)
CREATE TABLE IF NOT EXISTS query_log (
    id SERIAL PRIMARY KEY,

    -- Query info (no PII)
    query_hash VARCHAR(64),  -- Hash of normalized query
    intent VARCHAR(50),
    sub_intent VARCHAR(50),

    -- Demographics (for aggregation)
    user_state VARCHAR(50),
    user_lga VARCHAR(100),

    -- Performance
    response_time_ms INTEGER,
    was_successful BOOLEAN DEFAULT true,
    fallback_used BOOLEAN DEFAULT false,

    -- Sources used
    sources_used JSONB DEFAULT '[]',  -- ['database', 'knowledge_graph', 'web']

    queried_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- INDEXES
-- =====================================================

-- Polls indexes
CREATE INDEX IF NOT EXISTS idx_polls_status ON polls(status);
CREATE INDEX IF NOT EXISTS idx_polls_starts_at ON polls(starts_at);
CREATE INDEX IF NOT EXISTS idx_polls_ends_at ON polls(ends_at);
CREATE INDEX IF NOT EXISTS idx_polls_target_state ON polls(target_state);
CREATE INDEX IF NOT EXISTS idx_polls_category ON polls(category);

-- Poll responses indexes
CREATE INDEX IF NOT EXISTS idx_poll_responses_poll_id ON poll_responses(poll_id);
CREATE INDEX IF NOT EXISTS idx_poll_responses_user_state ON poll_responses(user_state);
CREATE INDEX IF NOT EXISTS idx_poll_responses_responded_at ON poll_responses(responded_at);
CREATE INDEX IF NOT EXISTS idx_poll_responses_phone_hash ON poll_responses(phone_hash);

-- Poll queue indexes
CREATE INDEX IF NOT EXISTS idx_poll_queue_status ON poll_queue(status);
CREATE INDEX IF NOT EXISTS idx_poll_queue_poll_id ON poll_queue(poll_id);
CREATE INDEX IF NOT EXISTS idx_poll_queue_phone_hash ON poll_queue(phone_hash);

-- Analytics indexes
CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_hourly_metrics_hour ON hourly_metrics(metric_hour);
CREATE INDEX IF NOT EXISTS idx_query_log_intent ON query_log(intent);
CREATE INDEX IF NOT EXISTS idx_query_log_queried_at ON query_log(queried_at);
CREATE INDEX IF NOT EXISTS idx_query_log_user_state ON query_log(user_state);

-- =====================================================
-- VIEWS
-- =====================================================

-- Active polls with response counts
CREATE OR REPLACE VIEW active_polls_summary AS
SELECT
    p.id,
    p.question,
    p.options,
    p.category,
    p.target_state,
    p.starts_at,
    p.ends_at,
    p.status,
    COUNT(pr.id) as response_count,
    p.max_responses,
    CASE
        WHEN p.max_responses IS NOT NULL
        THEN ROUND(COUNT(pr.id)::numeric / p.max_responses * 100, 1)
        ELSE NULL
    END as completion_percentage
FROM polls p
LEFT JOIN poll_responses pr ON p.id = pr.poll_id
WHERE p.status = 'active'
  AND (p.ends_at IS NULL OR p.ends_at > NOW())
GROUP BY p.id
ORDER BY p.priority DESC, p.created_at DESC;

-- Poll results with breakdown
CREATE OR REPLACE VIEW poll_results_view AS
SELECT
    p.id as poll_id,
    p.question,
    pr.response,
    COUNT(*) as count,
    ROUND(COUNT(*)::numeric / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY p.id), 0) * 100, 1) as percentage,
    pr.user_state,
    pr.user_age_range,
    pr.user_gender
FROM polls p
JOIN poll_responses pr ON p.id = pr.poll_id
GROUP BY p.id, p.question, pr.response, pr.user_state, pr.user_age_range, pr.user_gender
ORDER BY p.id, count DESC;

-- Weekly active users trend
CREATE OR REPLACE VIEW wau_trend AS
SELECT
    DATE_TRUNC('week', metric_date) as week_start,
    SUM(new_users) as new_users,
    AVG(active_users) as avg_dau,
    SUM(total_messages) as total_messages,
    SUM(total_queries) as total_queries
FROM daily_metrics
WHERE metric_date >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY DATE_TRUNC('week', metric_date)
ORDER BY week_start DESC;

-- Intent distribution (last 30 days)
CREATE OR REPLACE VIEW intent_distribution AS
SELECT
    intent,
    COUNT(*) as count,
    ROUND(COUNT(*)::numeric / NULLIF(SUM(COUNT(*)) OVER (), 0) * 100, 1) as percentage,
    AVG(response_time_ms) as avg_response_time_ms,
    SUM(CASE WHEN fallback_used THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100 as fallback_rate
FROM query_log
WHERE queried_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY intent
ORDER BY count DESC;

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function to get poll results with option breakdown
CREATE OR REPLACE FUNCTION get_poll_results(p_poll_id INTEGER)
RETURNS TABLE (
    option_text VARCHAR,
    response_count BIGINT,
    percentage NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pr.response::VARCHAR as option_text,
        COUNT(*)::BIGINT as response_count,
        ROUND(COUNT(*)::numeric / NULLIF((SELECT COUNT(*) FROM poll_responses WHERE poll_id = p_poll_id), 0) * 100, 1) as percentage
    FROM poll_responses pr
    WHERE pr.poll_id = p_poll_id
    GROUP BY pr.response
    ORDER BY response_count DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get poll results by state
CREATE OR REPLACE FUNCTION get_poll_results_by_state(p_poll_id INTEGER)
RETURNS TABLE (
    state VARCHAR,
    option_text VARCHAR,
    response_count BIGINT,
    percentage NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pr.user_state::VARCHAR as state,
        pr.response::VARCHAR as option_text,
        COUNT(*)::BIGINT as response_count,
        ROUND(COUNT(*)::numeric / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY pr.user_state), 0) * 100, 1) as percentage
    FROM poll_responses pr
    WHERE pr.poll_id = p_poll_id
      AND pr.user_state IS NOT NULL
    GROUP BY pr.user_state, pr.response
    ORDER BY pr.user_state, response_count DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to find eligible users for a poll
CREATE OR REPLACE FUNCTION find_eligible_poll_users(p_poll_id INTEGER, p_limit INTEGER DEFAULT 1000)
RETURNS TABLE (phone_hash VARCHAR) AS $$
DECLARE
    v_poll polls%ROWTYPE;
BEGIN
    -- Get poll details
    SELECT * INTO v_poll FROM polls WHERE id = p_poll_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    -- Find eligible users who haven't responded
    RETURN QUERY
    SELECT DISTINCT u.phone_hash::VARCHAR
    FROM users u
    WHERE u.phone_hash NOT IN (
        SELECT pr.phone_hash FROM poll_responses pr WHERE pr.poll_id = p_poll_id
    )
    AND u.phone_hash NOT IN (
        SELECT pq.phone_hash FROM poll_queue pq WHERE pq.poll_id = p_poll_id
    )
    -- Apply targeting filters
    AND (v_poll.target_state IS NULL OR u.state = v_poll.target_state)
    AND (v_poll.target_lga IS NULL OR u.lga = v_poll.target_lga)
    -- Add more filters as user table has more fields
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to record daily metrics
CREATE OR REPLACE FUNCTION record_daily_metrics(p_date DATE DEFAULT CURRENT_DATE)
RETURNS VOID AS $$
BEGIN
    INSERT INTO daily_metrics (
        metric_date,
        total_users,
        new_users,
        active_users,
        total_messages,
        total_queries,
        polls_responded
    )
    SELECT
        p_date,
        (SELECT COUNT(*) FROM users),
        (SELECT COUNT(*) FROM users WHERE DATE(created_at) = p_date),
        (SELECT COUNT(DISTINCT phone_hash) FROM query_log WHERE DATE(queried_at) = p_date),
        (SELECT COUNT(*) FROM interactions WHERE DATE(timestamp) = p_date),
        (SELECT COUNT(*) FROM query_log WHERE DATE(queried_at) = p_date),
        (SELECT COUNT(*) FROM poll_responses WHERE DATE(responded_at) = p_date)
    ON CONFLICT (metric_date) DO UPDATE SET
        total_users = EXCLUDED.total_users,
        new_users = EXCLUDED.new_users,
        active_users = EXCLUDED.active_users,
        total_messages = EXCLUDED.total_messages,
        total_queries = EXCLUDED.total_queries,
        polls_responded = EXCLUDED.polls_responded;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- SAMPLE DATA (for testing)
-- =====================================================

-- Sample poll
INSERT INTO polls (question, options, category, status, created_by)
VALUES (
    'Do you think the current government is handling the economy well?',
    '["Yes", "No", "Undecided"]'::JSONB,
    'governance',
    'draft',
    'system'
) ON CONFLICT DO NOTHING;

INSERT INTO polls (question, options, category, target_state, status, created_by)
VALUES (
    'Are you satisfied with the road infrastructure in your state?',
    '["Very Satisfied", "Satisfied", "Neutral", "Dissatisfied", "Very Dissatisfied"]'::JSONB,
    'governance',
    NULL,  -- All states
    'draft',
    'system'
) ON CONFLICT DO NOTHING;

INSERT INTO polls (question, options, category, status, created_by)
VALUES (
    'Will you vote in the next election?',
    '["Definitely Yes", "Probably Yes", "Unsure", "Probably No", "Definitely No"]'::JSONB,
    'election',
    'draft',
    'system'
) ON CONFLICT DO NOTHING;
