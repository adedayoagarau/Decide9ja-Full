"""
Decide9ja RAG Backend - Database Module
PostgreSQL/SQLite with SQLAlchemy.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Text, Integer, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
import json

# Load environment variables from .env file
load_dotenv(override=True)

# Database URL from environment or default SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./decide9ja.db")

# Create engine (SQLite specific settings)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI - yields database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===========================================
# MODELS
# ===========================================

class Document(Base):
    """
    Stores all retrievable documents with embeddings.
    Each document is a searchable chunk of political data.
    """
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_type = Column(String(50), nullable=False, index=True)  # politician, election, poll, fact_check
    doc_id = Column(String(200), nullable=False, index=True)   # e.g., "lagos_central_senator"
    title = Column(String(500))
    content = Column(Text, nullable=False)  # Full text content for retrieval
    metadata_json = Column(Text)  # JSON string of structured data
    embedding_json = Column(Text)  # JSON string of embedding vector
    
    # For filtering
    state = Column(String(50), index=True)
    party = Column(String(20), index=True)
    position = Column(String(100), index=True)
    category = Column(String(50), index=True)
    
    created_at = Column(DateTime, server_default=func.now())


class Politician(Base):
    """Structured politician data for direct lookups."""
    __tablename__ = "politicians"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    name = Column(String(300), nullable=False)
    party = Column(String(20), index=True)
    position = Column(String(100), index=True)
    state = Column(String(50), index=True)
    constituency = Column(String(200))
    data_json = Column(Text)  # Full JSON data
    
    created_at = Column(DateTime, server_default=func.now())


class Interaction(Base):
    """Logs all user interactions for analytics."""
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50)) # Added for attribution
    query = Column(Text, nullable=False)
    response = Column(Text)
    intent = Column(String(50))
    context_used = Column(Text)
    response_time_ms = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


class NewsArticle(Base):
    """Stores scraped news articles with embeddings for RAG."""
    __tablename__ = "news_articles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String(20), unique=True, nullable=False, index=True)  # MD5 hash of URL
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False)
    source = Column(String(50), nullable=False, index=True)  # premium_times, punch, etc.
    source_name = Column(String(100))  # "Premium Times"
    excerpt = Column(Text)
    full_text = Column(Text)
    
    # Entity extraction
    politicians_json = Column(Text)  # JSON list of mentioned politicians
    topics_json = Column(Text)  # JSON list of topics
    
    # Embeddings
    embedding_json = Column(Text)  # JSON embedding vector
    
    # Timestamps
    published_date = Column(String(50))
    scraped_at = Column(DateTime, server_default=func.now())
    
    # Status
    is_processed = Column(Boolean, default=False)
    is_indexed = Column(Boolean, default=False, index=True)


class Issue(Base):
    """
    Political issues tracked from news and user reports.
    Top-level issues like "Power Grid Collapse" or "Lagos-Ibadan Road Delays"
    """
    __tablename__ = "issues"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "power-grid-2024-07"
    title = Column(String(500), nullable=False)
    domain = Column(String(50), nullable=False, index=True)  # power, roads, security, water, health, education
    severity = Column(String(20), default="moderate", index=True)  # low, moderate, severe
    status = Column(String(20), default="active", index=True)  # active, resolved, archived
    
    # Location
    location = Column(String(200))  # Human readable like "Nationwide" or "Lagos, Ogun"
    states_json = Column(Text)  # JSON array of affected states
    
    # Content
    summary = Column(Text)
    first_reported = Column(DateTime)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Verification
    confidence = Column(Float, default=0.5)  # 0-1 confidence score
    verified = Column(Boolean, default=False)
    event_count = Column(Integer, default=0)
    source_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, server_default=func.now())


class IssueEvent(Base):
    """
    Individual events in an issue timeline.
    Each news article or user report becomes an event.
    """
    __tablename__ = "issue_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(50), unique=True, nullable=False, index=True)
    issue_id = Column(String(50), nullable=False, index=True)  # Links to Issue.issue_id
    
    # Event details
    title = Column(String(500))
    description = Column(Text)
    event_date = Column(DateTime)
    event_type = Column(String(50))  # news, statement, action, user_report
    
    # Source
    source_url = Column(String(1000))
    source_name = Column(String(100))
    article_id = Column(String(20))  # Links to NewsArticle.article_id
    
    # Extracted data
    politicians_json = Column(Text)  # JSON array of politician slugs
    quotes_json = Column(Text)  # JSON array of notable quotes
    
    # Verification
    confidence = Column(Float, default=0.5)
    verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime, server_default=func.now())


class PoliticianIssue(Base):
    """
    Links politicians to issues with their role.
    Enables "show me issues for Tinubu" queries.
    """
    __tablename__ = "politician_issues"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    politician_slug = Column(String(200), nullable=False, index=True)  # Links to Politician.slug
    issue_id = Column(String(50), nullable=False, index=True)  # Links to Issue.issue_id
    
    # Role classification
    role = Column(String(50), default="mentioned")  # responsible, responding, mentioned, affected
    
    # Context
    mention_count = Column(Integer, default=1)
    first_mentioned = Column(DateTime, server_default=func.now())
    last_mentioned = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Unique constraint
    __table_args__ = (
        # Can't use UniqueConstraint with SQLite easily, handled via code
    )


class User(Base):
    """
    Stores user profiles for conversation memory.
    Privacy: Phone number stored as SHA256 hash, never raw.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA256 of phone (privacy)
    
    # Collected via onboarding
    first_name = Column(String(50))       # User's first name (used for addressing)
    last_name = Column(String(50))        # User's last name/surname
    name = Column(String(100))            # Full name (for backward compatibility)
    state = Column(String(50))
    lga = Column(String(100))
    
    # State Management (JSON) - for backup, primary storage is Redis
    flow_state = Column(Text)  # Stores current state, step, and temp data
    
    # Preferences & Metadata
    preferences_json = Column(Text)  # JSON dict of preferences
    onboarding_completed = Column(Boolean, default=False)
    
    # Timestamps
    last_interaction = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())


