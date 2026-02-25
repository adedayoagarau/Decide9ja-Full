"""
Community Agent Implementation

Handles civic engagement intents:
- MY_POINTS, LEADERBOARD, MY_CIVIC_PROFILE
- REPORT_COMMUNITY_ISSUE
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
from app.services.agents.community_agent.prompt import get_community_prompt

logger = logging.getLogger(__name__)


class CommunityAgent(BaseAgent):
    """
    Specialist agent for civic engagement and gamification.

    Handles points, leaderboards, profiles, and issue reporting.
    """

    name = "community"
    capabilities = [AgentCapability.COMMUNITY]
    handled_intents: Set[str] = {
        "my_points",
        "leaderboard",
        "my_civic_profile",
        "report_community_issue",
    }

    def get_system_prompt(self) -> str:
        """Return the community-focused system prompt."""
        return get_community_prompt()

    async def can_handle(self, message: AgentMessage) -> bool:
        """Check if this is a community-related intent."""
        if message.intent:
            return message.intent.lower() in self.handled_intents
        return False

    async def handle(self, message: AgentMessage) -> AgentResult:
        """Route to the appropriate community handler."""
        intent = message.intent.lower() if message.intent else ""

        try:
            if intent == "my_points":
                return await self._handle_my_points(message)

            elif intent == "leaderboard":
                return await self._handle_leaderboard(message)

            elif intent == "my_civic_profile":
                return await self._handle_civic_profile(message)

            elif intent == "report_community_issue":
                return await self._handle_report_issue(message)

            else:
                return self.handoff("response", HandoffReason.INTENT_MISMATCH)

        except Exception as e:
            logger.exception(f"[CommunityAgent] Error handling {intent}: {e}")
            return self.failure(f"Error processing community query: {str(e)}")

    async def _handle_my_points(self, message: AgentMessage) -> AgentResult:
        """Handle my points / civic score request."""
        from app.services.twilio_whatsapp import hash_phone
        from app.services.gamification_service import GamificationService

        ctx = message.user_context

        try:
            user_hash = hash_phone(ctx.phone)
            gamification = GamificationService()
            profile = gamification.get_profile(user_hash, ctx.name, ctx.state, ctx.lga)

            badges_text = ""
            if profile.get("badges"):
                badges_text = "\n🏅 *Badges:* " + " ".join(profile["badges"][:5])

            streak_emoji = "🔥" if profile.get("current_streak", 0) >= 3 else "📅"

            response = f"""🏆 *Your Civic Score*

👤 *{profile.get('display_name', ctx.name or 'Citizen')}*
📍 {profile.get('state', ctx.state or 'Nigeria')}

⭐ *Total Points:* {profile.get('total_points', 0):,}
📊 *Level:* {profile.get('level', 1)} - {profile.get('title', 'Civic Observer')}
{streak_emoji} *Current Streak:* {profile.get('current_streak', 0)} days{badges_text}

📈 *This Week:* {profile.get('points_this_week', 0)} points
📆 *This Month:* {profile.get('points_this_month', 0)} points

💡 *Earn more points by:*
• Asking questions (+5)
• Reporting issues (+20)
• Verifying facts (+15)
• Daily check-ins (+10)

Say 'leaderboard' to see top citizens!"""

            return self.success(response)

        except Exception as e:
            logger.error(f"Points error: {e}")
            return self.failure("Sorry, I couldn't load your points. Please try again.")

    async def _handle_leaderboard(self, message: AgentMessage) -> AgentResult:
        """Handle leaderboard request."""
        from app.services.twilio_whatsapp import hash_phone
        from app.services.gamification_service import GamificationService

        ctx = message.user_context

        try:
            user_hash = hash_phone(ctx.phone)
            gamification = GamificationService()
            leaderboard = gamification.get_leaderboard(
                state=ctx.state,
                lga=ctx.lga,
                user_hash=user_hash
            )

            location = ctx.lga or ctx.state or "Nigeria"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

            text = f"🏆 *{location} Leaderboard*\n\n"

            for i, entry in enumerate(leaderboard.get("top_10", [])[:10]):
                medal = medals[i] if i < len(medals) else f"{i+1}."
                name = entry.get("display_name", "Anonymous")[:15]
                points = entry.get("total_points", 0)
                level = entry.get("level", 1)
                text += f"{medal} {name} - {points:,} pts (Lv.{level})\n"

            user_rank = leaderboard.get("user_rank")
            if user_rank and user_rank > 10:
                text += f"\n📍 *Your rank:* #{user_rank}"

            text += f"""

