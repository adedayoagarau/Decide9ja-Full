"""
EngagementAgent
===============
Handles civic engagement queries: points, badges, streaks, leaderboard.

NO LLM CALLS - pure database operations via engagement services.
Cost: FREE

Handles:
- "What are my points?"
- "Show my badges"
- "My civic score"
- "Show leaderboard"
- "Top contributors in Lagos"
"""

import logging

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent
from app.agents.tier1_entry.classifier import Intent

logger = logging.getLogger(__name__)


@register_agent
class EngagementAgent(BaseAgent):
    name = "engagement"
    description = "Handle civic engagement queries (points, badges, leaderboard)"
    tier = AgentTier.CORE
    cost_level = CostLevel.FREE  # No LLM, database only
    handled_intents = [
        Intent.MY_POINTS,
        Intent.MY_BADGES,
        Intent.MY_STREAK,
        Intent.LEADERBOARD,
    ]

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent in self.handled_intents

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        intent = input.intent
        text = input.raw_text.lower()
        user_hash = input.user.phone_hash
        state = input.user.state
        lga = input.user.lga

        try:
            # Import services
            from app.services.engagement import (
                points_service,
                badges_service,
                streak_service,
                leaderboard_service
            )

            # Route by intent
            if intent == Intent.LEADERBOARD:
                return await self._handle_leaderboard(state, lga, user_hash, leaderboard_service)

            elif intent == Intent.MY_BADGES:
                return await self._handle_badges(user_hash, badges_service)

            elif intent == Intent.MY_STREAK:
                return await self._handle_streak(user_hash, streak_service)

            else:
                # Default: MY_POINTS - show points summary (comprehensive view)
                return await self._handle_points(user_hash, points_service, badges_service, streak_service)

        except Exception as e:
            logger.error(f"Engagement agent error: {e}")
            return AgentOutput(
                success=False,
                response_text="Sorry, I couldn't load your engagement data. Please try again.",
                error=str(e),
                cost_level=CostLevel.FREE
            )

    async def _handle_points(self, user_hash: str, points_svc, badges_svc, streak_svc) -> AgentOutput:
        """Show comprehensive points summary."""
        points_data = points_svc.get_points(user_hash)
        streak_data = streak_svc.get_streak(user_hash)
        badges_data = badges_svc.get_badges(user_hash)

        total_points = points_data.get("total_points", 0)
        rank = points_data.get("rank", "N/A")
        level = points_data.get("level", "Citizen")
        current_streak = streak_data.get("current_streak", 0)
        badge_count = len(badges_data.get("badges", []))
        multiplier = streak_data.get("multiplier", 1.0)

        # Format response
        response = f"""🏆 *Your Civic Profile*

*Points:* {total_points:,} pts
*Level:* {level}
*Rank:* #{rank}

🔥 *Streak:* {current_streak} days
{'✨ Multiplier: ' + str(multiplier) + 'x' if multiplier > 1 else ''}

🎖️ *Badges:* {badge_count} earned

---
*Recent Activity:*"""

        # Add recent transactions
        recent = points_data.get("recent_transactions", [])[:3]
        if recent:
            for tx in recent:
                action = tx.get("action", "activity")
                pts = tx.get("points", 0)
                response += f"\n• {action.replace('_', ' ').title()}: +{pts} pts"
        else:
            response += "\n_No recent activity_"

        response += "\n\n_Keep engaging to earn more points!_"

        return AgentOutput(
            success=True,
            response_text=response,
            buttons=[
                {"text": "🎖️ My Badges", "callback": "my_badges"},
                {"text": "🏅 Leaderboard", "callback": "leaderboard"},
            ],
            cost_level=CostLevel.FREE,
            analytics_tags={"type": "points", "total": total_points}
        )

    async def _handle_badges(self, user_hash: str, badges_svc) -> AgentOutput:
        """Show user's badges."""
        data = badges_svc.get_badges(user_hash)
        badges = data.get("badges", [])
        total_available = data.get("total_available", 18)

        if not badges:
            response = """🎖️ *Your Badges*

You haven't earned any badges yet.

*How to earn badges:*
• Report community issues
• Verify other reports
• Check in daily
• Reach point milestones

Keep engaging to unlock badges!"""
        else:
            response = f"""🎖️ *Your Badges* ({len(badges)}/{total_available})

"""
            # Group badges by category
            categories = {}
            for badge in badges:
                cat = badge.get("category", "other")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(badge)

            for cat, cat_badges in categories.items():
                response += f"*{cat.title()}:*\n"
                for b in cat_badges:
                    response += f"  {b['icon']} {b['name']}\n"
                response += "\n"

            # Show next badges to earn
            next_badges = data.get("next_badges", [])
            if next_badges:
                response += "*Next to unlock:*\n"
                for b in next_badges[:2]:
                    response += f"  {b['icon']} {b['name']} - {b.get('requirement', '')}\n"

        return AgentOutput(
            success=True,
            response_text=response,
            cost_level=CostLevel.FREE,
            analytics_tags={"type": "badges", "count": len(badges)}
        )

    async def _handle_streak(self, user_hash: str, streak_svc) -> AgentOutput:
        """Show streak information."""
        data = streak_svc.get_streak(user_hash)

        current = data.get("current_streak", 0)
        longest = data.get("longest_streak", 0)
        multiplier = data.get("multiplier", 1.0)
        last_active = data.get("last_active_date")

        response = f"""🔥 *Your Streak*

*Current Streak:* {current} days
*Longest Streak:* {longest} days
*Point Multiplier:* {multiplier}x

"""
        if current >= 7:
            response += "🌟 _Amazing! 7+ day streak bonus active!_\n"
        elif current >= 3:
            response += "⭐ _Good going! Keep it up for the 7-day bonus._\n"
        else:
            response += "_Come back daily to build your streak!_\n"

        response += """
*Streak Multipliers:*
• 7 days: 1.5x points
• 30 days: 2.0x points

Check in daily to maintain your streak!"""

        return AgentOutput(
            success=True,
            response_text=response,
            cost_level=CostLevel.FREE,
            analytics_tags={"type": "streak", "current": current}
        )

    async def _handle_leaderboard(self, state: str, lga: str, user_hash: str, leaderboard_svc) -> AgentOutput:
        """Show leaderboard."""
        # Get user's rank first
        user_rank = leaderboard_svc.get_user_rank(user_hash, state)

        # Get leaderboard
        if state:
            data = leaderboard_svc.get_leaderboard(state=state, lga=lga, limit=10)
            scope = f"{lga}, {state}" if lga else state
        else:
            data = leaderboard_svc.get_leaderboard(limit=10)
            scope = "Nigeria"

        rankings = data.get("rankings", [])

        response = f"""🏅 *Leaderboard - {scope}*

"""
        medals = ["🥇", "🥈", "🥉"]

        for i, entry in enumerate(rankings):
            medal = medals[i] if i < 3 else f"{i+1}."
            name = entry.get("display_name", "Anonymous")
            points = entry.get("total_points", 0)
            level = entry.get("level", "Citizen")

            # Highlight if this is the user
            if entry.get("is_you"):
                response += f"*{medal} {name} (You)*\n   {points:,} pts - {level}\n"
            else:
                response += f"{medal} {name}\n   {points:,} pts - {level}\n"

        # Add user's position if not in top 10
        if user_rank:
            user_position = user_rank.get("rank", 0)
            if user_position > 10:
                response += f"\n---\nYour rank: #{user_position}"
                percentile = user_rank.get("percentile", 0)
                if percentile:
                    response += f" (Top {100-percentile:.0f}%)"

        response += "\n\n_Earn points by reporting issues and verifying reports!_"

        return AgentOutput(
            success=True,
            response_text=response,
            cost_level=CostLevel.FREE,
            analytics_tags={"type": "leaderboard", "scope": scope}
        )
