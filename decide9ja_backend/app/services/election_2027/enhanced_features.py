"""
Election 2027 Enhanced Features for Decide9ja.

Adds:
1. Candidate Matcher - Match users with candidates based on issue stances
2. Debate Tracker - Track, summarize, and analyze election debates
3. Poll Aggregator - Aggregate polls from multiple sources with weighting

Usage:
    from app.services.election_2027.enhanced_features import (
        CandidateMatcher,
        DebateTracker,
        PollAggregator
    )

    matcher = CandidateMatcher()
    matches = matcher.match_user(user_stances)

    debates = DebateTracker()
    upcoming = debates.get_upcoming_debates()

    aggregator = PollAggregator()
    national_avg = aggregator.get_national_polling_average("president")
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib

from app.database import SessionLocal, Politician

logger = logging.getLogger(__name__)


# =============================================================================
# Issue Stances for Candidate Matching
# =============================================================================

# Key issues for the 2027 election
ELECTION_ISSUES = [
    {
        "id": "economy",
        "name": "Economy & Inflation",
        "description": "Managing inflation, exchange rates, and economic growth",
        "positions": [
            {"id": "market_free", "label": "Free market approach", "description": "Reduce government intervention, lower taxes"},
            {"id": "market_mixed", "label": "Mixed economy", "description": "Balance government support with private enterprise"},
            {"id": "market_interventionist", "label": "Strong government intervention", "description": "Price controls, subsidies, direct government investment"}
        ]
    },
    {
        "id": "security",
        "name": "Security & Insurgency",
        "description": "Addressing Boko Haram, banditry, and general security",
        "positions": [
            {"id": "security_military", "label": "Military solution", "description": "Stronger military action, no negotiation"},
            {"id": "security_balanced", "label": "Balanced approach", "description": "Military action with dialogue and rehabilitation"},
            {"id": "security_dialogue", "label": "Dialogue-first", "description": "Prioritize negotiation and addressing root causes"}
        ]
    },
    {
        "id": "restructuring",
        "name": "Restructuring & Federalism",
        "description": "State autonomy, fiscal federalism, devolution of power",
        "positions": [
            {"id": "restructure_yes", "label": "Full restructuring", "description": "True federalism, state police, resource control"},
            {"id": "restructure_moderate", "label": "Moderate reforms", "description": "Some devolution while maintaining federal structure"},
            {"id": "restructure_no", "label": "Maintain current structure", "description": "Keep current federal system with minor adjustments"}
        ]
    },
    {
        "id": "corruption",
        "name": "Anti-Corruption",
        "description": "Fighting corruption and improving transparency",
        "positions": [
            {"id": "corruption_aggressive", "label": "Aggressive prosecution", "description": "Strong agencies, swift prosecution, asset recovery"},
            {"id": "corruption_systemic", "label": "Systemic reform", "description": "Focus on preventing corruption through institutional reform"},
            {"id": "corruption_balanced", "label": "Balanced approach", "description": "Both prosecution and prevention measures"}
        ]
    },
    {
        "id": "education",
        "name": "Education",
        "description": "Improving education access and quality",
        "positions": [
            {"id": "edu_public", "label": "Public education focus", "description": "Free education, massive public investment"},
            {"id": "edu_mixed", "label": "Public-private partnership", "description": "Government funding with private sector involvement"},
            {"id": "edu_privatize", "label": "Encourage private schools", "description": "Vouchers, reduce bureaucracy, competition"}
        ]
    },
    {
        "id": "healthcare",
        "name": "Healthcare",
        "description": "Health system reform and access",
        "positions": [
            {"id": "health_universal", "label": "Universal healthcare", "description": "Government-funded healthcare for all"},
            {"id": "health_insurance", "label": "Insurance-based", "description": "Mandatory health insurance with government subsidies"},
            {"id": "health_mixed", "label": "Mixed system", "description": "Improve public facilities while supporting private providers"}
        ]
    },
    {
        "id": "power",
        "name": "Power & Energy",
        "description": "Solving the electricity crisis",
        "positions": [
            {"id": "power_privatize", "label": "Full privatization", "description": "Complete privatization and deregulation"},
            {"id": "power_mixed", "label": "Mixed approach", "description": "Public-private partnerships, targeted subsidies"},
            {"id": "power_nationalize", "label": "Government control", "description": "Return to government control with massive investment"}
        ]
    },
    {
        "id": "youth",
        "name": "Youth & Employment",
        "description": "Addressing youth unemployment and engagement",
        "positions": [
            {"id": "youth_entrepreneurship", "label": "Entrepreneurship focus", "description": "Loans, training, startup support"},
            {"id": "youth_jobs", "label": "Direct job creation", "description": "Government programs, public works, employment quotas"},
            {"id": "youth_skills", "label": "Skills development", "description": "TVET, apprenticeships, industry partnerships"}
        ]
    }
]

# Candidate positions (simplified - would be from database in production)
CANDIDATE_POSITIONS = {
    "bola-tinubu": {
        "economy": "market_mixed",
        "security": "security_military",
        "restructuring": "restructure_no",
        "corruption": "corruption_balanced",
        "education": "edu_mixed",
        "healthcare": "health_insurance",
        "power": "power_privatize",
        "youth": "youth_entrepreneurship"
    },
    "peter-obi": {
        "economy": "market_mixed",
        "security": "security_balanced",
        "restructuring": "restructure_yes",
        "corruption": "corruption_aggressive",
        "education": "edu_public",
        "healthcare": "health_universal",
        "power": "power_mixed",
        "youth": "youth_skills"
    },
    "atiku-abubakar": {
        "economy": "market_free",
        "security": "security_balanced",
        "restructuring": "restructure_yes",
        "corruption": "corruption_systemic",
        "education": "edu_mixed",
        "healthcare": "health_mixed",
        "power": "power_privatize",
        "youth": "youth_jobs"
    },
    "rabiu-kwankwaso": {
        "economy": "market_interventionist",
        "security": "security_dialogue",
        "restructuring": "restructure_moderate",
        "corruption": "corruption_balanced",
        "education": "edu_public",
        "healthcare": "health_universal",
        "power": "power_mixed",
        "youth": "youth_jobs"
    }
}


# =============================================================================
# Candidate Matcher
# =============================================================================

@dataclass
class CandidateMatch:
    """Result of matching a user with a candidate."""
    slug: str
    name: str
    party: str
    position: str
    match_percentage: float
    matching_issues: List[str]
    differing_issues: List[str]
    key_agreements: List[Dict[str, str]]
    key_disagreements: List[Dict[str, str]]


class CandidateMatcher:
    """
    Matches users with candidates based on issue stances.

    Users answer questions about their positions on key issues,
    and we find candidates that align with their views.
    """

    def __init__(self):
        self.issues = ELECTION_ISSUES
        self.candidate_positions = CANDIDATE_POSITIONS

    def get_quiz_questions(self) -> List[Dict[str, Any]]:
        """
        Get the quiz questions for candidate matching.

        Returns list of issues with their position options.
        """
        return [
            {
                "id": issue["id"],
                "question": f"What is your position on {issue['name']}?",
                "description": issue["description"],
                "options": [
                    {
                        "id": pos["id"],
                        "label": pos["label"],
                        "description": pos["description"]
                    }
                    for pos in issue["positions"]
                ]
            }
            for issue in self.issues
        ]

    def match_user(
        self,
        user_stances: Dict[str, str],
        position: str = "president"
    ) -> List[CandidateMatch]:
        """
        Match user stances with candidates.

        Args:
            user_stances: Dict of issue_id -> position_id
            position: Position to filter by (president, governor, etc.)

        Returns:
            List of CandidateMatch sorted by match percentage
        """
        db = SessionLocal()
        try:
            matches = []

            for slug, candidate_stances in self.candidate_positions.items():
                # Get politician info
                politician = db.query(Politician).filter(
                    Politician.slug == slug
                ).first()

                if not politician:
                    continue

                # Calculate match
                total_issues = len(user_stances)
                matching_issues = []
                differing_issues = []
                key_agreements = []
                key_disagreements = []

                for issue_id, user_position in user_stances.items():
                    candidate_position = candidate_stances.get(issue_id)

                    if candidate_position == user_position:
                        matching_issues.append(issue_id)
                        issue_name = self._get_issue_name(issue_id)
                        position_label = self._get_position_label(issue_id, user_position)
                        key_agreements.append({
                            "issue": issue_name,
                            "position": position_label
                        })
                    else:
                        differing_issues.append(issue_id)
                        issue_name = self._get_issue_name(issue_id)
                        user_label = self._get_position_label(issue_id, user_position)
                        candidate_label = self._get_position_label(issue_id, candidate_position) if candidate_position else "Unknown"
                        key_disagreements.append({
                            "issue": issue_name,
                            "your_position": user_label,
                            "candidate_position": candidate_label
                        })

                match_percentage = (len(matching_issues) / total_issues * 100) if total_issues > 0 else 0

                matches.append(CandidateMatch(
                    slug=slug,
                    name=politician.name,
                    party=politician.party or "Unknown",
                    position=politician.position or "Presidential Candidate",
                    match_percentage=round(match_percentage, 1),
                    matching_issues=matching_issues,
                    differing_issues=differing_issues,
                    key_agreements=key_agreements[:3],  # Top 3
                    key_disagreements=key_disagreements[:3]
                ))

            # Sort by match percentage
            matches.sort(key=lambda m: m.match_percentage, reverse=True)
            return matches

        finally:
            db.close()

    def _get_issue_name(self, issue_id: str) -> str:
        """Get human-readable issue name."""
        for issue in self.issues:
            if issue["id"] == issue_id:
                return issue["name"]
        return issue_id

    def _get_position_label(self, issue_id: str, position_id: str) -> str:
        """Get human-readable position label."""
        for issue in self.issues:
            if issue["id"] == issue_id:
                for pos in issue["positions"]:
                    if pos["id"] == position_id:
                        return pos["label"]
        return position_id

    def get_candidate_stance_card(self, slug: str) -> Dict[str, Any]:
        """
        Get a candidate's stance on all issues.

        Returns formatted card for display.
        """
        stances = self.candidate_positions.get(slug, {})

        formatted_stances = []
        for issue in self.issues:
            position_id = stances.get(issue["id"])
            position_label = "No position stated"
            position_desc = ""

            for pos in issue["positions"]:
                if pos["id"] == position_id:
                    position_label = pos["label"]
                    position_desc = pos["description"]
                    break

            formatted_stances.append({
                "issue": issue["name"],
                "position": position_label,
                "description": position_desc
            })

        return {
            "slug": slug,
            "stances": formatted_stances
        }


# =============================================================================
# Debate Tracker
# =============================================================================

@dataclass
class Debate:
    """Election debate information."""
    debate_id: str
    title: str
    date: datetime
    location: str
    organizer: str
    position: str  # president, governor, etc.
    state: Optional[str]  # For state-level debates
    participants: List[str]  # Candidate slugs
    format: str  # town_hall, moderated, one_on_one
    topics: List[str]
    status: str  # scheduled, ongoing, completed, cancelled
    stream_url: Optional[str]
    summary: Optional[str]
    key_moments: List[Dict[str, Any]] = field(default_factory=list)
    fact_checks: List[Dict[str, Any]] = field(default_factory=list)


class DebateTracker:
    """
    Tracks election debates, provides summaries and analysis.
    """

    def __init__(self):
        # In production, this would be from database
        self.debates = self._load_sample_debates()

    def _load_sample_debates(self) -> Dict[str, Debate]:
        """Load sample debate data."""
        return {
            "pres-debate-1-2027": Debate(
                debate_id="pres-debate-1-2027",
                title="First Presidential Debate 2027",
                date=datetime(2027, 1, 15, 19, 0),
                location="Lagos",
                organizer="Nigerian Election Debate Group (NEDG)",
                position="president",
                state=None,
                participants=["bola-tinubu", "peter-obi", "atiku-abubakar", "rabiu-kwankwaso"],
                format="moderated",
                topics=["Economy", "Security", "Education", "Healthcare"],
                status="scheduled",
                stream_url=None,
                summary=None
            ),
            "pres-debate-2-2027": Debate(
                debate_id="pres-debate-2-2027",
                title="Second Presidential Debate 2027",
                date=datetime(2027, 1, 25, 19, 0),
                location="Abuja",
                organizer="Nigerian Election Debate Group (NEDG)",
                position="president",
                state=None,
                participants=["bola-tinubu", "peter-obi", "atiku-abubakar", "rabiu-kwankwaso"],
                format="town_hall",
                topics=["Infrastructure", "Youth Employment", "Corruption", "Foreign Policy"],
                status="scheduled",
                stream_url=None,
                summary=None
            ),
            "vp-debate-2027": Debate(
                debate_id="vp-debate-2027",
                title="Vice Presidential Debate 2027",
                date=datetime(2027, 1, 20, 19, 0),
                location="Abuja",
                organizer="Nigerian Election Debate Group (NEDG)",
                position="vice_president",
                state=None,
                participants=[],  # Would be VP candidates
                format="moderated",
                topics=["Governance", "Economy", "Youth", "Social Services"],
                status="scheduled",
                stream_url=None,
                summary=None
            )
        }

    def get_upcoming_debates(
        self,
        position: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming debates.
        """
        now = datetime.now()
        upcoming = []

        for debate in self.debates.values():
            if debate.date > now and debate.status in ["scheduled", "ongoing"]:
                if position is None or debate.position == position:
                    upcoming.append(self._debate_to_dict(debate))

        upcoming.sort(key=lambda d: d["date"])
        return upcoming[:limit]

    def get_past_debates(
        self,
        position: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get past debates with summaries.
        """
        now = datetime.now()
        past = []

        for debate in self.debates.values():
            if debate.date <= now or debate.status == "completed":
                if position is None or debate.position == position:
                    past.append(self._debate_to_dict(debate))

        past.sort(key=lambda d: d["date"], reverse=True)
        return past[:limit]

    def get_debate(self, debate_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific debate.
        """
        debate = self.debates.get(debate_id)
        if debate:
            return self._debate_to_dict(debate, include_details=True)
        return None

    def get_debate_calendar(self, year: int = 2027) -> Dict[str, List[Dict]]:
        """
        Get debate calendar organized by month.
        """
        calendar = defaultdict(list)

        for debate in self.debates.values():
            if debate.date.year == year:
                month_key = debate.date.strftime("%Y-%m")
                calendar[month_key].append({
                    "debate_id": debate.debate_id,
                    "title": debate.title,
                    "date": debate.date.isoformat(),
                    "position": debate.position,
                    "status": debate.status
                })

        return dict(calendar)

    def add_debate_summary(
        self,
        debate_id: str,
        summary: str,
        key_moments: List[Dict] = None,
        fact_checks: List[Dict] = None
    ) -> bool:
        """
        Add summary and analysis to a completed debate.
        """
        debate = self.debates.get(debate_id)
        if not debate:
            return False

        debate.summary = summary
        debate.status = "completed"

        if key_moments:
            debate.key_moments = key_moments

        if fact_checks:
            debate.fact_checks = fact_checks

        return True

    def _debate_to_dict(self, debate: Debate, include_details: bool = False) -> Dict[str, Any]:
        """Convert Debate to dictionary."""
        result = {
            "debate_id": debate.debate_id,
            "title": debate.title,
            "date": debate.date.isoformat(),
            "location": debate.location,
            "organizer": debate.organizer,
            "position": debate.position,
            "state": debate.state,
            "participants": debate.participants,
            "format": debate.format,
            "topics": debate.topics,
            "status": debate.status,
            "stream_url": debate.stream_url
        }

        if include_details:
            result["summary"] = debate.summary
            result["key_moments"] = debate.key_moments
            result["fact_checks"] = debate.fact_checks

        return result


# =============================================================================
# Poll Aggregator
# =============================================================================

@dataclass
class PollSource:
    """Information about a polling source."""
    source_id: str
    name: str
    organization: str
    methodology: str  # telephone, online, face_to_face, mixed
    sample_size_typical: int
    credibility_rating: float  # 0-1, based on past accuracy
    lean: Optional[str]  # neutral, apc_lean, pdp_lean, etc.


@dataclass
class ExternalPoll:
    """A poll from an external source."""
    poll_id: str
    source_id: str
    title: str
    position: str  # president, governor, etc.
    state: Optional[str]
    date_conducted: datetime
    date_published: datetime
    sample_size: int
    margin_of_error: float
    results: Dict[str, float]  # candidate_slug -> percentage
    methodology: str
    url: Optional[str]


class PollAggregator:
    """
    Aggregates polls from multiple sources with weighting.

    Uses weighted averaging based on:
    - Recency (more recent polls weighted higher)
    - Sample size
    - Methodology quality
    - Source credibility
    """

    def __init__(self):
        self.sources = self._load_sources()
        self.polls = self._load_sample_polls()

        # Weighting factors
        self.recency_weight = 0.3
        self.sample_weight = 0.2
        self.methodology_weight = 0.2
        self.credibility_weight = 0.3

    def _load_sources(self) -> Dict[str, PollSource]:
        """Load polling sources."""
        return {
            "noi": PollSource(
                source_id="noi",
                name="NOI Polls",
                organization="NOI Polls Limited",
                methodology="mixed",
                sample_size_typical=2000,
                credibility_rating=0.85,
                lean="neutral"
            ),
            "cdd": PollSource(
                source_id="cdd",
                name="CDD Survey",
                organization="Centre for Democracy and Development",
                methodology="face_to_face",
                sample_size_typical=1500,
                credibility_rating=0.80,
                lean="neutral"
            ),
            "bloomberg": PollSource(
                source_id="bloomberg",
                name="Bloomberg Survey",
                organization="Bloomberg News",
                methodology="telephone",
                sample_size_typical=1000,
                credibility_rating=0.75,
                lean="neutral"
            ),
            "decide9ja": PollSource(
                source_id="decide9ja",
                name="Decide9ja Poll",
                organization="Decide9ja",
                methodology="online",
                sample_size_typical=5000,
                credibility_rating=0.70,
                lean="neutral"
            )
        }

    def _load_sample_polls(self) -> List[ExternalPoll]:
        """Load sample polls for demonstration."""
        now = datetime.now()
        return [
            ExternalPoll(
                poll_id="noi-pres-jan-2027",
                source_id="noi",
                title="Presidential Race January 2027",
                position="president",
                state=None,
                date_conducted=now - timedelta(days=5),
                date_published=now - timedelta(days=3),
                sample_size=2500,
                margin_of_error=2.5,
                results={
                    "bola-tinubu": 32.5,
                    "peter-obi": 28.3,
                    "atiku-abubakar": 22.1,
                    "rabiu-kwankwaso": 10.2,
                    "undecided": 6.9
                },
                methodology="mixed",
                url=None
            ),
            ExternalPoll(
                poll_id="cdd-pres-jan-2027",
                source_id="cdd",
                title="CDD Presidential Survey",
                position="president",
                state=None,
                date_conducted=now - timedelta(days=10),
                date_published=now - timedelta(days=7),
                sample_size=1800,
                margin_of_error=3.0,
                results={
                    "bola-tinubu": 30.1,
                    "peter-obi": 31.2,
                    "atiku-abubakar": 20.5,
                    "rabiu-kwankwaso": 11.8,
                    "undecided": 6.4
                },
                methodology="face_to_face",
                url=None
            ),
            ExternalPoll(
                poll_id="decide9ja-pres-jan-2027",
                source_id="decide9ja",
                title="Decide9ja User Poll",
                position="president",
                state=None,
                date_conducted=now - timedelta(days=1),
                date_published=now,
                sample_size=8500,
                margin_of_error=1.5,
                results={
                    "bola-tinubu": 28.5,
                    "peter-obi": 35.2,
                    "atiku-abubakar": 18.8,
                    "rabiu-kwankwaso": 12.5,
                    "undecided": 5.0
                },
                methodology="online",
                url=None
            )
        ]

    def get_polling_average(
        self,
        position: str = "president",
        state: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get weighted polling average.
        """
        cutoff = datetime.now() - timedelta(days=days)

        # Filter polls
        relevant_polls = [
            p for p in self.polls
            if p.position == position
            and (state is None or p.state == state)
            and p.date_conducted >= cutoff
        ]

        if not relevant_polls:
            return {"error": "No polls found for criteria"}

        # Calculate weights for each poll
        poll_weights = {}
        for poll in relevant_polls:
            weight = self._calculate_poll_weight(poll)
            poll_weights[poll.poll_id] = weight

        # Normalize weights
        total_weight = sum(poll_weights.values())
        for poll_id in poll_weights:
            poll_weights[poll_id] /= total_weight

        # Aggregate results
        aggregated = defaultdict(float)
        for poll in relevant_polls:
            weight = poll_weights[poll.poll_id]
            for candidate, percentage in poll.results.items():
                if candidate != "undecided":
                    aggregated[candidate] += percentage * weight

        # Sort by percentage
        sorted_results = sorted(
            aggregated.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Get candidate names
        db = SessionLocal()
        try:
            results_with_names = []
            for slug, pct in sorted_results:
                politician = db.query(Politician).filter(
                    Politician.slug == slug
                ).first()
                results_with_names.append({
                    "slug": slug,
                    "name": politician.name if politician else slug.replace("-", " ").title(),
                    "party": politician.party if politician else "Unknown",
                    "percentage": round(pct, 1)
                })
        finally:
            db.close()

        # Calculate average margin of error
        avg_moe = sum(p.margin_of_error for p in relevant_polls) / len(relevant_polls)

        return {
            "position": position,
            "state": state,
            "period_days": days,
            "polls_included": len(relevant_polls),
            "average_margin_of_error": round(avg_moe, 1),
            "results": results_with_names,
            "polls": [
                {
                    "poll_id": p.poll_id,
                    "source": self.sources[p.source_id].name,
                    "date": p.date_conducted.isoformat(),
                    "sample_size": p.sample_size,
                    "weight": round(poll_weights[p.poll_id] * 100, 1)
                }
                for p in relevant_polls
            ],
            "last_updated": datetime.now().isoformat()
        }

    def _calculate_poll_weight(self, poll: ExternalPoll) -> float:
        """
        Calculate weight for a poll based on various factors.
        """
        source = self.sources.get(poll.source_id)
        if not source:
            return 0.5

        # Recency score (0-1, higher for more recent)
        days_ago = (datetime.now() - poll.date_conducted).days
        recency_score = max(0, 1 - (days_ago / 30))

        # Sample size score (normalized to typical range 1000-5000)
        sample_score = min(1.0, poll.sample_size / 3000)

        # Methodology score
        methodology_scores = {
            "face_to_face": 1.0,
            "mixed": 0.9,
            "telephone": 0.8,
            "online": 0.6
        }
        methodology_score = methodology_scores.get(poll.methodology, 0.5)

        # Credibility score from source
        credibility_score = source.credibility_rating

        # Weighted combination
        weight = (
            self.recency_weight * recency_score +
            self.sample_weight * sample_score +
            self.methodology_weight * methodology_score +
            self.credibility_weight * credibility_score
        )

        return weight

    def get_trend(
        self,
        candidate_slug: str,
        position: str = "president",
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Get polling trend for a specific candidate.
        """
        cutoff = datetime.now() - timedelta(days=days)

        trend_data = []
        for poll in self.polls:
            if poll.position == position and poll.date_conducted >= cutoff:
                if candidate_slug in poll.results:
                    trend_data.append({
                        "date": poll.date_conducted.isoformat(),
                        "source": self.sources[poll.source_id].name,
                        "percentage": poll.results[candidate_slug]
                    })

        trend_data.sort(key=lambda x: x["date"])
        return trend_data

    def get_sources(self) -> List[Dict[str, Any]]:
        """
        Get information about polling sources.
        """
        return [
            {
                "source_id": s.source_id,
                "name": s.name,
                "organization": s.organization,
                "methodology": s.methodology,
                "credibility_rating": s.credibility_rating
            }
            for s in self.sources.values()
        ]

    def add_poll(self, poll_data: Dict[str, Any]) -> str:
        """
        Add a new external poll to the aggregator.
        """
        poll_id = f"{poll_data['source_id']}-{poll_data['position']}-{datetime.now().strftime('%Y%m%d')}"

        poll = ExternalPoll(
            poll_id=poll_id,
            source_id=poll_data["source_id"],
            title=poll_data.get("title", "Poll"),
            position=poll_data["position"],
            state=poll_data.get("state"),
            date_conducted=datetime.fromisoformat(poll_data["date_conducted"]),
            date_published=datetime.now(),
            sample_size=poll_data["sample_size"],
            margin_of_error=poll_data.get("margin_of_error", 3.0),
            results=poll_data["results"],
            methodology=poll_data.get("methodology", "unknown"),
            url=poll_data.get("url")
        )

        self.polls.append(poll)
        return poll_id


# =============================================================================
# Helper Functions
# =============================================================================

def get_candidate_matcher() -> CandidateMatcher:
    """Get singleton matcher instance."""
    return CandidateMatcher()


def get_debate_tracker() -> DebateTracker:
    """Get singleton debate tracker instance."""
    return DebateTracker()


def get_poll_aggregator() -> PollAggregator:
    """Get singleton poll aggregator instance."""
    return PollAggregator()
