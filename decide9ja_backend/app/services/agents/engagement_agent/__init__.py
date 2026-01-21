"""
Engagement Agent - Handles civic engagement queries.

Intents:
- MY_POINTS: Show user's points
- MY_BADGES: Show user's badges
- MY_STREAK: Show user's streak
- LEADERBOARD: Show rankings
"""

from app.services.agents.engagement_agent.agent import EngagementAgent

__all__ = ["EngagementAgent"]