class ChatHistory(Base):
    """
    Stores recent conversation history for context (Memory).
    Privacy: References user by phone_hash, not raw phone.
    """
    __tablename__ = "chat_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_hash = Column(String(64), nullable=False, index=True)  # SHA256 hash for privacy
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())
    
    # Metadata for analysis
    intent = Column(String(50))
    

class UserSubscription(Base):
    """
    User subscriptions for notifications.
    Tracks what politicians, issues, and topics users want alerts for.
    """
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_hash = Column(String(64), nullable=False, index=True)  # SHA256 of phone

    # Subscription type
    subscription_type = Column(String(50), nullable=False, index=True)  # politician, issue, topic, state
    target_id = Column(String(200), nullable=False, index=True)  # politician slug, issue_id, topic name, or state
    target_name = Column(String(300))  # Human readable name for display

    # Notification preferences
    notify_news = Column(Boolean, default=True)  # Notify on news mentions
    notify_updates = Column(Boolean, default=True)  # Notify on status updates
    notify_daily_digest = Column(Boolean, default=False)  # Include in daily digest

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Notification(Base):
    """
    Notifications to be sent to users.
    Central queue for all notification types.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_id = Column(String(50), unique=True, nullable=False, index=True)

    # Target user
    user_hash = Column(String(64), nullable=False, index=True)

    # Notification content
    notification_type = Column(String(50), nullable=False, index=True)  # news_alert, issue_update, daily_digest, election_reminder
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)

    # Reference to trigger
    reference_type = Column(String(50))  # politician, issue, article, election
    reference_id = Column(String(200))  # The ID of the referenced item
    reference_url = Column(String(1000))  # Optional URL for more info

    # Priority and scheduling
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    scheduled_for = Column(DateTime)  # When to send (null = immediately)

    # Status
    status = Column(String(20), default="pending", index=True)  # pending, sent, failed, cancelled

    # Delivery tracking
    attempts = Column(Integer, default=0)
    last_attempt = Column(DateTime)
    sent_at = Column(DateTime)
    error_message = Column(Text)

    # Channel used
    channel = Column(String(20), default="whatsapp")  # whatsapp, sms, web_push

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)  # Don't send if expired


class DailyDigest(Base):
    """
    Aggregated daily digest for users.
    Sent once per day with summary of tracked items.
    """
    __tablename__ = "daily_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_hash = Column(String(64), nullable=False, index=True)
    digest_date = Column(DateTime, nullable=False, index=True)

    # Content (JSON structure)
    content_json = Column(Text)  # JSON with sections: politicians, issues, news

    # Status
    status = Column(String(20), default="pending")  # pending, sent, failed
    sent_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())


class UserReport(Base):
    """
    Issues reported by WhatsApp users.
    Goes into verification queue before becoming an Event.
    """
    __tablename__ = "user_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(50), unique=True, nullable=False, index=True)
    user_hash = Column(String(64), nullable=False, index=True)
    
    # Report content
    domain = Column(String(50))  # power, roads, security, etc.
    description = Column(Text, nullable=False)
    location = Column(String(200))
    state = Column(String(50))
    lga = Column(String(100))
    
    # Media
    image_url = Column(String(500))
    voice_transcript = Column(Text)
    
    # Geo
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Status
    status = Column(String(20), default="pending")  # pending, approved, rejected, merged
    linked_issue_id = Column(String(50))  # If merged into existing issue
    
    created_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime)


class Bill(Base):
    """
    Legislative bills tracked from National Assembly.
    Tracks bills from introduction through passage.
    """
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "HB.123.2024" or "SB.456.2024"

    # Basic info
    title = Column(String(1000), nullable=False)
    short_title = Column(String(200))  # Abbreviated title for display
    description = Column(Text)
    bill_type = Column(String(50), index=True)  # executive, private_member, appropriation, constitutional

    # Chamber
    chamber = Column(String(20), nullable=False, index=True)  # senate, house
    originating_chamber = Column(String(20))  # senate or house

    # Sponsors
    sponsor_slug = Column(String(200), index=True)  # Primary sponsor politician slug
    sponsor_name = Column(String(300))
    co_sponsors_json = Column(Text)  # JSON array of co-sponsor slugs

    # Status tracking
    status = Column(String(50), default="introduced", index=True)  # introduced, first_reading, second_reading, committee, third_reading, passed, presidential_assent, enacted, rejected, withdrawn
    current_stage = Column(String(100))  # Detailed stage description
    introduced_date = Column(DateTime, index=True)
    last_action_date = Column(DateTime, index=True)
    last_action = Column(String(500))

    # Timeline (JSON array of actions)
    timeline_json = Column(Text)  # [{date, action, chamber, details}, ...]

    # Content
    full_text_url = Column(String(1000))  # Link to bill text
    summary = Column(Text)  # AI-generated or official summary

    # Classification
    category = Column(String(100), index=True)  # health, education, finance, security, infrastructure
    tags_json = Column(Text)  # JSON array of tags
    states_affected_json = Column(Text)  # JSON array of states affected (null = nationwide)

    # Voting results (after passed/rejected)
    ayes_count = Column(Integer)
    nays_count = Column(Integer)
    abstentions_count = Column(Integer)
    vote_date = Column(DateTime)

    # Metadata
    source_url = Column(String(1000))
    last_scraped = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Vote(Base):
    """
    Individual votes cast by politicians on bills or motions.
    Tracks each politician's voting record.
    """
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vote_id = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "vote-SB.123-tinubu-2024-01-15"

    # Bill/Motion being voted on
    bill_id = Column(String(100), index=True)  # Links to Bill.bill_id
    motion_title = Column(String(500))  # For non-bill votes (motions, resolutions)
    motion_description = Column(Text)

    # Vote session
    session_id = Column(String(100), index=True)  # Links to VotingSession
    chamber = Column(String(20), nullable=False, index=True)  # senate, house
    vote_date = Column(DateTime, nullable=False, index=True)

    # Politician casting the vote
    politician_slug = Column(String(200), nullable=False, index=True)
    politician_name = Column(String(300))
    politician_party = Column(String(20), index=True)
    politician_state = Column(String(50), index=True)

    # The vote itself
    vote_cast = Column(String(20), nullable=False, index=True)  # aye, nay, abstain, absent, excused

    # Context
    party_position = Column(String(20))  # What the party leadership recommended
    voted_with_party = Column(Boolean)  # Did they follow party line?

    # Source
    source_url = Column(String(1000))
    verified = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())


class VotingSession(Base):
    """
    A voting session in the legislature.
    Groups multiple individual votes together.
    """
    __tablename__ = "voting_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)

    # Session details
    chamber = Column(String(20), nullable=False, index=True)  # senate, house
    session_date = Column(DateTime, nullable=False, index=True)
    session_type = Column(String(50))  # plenary, committee, joint

    # What was voted on
    bill_id = Column(String(100), index=True)  # Links to Bill.bill_id
    motion_title = Column(String(500))
    vote_type = Column(String(50))  # second_reading, third_reading, amendment, motion, resolution

    # Results
    total_votes = Column(Integer)
    ayes = Column(Integer)
    nays = Column(Integer)
    abstentions = Column(Integer)
    absent = Column(Integer)
    result = Column(String(20))  # passed, rejected, tied

    # Quorum
    required_majority = Column(String(50))  # simple, two-thirds, absolute
    quorum_present = Column(Boolean, default=True)

    # Party breakdown (JSON)
    party_breakdown_json = Column(Text)  # {APC: {aye: X, nay: Y}, PDP: {...}}

    # Source
    source_url = Column(String(1000))
    source_document = Column(String(500))  # Hansard reference

    created_at = Column(DateTime, server_default=func.now())


class PoliticianVotingRecord(Base):
    """
    Aggregated voting statistics for politicians.
    Pre-calculated for performance.
    """
    __tablename__ = "politician_voting_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    politician_slug = Column(String(200), unique=True, nullable=False, index=True)

    # Overall stats
    total_votes = Column(Integer, default=0)
    total_ayes = Column(Integer, default=0)
    total_nays = Column(Integer, default=0)
    total_abstentions = Column(Integer, default=0)
    total_absent = Column(Integer, default=0)

    # Percentages
    attendance_rate = Column(Float)  # % of sessions attended
    participation_rate = Column(Float)  # % of votes cast (not abstained/absent)
    party_loyalty_rate = Column(Float)  # % voting with party

    # By category (JSON: {category: {aye: X, nay: Y}})
    votes_by_category_json = Column(Text)

    # Notable votes (JSON array of significant votes)
    notable_votes_json = Column(Text)

    # Bills sponsored/co-sponsored
    bills_sponsored = Column(Integer, default=0)
    bills_co_sponsored = Column(Integer, default=0)
    bills_passed = Column(Integer, default=0)

    # Last updated
    last_calculated = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ===========================================
# BROADCAST & PROACTIVE MESSAGING MODELS
# ===========================================

class BroadcastCampaign(Base):
    """
    Broadcast campaign for proactive WhatsApp messaging.
    Supports targeted campaigns by state, LGA, interests, etc.
    """
    __tablename__ = "broadcast_campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(100), unique=True, nullable=False, index=True)

    # Campaign info
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)  # news, election, civic, alert, digest

    # Message content
    message_content = Column(Text, nullable=False)
    message_title = Column(String(200))
    cta_text = Column(String(200))  # Call to action
    cta_options_json = Column(Text)  # JSON array of reply options

    # Audience targeting (JSON)
    audience_criteria_json = Column(Text)  # JSON with targeting rules

    # Scheduling
    priority = Column(String(20), default="normal")  # breaking, high, normal, low
    scheduled_at = Column(DateTime, index=True)
    send_window_start = Column(Integer)  # Hour (0-23)
    send_window_end = Column(Integer)

    # Status
    status = Column(String(20), default="draft", index=True)  # draft, scheduled, sending, completed, paused, cancelled

    # Statistics
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    read_count = Column(Integer, default=0)
    replied_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)

    # Timestamps
    created_by = Column(String(100))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BroadcastMessage(Base):
    """
    Individual messages in a broadcast campaign.
    Tracks delivery status per recipient.
    """
    __tablename__ = "broadcast_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(100), unique=True, nullable=False, index=True)

    # Links
    campaign_id = Column(String(100), index=True)  # Links to BroadcastCampaign
    user_hash = Column(String(64), nullable=False, index=True)

    # Content (personalized)
    content = Column(Text, nullable=False)

    # Delivery
    priority = Column(String(20), default="normal")
    status = Column(String(20), default="queued", index=True)  # queued, sent, delivered, read, failed
    twilio_sid = Column(String(100))  # Twilio message SID

    # Tracking
    queued_at = Column(DateTime, server_default=func.now())
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    failed_at = Column(DateTime)
    error_message = Column(Text)

    # Response tracking
    user_replied = Column(Boolean, default=False)
    reply_content = Column(Text)
    reply_at = Column(DateTime)


class DigestSubscription(Base):
    """
    User subscriptions to news digests.
    Controls what and when users receive digests.
    """
    __tablename__ = "digest_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Subscription settings
    is_active = Column(Boolean, default=True, index=True)
    frequency = Column(String(20), default="daily")  # daily, weekly, breaking
    send_time = Column(String(10), default="07:00")  # HH:MM in WAT
    send_days_json = Column(Text)  # JSON array [0,1,2,3,4,5,6] for days of week

    # Content preferences
    categories_json = Column(Text)  # JSON array of preferred categories
    states_of_interest_json = Column(Text)  # JSON array of states
    max_items = Column(Integer, default=5)
    include_polls = Column(Boolean, default=True)
    include_election_updates = Column(Boolean, default=True)
    language = Column(String(10), default="en")

    # Stats
    digests_sent = Column(Integer, default=0)
    last_sent_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ===========================================
# FACT-CHECK MODELS
# ===========================================

class FactCheck(Base):
    """
    Fact-checked political claims.
    Stores verified claims with verdicts and sources.
    """
    __tablename__ = "fact_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fact_check_id = Column(String(100), unique=True, nullable=False, index=True)

    # The claim
    claim = Column(Text, nullable=False)
    claim_hash = Column(String(64), nullable=False, index=True)  # For deduplication
    claimant = Column(String(200))  # Who made the claim
    claim_date = Column(DateTime)
    claim_context = Column(Text)

    # Verdict
    verdict = Column(String(30), nullable=False, index=True)  # true, mostly_true, half_true, mostly_false, false, unverifiable, satire, outdated
    explanation = Column(Text, nullable=False)

    # Sources (JSON array)
    sources_json = Column(Text)  # [{name, url, credibility}, ...]

    # Classification
    category = Column(String(50), index=True)  # election, politician, policy, economy, security, statistics
    tags_json = Column(Text)

    # Tracking
    is_viral = Column(Boolean, default=False, index=True)
    alert_level = Column(String(20), default="normal")  # normal, elevated, critical
    times_queried = Column(Integer, default=0)

    # Verification
    checked_by = Column(String(100))
    verified = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class FactCheckRequest(Base):
    """
    User requests for fact-checking.
    Queue of claims submitted by users.
    """
    __tablename__ = "fact_check_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(100), unique=True, nullable=False, index=True)

    # Submitter
    user_hash = Column(String(64), nullable=False, index=True)

    # The claim
    claim = Column(Text, nullable=False)
    claim_hash = Column(String(64), index=True)

    # Status
    status = Column(String(20), default="pending", index=True)  # pending, processing, completed, rejected
    result_id = Column(String(100))  # Links to FactCheck.fact_check_id when completed

    # Processing
    assigned_to = Column(String(100))
    notes = Column(Text)

    submitted_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime)


# ===========================================
# COMMUNITY & GAMIFICATION MODELS
# ===========================================

class CommunityIssue(Base):
    """
    Community-reported issues.
    Crowdsourced civic problem reporting.
    """
    __tablename__ = "community_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., ISS00123

    # Issue details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, index=True)  # roads, electricity, water, security, sanitation, etc.

    # Location
    state = Column(String(50), nullable=False, index=True)
    lga = Column(String(100), nullable=False, index=True)
    ward = Column(String(100))
    address = Column(String(500))
    latitude = Column(Float)
    longitude = Column(Float)

    # Reporter
    reporter_hash = Column(String(64), nullable=False, index=True)
    reporter_name = Column(String(100))

    # Status
    status = Column(String(20), default="reported", index=True)  # reported, verified, acknowledged, in_progress, resolved, closed, rejected

    # Engagement
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    verification_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)

    # Authority tracking
    responsible_authority = Column(String(200))
    official_response = Column(Text)
    reference_number = Column(String(100))

    # Media (JSON array of URLs)
    photo_urls_json = Column(Text)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime)


class CommunityIssueUpdate(Base):
    """
    Updates to community issues.
    Comments, status changes, photos.
    """
    __tablename__ = "community_issue_updates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    update_id = Column(String(100), unique=True, nullable=False, index=True)

    # Links
    issue_id = Column(String(50), nullable=False, index=True)  # Links to CommunityIssue

    # Update content
    update_type = Column(String(30), nullable=False)  # status_change, comment, photo_update, verification, official_response
    content = Column(Text, nullable=False)
    photo_url = Column(String(500))

    # Author
    author_hash = Column(String(64), nullable=False)
    author_name = Column(String(100))
    is_official = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())


class CommunityIssueVote(Base):
    """
    Votes on community issues.
    Tracks who voted on what.
    """
    __tablename__ = "community_issue_votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String(50), nullable=False, index=True)
    voter_hash = Column(String(64), nullable=False, index=True)
    vote_type = Column(String(10), nullable=False)  # up, down

    created_at = Column(DateTime, server_default=func.now())

    # Unique constraint: one vote per user per issue
    __table_args__ = (
        # Handled in code for SQLite compatibility
    )


class CivicProfile(Base):
    """
    User's civic engagement profile.
    Gamification tracking: points, badges, streaks.
    """
    __tablename__ = "civic_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Display
    display_name = Column(String(100))
    state = Column(String(50), index=True)
    lga = Column(String(100))

    # Points
    total_points = Column(Integer, default=0, index=True)
    points_this_month = Column(Integer, default=0)
    points_this_week = Column(Integer, default=0)

    # Level
    level = Column(Integer, default=1)
    title = Column(String(100), default="Civic Observer")

    # Streaks
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_active_date = Column(DateTime)

    # Badges (JSON array of badge IDs)
    badges_json = Column(Text)

    # Action counts (JSON: {action: count})
    action_counts_json = Column(Text)

    # Timestamps
    joined_at = Column(DateTime, server_default=func.now())
    last_points_earned = Column(DateTime)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PointTransaction(Base):
    """
    Point earning transactions.
    Audit log of all points earned.
    """
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(100), unique=True, nullable=False, index=True)

    # User
    user_hash = Column(String(64), nullable=False, index=True)

    # Transaction
    action = Column(String(50), nullable=False, index=True)  # daily_login, report_issue, verify_issue, etc.
    points = Column(Integer, nullable=False)
    description = Column(String(500))

    # Metadata (JSON)
    metadata_json = Column(Text)

    created_at = Column(DateTime, server_default=func.now())


# ===========================================
# SECURITY & AUTHENTICATION MODELS
# ===========================================

class APIKeyDB(Base):
    """
    Persistent API key storage.
    Keys are hashed for security.
    """
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_id = Column(String(50), unique=True, nullable=False, index=True)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Metadata
    name = Column(String(200), nullable=False)
    description = Column(Text)
    role = Column(String(50), nullable=False, index=True)  # admin, moderator, viewer, api
    scopes_json = Column(Text)  # JSON array of scopes

    # Ownership
    created_by = Column(String(100), nullable=False)
    organization = Column(String(200))

    # Status
    is_active = Column(Boolean, default=True, index=True)
    rate_limit = Column(Integer, default=1000)  # requests per hour

    # Usage tracking
    last_used = Column(DateTime)
    usage_count = Column(Integer, default=0)

    # Timestamps
    expires_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """
    Audit log for tracking admin operations.
    Immutable record for compliance.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_id = Column(String(50), unique=True, nullable=False, index=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(100), index=True)
    details_json = Column(Text)

    # Actor
    actor_id = Column(String(100), nullable=False, index=True)
    actor_role = Column(String(50))
    actor_name = Column(String(200))

    # Request context
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    request_id = Column(String(100))

    # Outcome
    success = Column(Boolean, default=True)
    error_message = Column(Text)

    # Timestamp
    timestamp = Column(DateTime, server_default=func.now(), index=True)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized!")

