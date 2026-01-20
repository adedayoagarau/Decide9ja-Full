"""
Digest Agent Implementation

Handles news digest subscription intents:
- SUBSCRIBE_DIGEST
- UNSUBSCRIBE_DIGEST
"""
import logging
from typing import Set

from app.services.agents.base import BaseAgent
from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability,
    HandoffReason
)
from app.services.agents.digest_agent.prompt import get_digest_prompt

logger = logging.getLogger(__name__)


class DigestAgent(BaseAgent):
    """
    Specialist agent for news digest subscriptions.

    Simple transactional agent for subscribe/unsubscribe.
    """

    name = "digest"
    capabilities = [AgentCapability.DIGEST]
    handled_intents: Set[str] = {
        "subscribe_digest",
        "unsubscribe_digest",
    }

    def get_system_prompt(self) -> str:
        """Return the digest-focused system prompt."""
        return get_digest_prompt()

    async def can_handle(self, message: AgentMessage) -> bool:
        """Check if this is a digest-related intent."""
        if message.intent:
            return message.intent.lower() in self.handled_intents
        return False

    async def handle(self, message: AgentMessage) -> AgentResult:
        """Route to the appropriate digest handler."""
        intent = message.intent.lower() if message.intent else ""

        try:
            if intent == "subscribe_digest":
                return await self._handle_subscribe(message)

            elif intent == "unsubscribe_digest":
                return await self._handle_unsubscribe(message)

            else:
                return self.handoff("response", HandoffReason.INTENT_MISMATCH)

        except Exception as e:
            logger.exception(f"[DigestAgent] Error handling {intent}: {e}")
            return self.failure(f"Error processing digest request: {str(e)}")

    async def _handle_subscribe(self, message: AgentMessage) -> AgentResult:
        """Handle subscribing to news digest."""
        from app.services.twilio_whatsapp import hash_phone
        from app.services.news_digest_service import NewsDigestService

        ctx = message.user_context

        try:
            user_hash = hash_phone(ctx.phone)
            digest_service = NewsDigestService()
            frequency = message.entities.get("frequency", "daily")

            success = digest_service.subscribe_user(user_hash, frequency)

            if success:
                response = f"""✅ *Subscribed to {frequency.title()} Digest!*

You'll receive political news and updates {frequency} at 7 AM WAT.

📰 What you'll get:
• Breaking political news
• Policy updates and explainers
• 2027 election updates
• Local updates for {ctx.state or 'your state'}

Reply "unsubscribe" anytime to stop.

Is there anything specific you want me to focus on? (e.g., elections, economy, security)"""
                return self.success(response)
            else:
                return self.success(
                    "You're already subscribed to the digest! "
                    "Reply 'unsubscribe' to stop receiving updates."
                )

        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return self.failure(
                "Sorry, I couldn't process your subscription. Please try again later."
            )

    async def _handle_unsubscribe(self, message: AgentMessage) -> AgentResult:
        """Handle unsubscribing from news digest."""
        from app.services.twilio_whatsapp import hash_phone
        from app.services.news_digest_service import NewsDigestService

        ctx = message.user_context

        try:
            user_hash = hash_phone(ctx.phone)
            digest_service = NewsDigestService()

            success = digest_service.unsubscribe_user(user_hash)

            if success:
                response = """✅ *Unsubscribed from Digest*

You won't receive automatic updates anymore.

You can still:
• Ask me questions anytime
• Say "subscribe" to get updates again
• Follow specific politicians for their news

Anything else I can help with?"""
                return self.success(response)
            else:
                return self.success(
                    "You're not currently subscribed to any digest. "
                    "Say 'subscribe' to start receiving updates."
                )

        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            return self.failure("Sorry, I couldn't process that. Please try again.")
