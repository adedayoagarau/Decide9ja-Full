-- Migration 009: Add encrypted phone number storage
-- Enables proactive WhatsApp messaging while maintaining privacy

-- =====================================================
-- ADD ENCRYPTED PHONE COLUMN TO USERS
-- =====================================================

-- Add encrypted phone column (nullable for existing users)
ALTER TABLE users ADD COLUMN IF NOT EXISTS encrypted_phone TEXT;

-- Add notification preferences
ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_preferences JSONB DEFAULT '{
    "breaking_news": true,
    "election_reminders": true,
    "poll_invites": true,
    "weekly_digest": false
}'::jsonb;

-- Track when user opted in for notifications
ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_opted_in_at TIMESTAMP;

-- =====================================================
-- NOTIFICATION QUEUE TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS notification_queue (
    id SERIAL PRIMARY KEY,

    -- Target user
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    phone_hash VARCHAR(64),  -- Fallback lookup

    -- Notification content
    notification_type VARCHAR(50) NOT NULL,  -- 'breaking_news', 'election_reminder', 'poll_invite', 'digest'
    title VARCHAR(200),
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',  -- Additional data (poll_id, article_id, etc.)

    -- Scheduling
    scheduled_for TIMESTAMP DEFAULT NOW(),
    priority INTEGER DEFAULT 0,  -- Higher = more urgent

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'sent', 'delivered', 'failed', 'cancelled'
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    error_message TEXT,

    -- Retry logic
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_attempt_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),

    -- Prevent duplicate notifications
    CONSTRAINT unique_notification UNIQUE (user_id, notification_type, data, scheduled_for)
);

-- =====================================================
-- NOTIFICATION LOG (for analytics)
-- =====================================================

CREATE TABLE IF NOT EXISTS notification_log (
    id SERIAL PRIMARY KEY,

    notification_type VARCHAR(50) NOT NULL,
    user_state VARCHAR(50),  -- For geographic analytics

    -- Counts
    total_sent INTEGER DEFAULT 0,
    total_delivered INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,

    -- Date-based aggregation
    log_date DATE NOT NULL,

    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_notification_log UNIQUE (notification_type, user_state, log_date)
);

-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_notification_queue_status ON notification_queue(status);
CREATE INDEX IF NOT EXISTS idx_notification_queue_scheduled ON notification_queue(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_notification_queue_type ON notification_queue(notification_type);
CREATE INDEX IF NOT EXISTS idx_notification_queue_user ON notification_queue(user_id);
CREATE INDEX IF NOT EXISTS idx_users_notifications_enabled ON users(notifications_enabled) WHERE notifications_enabled = true;

-- =====================================================
-- VIEWS
-- =====================================================

-- Users eligible for notifications
CREATE OR REPLACE VIEW notifiable_users AS
SELECT
    u.id,
    u.phone_hash,
    u.encrypted_phone,
    u.name,
    u.state,
    u.lga,
    u.notification_preferences
FROM users u
WHERE u.notifications_enabled = true
  AND u.encrypted_phone IS NOT NULL;

-- Pending notifications summary
CREATE OR REPLACE VIEW pending_notifications_summary AS
SELECT
    notification_type,
    COUNT(*) as pending_count,
    MIN(scheduled_for) as earliest_scheduled,
    MAX(priority) as highest_priority
FROM notification_queue
WHERE status = 'pending'
GROUP BY notification_type;

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function to queue a notification for a user
CREATE OR REPLACE FUNCTION queue_notification(
    p_user_id INTEGER,
    p_type VARCHAR(50),
    p_message TEXT,
    p_title VARCHAR(200) DEFAULT NULL,
    p_data JSONB DEFAULT '{}'::jsonb,
    p_scheduled_for TIMESTAMP DEFAULT NOW(),
    p_priority INTEGER DEFAULT 0
) RETURNS BOOLEAN AS $$
DECLARE
    v_user users%ROWTYPE;
    v_prefs JSONB;
BEGIN
    -- Get user
    SELECT * INTO v_user FROM users WHERE id = p_user_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Check if notifications enabled
    IF NOT v_user.notifications_enabled OR v_user.encrypted_phone IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Check notification preferences
    v_prefs := v_user.notification_preferences;
    IF v_prefs IS NOT NULL THEN
        -- Map notification type to preference key
        CASE p_type
            WHEN 'breaking_news' THEN
                IF NOT COALESCE((v_prefs->>'breaking_news')::boolean, true) THEN
                    RETURN FALSE;
                END IF;
            WHEN 'election_reminder' THEN
                IF NOT COALESCE((v_prefs->>'election_reminders')::boolean, true) THEN
                    RETURN FALSE;
                END IF;
            WHEN 'poll_invite' THEN
                IF NOT COALESCE((v_prefs->>'poll_invites')::boolean, true) THEN
                    RETURN FALSE;
                END IF;
            WHEN 'weekly_digest' THEN
                IF NOT COALESCE((v_prefs->>'weekly_digest')::boolean, false) THEN
                    RETURN FALSE;
                END IF;
            ELSE
                -- Allow unknown types by default
                NULL;
        END CASE;
    END IF;

    -- Queue the notification
    INSERT INTO notification_queue (
        user_id, phone_hash, notification_type, title, message, data,
        scheduled_for, priority
    ) VALUES (
        p_user_id, v_user.phone_hash, p_type, p_title, p_message, p_data,
        p_scheduled_for, p_priority
    )
    ON CONFLICT (user_id, notification_type, data, scheduled_for) DO NOTHING;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to opt user into notifications
CREATE OR REPLACE FUNCTION enable_user_notifications(
    p_user_id INTEGER,
    p_encrypted_phone TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE users
    SET
        encrypted_phone = p_encrypted_phone,
        notifications_enabled = true,
        notifications_opted_in_at = NOW()
    WHERE id = p_user_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON COLUMN users.encrypted_phone IS 'AES-encrypted phone number for proactive messaging. Decrypt only when sending.';
COMMENT ON COLUMN users.notifications_enabled IS 'User has opted in to receive proactive notifications';
COMMENT ON TABLE notification_queue IS 'Queue for outbound WhatsApp notifications';
