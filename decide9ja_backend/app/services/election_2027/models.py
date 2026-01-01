"""
Database Models for 2027 Election System

New tables to support:
- Candidate tracking
- Polling system
- News/content pipeline
- Analytics
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, Boolean,
    ForeignKey, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
from enum import Enum

# Import base from main database module
import sys
sys.path.insert(0, '/home/user/Decide9ja-Full/decide9ja_backend')

try:
    from app.database import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


# === ENUMS ===

class PositionType(str, Enum):
    PRESIDENT = "president"
    VICE_PRESIDENT = "vice_president"
    GOVERNOR = "governor"
    DEPUTY_GOVERNOR = "deputy_governor"
    SENATOR = "senator"
    HOUSE_REP = "house_rep"
    STATE_ASSEMBLY = "state_assembly"
    LGA_CHAIRMAN = "lga_chairman"


class PollType(str, Enum):
    VOTING_INTENTION = "voting_intention"  # Who will you vote for?
    APPROVAL_RATING = "approval_rating"     # How is X performing?
    ISSUE_IMPORTANCE = "issue_importance"   # What matters most?
    PREDICTION = "prediction"               # Who do you think will win?
    OPINION = "opinion"                     # General opinion poll


class PollTargetLevel(str, Enum):
    NATIONAL = "national"
    STATE = "state"
    SENATORIAL = "senatorial"
    FEDERAL_CONSTITUENCY = "federal_constituency"
    STATE_CONSTITUENCY = "state_constituency"
    LGA = "lga"


class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


# === CANDIDATE MODEL ===

class Candidate2027(Base):
    """2027 Election Candidates"""
    __tablename__ = "candidates_2027"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)

    # Basic Info
    name = Column(String(200), nullable=False)
    aliases = Column(JSON, default=list)  # ["BAT", "Jagaban"]
    party = Column(String(50), nullable=False)
    party_full = Column(String(200))  # "All Progressives Congress"

    # Position
    position_sought = Column(String(50), nullable=False)  # president, governor, senator
    state = Column(String(50))  # For state-level positions
    constituency = Column(String(200))  # For constituency-level positions
    senatorial_district = Column(String(200))
    federal_constituency = Column(String(200))

    # Profile
    photo_url = Column(String(500))
    bio_short = Column(Text)  # 2-3 sentences
    bio_full = Column(Text)  # Full biography
    date_of_birth = Column(String(20))
    state_of_origin = Column(String(50))
    education = Column(JSON)  # List of education history
    career = Column(JSON)  # List of career history

    # Political
    previous_positions = Column(JSON)  # List of previous political positions
    policy_positions = Column(JSON)  # Key policy stances
    campaign_promises = Column(JSON)  # 2027 campaign promises
    manifesto_url = Column(String(500))

    # Tracking
    is_incumbent = Column(Boolean, default=False)
    is_declared = Column(Boolean, default=True)  # Officially declared candidacy
    declaration_date = Column(DateTime)

    # Social Media
    twitter = Column(String(100))
    facebook = Column(String(100))
    instagram = Column(String(100))
    website = Column(String(200))

    # Analytics (updated by agent)
    sentiment_score = Column(Float, default=0.0)  # -1 to 1
    mention_count_7d = Column(Integer, default=0)
    mention_count_30d = Column(Integer, default=0)
    trending_score = Column(Float, default=0.0)
    last_news_date = Column(DateTime)

    # Metadata
    data_json = Column(JSON)  # Full raw data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_candidate_position', 'position_sought'),
        Index('idx_candidate_party', 'party'),
        Index('idx_candidate_state', 'state'),
    )


# === USER FOLLOWS ===

class UserFollow(Base):
    """Track which candidates users follow"""
    __tablename__ = "user_follows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_phone_hash = Column(String(64), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates_2027.id"), nullable=False)

    # Preferences
    notification_frequency = Column(String(20), default="daily")  # daily, weekly, breaking
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_user_candidate', 'user_phone_hash', 'candidate_id', unique=True),
    )


# === POLLS ===

class Poll(Base):
    """Poll definitions"""
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False)

    # Poll Info
    title = Column(String(300), nullable=False)
    question = Column(Text, nullable=False)
    poll_type = Column(String(50), nullable=False)  # voting_intention, approval, etc.

    # Options
    options = Column(JSON, nullable=False)  # [{"id": "opt1", "text": "Tinubu", "candidate_id": 1}, ...]

    # Targeting
    target_level = Column(String(50), default="national")  # national, state, lga, etc.
    target_values = Column(JSON)  # ["Lagos", "Oyo"] or ["Ikeja Fed"]

    # Position-specific (for voting intention polls)
    position = Column(String(50))  # president, governor, senator
    position_state = Column(String(50))  # For gubernatorial
    position_constituency = Column(String(200))  # For senator/rep

    # Timing
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)

    # Settings
    allow_multiple = Column(Boolean, default=False)
    is_anonymous = Column(Boolean, default=True)
    show_results = Column(Boolean, default=True)  # Show results after voting

    # Metadata
    created_by = Column(String(100), default="system")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_poll_active', 'is_active'),
        Index('idx_poll_type', 'poll_type'),
    )


class PollResponse(Base):
    """User poll responses (anonymized)"""
    __tablename__ = "poll_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey("polls.id"), nullable=False)
    option_id = Column(String(50), nullable=False)  # References options[].id

    # User demographics (for aggregation, not identification)
    user_hash = Column(String(64), nullable=False)  # Hashed phone
    user_state = Column(String(50))
    user_lga = Column(String(100))
    user_senatorial = Column(String(200))
    user_federal_const = Column(String(200))

    # Metadata
    responded_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_response_poll', 'poll_id'),
        Index('idx_response_user', 'user_hash', 'poll_id', unique=True),  # One response per user per poll
    )


# === NEWS/CONTENT PIPELINE ===

class NewsItem(Base):
    """Collected and processed news items"""
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url_hash = Column(String(64), unique=True, nullable=False)  # MD5 of URL

    # Source
    source = Column(String(100), nullable=False)  # "punch", "premium_times"
    url = Column(String(1000), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    summary = Column(Text)  # AI-generated summary
    published_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)

    # NLP Analysis
    entities = Column(JSON)  # Extracted entities: {"politicians": [...], "parties": [...]}
    topics = Column(JSON)  # ["economy", "security", "education"]
    sentiment = Column(String(20))  # positive, negative, neutral
    sentiment_score = Column(Float)  # -1 to 1

    # Relations
    mentioned_candidates = Column(JSON)  # List of candidate IDs mentioned
    related_state = Column(String(50))

    # Status
    is_processed = Column(Boolean, default=False)
    is_relevant = Column(Boolean, default=True)  # False if not politics-related

    __table_args__ = (
        Index('idx_news_source', 'source'),
        Index('idx_news_date', 'published_at'),
        Index('idx_news_sentiment', 'sentiment'),
    )


class DailySentiment(Base):
    """Daily aggregated sentiment for entities"""
    __tablename__ = "daily_sentiment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False)
    entity_type = Column(String(50), nullable=False)  # "candidate", "party", "policy"
    entity_id = Column(String(100), nullable=False)  # candidate_id or party name
    entity_name = Column(String(200))

    # Scores
    sentiment_score = Column(Float)  # Average sentiment -1 to 1
    mention_count = Column(Integer, default=0)
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)

    # Top stories
    top_positive_story = Column(String(500))
    top_negative_story = Column(String(500))

    __table_args__ = (
        Index('idx_sentiment_date', 'date'),
        Index('idx_sentiment_entity', 'entity_type', 'entity_id'),
    )


# === ANALYTICS ===

class PollAnalytics(Base):
    """Pre-computed poll analytics for fast retrieval"""
    __tablename__ = "poll_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey("polls.id"), nullable=False)
    computed_at = Column(DateTime, default=datetime.utcnow)

    # Overall results
    total_responses = Column(Integer, default=0)
    results = Column(JSON)  # {"opt1": 45.2, "opt2": 30.1, ...}

    # Breakdown by demographics
    results_by_state = Column(JSON)  # {"Lagos": {"opt1": 50, ...}, ...}
    results_by_region = Column(JSON)  # {"Southwest": {...}, ...}

    # Trends
    daily_trend = Column(JSON)  # [{"date": "2026-01-01", "opt1": 45}, ...]

    __table_args__ = (
        Index('idx_analytics_poll', 'poll_id'),
    )


class TrendingTopic(Base):
    """Trending political topics"""
    __tablename__ = "trending_topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, default=datetime.utcnow)

    topic = Column(String(200), nullable=False)
    category = Column(String(50))  # economy, security, scandal, election
    mention_count = Column(Integer, default=0)
    sentiment = Column(String(20))
    related_entities = Column(JSON)  # Politicians, parties involved
    sample_headlines = Column(JSON)  # Example headlines

    score = Column(Float)  # Trending score

    __table_args__ = (
        Index('idx_trending_date', 'date'),
    )


# === HELPER FUNCTIONS ===

def init_election_tables(engine):
    """Create all election-related tables."""
    Base.metadata.create_all(engine, tables=[
        Candidate2027.__table__,
        UserFollow.__table__,
        Poll.__table__,
        PollResponse.__table__,
        NewsItem.__table__,
        DailySentiment.__table__,
        PollAnalytics.__table__,
        TrendingTopic.__table__,
    ])
    print("✅ Election 2027 tables created")
