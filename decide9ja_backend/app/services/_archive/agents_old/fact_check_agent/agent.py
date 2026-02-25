"""
Fact Check Agent Implementation

Handles claim verification intent:
- VERIFY_CLAIM
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
from app.services.agents.fact_check_agent.prompt import get_fact_check_prompt

logger = logging.getLogger(__name__)


class FactCheckAgent(BaseAgent):
    """
    Specialist agent for fact-checking political claims.

    Verifies claims against trusted sources and presents findings.
    """

    name = "fact_check"
    capabilities = [AgentCapability.FACT_CHECK]
    handled_intents: Set[str] = {
        "verify_claim",
    }

    # Prefixes to strip from claim text
    CLAIM_PREFIXES = [
        "verify",
        "fact check",
        "is it true that",
        "check if",
        "is it true",
        "true or false",
    ]

    def get_system_prompt(self) -> str:
        """Return the fact-check-focused system prompt."""
        return get_fact_check_prompt()

    async def can_handle(self, message: AgentMessage) -> bool:
        """Check if this is a fact-check intent."""
        if message.intent:
            return message.intent.lower() in self.handled_intents
        return False

    async def handle(self, message: AgentMessage) -> AgentResult:
        """Handle fact-check request."""
        intent = message.intent.lower() if message.intent else ""

        if intent != "verify_claim":
            return self.handoff("response", HandoffReason.INTENT_MISMATCH)

        try:
            return await self._handle_verify_claim(message)
        except Exception as e:
            logger.exception(f"[FactCheckAgent] Error: {e}")
            return self.failure(
                "Sorry, I couldn't process that fact-check. "
                "Please try again with a clearer claim."
            )

    async def _handle_verify_claim(self, message: AgentMessage) -> AgentResult:
        """Handle verifying a claim."""
        from app.services.twilio_whatsapp import hash_phone
        from app.services.fact_check_service import FactCheckService

        ctx = message.user_context

        # Extract and clean the claim
        claim = message.entities.get("claim", message.query)
        claim = self._clean_claim(claim)

        try:
            user_hash = hash_phone(ctx.phone)
            fact_service = FactCheckService()
            result = fact_service.check_claim(claim, user_hash)

            if result.get("found"):
                return self._format_found_result(claim, result["fact_check"])
            else:
                return self._format_pending_result(claim, result.get("request_id", "pending"))

        except Exception as e:
            logger.error(f"Fact check error: {e}")
            return self.failure(
                "Sorry, I couldn't process that fact-check. Please try again."
            )

    def _clean_claim(self, claim: str) -> str:
        """Remove common prefixes from claim text."""
        claim_lower = claim.lower()
        for prefix in self.CLAIM_PREFIXES:
            if claim_lower.startswith(prefix):
                claim = claim[len(prefix):].strip()
                claim_lower = claim.lower()
        return claim

    def _format_found_result(self, claim: str, fc: dict) -> AgentResult:
        """Format a fact-check result that was found in database."""
        verdict_emoji = {
            "true": "✅",
            "mostly_true": "🟢",
            "half_true": "🟡",
            "mostly_false": "🟠",
            "false": "❌",
            "unverifiable": "❓"
        }

        emoji = verdict_emoji.get(fc.get("verdict", ""), "🔍")
        verdict_text = fc.get('verdict', 'Unknown').replace('_', ' ').title()
        explanation = fc.get('explanation', 'No explanation available')[:400]
        source_count = len(fc.get('sources', []))

        # Truncate claim for display
        claim_display = claim[:100] + "..." if len(claim) > 100 else claim

        response = f"""{emoji} *Fact Check Result*

📋 *Claim:* {claim_display}

🔍 *Verdict:* {verdict_text}

📝 *Explanation:*
{explanation}

📰 *Sources:* {source_count} verified source(s)

Want me to explain more about this topic?"""

        return self.success(response)

    def _format_pending_result(self, claim: str, request_id: str) -> AgentResult:
        """Format a result for claims submitted for review."""
        claim_display = claim[:80] + "..." if len(claim) > 80 else claim

        response = f"""🔍 *Fact Check Request Submitted*

I'm checking: "{claim_display}"

This claim hasn't been verified yet. Your request has been submitted for review by our fact-checkers.

📋 Request ID: {request_id}

I'll check our database and news sources. You can also:
• Ask me to explain the topic
• Share where you heard this claim
• Check back later for updates

Want me to search for related news on this topic?"""

        return self.success(response, data={"fact_check_pending": True})
