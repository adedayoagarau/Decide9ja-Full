"""
Politician Dossier Generator for Decide9ja.

Creates and maintains individual source-of-truth files for each politician.
Each politician gets their own JSON dossier that accumulates:
- Profile data (name, party, position, state, constituency)
- Biographical info (education, career, age)
- Legislative record (bills, voting, committees)
- News mentions (daily updates from scraped news)
- Issue involvement (stances, roles, mentions)
- Historical timeline of events

Cron jobs update these dossiers daily with new news articles.

Directory Structure:
    nigeria_knowledge_data/
    └── politician_dossiers/
        ├── index.json                    # Master index of all politicians
        ├── bola-tinubu.json             # Individual dossier
        ├── peter-obi.json
        ├── atiku-abubakar.json
        └── ...

Usage:
    from app.services.politician_dossier_generator import (
        generate_all_dossiers,
        update_dossier_with_news,
        get_politician_dossier
    )

    # Generate all dossiers (initial setup)
    generate_all_dossiers()

    # Update single politician with today's news
    update_dossier_with_news("bola-tinubu")

    # Get dossier for RAG/queries
    dossier = get_politician_dossier("bola-tinubu")
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Base directory for dossiers
DOSSIER_BASE_DIR = Path(__file__).parent.parent.parent / "nigeria_knowledge_data" / "politician_dossiers"

# Party information
PARTY_FULL_NAMES = {
    "APC": "All Progressives Congress",
    "PDP": "Peoples Democratic Party",
    "LP": "Labour Party",
    "NNPP": "New Nigeria Peoples Party",
    "APGA": "All Progressives Grand Alliance",
    "YPP": "Young Progressives Party",
    "SDP": "Social Democratic Party",
    "ADC": "African Democratic Congress",
    "AA": "Action Alliance",
    "ACN": "Action Congress of Nigeria",
    "ANPP": "All Nigeria Peoples Party",
    "CPC": "Congress for Progressive Change",
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class NewsEntry:
    """A news article mentioning the politician."""
    article_id: str
    title: str
    source: str
    source_url: Optional[str]
    published_date: str
    snippet: str  # Relevant excerpt mentioning the politician
    sentiment: Optional[str] = None  # positive, negative, neutral
    topics: List[str] = field(default_factory=list)
    trust_tier: Optional[str] = None  # From verifier agent
    added_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class IssueInvolvement:
    """Politician's involvement in an issue."""
    issue_id: str
    issue_title: str
    domain: str
    role: str  # responsible, responding, mentioned, sponsor
    first_mentioned: str
    last_updated: str
    mention_count: int = 1
    actions: List[str] = field(default_factory=list)  # Specific actions taken


@dataclass
class TimelineEvent:
    """A significant event in the politician's career."""
    date: str
    event_type: str  # election, appointment, speech, scandal, achievement
    title: str
    description: str
    sources: List[str] = field(default_factory=list)
    verified: bool = False


@dataclass
class PoliticianDossier:
    """
    Complete source-of-truth for a politician.
    This is the master file that gets updated with daily news.
    """
    # Identity
    slug: str
    name: str
    aliases: List[str] = field(default_factory=list)  # Other names they're known by

    # Political Info
    party: str = ""
    party_full_name: str = ""
    party_history: List[Dict[str, str]] = field(default_factory=list)  # [{party, start, end}]
    position: str = ""
    position_history: List[Dict[str, str]] = field(default_factory=list)
    state: str = ""
    constituency: Optional[str] = None
    senatorial_district: Optional[str] = None
    federal_constituency: Optional[str] = None

    # Biographical
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    education: List[str] = field(default_factory=list)
    career_before_politics: str = ""
    image_url: Optional[str] = None

    # Legislative Record
    bills_sponsored: int = 0
    bills_passed: int = 0
    motions_moved: int = 0
    committee_memberships: List[str] = field(default_factory=list)
    attendance_rate: Optional[float] = None
    voting_record: Dict[str, Any] = field(default_factory=dict)

    # Scores & Metrics
    promise_score: Optional[float] = None
    transparency_score: Optional[float] = None
    approval_rating: Optional[float] = None

    # Term Info
    current_term_start: Optional[str] = None
    current_term_end: Optional[str] = None
    terms_served: int = 1

    # News & Media
    news_entries: List[Dict] = field(default_factory=list)  # NewsEntry as dict
    total_news_mentions: int = 0
    last_news_update: Optional[str] = None

    # Issues
    issue_involvements: List[Dict] = field(default_factory=list)  # IssueInvolvement as dict

    # Timeline
    timeline: List[Dict] = field(default_factory=list)  # TimelineEvent as dict

    # Metadata
    data_sources: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1

    # Wikidata reference
    wikidata_id: Optional[str] = None
    wikipedia_url: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'PoliticianDossier':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# File Operations
