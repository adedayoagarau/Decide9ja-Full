"""
User Segmentation & Memory Service for Decide9ja.

Provides:
1. User segment classification (engagement tier, profile tier, voter status)
2. Topic memory and recall
3. Personalization context for responses

Key Segments:
- Engagement: power_user, regular, engaged, new, inactive
- Profile: complete, partial, minimal, new
- Voter: registered_voter, unregistered, unknown
- Interest: politics-focused, economy-focused, local-focused, general
"""
import logging
from typing import Optional, List, Dict, Set
from dataclasses import dataclass, field
from datetime import datetime

from app.models.state import UserState

logger = logging.getLogger(__name__)


@dataclass
class UserSegment:
    """User segment classification."""
    engagement_tier: str  # power_user, regular, engaged, new, inactive
    profile_tier: str     # complete, partial, minimal, new
    voter_status: str     # registered_voter, unregistered, unknown
    primary_interest: Optional[str] = None  # politics, economy, security, local, general
    state_focus: Optional[str] = None       # Their primary state of interest
    last_active_days: int = 0               # Days since last active

    def to_dict(self) -> dict:
        return {
            "engagement_tier": self.engagement_tier,
            "profile_tier": self.profile_tier,
            "voter_status": self.voter_status,
            "primary_interest": self.primary_interest,
            "state_focus": self.state_focus,
            "last_active_days": self.last_active_days
        }


@dataclass
class TopicMemory:
    """Remembers what topics the user has discussed."""
    politicians_discussed: List[str] = field(default_factory=list)
    topics_explored: List[str] = field(default_factory=list)
    questions_asked: List[str] = field(default_factory=list)
    last_topic: Optional[str] = None
    topic_frequency: Dict[str, int] = field(default_factory=dict)


