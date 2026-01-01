"""
Candidate Tracking System
=========================

System for tracking 2027 election candidates.

Features:
1. Candidate profiles with full details
2. Follow/unfollow candidates
3. Get updates on followed candidates
4. Compare candidates side-by-side
5. Track candidate sentiment and mentions
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib


@dataclass
class CandidateProfile:
    """A 2027 candidate profile."""
    id: str
    name: str
    party: str
    party_full: str
    position_sought: str  # president, governor, senator

    # Location (for state/local candidates)
    state: Optional[str] = None
    constituency: Optional[str] = None

    # Bio
    photo_url: Optional[str] = None
    bio_short: str = ""
    age: Optional[int] = None
    state_of_origin: Optional[str] = None
    religion: Optional[str] = None

    # Political
    is_incumbent: bool = False
    previous_positions: List[str] = field(default_factory=list)
    key_policies: List[str] = field(default_factory=list)
    campaign_slogan: Optional[str] = None

    # Social
    twitter: Optional[str] = None
    website: Optional[str] = None

    # Analytics (updated by agent)
    sentiment_score: float = 0.0
    mention_count_7d: int = 0
    trending: bool = False
    latest_news: List[Dict] = field(default_factory=list)


# === SAMPLE CANDIDATES ===

SAMPLE_CANDIDATES = {
    "tinubu": CandidateProfile(
        id="tinubu",
        name="Bola Ahmed Tinubu",
        party="APC",
        party_full="All Progressives Congress",
        position_sought="president",
        bio_short="16th President of Nigeria. Former Lagos State Governor (1999-2007). Known as 'Jagaban' and national leader of APC.",
        age=73,
        state_of_origin="Lagos",
        religion="Muslim",
        is_incumbent=True,
        previous_positions=["Governor of Lagos (1999-2007)", "Senator (1992-1993)"],
        key_policies=[
            "Renewed Hope Agenda",
            "Fuel subsidy removal",
            "Naira float",
            "Student loan scheme",
            "Tax reform"
        ],
        campaign_slogan="Renewed Hope",
        twitter="@officialABAT",
        sentiment_score=0.15,
        mention_count_7d=450
    ),

    "atiku": CandidateProfile(
        id="atiku",
        name="Atiku Abubakar",
        party="PDP",
        party_full="Peoples Democratic Party",
        position_sought="president",
        bio_short="Former Vice President of Nigeria (1999-2007). Businessman and perennial presidential candidate since 2007.",
        age=78,
        state_of_origin="Adamawa",
        religion="Muslim",
        is_incumbent=False,
        previous_positions=["Vice President (1999-2007)", "Customs Officer"],
        key_policies=[
            "Private sector-led economy",
            "Restructuring Nigeria",
            "Education investment",
            "Fighting corruption"
        ],
        campaign_slogan="Let's Get Nigeria Working Again",
        twitter="@atikiAbubakar",
        sentiment_score=0.05,
        mention_count_7d=180
    ),

    "obi": CandidateProfile(
        id="obi",
        name="Peter Obi",
        party="LP",
        party_full="Labour Party",
        position_sought="president",
        bio_short="Former Anambra State Governor (2006-2014). Rose to prominence in 2023 with 'Obidient' youth movement.",
        age=63,
        state_of_origin="Anambra",
        religion="Catholic",
        is_incumbent=False,
        previous_positions=["Governor of Anambra (2006-2014)", "Businessman"],
        key_policies=[
            "Production economy over consumption",
            "Security sector reform",
            "Education and health focus",
            "Reduced governance costs"
        ],
        campaign_slogan="Take Back Nigeria",
        twitter="@PeterObi",
        sentiment_score=0.35,
        mention_count_7d=320
    ),

    "kwankwaso": CandidateProfile(
        id="kwankwaso",
        name="Rabiu Kwankwaso",
        party="NNPP",
        party_full="New Nigeria Peoples Party",
        position_sought="president",
        bio_short="Former Kano State Governor (1999-2003, 2011-2015). Former Senator and Minister. Leader of Kwankwasiyya movement.",
        age=68,
        state_of_origin="Kano",
        religion="Muslim",
        is_incumbent=False,
        previous_positions=["Governor of Kano (twice)", "Senator", "Defence Minister"],
        key_policies=[
            "Free education",
            "Infrastructure development",
            "Youth empowerment",
            "Agricultural revolution"
        ],
        campaign_slogan="New Nigeria",
        twitter="@KwsOfficial",
        sentiment_score=0.1,
        mention_count_7d=90
    ),
}


class CandidateTracker:
    """
    System for tracking and following candidates.
    """

    def __init__(self, db_session=None):
        self.db = db_session
        self.candidates = SAMPLE_CANDIDATES.copy()
        self.user_follows = {}  # user_hash -> [candidate_ids]

    # === CANDIDATE LOOKUP ===

    def get_candidate(self, candidate_id: str) -> Optional[CandidateProfile]:
        """Get a candidate by ID."""
        return self.candidates.get(candidate_id)

    def search_candidates(
        self,
        query: str = None,
        position: str = None,
        party: str = None,
        state: str = None
    ) -> List[CandidateProfile]:
        """Search candidates by various criteria."""
        results = list(self.candidates.values())

        if query:
            query_lower = query.lower()
            results = [
                c for c in results
                if query_lower in c.name.lower()
                or query_lower in c.party.lower()
                or query_lower in c.bio_short.lower()
            ]

        if position:
            results = [c for c in results if c.position_sought == position]

        if party:
            results = [c for c in results if c.party.lower() == party.lower()]

        if state:
            results = [c for c in results if c.state and c.state.lower() == state.lower()]

        return results

    def get_presidential_candidates(self) -> List[CandidateProfile]:
        """Get all presidential candidates."""
        return self.search_candidates(position="president")

    def get_gubernatorial_candidates(self, state: str) -> List[CandidateProfile]:
        """Get gubernatorial candidates for a state."""
        return self.search_candidates(position="governor", state=state)

    # === FOLLOW SYSTEM ===

    def follow_candidate(self, user_phone: str, candidate_id: str) -> Tuple[bool, str]:
        """Follow a candidate."""
        user_hash = hashlib.sha256(user_phone.encode()).hexdigest()

        if candidate_id not in self.candidates:
            return False, "Candidate not found"

        if user_hash not in self.user_follows:
            self.user_follows[user_hash] = []

        if candidate_id in self.user_follows[user_hash]:
            return False, f"You're already following {self.candidates[candidate_id].name}"

        self.user_follows[user_hash].append(candidate_id)
        candidate = self.candidates[candidate_id]
        return True, f"✅ You're now following {candidate.name} ({candidate.party}). I'll send you updates!"

    def unfollow_candidate(self, user_phone: str, candidate_id: str) -> Tuple[bool, str]:
        """Unfollow a candidate."""
        user_hash = hashlib.sha256(user_phone.encode()).hexdigest()

        if user_hash not in self.user_follows:
            return False, "You're not following any candidates"

        if candidate_id not in self.user_follows[user_hash]:
            return False, "You're not following this candidate"

        self.user_follows[user_hash].remove(candidate_id)
        candidate = self.candidates.get(candidate_id)
        name = candidate.name if candidate else candidate_id
        return True, f"You've unfollowed {name}"

    def get_followed_candidates(self, user_phone: str) -> List[CandidateProfile]:
        """Get candidates a user is following."""
        user_hash = hashlib.sha256(user_phone.encode()).hexdigest()
        candidate_ids = self.user_follows.get(user_hash, [])
        return [self.candidates[cid] for cid in candidate_ids if cid in self.candidates]

    def is_following(self, user_phone: str, candidate_id: str) -> bool:
        """Check if user is following a candidate."""
        user_hash = hashlib.sha256(user_phone.encode()).hexdigest()
        return candidate_id in self.user_follows.get(user_hash, [])

    # === COMPARISON ===

    def compare_candidates(self, candidate_ids: List[str]) -> Dict:
        """Compare multiple candidates side by side."""
        candidates = [self.get_candidate(cid) for cid in candidate_ids]
        candidates = [c for c in candidates if c]

        if len(candidates) < 2:
            return {"error": "Need at least 2 candidates to compare"}

        comparison = {
            "candidates": [
                {
                    "id": c.id,
                    "name": c.name,
                    "party": c.party,
                    "age": c.age,
                    "state_of_origin": c.state_of_origin,
                    "key_policies": c.key_policies[:3],
                    "is_incumbent": c.is_incumbent,
                    "sentiment_score": c.sentiment_score,
                    "mention_count_7d": c.mention_count_7d
                }
                for c in candidates
            ]
        }

        return comparison

    # === FORMATTING ===

    def format_candidate_profile(self, candidate: CandidateProfile) -> str:
        """Format candidate profile for WhatsApp."""
        emoji = "🟢" if candidate.party == "APC" else "🔴" if candidate.party == "PDP" else "🟡"

        text = f"{emoji} *{candidate.name}*\n"
        text += f"Party: {candidate.party_full}\n"
        text += f"Position: {candidate.position_sought.title()}\n\n"

        text += f"📝 {candidate.bio_short}\n\n"

        if candidate.key_policies:
            text += "*Key Policies:*\n"
            for policy in candidate.key_policies[:4]:
                text += f"• {policy}\n"
            text += "\n"

        if candidate.previous_positions:
            text += "*Previous Positions:*\n"
            for pos in candidate.previous_positions[:3]:
                text += f"• {pos}\n"
            text += "\n"

        # Sentiment indicator
        if candidate.sentiment_score > 0.2:
            sentiment_emoji = "📈 Positive"
        elif candidate.sentiment_score < -0.2:
            sentiment_emoji = "📉 Negative"
        else:
            sentiment_emoji = "➡️ Mixed"

        text += f"*Current Sentiment:* {sentiment_emoji}\n"
        text += f"*Mentions (7 days):* {candidate.mention_count_7d:,}\n"

        if candidate.twitter:
            text += f"\nTwitter: {candidate.twitter}"

        return text

    def format_comparison(self, comparison: Dict) -> str:
        """Format comparison for WhatsApp."""
        if "error" in comparison:
            return comparison["error"]

        candidates = comparison["candidates"]

        text = "📊 *Candidate Comparison*\n\n"

        for c in candidates:
            emoji = "🟢" if c["party"] == "APC" else "🔴" if c["party"] == "PDP" else "🟡"
            text += f"{emoji} *{c['name']}* ({c['party']})\n"
            text += f"   Age: {c['age'] or 'N/A'}\n"
            text += f"   From: {c['state_of_origin'] or 'N/A'}\n"
            text += f"   Incumbent: {'Yes' if c['is_incumbent'] else 'No'}\n"
            text += f"   Mentions: {c['mention_count_7d']:,}\n\n"

        text += "Reply 'policies' to compare their policies."
        return text

    def format_followed_list(self, candidates: List[CandidateProfile]) -> str:
        """Format followed candidates list."""
        if not candidates:
            return "You're not following any candidates yet.\n\nTry: 'Follow Tinubu' or 'Follow Peter Obi'"

        text = "📌 *Candidates You're Following*\n\n"

        for c in candidates:
            emoji = "🟢" if c.party == "APC" else "🔴" if c.party == "PDP" else "🟡"
            trending = "🔥" if c.trending else ""
            text += f"{emoji} {c.name} ({c.party}) {trending}\n"

        text += "\nSay a candidate's name for latest updates."
        return text


# === CONVENIENCE FUNCTIONS ===

_tracker_instance = None

def get_candidate_tracker() -> CandidateTracker:
    """Get or create tracker singleton."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = CandidateTracker()
    return _tracker_instance