🎯 *Weekly Challenge:*
Be more active to climb the ranks!

Say 'my points' to see your score."""

            return self.success(text)

        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            return self.failure("Sorry, I couldn't load the leaderboard. Please try again.")

    async def _handle_civic_profile(self, message: AgentMessage) -> AgentResult:
        """Handle detailed civic profile request."""
        from app.services.twilio_whatsapp import hash_phone
        from app.services.gamification_service import GamificationService

        ctx = message.user_context

        try:
            user_hash = hash_phone(ctx.phone)
            gamification = GamificationService()
            profile = gamification.get_profile(user_hash, ctx.name, ctx.state, ctx.lga)

            # Badge details
            badges_section = ""
            earned = profile.get("badges", [])
            if earned:
                badges_section = "\n\n🏅 *Your Badges:*\n"
                for badge in earned[:5]:
                    badges_section += f"✅ {badge}\n"

            # Action counts
            actions = profile.get("action_counts", {})
            actions_section = ""
            if actions:
                actions_section = "\n\n📊 *Your Activity:*\n"
                action_names = {
                    "daily_login": "Daily Logins",
                    "question_asked": "Questions Asked",
                    "issue_reported": "Issues Reported",
                    "fact_checked": "Fact Checks",
                    "poll_voted": "Polls Voted"
                }
                for action, count in actions.items():
                    name = action_names.get(action, action.replace("_", " ").title())
                    actions_section += f"• {name}: {count}\n"

            joined_at = profile.get('joined_at', 'Recently')
            if joined_at and len(joined_at) > 10:
                joined_at = joined_at[:10]

            response = f"""👤 *Your Civic Profile*

📛 *Name:* {profile.get('display_name', ctx.name or 'Citizen')}
📍 *Location:* {profile.get('lga', ctx.lga or '')} {profile.get('state', ctx.state or 'Nigeria')}

⭐ *Total Points:* {profile.get('total_points', 0):,}
📊 *Level:* {profile.get('level', 1)}
🎖️ *Title:* {profile.get('title', 'Civic Observer')}

🔥 *Streaks:*
• Current: {profile.get('current_streak', 0)} days
• Longest: {profile.get('longest_streak', 0)} days{badges_section}{actions_section}

📅 *Member Since:* {joined_at}

Keep engaging to earn more badges and climb the ranks! 🚀"""

            return self.success(response)

        except Exception as e:
            logger.error(f"Profile error: {e}")
            return self.failure("Sorry, I couldn't load your profile. Please try again.")

    async def _handle_report_issue(self, message: AgentMessage) -> AgentResult:
        """Handle community issue reporting - starts the flow."""
        ctx = message.user_context

        category = message.entities.get("category", "")
        description = message.entities.get("description", message.query)

        category_options = """
📂 *Issue Categories:*
1️⃣ Roads/Potholes
2️⃣ Electricity (NEPA)
3️⃣ Water Supply
4️⃣ Security
5️⃣ Sanitation/Waste
6️⃣ Education
7️⃣ Health
8️⃣ Other

Reply with the number or name of the category."""

        if category:
            # Category already identified, ask for location
            response = f"""📍 *Reporting: {category.title()} Issue*

Got it! Now I need more details:

1. What's the exact location? (Street, area, LGA)
2. Brief description of the problem

Please share the location first:"""

            return self.success(response, data={
                "start_flow": "issue",
                "flow_step": 1,
                "flow_data": {
                    "type": "community",
                    "category": category,
                    "initial_description": description
                }
            })

        # No category yet, show options
        response = f"""📢 *Report a Community Issue*

I'll help you report this issue to the relevant authorities and track it.

{category_options}"""

        return self.success(response, data={
            "start_flow": "issue",
            "flow_step": 0,
            "flow_data": {
                "type": "community",
                "initial_description": description
            }
        })