class UserSegmentationService:
    """
    Analyzes and classifies users for personalized experiences.

    Uses profile data and behavior patterns to segment users
    and tailor responses accordingly.
    """

    def __init__(self):
        # Interest categories and their keywords
        self.interest_categories = {
            "politics": ["election", "vote", "party", "governor", "senator", "president", "apc", "pdp", "lp"],
            "economy": ["budget", "tax", "naira", "dollar", "subsidy", "fuel", "inflation", "price"],
            "security": ["security", "police", "military", "bandit", "kidnap", "boko haram", "crime"],
            "education": ["school", "university", "student", "lecturer", "asuu", "jamb", "education"],
            "health": ["health", "hospital", "doctor", "medicine", "covid", "disease"],
            "infrastructure": ["road", "power", "electricity", "water", "housing", "transport"],
            "local": ["my senator", "my governor", "my rep", "my lga", "my state"],
        }

    def classify_user(self, state: UserState) -> UserSegment:
        """
        Classify user into segments based on their profile and behavior.

        Returns comprehensive segment classification.
        """
        # Calculate days since last active
        last_active_days = 0
        if state.last_active_at:
            try:
                delta = datetime.utcnow() - state.last_active_at
                last_active_days = delta.days
            except:
                pass

        # Get voter status
        if state.has_pvc is True:
            voter_status = "registered_voter"
        elif state.has_pvc is False:
            voter_status = "unregistered"
        else:
            voter_status = "unknown"

        # Determine primary interest
        primary_interest = self._determine_primary_interest(state)

        # Determine state focus (where their political interest lies)
        state_focus = self._determine_state_focus(state)

        return UserSegment(
            engagement_tier=state.get_engagement_tier(),
            profile_tier=state.get_profile_tier(),
            voter_status=voter_status,
            primary_interest=primary_interest,
            state_focus=state_focus,
            last_active_days=last_active_days
        )

    def _determine_primary_interest(self, state: UserState) -> str:
        """Determine user's primary interest from their tracked interests and topics."""
        if not state.interests and not state.topics_asked:
            return "general"

        # Count interest category matches
        category_scores = {cat: 0 for cat in self.interest_categories}

        all_interests = (state.interests or []) + (state.topics_asked or [])
        for interest in all_interests:
            interest_lower = interest.lower()
            for category, keywords in self.interest_categories.items():
                if any(kw in interest_lower for kw in keywords):
                    category_scores[category] += 1

        # Return highest scoring category
        if max(category_scores.values()) > 0:
            return max(category_scores, key=category_scores.get)
        return "general"

    def _determine_state_focus(self, state: UserState) -> Optional[str]:
        """Determine which state the user is most interested in."""
        # Priority: registered_state > residence_state > origin_state > state
        return (
            state.registered_state or
            state.residence_state or
            state.origin_state or
            state.state
        )

    def get_personalization_context(self, state: UserState) -> str:
        """
        Generate personalization context for Claude prompt.

        Returns a string that can be added to system prompts.
        """
        segment = self.classify_user(state)

        context_parts = []

        # User engagement context
        if segment.engagement_tier == "power_user":
            context_parts.append("This is a highly engaged power user. They appreciate detailed, nuanced responses.")
        elif segment.engagement_tier == "regular":
            context_parts.append("This is a regular user familiar with the platform. Keep responses balanced.")
        elif segment.engagement_tier == "new":
            context_parts.append("This is a newer user. Be welcoming and explain any complex terms.")

        # Profile completeness
        if segment.profile_tier == "minimal" or segment.profile_tier == "new":
            context_parts.append("Their profile is minimal - we're still learning about them.")

        # Voter status context
        if segment.voter_status == "registered_voter":
            context_parts.append("They have their PVC - they may be interested in election updates.")
        elif segment.voter_status == "unregistered":
            context_parts.append("They don't have a PVC yet - voter registration may be relevant.")

        # Interest context
        if segment.primary_interest and segment.primary_interest != "general":
            context_parts.append(f"They're particularly interested in {segment.primary_interest} topics.")

        # State focus
        if segment.state_focus:
            context_parts.append(f"Their focus state is {segment.state_focus}.")

        # Topics they've explored
        if state.topics_asked and len(state.topics_asked) > 3:
            recent_topics = state.topics_asked[-5:]
            context_parts.append(f"Recent topics explored: {', '.join(recent_topics)}")

        return " ".join(context_parts) if context_parts else ""

    def get_memory_recall(self, state: UserState, current_query: str) -> Optional[str]:
        """
        Check if current query relates to previously discussed topics.

        Returns a memory prompt if relevant, None otherwise.
        """
        if not state.active_politician_name:
            return None

        # Check if query might be a follow-up about the active politician
        followup_signals = [
            "their", "his", "her", "them", "he", "she",
            "bills", "record", "achievements", "projects",
            "more", "else", "what about"
        ]

        query_lower = current_query.lower()
        if any(signal in query_lower for signal in followup_signals):
            return f"User was previously discussing {state.active_politician_name}. This may be a follow-up question about them."

        return None

    def should_remind_about_topic(
        self,
        state: UserState,
        current_topic: str
    ) -> Optional[str]:
        """
        Check if we should remind the user about a related previous discussion.

        Returns a reminder string if appropriate, None otherwise.
        """
        if not state.topics_asked:
            return None

        # Check for related topic in history
        related_topics = {
            "tax": ["budget", "economy", "spending"],
            "election": ["vote", "candidate", "campaign"],
            "security": ["military", "police", "crime"],
        }

        current_lower = current_topic.lower()
        for topic, related in related_topics.items():
            if topic in current_lower:
                for past_topic in state.topics_asked:
                    if any(r in past_topic.lower() for r in related):
                        return f"You previously asked about {past_topic}. This is related."

        return None

    def get_welcome_personalization(self, state: UserState) -> Dict[str, str]:
        """
        Get personalized welcome message components.

        Returns dict with greeting additions based on user segment.
        """
        segment = self.classify_user(state)
        result = {}

        # Time-based greeting modifier
        if segment.last_active_days > 14:
            result["time_modifier"] = "It's been a while!"
        elif segment.last_active_days > 7:
            result["time_modifier"] = "Good to see you back!"

        # Engagement-based add-on
        if segment.engagement_tier == "power_user":
            result["engagement_addon"] = "What's on your mind today?"
        elif segment.engagement_tier == "new":
            result["engagement_addon"] = "I'm here to help you stay informed about Nigerian politics."

        # Topic suggestion based on interests
        if segment.primary_interest:
            interest_prompts = {
                "politics": "Would you like updates on the latest political news?",
                "economy": "Interested in the latest economic developments?",
                "security": "Want to know about security updates in your area?",
                "local": "I can tell you about your local representatives.",
            }
            if segment.primary_interest in interest_prompts:
                result["topic_suggestion"] = interest_prompts[segment.primary_interest]

        return result


# Singleton instance
user_segmentation = UserSegmentationService()


def get_user_segment(state: UserState) -> UserSegment:
    """Convenience function to get user segment."""
    return user_segmentation.classify_user(state)


def get_personalization(state: UserState) -> str:
    """Convenience function to get personalization context."""
    return user_segmentation.get_personalization_context(state)
