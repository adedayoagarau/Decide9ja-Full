"""
Engagement Agent - Handles civic engagement queries.

This is a database agent (no LLM calls) that routes to the appropriate
engagement service based on intent.
"""

import logging
from typing import Set

from app.services.agents.base import BaseAgent
from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability
)
from app.services.engagement import (
    points_service,
    badges_service,
    streak_service,
    leaderboard_service
)

logger = logging.getLogger(__name__)


class EngagementAgent(BaseAgent):
    """
    Handles all civic engagement queries:
    - Points lookup
    - Badge display
    - Streak tracking
    - Leaderboard rankings

    This agent does NOT use LLM - it's purely database operations.
    """

    name = "engagement"
    capabilities = [AgentCapability.COMMUNITY]
    handled_intents: Set[str] = {
        "my_points", "points",
        "my_badges", "badges", "achievements",
        "my_streak", "streak",
        "leaderboard", "rankings", "top_contributors"
    }

    # Override - no LLM needed
    model = None
    max_tokens = 0

    def get_system_prompt(self) -> str:
        """Not used - no LLM calls."""
        return ""

    async def can_handle(self, message: AgentMessage) -> bool:
        """Check if this agent handles the intent."""
        intent = (message.intent or "").lower()

        # Direct intent match
        if intent in self.handled_intents:
            return True

        # Keyword detection
        query_lower = message.query.lower()
        keywords = ["points", "badges", "streak", "leaderboard", "rank", "score", "achievements"]
        return any(kw in query_lower for kw in keywords)

    async def handle(self, message: AgentMessage) -> AgentResult:
        """
        Handle engagement queries by routing to appropriate service.
        """
        intent = (message.intent or "").lower()
        query_lower = message.query.lower()
        user_hash = message.user_context.phone  # Use phone as user_hash

        try:
            # Route to appropriate handler
            if "leaderboard" in query_lower or "rank" in query_lower or intent == "leaderboard":
                return await self._handle_leaderboard(message, user_hash)

            elif "badge" in query_lower or "achievement" in query_lower or intent in ("my_badges", "badges"):
                return await self._handle_badges(user_hash)

            elif "streak" in query_lower or intent in ("my_streak", "streak"):
                return await self._handle_streak(user_hash)

            else:
                # Default to points
                return await self._handle_points(user_hash)

        except Exception as e:
            logger.error(f"Engagement agent error: {e}")
            return self.failure(f"Failed to load engagement data: {e}")

    async def _handle_points(self, user_hash: str) -> AgentResult:
        """Handle points queries."""
        data = points_service.get_points(user_hash)
        response = points_service.format_whatsapp(data)
        return self.success(response, {"type": "points", "data": data})

    async def _handle_badges(self, user_hash: str) -> AgentResult:
        """Handle badge queries."""
        data = badges_service.get_badges(user_hash)
        response = badges_service.format_whatsapp(data)
        return self.success(response, {"type": "badges", "data": data})

    async def _handle_streak(self, user_hash: str) -> AgentResult:
        """Handle streak queries."""
        data = streak_service.get_streak(user_hash)
        response = streak_service.format_whatsapp(data)
        return self.success(response, {"type": "streak", "data": data})

    async def _handle_leaderboard(self, message: AgentMessage, user_hash: str) -> AgentResult:
        """Handle leaderboard queries."""
        query_lower = message.query.lower()
        ctx = message.user_context

        # Determine scope
        state = ctx.state
        lga = ctx.lga

        if "local" in query_lower or "my lga" in query_lower or "my area" in query_lower:
            data = leaderboard_service.get_leaderboard(state=state, lga=lga)
        elif "state" in query_lower:
            data = leaderboard_service.get_leaderboard(state=state)
        else:
            # National
            data = leaderboard_service.get_leaderboard()

        response = leaderboard_service.format_whatsapp(data, user_hash=user_hash)

        # Add user's rank if not in top
        user_rank = leaderboard_service.get_user_rank(user_hash, state, lga)
        if user_rank["rank"] and user_rank["rank"] > 10:
            response += f"\n\nYour rank: #{user_rank['rank']:,}"

        return self.success(response, {"type": "leaderboard", "data": data})


# Export for agent registry
def get_agent():
    """Factory function for agent registry."""
    return EngagementAgent()
