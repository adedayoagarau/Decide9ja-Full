"""
Progressive Profiling Service for Decide9ja.

Determines what profile information to collect and when,
based on user engagement and context.

Key principles:
- Never interrupt the user's primary goal
- Ask one question at a time
- Use natural conversation moments
- Prioritize high-value questions
"""
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from app.models.state import UserState

logger = logging.getLogger(__name__)


class ProfileQuestion(Enum):
    """Profile questions in priority order."""
    # High priority - needed for core functionality
    REGISTERED_STATE = "registered_state"
    REGISTERED_LGA = "registered_lga"
    HAS_PVC = "has_pvc"

    # Medium priority - improves personalization
    AGE_RANGE = "age_range"
    ORIGIN_STATE = "origin_state"

    # Lower priority - nice to have
    GENDER = "gender"
    INTERESTS = "interests"


@dataclass
class ProfilePrompt:
    """A prompt to collect profile information."""
    question_type: ProfileQuestion
    prompt_text: str
    follow_up_on_answer: Optional[str] = None  # What to say after they answer


# Question definitions
PROFILE_PROMPTS = {
    ProfileQuestion.REGISTERED_STATE: ProfilePrompt(
        question_type=ProfileQuestion.REGISTERED_STATE,
        prompt_text="By the way, which state are you registered to vote in?",
        follow_up_on_answer="Got it. That helps me give you better election info."
    ),
    ProfileQuestion.REGISTERED_LGA: ProfilePrompt(
        question_type=ProfileQuestion.REGISTERED_LGA,
        prompt_text="Which LGA is your polling unit in?",
        follow_up_on_answer="Noted."
    ),
    ProfileQuestion.HAS_PVC: ProfilePrompt(
        question_type=ProfileQuestion.HAS_PVC,
        prompt_text="Do you have your PVC (Permanent Voter Card)?",
        follow_up_on_answer=None  # Different responses for yes/no
    ),
    ProfileQuestion.AGE_RANGE: ProfilePrompt(
        question_type=ProfileQuestion.AGE_RANGE,
        prompt_text="What age group are you in? (18-24, 25-34, 35-44, 45-54, 55-64, 65+)",
        follow_up_on_answer="Thanks."
    ),
    ProfileQuestion.ORIGIN_STATE: ProfilePrompt(
        question_type=ProfileQuestion.ORIGIN_STATE,
        prompt_text="What state are you originally from?",
        follow_up_on_answer="Interesting! That helps me understand your perspective."
    ),
    ProfileQuestion.GENDER: ProfilePrompt(
        question_type=ProfileQuestion.GENDER,
        prompt_text="How should I address you? (Sir/Ma)",
        follow_up_on_answer="Noted."
    ),
    ProfileQuestion.INTERESTS: ProfilePrompt(
        question_type=ProfileQuestion.INTERESTS,
        prompt_text="What political topics interest you most? (economy, education, security, health, etc.)",
        follow_up_on_answer="I'll keep that in mind."
    ),
}