# =============================================================================

def ensure_dossier_directory():
    """Ensure the dossier directory exists."""
    DOSSIER_BASE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Dossier directory: {DOSSIER_BASE_DIR}")


def get_dossier_path(slug: str) -> Path:
    """Get the file path for a politician's dossier."""
    return DOSSIER_BASE_DIR / f"{slug}.json"


def save_dossier(dossier: PoliticianDossier) -> bool:
    """Save a dossier to disk."""
    ensure_dossier_directory()
    try:
        path = get_dossier_path(dossier.slug)
        dossier.last_updated = datetime.utcnow().isoformat()
        dossier.version += 1

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(dossier.to_dict(), f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved dossier: {dossier.slug}")
        return True
    except Exception as e:
        logger.error(f"Failed to save dossier {dossier.slug}: {e}")
        return False


def load_dossier(slug: str) -> Optional[PoliticianDossier]:
    """Load a dossier from disk."""
    path = get_dossier_path(slug)
    if not path.exists():
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return PoliticianDossier.from_dict(data)
    except Exception as e:
        logger.error(f"Failed to load dossier {slug}: {e}")
        return None


def get_politician_dossier(slug: str) -> Optional[Dict]:
    """
    Get a politician's dossier as a dictionary.
    Public API for other services.
    """
    dossier = load_dossier(slug)
    return dossier.to_dict() if dossier else None


# =============================================================================
# Index Management
# =============================================================================

def load_index() -> Dict[str, Dict]:
    """Load the master index of all politicians."""
    index_path = DOSSIER_BASE_DIR / "index.json"
    if index_path.exists():
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
    return {"politicians": {}, "last_updated": None, "total_count": 0}


def save_index(index: Dict):
    """Save the master index."""
    ensure_dossier_directory()
    index["last_updated"] = datetime.utcnow().isoformat()
    index["total_count"] = len(index.get("politicians", {}))

    index_path = DOSSIER_BASE_DIR / "index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def update_index_entry(dossier: PoliticianDossier):
    """Update a single entry in the index."""
    index = load_index()
    index["politicians"][dossier.slug] = {
        "name": dossier.name,
        "party": dossier.party,
        "position": dossier.position,
        "state": dossier.state,
        "last_updated": dossier.last_updated,
        "news_count": len(dossier.news_entries),
        "total_mentions": dossier.total_news_mentions,
    }
    save_index(index)


# =============================================================================
# Dossier Generation
# =============================================================================

def create_dossier_from_database(politician_row) -> PoliticianDossier:
    """
    Create a dossier from a Politician database row.
    """
    # Parse JSON data if available
    data_json = {}
    if politician_row.data_json:
        try:
            data_json = json.loads(politician_row.data_json)
        except:
            pass

    dossier = PoliticianDossier(
        slug=politician_row.slug,
        name=politician_row.name,
        party=politician_row.party or "",
        party_full_name=PARTY_FULL_NAMES.get(politician_row.party, politician_row.party or ""),
        position=politician_row.position or "",
        state=politician_row.state or "",
        constituency=politician_row.constituency,
        data_sources=["database"],
    )

    # Extract additional data from JSON
    if data_json:
        dossier.education = data_json.get("education", [])
        dossier.career_before_politics = data_json.get("career_before_politics", "")
        dossier.committee_memberships = data_json.get("committees", [])
        dossier.image_url = data_json.get("image_url")
        dossier.date_of_birth = data_json.get("birth_date")
        dossier.wikidata_id = data_json.get("wikidata_id")
        dossier.senatorial_district = data_json.get("senatorial_district")
        dossier.federal_constituency = data_json.get("federal_constituency")

        # Party history
        if "party_history" in data_json:
            dossier.party_history = data_json["party_history"]

        # Position history
        if "positions" in data_json:
            dossier.position_history = data_json["positions"]

    return dossier


def enrich_from_knowledge_graph(dossier: PoliticianDossier) -> PoliticianDossier:
    """
    Enrich dossier with data from the knowledge graph.
    """
    try:
        from app.services.nigeria_knowledge.knowledge_graph import knowledge_graph

        # Search for the politician in the graph
        entity = knowledge_graph.get_entity_by_name(dossier.name)

        if entity:
            props = entity.properties or {}

            # Add wikidata ID
            if props.get("wikidata_id"):
                dossier.wikidata_id = props["wikidata_id"]

            # Add image
            if props.get("image_url") and not dossier.image_url:
                dossier.image_url = props["image_url"]

            # Add gender
            if props.get("gender"):
                dossier.gender = props["gender"]

            # Add party history from graph
            if props.get("party_history") and not dossier.party_history:
                dossier.party_history = [{"party": p} for p in props["party_history"]]

            # Add positions from graph
            if props.get("positions") and not dossier.position_history:
                dossier.position_history = [{"position": p} for p in props["positions"]]

            # Add birth date
            if entity.start_date and not dossier.date_of_birth:
                dossier.date_of_birth = entity.start_date.isoformat()

            if "knowledge_graph" not in dossier.data_sources:
                dossier.data_sources.append("knowledge_graph")

            logger.debug(f"Enriched {dossier.slug} from knowledge graph")

    except Exception as e:
        logger.warning(f"Could not enrich from knowledge graph: {e}")

    return dossier


def enrich_from_wikidata(dossier: PoliticianDossier) -> PoliticianDossier:
    """
    Enrich dossier with Wikidata information.
    """
    try:
        wikidata_path = Path(__file__).parent.parent.parent / "nigeria_knowledge_data" / "wikidata" / "nigerian_politicians.json"

        if not wikidata_path.exists():
            return dossier

        with open(wikidata_path, 'r', encoding='utf-8') as f:
            politicians = json.load(f)

        # Find matching politician by name
        name_lower = dossier.name.lower()
        for p in politicians:
            if p.get("personLabel", "").lower() == name_lower:
                # Found match
                if p.get("person"):
                    wikidata_id = p["person"].split("/")[-1]
                    dossier.wikidata_id = wikidata_id

                if p.get("birthDate") and not dossier.date_of_birth:
                    dossier.date_of_birth = p["birthDate"][:10]  # YYYY-MM-DD

                if p.get("genderLabel") and not dossier.gender:
                    dossier.gender = p["genderLabel"]

                if p.get("image") and not dossier.image_url:
                    dossier.image_url = p["image"]

                if p.get("positionLabel"):
                    if not dossier.position_history:
                        dossier.position_history = []
                    dossier.position_history.append({"position": p["positionLabel"]})

                if "wikidata" not in dossier.data_sources:
                    dossier.data_sources.append("wikidata")

                break

    except Exception as e:
        logger.warning(f"Could not enrich from wikidata: {e}")

    return dossier


def enrich_from_wikipedia(dossier: PoliticianDossier) -> PoliticianDossier:
    """
    Enrich dossier with Wikipedia article content.
    """
    try:
        wiki_dir = Path(__file__).parent.parent.parent / "nigeria_knowledge_data" / "wikipedia"

        if not wiki_dir.exists():
            return dossier

        # Search for matching Wikipedia article
        name_parts = dossier.name.lower().replace(" ", "_")

        for wiki_file in wiki_dir.glob("*.json"):
            if name_parts in wiki_file.name.lower():
                with open(wiki_file, 'r', encoding='utf-8') as f:
                    wiki_data = json.load(f)

                if wiki_data.get("url"):
                    dossier.wikipedia_url = wiki_data["url"]

                # Extract education from content if not present
                content = wiki_data.get("content", "")
                if content and not dossier.education:
                    # Simple extraction - could be enhanced with NLP
                    if "university" in content.lower() or "college" in content.lower():
                        # Mark that education info exists
                        dossier.education = ["See Wikipedia article"]

                if "wikipedia" not in dossier.data_sources:
                    dossier.data_sources.append("wikipedia")

                break

    except Exception as e:
        logger.warning(f"Could not enrich from wikipedia: {e}")

    return dossier


def generate_single_dossier(slug: str) -> Optional[PoliticianDossier]:
    """
    Generate a complete dossier for a single politician.
    """
    from app.database import SessionLocal, Politician

    db = SessionLocal()
    try:
        # Get from database
        politician = db.query(Politician).filter(Politician.slug == slug).first()

        if not politician:
            logger.warning(f"Politician not found: {slug}")
            return None

        # Create base dossier
        dossier = create_dossier_from_database(politician)

        # Enrich from multiple sources
        dossier = enrich_from_knowledge_graph(dossier)
        dossier = enrich_from_wikidata(dossier)
        dossier = enrich_from_wikipedia(dossier)

        # Add existing news entries
        dossier = add_existing_news(dossier, db)

        # Add issue involvements
        dossier = add_issue_involvements(dossier, db)

        # Save dossier
        save_dossier(dossier)
        update_index_entry(dossier)

        return dossier

    except Exception as e:
        logger.error(f"Error generating dossier for {slug}: {e}")
        return None
    finally:
        db.close()


def add_existing_news(dossier: PoliticianDossier, db) -> PoliticianDossier:
    """Add existing news articles that mention this politician."""
    from app.database import NewsArticle
    from sqlalchemy import or_

    try:
        # Search for articles mentioning the politician
        name_pattern = f"%{dossier.name}%"

        articles = db.query(NewsArticle).filter(
            or_(
                NewsArticle.title.ilike(name_pattern),
                NewsArticle.content.ilike(name_pattern)
            )
        ).order_by(NewsArticle.published_at.desc()).limit(50).all()

        for article in articles:
            # Create news entry
            entry = {
                "article_id": str(article.id),
                "title": article.title,
                "source": article.source or "Unknown",
                "source_url": article.url,
                "published_date": article.published_at.isoformat() if article.published_at else None,
                "snippet": _extract_snippet(article.content, dossier.name) if article.content else "",
                "added_date": datetime.utcnow().isoformat(),
            }

            # Check if already in dossier
            existing_ids = {e.get("article_id") for e in dossier.news_entries}
            if entry["article_id"] not in existing_ids:
                dossier.news_entries.append(entry)

        dossier.total_news_mentions = len(dossier.news_entries)
        dossier.last_news_update = datetime.utcnow().isoformat()

    except Exception as e:
        logger.warning(f"Could not add news for {dossier.slug}: {e}")

    return dossier


def add_issue_involvements(dossier: PoliticianDossier, db) -> PoliticianDossier:
    """Add issue involvements for this politician."""
    from app.database import PoliticianIssue, Issue

    try:
        links = db.query(PoliticianIssue).filter(
            PoliticianIssue.politician_slug == dossier.slug
        ).all()

        for link in links:
            issue = db.query(Issue).filter(Issue.issue_id == link.issue_id).first()
            if issue:
                involvement = {
                    "issue_id": issue.issue_id,
                    "issue_title": issue.title,
                    "domain": issue.domain,
                    "role": link.role,
                    "first_mentioned": link.created_at.isoformat() if link.created_at else None,
                    "last_updated": datetime.utcnow().isoformat(),
                    "mention_count": 1,
                }
                dossier.issue_involvements.append(involvement)

    except Exception as e:
        logger.warning(f"Could not add issues for {dossier.slug}: {e}")

    return dossier


def _extract_snippet(content: str, name: str, context_chars: int = 200) -> str:
    """Extract a snippet around the politician's name mention."""
    if not content or not name:
        return ""

    content_lower = content.lower()
    name_lower = name.lower()

    pos = content_lower.find(name_lower)
    if pos == -1:
        return content[:context_chars] + "..."

    start = max(0, pos - context_chars // 2)
    end = min(len(content), pos + len(name) + context_chars // 2)

    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet


# =============================================================================
# Batch Operations
# =============================================================================

def generate_all_dossiers(limit: Optional[int] = None) -> Dict[str, int]:
    """
    Generate dossiers for all politicians in the database.

    Returns:
        Dict with counts: generated, failed, skipped
    """
    from app.database import SessionLocal, Politician

    ensure_dossier_directory()

    db = SessionLocal()
    stats = {"generated": 0, "failed": 0, "skipped": 0, "total": 0}

    try:
        query = db.query(Politician)
        if limit:
            query = query.limit(limit)

        politicians = query.all()
        stats["total"] = len(politicians)

        logger.info(f"Generating dossiers for {stats['total']} politicians...")

        for i, politician in enumerate(politicians):
            try:
                # Check if dossier already exists
                existing = load_dossier(politician.slug)
                if existing:
                    # Update existing dossier
                    dossier = generate_single_dossier(politician.slug)
                    if dossier:
                        stats["generated"] += 1
                    else:
                        stats["failed"] += 1
                else:
                    # Create new dossier
                    dossier = generate_single_dossier(politician.slug)
                    if dossier:
                        stats["generated"] += 1
                    else:
                        stats["failed"] += 1

                if (i + 1) % 100 == 0:
                    logger.info(f"Progress: {i + 1}/{stats['total']} dossiers processed")

            except Exception as e:
                logger.error(f"Error processing {politician.slug}: {e}")
                stats["failed"] += 1

        logger.info(f"Dossier generation complete: {stats}")
        return stats

    finally:
        db.close()


def get_all_politician_slugs() -> List[str]:
    """Get list of all politician slugs in the database."""
    from app.database import SessionLocal, Politician

    db = SessionLocal()
    try:
        slugs = [p.slug for p in db.query(Politician.slug).all()]
        return slugs
    finally:
        db.close()


def list_all_dossiers() -> List[Dict]:
    """List all existing dossiers with summary info."""
    index = load_index()
    return list(index.get("politicians", {}).values())


# =============================================================================
# News Update Functions (Called by Cron)
# =============================================================================

def update_dossier_with_news(slug: str, articles: List[Dict] = None) -> bool:
    """
    Update a politician's dossier with new news articles.

    Args:
        slug: Politician slug
        articles: Optional list of articles. If None, fetches from database.

    Returns:
        True if updated successfully
    """
    dossier = load_dossier(slug)
    if not dossier:
        logger.warning(f"Dossier not found for {slug}, generating...")
        dossier = generate_single_dossier(slug)
        if not dossier:
            return False

    # Get new articles if not provided
    if articles is None:
        articles = fetch_recent_news_for_politician(dossier.name, days=1)

    # Add new articles
    existing_ids = {e.get("article_id") for e in dossier.news_entries}
    new_count = 0

    for article in articles:
        article_id = str(article.get("id", article.get("article_id", "")))
        if article_id and article_id not in existing_ids:
            entry = {
                "article_id": article_id,
                "title": article.get("title", ""),
                "source": article.get("source", "Unknown"),
                "source_url": article.get("url"),
                "published_date": article.get("published_date") or article.get("published_at"),
                "snippet": article.get("snippet", ""),
                "sentiment": article.get("sentiment"),
                "topics": article.get("topics", []),
                "trust_tier": article.get("trust_tier"),
                "added_date": datetime.utcnow().isoformat(),
            }
            dossier.news_entries.append(entry)
            new_count += 1

    if new_count > 0:
        dossier.total_news_mentions += new_count
        dossier.last_news_update = datetime.utcnow().isoformat()
        save_dossier(dossier)
        update_index_entry(dossier)
        logger.info(f"Added {new_count} news entries to {slug}")

    return True


def fetch_recent_news_for_politician(name: str, days: int = 1) -> List[Dict]:
    """Fetch recent news articles mentioning a politician."""
    from app.database import SessionLocal, NewsArticle
    from sqlalchemy import or_
    from datetime import datetime, timedelta

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        name_pattern = f"%{name}%"

        articles = db.query(NewsArticle).filter(
            or_(
                NewsArticle.title.ilike(name_pattern),
                NewsArticle.content.ilike(name_pattern)
            ),
            NewsArticle.scraped_at >= cutoff
        ).all()

        return [
            {
                "id": str(a.id),
                "title": a.title,
                "source": a.source,
                "url": a.url,
                "published_date": a.published_at.isoformat() if a.published_at else None,
                "snippet": _extract_snippet(a.content, name) if a.content else "",
            }
            for a in articles
        ]
    finally:
        db.close()


def update_all_dossiers_with_news(days: int = 1) -> Dict[str, int]:
    """
    Update all dossiers with recent news.
    Called by daily cron job.

    Returns:
        Stats dict with updated, failed, no_news counts
    """
    stats = {"updated": 0, "failed": 0, "no_news": 0, "total": 0}

    index = load_index()
    politicians = index.get("politicians", {})
    stats["total"] = len(politicians)

    logger.info(f"Updating {stats['total']} politician dossiers with news from last {days} day(s)...")

    for slug in politicians.keys():
        try:
            dossier = load_dossier(slug)
            if not dossier:
                continue

            articles = fetch_recent_news_for_politician(dossier.name, days=days)

            if articles:
                if update_dossier_with_news(slug, articles):
                    stats["updated"] += 1
                else:
                    stats["failed"] += 1
            else:
                stats["no_news"] += 1

        except Exception as e:
            logger.error(f"Error updating {slug}: {e}")
            stats["failed"] += 1

    logger.info(f"Dossier news update complete: {stats}")
    return stats


# =============================================================================
# RAG Integration
# =============================================================================

def get_dossier_for_rag(slug: str) -> Optional[str]:
    """
    Get dossier formatted for RAG retrieval.
    Returns markdown-formatted content.
    """
    dossier = load_dossier(slug)
    if not dossier:
        return None

    lines = []
    lines.append(f"# {dossier.name}")
    lines.append(f"**Party:** {dossier.party_full_name or dossier.party}")
    lines.append(f"**Position:** {dossier.position}")
    lines.append(f"**State:** {dossier.state}")

    if dossier.constituency:
        lines.append(f"**Constituency:** {dossier.constituency}")

    lines.append("")

    # Biographical
    if dossier.date_of_birth:
        lines.append(f"**Born:** {dossier.date_of_birth}")
    if dossier.gender:
        lines.append(f"**Gender:** {dossier.gender}")

    if dossier.education:
        lines.append("")
        lines.append("## Education")
        for edu in dossier.education:
            lines.append(f"- {edu}")

    if dossier.committee_memberships:
        lines.append("")
        lines.append("## Committee Memberships")
        for committee in dossier.committee_memberships:
            lines.append(f"- {committee}")

    # Recent news
    if dossier.news_entries:
        lines.append("")
        lines.append("## Recent News")
        for entry in dossier.news_entries[:5]:  # Last 5
            date = entry.get("published_date", "")[:10] if entry.get("published_date") else ""
            lines.append(f"- [{date}] {entry.get('title', 'Untitled')} ({entry.get('source', 'Unknown')})")

    # Issues
    if dossier.issue_involvements:
        lines.append("")
        lines.append("## Issue Involvements")
        for issue in dossier.issue_involvements[:5]:
            lines.append(f"- **{issue.get('issue_title')}** ({issue.get('domain')}) - {issue.get('role')}")

    lines.append("")
    lines.append(f"*Last updated: {dossier.last_updated}*")

    return "\n".join(lines)


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python politician_dossier_generator.py [generate|update|list|get <slug>]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        stats = generate_all_dossiers(limit=limit)
        print(f"Generated: {stats}")

    elif command == "update":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        stats = update_all_dossiers_with_news(days=days)
        print(f"Updated: {stats}")

    elif command == "list":
        dossiers = list_all_dossiers()
        for d in dossiers:
            print(f"{d.get('name', 'Unknown')} ({d.get('party', '?')}) - {d.get('position', '?')}")
        print(f"Total: {len(dossiers)}")

    elif command == "get" and len(sys.argv) > 2:
        slug = sys.argv[2]
        content = get_dossier_for_rag(slug)
        if content:
            print(content)
        else:
            print(f"Dossier not found: {slug}")

    else:
        print("Unknown command")
        sys.exit(1)
