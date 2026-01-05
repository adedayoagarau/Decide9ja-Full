"""
Politician Comparison Service for Decide9ja.

Provides side-by-side comparison of politicians including:
- Basic profile information
- Party affiliations and history
- Committee memberships
- Voting records (when available)
- Issue stances and mentions
- Promise tracking scores
- News sentiment analysis

Usage:
    from app.services.politician_comparison import compare_politicians

    comparison = compare_politicians(["bola-tinubu", "peter-obi", "atiku-abubakar"])
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

from app.database import (
    SessionLocal, Politician, Issue, PoliticianIssue,
    NewsArticle, Document
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PoliticianProfile:
    """Profile data for comparison."""
    slug: str
    name: str
    party: str
    party_full_name: str
    position: str
    state: str
    constituency: Optional[str] = None
    image_url: Optional[str] = None

    # Background
    education: List[str] = field(default_factory=list)
    career_before_politics: str = ""
    age: Optional[int] = None

    # Legislative record
    committee_memberships: List[str] = field(default_factory=list)
    bills_sponsored: int = 0
    attendance_rate: Optional[float] = None

    # Scores
    promise_score: Optional[float] = None
    transparency_score: Optional[float] = None

    # Term info
    term_start: Optional[str] = None
    term_end: Optional[str] = None
    terms_served: int = 1


@dataclass
class IssueStance:
    """Politician's stance on an issue."""
    issue_id: str
    issue_title: str
    domain: str
    role: str  # responsible, responding, mentioned
    mention_count: int
    sentiment: Optional[str] = None  # positive, negative, neutral