class ProgressiveProfilingService:
    """
    Manages progressive collection of user profile data.

    Strategy:
    1. Only ask after completing user's primary request
    2. Don't ask on every interaction (cooldown)
    3. Prioritize questions by value
    4. Context-aware timing (e.g., ask about PVC near elections)
    """

    def __init__(self, min_messages_before_profiling: int = 3, cooldown_messages: int = 5):
        """
        Args:
            min_messages_before_profiling: Minimum messages before we start asking
            cooldown_messages: Messages between profile questions
        """
        self.min_messages = min_messages_before_profiling
        self.cooldown = cooldown_messages

    def should_ask_profile_question(self, state: UserState) -> bool:
        """
        Determine if this is a good moment to ask a profile question.

        Returns True if:
        - User has sent enough messages (engaged)
        - We haven't asked recently (cooldown)
        - There are questions we still need to ask
        """
        # Don't ask during onboarding
        if not state.is_onboarding_complete():
            return False

        # User needs minimum engagement first
        if state.message_count < self.min_messages:
            return False

        # Check if there's anything to ask
        next_question = self.get_next_question(state)
        if not next_question:
            return False

        # Apply cooldown - only ask every N messages
        # We use message_count % cooldown to space out questions
        if state.message_count > self.min_messages and (state.message_count % self.cooldown != 0):
            return False

        return True

    def get_next_question(self, state: UserState) -> Optional[ProfilePrompt]:
        """
        Get the next profile question to ask, in priority order.

        Returns None if profile is complete or no questions are appropriate.
        """
        # Priority 1: Voter registration (if they've asked about voting/elections)
        if self._user_interested_in_voting(state):
            if not state.registered_state:
                return PROFILE_PROMPTS[ProfileQuestion.REGISTERED_STATE]
            if state.registered_state and not state.registered_lga:
                return PROFILE_PROMPTS[ProfileQuestion.REGISTERED_LGA]
            if state.has_pvc is None:
                return PROFILE_PROMPTS[ProfileQuestion.HAS_PVC]

        # Priority 2: Age (useful for all users)
        if not state.age_range:
            return PROFILE_PROMPTS[ProfileQuestion.AGE_RANGE]

        # Priority 3: Origin state (if different from residence - implies diaspora voting interest)
        if not state.origin_state:
            return PROFILE_PROMPTS[ProfileQuestion.ORIGIN_STATE]

        # Priority 4: Gender (for proper addressing)
        if not state.gender:
            return PROFILE_PROMPTS[ProfileQuestion.GENDER]

        # Priority 5: Interests (for personalization)
        if not state.interests:
            return PROFILE_PROMPTS[ProfileQuestion.INTERESTS]

        # Profile is complete
        return None

    def get_contextual_prompt(
        self,
        state: UserState,
        just_answered_intent: str = None
    ) -> Optional[str]:
        """
        Get a context-appropriate profile prompt to append to a response.

        Args:
            state: User state
            just_answered_intent: The intent we just handled (for context)

        Returns:
            A prompt string to append, or None if not appropriate
        """
        if not self.should_ask_profile_question(state):
            return None

        next_q = self.get_next_question(state)
        if not next_q:
            return None

        # Make the ask feel natural based on context
        if just_answered_intent == "voter_registration":
            # Great context for PVC/registration questions
            if next_q.question_type in [
                ProfileQuestion.HAS_PVC,
                ProfileQuestion.REGISTERED_STATE,
                ProfileQuestion.REGISTERED_LGA
            ]:
                return f"\n\n{next_q.prompt_text}"

        # For other contexts, add a brief transition
        return f"\n\nQuick question: {next_q.prompt_text}"

    def process_profile_answer(
        self,
        state: UserState,
        question_type: ProfileQuestion,
        answer: str
    ) -> str:
        """
        Process an answer to a profile question and update state.

        Returns a confirmation message.
        """
        answer_lower = answer.lower().strip()

        if question_type == ProfileQuestion.REGISTERED_STATE:
            # Extract state from answer
            from app.services.flows.onboarding import extract_nigerian_state
            extracted = extract_nigerian_state(answer)
            if extracted:
                state.registered_state = extracted
                return PROFILE_PROMPTS[question_type].follow_up_on_answer
            return "I didn't catch that state. Which state are you registered in?"

        elif question_type == ProfileQuestion.REGISTERED_LGA:
            state.registered_lga = answer.strip()
            return PROFILE_PROMPTS[question_type].follow_up_on_answer

        elif question_type == ProfileQuestion.HAS_PVC:
            if any(word in answer_lower for word in ["yes", "yeah", "yep", "have", "got"]):
                state.has_pvc = True
                return "You're ready to vote. Let me know if you need polling unit info."
            elif any(word in answer_lower for word in ["no", "nope", "don't", "not yet"]):
                state.has_pvc = False
                return "I can help you with PVC registration when you're ready."
            else:
                return "Just checking - do you have your PVC? (yes/no)"

        elif question_type == ProfileQuestion.AGE_RANGE:
            # Parse age range
            age_ranges = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
            for ar in age_ranges:
                if ar in answer or ar.replace("-", " to ") in answer:
                    state.age_range = ar
                    return PROFILE_PROMPTS[question_type].follow_up_on_answer
            # Try to extract number
            import re
            numbers = re.findall(r'\d+', answer)
            if numbers:
                age = int(numbers[0])
                if 18 <= age <= 24:
                    state.age_range = "18-24"
                elif 25 <= age <= 34:
                    state.age_range = "25-34"
                elif 35 <= age <= 44:
                    state.age_range = "35-44"
                elif 45 <= age <= 54:
                    state.age_range = "45-54"
                elif 55 <= age <= 64:
                    state.age_range = "55-64"
                else:
                    state.age_range = "65+"
                return PROFILE_PROMPTS[question_type].follow_up_on_answer
            return "Which age group? (18-24, 25-34, 35-44, 45-54, 55-64, 65+)"

        elif question_type == ProfileQuestion.ORIGIN_STATE:
            from app.services.flows.onboarding import extract_nigerian_state
            extracted = extract_nigerian_state(answer)
            if extracted:
                state.origin_state = extracted
                return PROFILE_PROMPTS[question_type].follow_up_on_answer
            return "Which Nigerian state are you originally from?"

        elif question_type == ProfileQuestion.GENDER:
            if any(word in answer_lower for word in ["sir", "male", "man", "mr", "he"]):
                state.gender = "male"
                return "Noted, sir."
            elif any(word in answer_lower for word in ["ma", "madam", "female", "woman", "mrs", "miss", "she"]):
                state.gender = "female"
                return "Noted, ma."
            else:
                state.gender = "prefer_not_to_say"
                return "No problem."

        elif question_type == ProfileQuestion.INTERESTS:
            # Parse interests from comma-separated or space-separated list
            interests = [i.strip() for i in answer.replace(",", " ").split() if len(i.strip()) > 2]
            for interest in interests[:5]:  # Max 5 interests
                state.add_interest(interest)
            if state.interests:
                return PROFILE_PROMPTS[question_type].follow_up_on_answer
            return "What topics interest you? (e.g., economy, education, security)"

        return "Thanks."

    def _user_interested_in_voting(self, state: UserState) -> bool:
        """Check if user has shown interest in voting/elections."""
        voting_topics = ["vote", "election", "pvc", "inec", "polling", "ballot"]
        for topic in state.topics_asked:
            if any(vt in topic.lower() for vt in voting_topics):
                return True
        return False

    def infer_interests_from_query(self, query: str) -> List[str]:
        """
        Infer user interests from their query.

        Returns list of interest keywords to add to profile.
        """
        query_lower = query.lower()
        interests = []

        # Topic mappings
        topic_keywords = {
            "economy": ["economy", "budget", "tax", "inflation", "naira", "dollar", "gdp", "subsidy", "fuel"],
            "education": ["education", "school", "university", "student", "lecturer", "asuu", "jamb", "waec"],
            "security": ["security", "military", "police", "boko haram", "bandit", "kidnap", "terrorism", "crime"],
            "health": ["health", "hospital", "doctor", "medicine", "covid", "disease", "nhis"],
            "infrastructure": ["road", "power", "electricity", "water", "housing", "transport", "rail"],
            "politics": ["politics", "election", "vote", "party", "apc", "pdp", "governor", "senator"],
            "corruption": ["corruption", "efcc", "icpc", "fraud", "embezzle", "loot"],
            "judiciary": ["court", "judge", "supreme", "tribunal", "justice", "law"],
        }

        for interest, keywords in topic_keywords.items():
            if any(kw in query_lower for kw in keywords):
                interests.append(interest)

        return interests


# Singleton instance
progressive_profiling = ProgressiveProfilingService()


def get_profile_prompt(state: UserState, intent: str = None) -> Optional[str]:
    """
    Convenience function to get a profile prompt if appropriate.

    Use this at the end of a response to optionally add a profile question.
    """
    return progressive_profiling.get_contextual_prompt(state, intent)


def update_interests_from_query(state: UserState, query: str):
    """
    Convenience function to update user interests based on their query.

    Call this when processing any user query.
    """
    interests = progressive_profiling.infer_interests_from_query(query)
    for interest in interests:
        state.add_interest(interest)
