"""
Decide9ja RAG Backend - Database Module v2
PostgreSQL with pgvector for embeddings + Knowledge Graph persistence

This replaces file-based storage with proper database persistence for:
- Knowledge entities (politicians, elections, budgets, historical events)
- Embeddings (using pgvector for similarity search)
- Agent learning/feedback loop
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, String, Text, Integer, Float, DateTime,
    Boolean, ForeignKey, Index, UniqueConstraint, event, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# Load environment variables
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./decide9ja.db")

# Detect PostgreSQL vs SQLite
IS_POSTGRES = DATABASE_URL.startswith("postgres")

# Create engine with appropriate settings
if IS_POSTGRES:
    # PostgreSQL with connection pooling for production
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300
    )
else:
    # SQLite for local development
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

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
# PGVECTOR SETUP (PostgreSQL only)
# ===========================================

def setup_pgvector(engine):
    """Enable pgvector extension for PostgreSQL."""
    if IS_POSTGRES:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            logger.info("pgvector extension enabled")


# ===========================================
# KNOWLEDGE GRAPH MODELS
# ===========================================

class KnowledgeEntity(Base):
    """
    Central knowledge entity table.
    Replaces file-based wikidata/wikipedia storage.

    Types: politician, party, state, lga, election, budget,
           historical_event, ministry, agency, bill
    """
    __tablename__ = "knowledge_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String(200), unique=True, nullable=False, index=True)  # e.g., "Q123456" or "politician:tinubu"
    entity_type = Column(String(50), nullable=False, index=True)
    name = Column(String(500), nullable=False)

    # Searchable text content
    description = Column(Text)
    full_text = Column(Text)  # For full-text search

    # Structured data as JSON
    properties = Column(JSONB if IS_POSTGRES else Text)  # All structured attributes

    # For geographic filtering
    state = Column(String(50), index=True)
    lga = Column(String(100), index=True)

    # Temporal data
    start_date = Column(DateTime)  # e.g., term start, election date
    end_date = Column(DateTime)

    # Source tracking
    source = Column(String(100), index=True)  # wikidata, wikipedia, budgit, inec, manual
    source_url = Column(String(1000))
    source_updated_at = Column(DateTime)

    # Embedding for semantic search (stored separately in KnowledgeEmbedding)
    has_embedding = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Indexes
    __table_args__ = (
        Index('ix_entity_type_state', 'entity_type', 'state'),
        Index('ix_entity_source', 'source'),
    )


class KnowledgeEmbedding(Base):
    """
    Embeddings for knowledge entities.
    Uses pgvector for efficient similarity search.
    """
    __tablename__ = "knowledge_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String(200), ForeignKey("knowledge_entities.entity_id"), nullable=False, index=True)

    # Embedding vector (1536 dimensions for OpenAI ada-002)
    # For PostgreSQL: use pgvector column type
    # For SQLite: store as JSON string
    embedding = Column(Text, nullable=False)  # JSON array of floats

    # Embedding metadata
    model = Column(String(100), default="text-embedding-ada-002")
    dimensions = Column(Integer, default=1536)

    created_at = Column(DateTime, server_default=func.now())


class KnowledgeRelation(Base):
    """
    Relations between knowledge entities.
    Replaces NetworkX in-memory graph with persistent storage.
    """
    __tablename__ = "knowledge_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source and target entities
    source_id = Column(String(200), ForeignKey("knowledge_entities.entity_id"), nullable=False, index=True)
    target_id = Column(String(200), ForeignKey("knowledge_entities.entity_id"), nullable=False, index=True)

    # Relation type
    relation_type = Column(String(100), nullable=False, index=True)
    # Examples: "member_of", "won_election", "represents", "allocated_to", "part_of"

    # Relation properties
    properties = Column(JSONB if IS_POSTGRES else Text)
    weight = Column(Float, default=1.0)  # Relation strength

    # Temporal validity
    valid_from = Column(DateTime)
    valid_until = Column(DateTime)

    # Source tracking
    source = Column(String(100))

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('ix_relation_type', 'relation_type'),
        Index('ix_relation_source_target', 'source_id', 'target_id'),
    )


# ===========================================
# BUDGET & FINANCIAL DATA MODELS
# ===========================================

class BudgetAllocation(Base):
    """
    Budget allocations from BudgIT data.
    Replaces excel_imports/ file storage.
    """
    __tablename__ = "budget_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    allocation_id = Column(String(100), unique=True, nullable=False, index=True)

    # Year and type
    fiscal_year = Column(Integer, nullable=False, index=True)
    allocation_type = Column(String(50), nullable=False, index=True)  # faac, capital, recurrent, statutory

    # Recipient
    recipient_type = Column(String(50), nullable=False, index=True)  # state, lga, mda, project
    recipient_name = Column(String(200), nullable=False)
    recipient_code = Column(String(50))  # Budget code

    # Location (for state/lga allocations)
    state = Column(String(50), index=True)
    lga = Column(String(100), index=True)

    # Amounts
    amount_naira = Column(Float, nullable=False)
    amount_usd = Column(Float)  # Converted at time of allocation

    # Budget category
    sector = Column(String(100), index=True)  # education, health, infrastructure, etc.
    sub_sector = Column(String(100))

    # Status tracking
    status = Column(String(50), default="allocated")  # allocated, disbursed, utilized
    disbursed_amount = Column(Float)
    utilization_rate = Column(Float)

    # Source
    source = Column(String(100), default="budgit")
    source_url = Column(String(1000))

    # Metadata
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_budget_year_type', 'fiscal_year', 'allocation_type'),
        Index('ix_budget_state_year', 'state', 'fiscal_year'),
    )


class FAACDistribution(Base):
    """
    Monthly FAAC (Federation Account Allocation Committee) distributions.
    """
    __tablename__ = "faac_distributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    distribution_id = Column(String(100), unique=True, nullable=False, index=True)

    # Period
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False)

    # Recipient
    recipient_type = Column(String(50), nullable=False)  # federal, state, lga
    recipient_name = Column(String(200), nullable=False, index=True)

    # Amounts by source
    statutory_allocation = Column(Float, default=0)
    vat_share = Column(Float, default=0)
    derivation = Column(Float, default=0)  # For oil-producing states
    exchange_gain = Column(Float, default=0)
    other = Column(Float, default=0)

    # Total
    total_allocation = Column(Float, nullable=False)

    # Per capita (if applicable)
    population = Column(Integer)
    per_capita = Column(Float)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('ix_faac_period', 'year', 'month'),
        UniqueConstraint('year', 'month', 'recipient_name', name='uq_faac_distribution'),
    )


class ConstituencyProject(Base):
    """
    Constituency projects tracked from budget data.
    """
    __tablename__ = "constituency_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(100), unique=True, nullable=False, index=True)

    # Project details
    title = Column(String(500), nullable=False)
    description = Column(Text)

    # Location
    state = Column(String(50), nullable=False, index=True)
    lga = Column(String(100), index=True)
    constituency = Column(String(200), index=True)
    address = Column(String(500))
    latitude = Column(Float)
    longitude = Column(Float)

    # Funding
    fiscal_year = Column(Integer, nullable=False, index=True)
    amount_allocated = Column(Float)
    amount_disbursed = Column(Float)
    contractor = Column(String(300))

    # Sponsorship
    sponsor_type = Column(String(50))  # senator, rep, executive
    sponsor_slug = Column(String(200), index=True)  # Links to Politician
    sponsor_name = Column(String(300))

    # Status
    status = Column(String(50), default="allocated", index=True)
    # allocated, ongoing, completed, abandoned, unknown
    completion_percentage = Column(Float)

    # Sector
    sector = Column(String(100), index=True)

    # Verification
    verified = Column(Boolean, default=False)
    verification_date = Column(DateTime)
    verification_notes = Column(Text)
    photo_urls = Column(JSONB if IS_POSTGRES else Text)  # Array of verification photos

    # Source
    source = Column(String(100), default="budgit")
    source_url = Column(String(1000))

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ===========================================
# ELECTION RESULTS MODELS
# ===========================================

class ElectionResult(Base):
    """
    Election results from INEC data.
    Replaces scraper file storage.
    """
    __tablename__ = "election_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(String(100), unique=True, nullable=False, index=True)

    # Election details
    election_year = Column(Integer, nullable=False, index=True)
    election_type = Column(String(50), nullable=False, index=True)
    # presidential, gubernatorial, senatorial, house_of_reps, house_of_assembly

    # Location
    state = Column(String(50), nullable=False, index=True)
    lga = Column(String(100), index=True)
    ward = Column(String(100))
    polling_unit = Column(String(200))
    senatorial_district = Column(String(100))
    federal_constituency = Column(String(200))
    state_constituency = Column(String(200))

    # Candidate
    candidate_name = Column(String(300), nullable=False)
    candidate_slug = Column(String(200), index=True)  # Links to Politician
    party = Column(String(20), nullable=False, index=True)

    # Votes
    votes = Column(Integer, nullable=False)
    percentage = Column(Float)

    # Position
    position = Column(Integer)  # 1st, 2nd, 3rd, etc.
    is_winner = Column(Boolean, default=False, index=True)

    # Context
    total_votes_cast = Column(Integer)
    registered_voters = Column(Integer)
    accredited_voters = Column(Integer)
    rejected_votes = Column(Integer)
    voter_turnout = Column(Float)

    # Source
    source = Column(String(100), default="inec")
    source_url = Column(String(1000))

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('ix_election_year_type', 'election_year', 'election_type'),
        Index('ix_election_state_year', 'state', 'election_year'),
    )


# ===========================================
# AGENT LEARNING & FEEDBACK MODELS
# ===========================================

class AgentFeedback(Base):
    """
    Stores feedback for continuous learning.
    Used with SuperMemory for agent improvement.
    """
    __tablename__ = "agent_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_id = Column(String(100), unique=True, nullable=False, index=True)

    # Interaction reference
    interaction_id = Column(Integer, ForeignKey("interactions.id"), index=True)
    user_hash = Column(String(64), index=True)

    # The query and response
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)

    # Feedback signals
    feedback_type = Column(String(50), nullable=False, index=True)
    # explicit_positive, explicit_negative, implicit_positive (follow-up),
    # implicit_negative (rephrased), correction, clarification_needed

    # Explicit feedback
    rating = Column(Integer)  # 1-5 if provided
    feedback_text = Column(Text)

    # Correction data (if user corrected the response)
    correction = Column(Text)
    correct_answer = Column(Text)

    # Analysis
    error_category = Column(String(100))
    # factual_error, outdated_info, wrong_entity, missing_context, etc.
    entities_mentioned = Column(JSONB if IS_POSTGRES else Text)  # Entities involved

    # For learning
    should_retrain = Column(Boolean, default=False, index=True)
    incorporated_at = Column(DateTime)  # When feedback was used for improvement

    created_at = Column(DateTime, server_default=func.now())


class AgentKnowledgeGap(Base):
    """
    Tracks knowledge gaps identified from user queries.
    Helps prioritize data collection.
    """
    __tablename__ = "agent_knowledge_gaps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gap_id = Column(String(100), unique=True, nullable=False, index=True)

    # Gap description
    topic = Column(String(200), nullable=False, index=True)
    description = Column(Text)

    # Category
    gap_type = Column(String(50), nullable=False, index=True)
    # missing_entity, outdated_info, missing_relation, incomplete_data

    # Evidence
    sample_queries = Column(JSONB if IS_POSTGRES else Text)  # Queries that exposed this gap
    query_count = Column(Integer, default=1)  # Times this gap was hit

    # Priority
    priority = Column(String(20), default="medium", index=True)  # low, medium, high, critical

    # Resolution
    status = Column(String(50), default="open", index=True)
    # open, researching, data_collected, resolved
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class QueryPattern(Base):
    """
    Tracks successful query patterns for learning.
    Helps improve retrieval and response generation.
    """
    __tablename__ = "query_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_id = Column(String(100), unique=True, nullable=False, index=True)

    # Pattern
    query_template = Column(String(500), nullable=False)  # Normalized query pattern
    intent = Column(String(100), nullable=False, index=True)

    # Entities involved
    entity_types = Column(JSONB if IS_POSTGRES else Text)  # Types of entities queried

    # Best retrieval strategy
    retrieval_strategy = Column(String(100))
    # knowledge_graph, semantic_search, structured_lookup, web_search, hybrid

    # Performance metrics
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    avg_response_time_ms = Column(Float)
    avg_user_satisfaction = Column(Float)

    # Response template (if applicable)
    response_template = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ===========================================
# IMPORT ORIGINAL MODELS (keep backwards compatibility)
# ===========================================

# Import from original database.py to maintain compatibility
from app.database import (
    Document, Politician, Interaction, NewsArticle,
    Issue, IssueEvent, PoliticianIssue, ArticlePoliticianMention,
    User, ChatHistory, UserSubscription, Notification, DailyDigest,
    UserReport, Bill, Vote, VotingSession, PoliticianVotingRecord,
    BroadcastCampaign, BroadcastMessage, DigestSubscription,
    FactCheck, FactCheckRequest, CommunityIssue, CommunityIssueUpdate,
    CommunityIssueVote, CivicProfile, PointTransaction,
    APIKeyDB, AuditLog
)


# ===========================================
# INITIALIZATION
# ===========================================

def init_db_v2():
    """Create all tables including new knowledge graph tables."""
    # Setup pgvector if PostgreSQL
    if IS_POSTGRES:
        setup_pgvector(engine)

    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database v2 initialized with knowledge graph tables")


def get_db_stats() -> Dict[str, int]:
    """Get counts of all tables for health checks."""
    db = SessionLocal()
    try:
        return {
            "knowledge_entities": db.query(KnowledgeEntity).count(),
            "knowledge_relations": db.query(KnowledgeRelation).count(),
            "budget_allocations": db.query(BudgetAllocation).count(),
            "election_results": db.query(ElectionResult).count(),
            "constituency_projects": db.query(ConstituencyProject).count(),
            "agent_feedback": db.query(AgentFeedback).count(),
        }
    finally:
        db.close()


if __name__ == "__main__":
    init_db_v2()
    print("Database v2 initialized!")
    print("Stats:", get_db_stats())