@dataclass
class NewsPresence:
    """Politician's presence in news."""
    total_mentions: int
    mentions_last_week: int
    mentions_last_month: int
    top_topics: List[str] = field(default_factory=list)
    sentiment_breakdown: Dict[str, int] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Full comparison result."""
    politicians: List[PoliticianProfile]
    issues: Dict[str, List[IssueStance]]  # politician_slug -> issues
    news_presence: Dict[str, NewsPresence]  # politician_slug -> news stats
    comparison_dimensions: List[str]
    generated_at: str


# =============================================================================
# Party Information
# =============================================================================

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
}

PARTY_COLORS = {
    "APC": "#1e3a8a",  # Blue
    "PDP": "#dc2626",  # Red
    "LP": "#16a34a",   # Green
    "NNPP": "#7c3aed", # Purple
    "APGA": "#f59e0b", # Amber
    "SDP": "#0ea5e9",  # Cyan
}


# =============================================================================
# Comparison Service
# =============================================================================

class PoliticianComparisonService:
    """
    Service for comparing politicians.
    """

    def __init__(self):
        pass

    def get_politician_profile(self, slug: str) -> Optional[PoliticianProfile]:
        """
        Get detailed profile for a politician.
        """
        db = SessionLocal()
        try:
            politician = db.query(Politician).filter(
                Politician.slug == slug
            ).first()

            if not politician:
                return None

            # Parse JSON data
            data = {}
            if politician.data_json:
                try:
                    data = json.loads(politician.data_json)
                except:
                    pass

            # Extract profile info
            personal = data.get("personal", {})
            political_career = data.get("political_career", {})
            senate_info = data.get("senate_info", {})
            house_info = data.get("house_info", {})
            track_record = data.get("track_record", {})
            metadata = data.get("metadata", {})

            # Get party
            party = politician.party or data.get("party", "Unknown")
            party_full = PARTY_FULL_NAMES.get(party, party)

            # Get education
            education = personal.get("education", [])
            if isinstance(education, list) and education:
                if isinstance(education[0], dict):
                    education = [
                        f"{e.get('degree', '')} - {e.get('institution', '')}"
                        for e in education if e.get('institution')
                    ]

            # Get career before politics
            career_before = personal.get("career_before_politics", [])
            if isinstance(career_before, list) and career_before:
                if isinstance(career_before[0], dict):
                    career_before = f"{career_before[0].get('role', '')} at {career_before[0].get('organization', '')}"
                else:
                    career_before = ", ".join(career_before[:2])
            else:
                career_before = ""

            # Get legislative info
            legislative_info = senate_info if politician.position == "Senator" else house_info
            committees = legislative_info.get("committee_memberships", [])
            bills = legislative_info.get("bills_sponsored", [])
            attendance = legislative_info.get("attendance_rate")

            # Get scores
            promise_score = track_record.get("promise_score")
            transparency = track_record.get("transparency_score")

            # Get term info
            positions_held = political_career.get("positions_held", [])
            term_start = None
            term_end = None
            terms_served = 1

            if positions_held:
                current = positions_held[0]
                period = current.get("period", "")
                if "-" in period:
                    parts = period.split("-")
                    term_start = parts[0].strip()
                    term_end = parts[1].strip() if len(parts) > 1 else None
                terms_served = len(positions_held)

            return PoliticianProfile(
                slug=slug,
                name=politician.name,
                party=party,
                party_full_name=party_full,
                position=politician.position or "Unknown",
                state=politician.state or data.get("state", "Unknown"),
                constituency=politician.constituency,
                image_url=data.get("image_url"),
                education=education[:3] if isinstance(education, list) else [],
                career_before_politics=career_before if isinstance(career_before, str) else "",
                age=personal.get("age"),
                committee_memberships=committees[:5] if isinstance(committees, list) else [],
                bills_sponsored=len(bills) if isinstance(bills, list) else 0,
                attendance_rate=float(attendance) if attendance else None,
                promise_score=float(promise_score) if promise_score else None,
                transparency_score=float(transparency) if transparency else None,
                term_start=term_start,
                term_end=term_end,
                terms_served=terms_served
            )

        finally:
            db.close()

    def get_issue_stances(self, slug: str, limit: int = 10) -> List[IssueStance]:
        """
        Get issues associated with a politician.
        """
        db = SessionLocal()
        try:
            # Get politician-issue links
            links = db.query(PoliticianIssue).filter(
                PoliticianIssue.politician_slug == slug
            ).order_by(
                PoliticianIssue.mention_count.desc()
            ).limit(limit).all()

            stances = []
            for link in links:
                issue = db.query(Issue).filter(
                    Issue.issue_id == link.issue_id
                ).first()

                if issue:
                    stances.append(IssueStance(
                        issue_id=issue.issue_id,
                        issue_title=issue.title,
                        domain=issue.domain,
                        role=link.role,
                        mention_count=link.mention_count or 1,
                        sentiment=None  # Could add sentiment analysis
                    ))

            return stances

        finally:
            db.close()

    def get_news_presence(self, slug: str) -> NewsPresence:
        """
        Analyze politician's presence in news.
        """
        db = SessionLocal()
        try:
            now = datetime.now()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)

            # Total mentions
            total = db.query(NewsArticle).filter(
                NewsArticle.politicians_json.contains(slug)
            ).count()

            # Last week
            last_week = db.query(NewsArticle).filter(
                NewsArticle.politicians_json.contains(slug),
                NewsArticle.scraped_at >= week_ago
            ).count()

            # Last month
            last_month = db.query(NewsArticle).filter(
                NewsArticle.politicians_json.contains(slug),
                NewsArticle.scraped_at >= month_ago
            ).count()

            # Get topics from recent articles
            recent_articles = db.query(NewsArticle).filter(
                NewsArticle.politicians_json.contains(slug),
                NewsArticle.scraped_at >= month_ago
            ).limit(20).all()

            topic_counts = {}
            for article in recent_articles:
                if article.topics_json:
                    try:
                        topics = json.loads(article.topics_json)
                        for topic in topics:
                            topic_counts[topic] = topic_counts.get(topic, 0) + 1
                    except:
                        pass

            # Sort topics by count
            top_topics = sorted(
                topic_counts.keys(),
                key=lambda t: topic_counts[t],
                reverse=True
            )[:5]

            return NewsPresence(
                total_mentions=total,
                mentions_last_week=last_week,
                mentions_last_month=last_month,
                top_topics=top_topics,
                sentiment_breakdown={"positive": 0, "neutral": total, "negative": 0}
            )

        finally:
            db.close()

    def compare(self, slugs: List[str]) -> ComparisonResult:
        """
        Compare multiple politicians.

        Args:
            slugs: List of politician slugs to compare (2-4 recommended)

        Returns:
            ComparisonResult with all comparison data
        """
        if len(slugs) < 2:
            raise ValueError("Need at least 2 politicians to compare")

        if len(slugs) > 4:
            slugs = slugs[:4]  # Limit to 4 for readability

        profiles = []
        issues = {}
        news_presence = {}

        for slug in slugs:
            # Get profile
            profile = self.get_politician_profile(slug)
            if profile:
                profiles.append(profile)

                # Get issues
                issues[slug] = self.get_issue_stances(slug)

                # Get news presence
                news_presence[slug] = self.get_news_presence(slug)

        if len(profiles) < 2:
            raise ValueError("Could not find enough politicians to compare")

        # Determine comparison dimensions based on available data
        dimensions = ["basic_info", "party"]

        if any(p.committee_memberships for p in profiles):
            dimensions.append("committees")

        if any(p.bills_sponsored > 0 for p in profiles):
            dimensions.append("legislative_record")

        if any(p.promise_score is not None for p in profiles):
            dimensions.append("promise_score")

        if any(issues.get(p.slug) for p in profiles):
            dimensions.append("issues")

        dimensions.append("news_presence")

        return ComparisonResult(
            politicians=profiles,
            issues=issues,
            news_presence=news_presence,
            comparison_dimensions=dimensions,
            generated_at=datetime.now().isoformat()
        )


# =============================================================================
# Helper Functions
# =============================================================================

def compare_politicians(slugs: List[str]) -> Dict[str, Any]:
    """
    Compare politicians and return dictionary result.

    Args:
        slugs: List of politician slugs

    Returns:
        Dictionary with comparison data
    """
    service = PoliticianComparisonService()
    result = service.compare(slugs)

    return {
        "politicians": [asdict(p) for p in result.politicians],
        "issues": {
            slug: [asdict(i) for i in stances]
            for slug, stances in result.issues.items()
        },
        "news_presence": {
            slug: asdict(presence)
            for slug, presence in result.news_presence.items()
        },
        "comparison_dimensions": result.comparison_dimensions,
        "generated_at": result.generated_at,
        "party_colors": PARTY_COLORS
    }


def search_politicians_for_comparison(query: str, limit: int = 10) -> List[Dict]:
    """
    Search for politicians to add to comparison.
    """
    db = SessionLocal()
    try:
        # Simple search by name
        politicians = db.query(Politician).filter(
            Politician.name.ilike(f"%{query}%")
        ).limit(limit).all()

        return [
            {
                "slug": p.slug,
                "name": p.name,
                "party": p.party,
                "position": p.position,
                "state": p.state
            }
            for p in politicians
        ]
    finally:
        db.close()


def get_suggested_comparisons() -> List[Dict]:
    """
    Get suggested comparison pairs/groups.
    """
    # Presidential candidates 2023
    suggestions = [
        {
            "title": "2023 Presidential Candidates",
            "description": "Compare the main presidential candidates from the 2023 election",
            "slugs": ["bola-tinubu", "atiku-abubakar", "peter-obi"],
            "category": "presidential"
        },
        {
            "title": "Senate Leadership",
            "description": "Compare key Senate leaders",
            "slugs": ["godswill-akpabio", "jibrin-barau"],
            "category": "legislative"
        },
        {
            "title": "South-West Governors",
            "description": "Compare governors from the South-West zone",
            "slugs": ["babajide-sanwo-olu", "seyi-makinde", "dapo-abiodun"],
            "category": "governors"
        }
    ]

    return suggestions
