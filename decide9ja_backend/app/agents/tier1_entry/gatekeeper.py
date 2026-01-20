"""
GatekeeperAgent
===============
First agent to process every message.
Handles user recognition, session setup, language detection.

NO LLM CALLS - pure database lookup.
Cost: FREE
"""

from typing import Optional
import logging

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel,
    UserContext
)
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class GatekeeperAgent(BaseAgent):
    name = "gatekeeper"
    description = "User recognition and session initialization"
    tier = AgentTier.ENTRY
    cost_level = CostLevel.FREE
    handled_intents = ["__all__"]  # Processes every message first

    # Language detection patterns
    PIDGIN_MARKERS = [
        "wetin", "dey", "una", "abeg", "abi", "wahala",
        "gist", "jare", "sef", "sha", "no be", "na so",
        "how far", "i no", "e no"
    ]
    HAUSA_MARKERS = [
        "yaya", "ina", "sannu", "dan", "kuma", "shin",
        "wani", "wannan", "ya", "kai", "ba", "ne"
    ]
    YORUBA_MARKERS = [
        "bawo", "ṣe", "jọwọ", "ẹ", "pẹlẹ", "kilode",
        "se", "ko", "ni", "mo", "ọjọ", "owo"
    ]
    IGBO_MARKERS = [
        "kedu", "biko", "nwanne", "ọ dị", "gịnị", "nna",
        "daalu", "ndewo", "ọ", "di", "anyi"
    ]

    async def can_handle(self, input: AgentInput) -> bool:
        return True  # Always runs first

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # 1. Look up user in database
        user_data = await self._lookup_user(input.user.phone_hash)

        # 2. Detect language
        language = self._detect_language(input.raw_text)

        # 3. Build enriched user context
        if user_data:
            # Returning user
            user = UserContext(
                phone_hash=input.user.phone_hash,
                name=user_data.get("name"),
                state=user_data.get("state"),
                lga=user_data.get("lga"),
                ward=user_data.get("ward"),
                language=language,
                is_new_user=False,
                is_verified=user_data.get("is_verified", False),
                preferences=user_data.get("preferences", {}),
                followed_politicians=user_data.get("followed_politicians", []),
                reported_issues=user_data.get("reported_issues", []),
            )
        else:
            # New user
            user = UserContext(
                phone_hash=input.user.phone_hash,
                language=language,
                is_new_user=True,
            )

        # 4. Check if needs onboarding
        if user.is_new_user or not user.name:
            return AgentOutput(
                success=True,
                handoff_to="onboarding",
                handoff_reason="new_user",
                data={"user": self._user_to_dict(user)},
                cost_level=CostLevel.FREE
            )

        # 5. Pass to classifier with enriched context
        return AgentOutput(
            success=True,
            handoff_to="classifier",
            handoff_reason="user_recognized",
            data={"user": self._user_to_dict(user)},
            cost_level=CostLevel.FREE,
            analytics_tags={
                "user_type": "returning",
                "language": language
            }
        )

    async def _lookup_user(self, phone_hash: str) -> Optional[dict]:
        """Look up user in database"""
        if not self.db:
            return None

        try:
            # Adapt this to your database schema
            # For SQLAlchemy async:
            # result = await self.db.execute(
            #     select(User).where(User.phone_hash == phone_hash)
            # )
            # return result.scalar_one_or_none()

            # For MongoDB:
            # return await self.db.users.find_one({"phone_hash": phone_hash})

            # Placeholder - adapt to your schema
            return None
        except Exception as e:
            logger.error(f"User lookup failed: {e}")
            return None

    def _detect_language(self, text: str) -> str:
        """Detect language from text patterns"""
        text_lower = text.lower()

        # Count markers for each language
        pidgin_count = sum(1 for m in self.PIDGIN_MARKERS if m in text_lower)
        hausa_count = sum(1 for m in self.HAUSA_MARKERS if m in text_lower)
        yoruba_count = sum(1 for m in self.YORUBA_MARKERS if m in text_lower)
        igbo_count = sum(1 for m in self.IGBO_MARKERS if m in text_lower)

        # Return language with most markers (minimum 1)
        max_count = max(pidgin_count, hausa_count, yoruba_count, igbo_count)

        if max_count == 0:
            return "en"  # Default to English

        if pidgin_count == max_count:
            return "pcm"  # Pidgin
        if hausa_count == max_count:
            return "ha"
        if yoruba_count == max_count:
            return "yo"
        if igbo_count == max_count:
            return "ig"

        return "en"

    def _user_to_dict(self, user: UserContext) -> dict:
        """Convert UserContext to dict for handoff"""
        return {
            "phone_hash": user.phone_hash,
            "name": user.name,
            "state": user.state,
            "lga": user.lga,
            "ward": user.ward,
            "language": user.language,
            "is_new_user": user.is_new_user,
            "is_verified": user.is_verified,
            "preferences": user.preferences,
            "followed_politicians": user.followed_politicians,
            "reported_issues": user.reported_issues,
        }