def get_candidate(name_or_id: str) -> Optional[CandidateProfile]:
    """Get candidate by name or ID."""
    tracker = get_candidate_tracker()

    # Try direct ID
    candidate = tracker.get_candidate(name_or_id.lower())
    if candidate:
        return candidate

    # Try search
    results = tracker.search_candidates(query=name_or_id)
    return results[0] if results else None


def follow(user_phone: str, candidate_name: str) -> str:
    """Follow a candidate."""
    tracker = get_candidate_tracker()
    candidate = get_candidate(candidate_name)

    if not candidate:
        return f"I couldn't find a candidate matching '{candidate_name}'. Try the full name."

    success, message = tracker.follow_candidate(user_phone, candidate.id)
    return message


def get_my_candidates(user_phone: str) -> str:
    """Get user's followed candidates."""
    tracker = get_candidate_tracker()
    candidates = tracker.get_followed_candidates(user_phone)
    return tracker.format_followed_list(candidates)


def compare(names: List[str]) -> str:
    """Compare candidates."""
    tracker = get_candidate_tracker()
    ids = []

    for name in names:
        candidate = get_candidate(name)
        if candidate:
            ids.append(candidate.id)

    if len(ids) < 2:
        return "I need at least 2 valid candidate names to compare."

    comparison = tracker.compare_candidates(ids)
    return tracker.format_comparison(comparison)
