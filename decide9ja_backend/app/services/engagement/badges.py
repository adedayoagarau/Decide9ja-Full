"""
Badges Service - Achievement badges for civic engagement.
Database-backed, called by BadgesAgent.
"""

import json
import logging
from typing import Dict, Any, List

from app.database import SessionLocal, CivicProfile

logger = logging.getLogger(__name__)


# Badge definitions
BADGES = {
    # Engagement badges
    "first_step": {
        "name": "First Step",
        "emoji": "👣",
        "description": "Asked your first question",
        "category": "engagement",
        "requirement": {"ask_question": 1}
    },
    "curious_citizen": {
        "name": "Curious Citizen",
        "emoji": "🔍",
        "description": "Asked 10 questions",
        "category": "engagement",
        "requirement": {"ask_question": 10}
    },

    # Community badges
    "watchdog": {
        "name": "Community Watchdog",
        "emoji": "👁️",
        "description": "Reported your first issue",
        "category": "community",
        "requirement": {"report_issue": 1}
    },
    "voice_of_people": {
        "name": "Voice of the People",
        "emoji": "📢",
        "description": "Reported 5 issues",
        "category": "community",
        "requirement": {"report_issue": 5}
    },
    "verifier": {
        "name": "Verified Verifier",
        "emoji": "✅",
        "description": "Verified 5 community issues",
        "category": "community",
        "requirement": {"verify_issue": 5}
    },
    "problem_solver": {
        "name": "Problem Solver",
        "emoji": "🏆",
        "description": "Your reported issue got resolved",
        "category": "community",
        "requirement": {"issue_resolved": 1}
    },

    # Knowledge badges
    "informed_voter": {
        "name": "Informed Voter",
        "emoji": "🗳️",
        "description": "Looked up 10 politicians",
        "category": "knowledge",
        "requirement": {"lookup_politician": 10}
    },
    "fact_finder": {
        "name": "Fact Finder",
        "emoji": "🔬",
        "description": "Compared 10 candidates",
        "category": "knowledge",
        "requirement": {"compare_candidates": 10}
    },
    "promise_tracker": {
        "name": "Promise Tracker",
        "emoji": "📋",
        "description": "Checked 20 promises",
        "category": "knowledge",
        "requirement": {"check_promise": 20}
    },

    # Streak badges
    "week_warrior": {
        "name": "Week Warrior",
        "emoji": "🔥",
        "description": "7-day engagement streak",
        "category": "streak",
        "requirement": {"streak_bonus_7": 1}
    },
    "monthly_champion": {
        "name": "Monthly Champion",
        "emoji": "💪",
        "description": "30-day engagement streak",
        "category": "streak",
        "requirement": {"streak_bonus_30": 1}
    },
    "civic_hero": {
        "name": "Civic Hero",
        "emoji": "🦸",
        "description": "100-day engagement streak",
        "category": "streak",
        "requirement": {"streak_bonus_100": 1}
    },

    # Points badges
    "civic_starter": {
        "name": "Civic Starter",
        "emoji": "⭐",
        "description": "Earned 100 points",
        "category": "points",
        "points_required": 100
    },
    "civic_champion": {
        "name": "Civic Champion",
        "emoji": "🏅",
        "description": "Earned 500 points",
        "category": "points",
        "points_required": 500
    },
    "civic_legend": {
        "name": "Civic Legend",
        "emoji": "🛡️",
        "description": "Earned 2500 points",
        "category": "points",
        "points_required": 2500
    },

    # Special
    "early_adopter": {
        "name": "Early Adopter",
        "emoji": "🚀",
        "description": "Joined before 2027 election",
        "category": "special",
        "special": True
    },
    "onboarded": {
        "name": "Welcome!",
        "emoji": "🎉",
        "description": "Completed onboarding",
        "category": "special",
        "requirement": {"complete_onboarding": 1}
    },
}


class BadgesService:
    """Database-backed badges service."""

    def check_badges(
        self,
        user_hash: str,
        action: str = None,
        total_points: int = None
    ) -> List[Dict]:
        """
        Check and award any new badges earned.
        Called after points are awarded.

        Returns list of newly earned badges.
        """
        db = SessionLocal()
        try:
            profile = db.query(CivicProfile).filter(
                CivicProfile.user_hash == user_hash
            ).first()

            if not profile:
                return []

            # Get current badges and action counts
            current_badges = set(json.loads(profile.badges_json or "[]"))
            action_counts = json.loads(profile.action_counts_json or "{}")
            points = total_points or profile.total_points or 0

            new_badges = []

            for badge_id, badge in BADGES.items():
                if badge_id in current_badges:
                    continue

                earned = False

                # Check points requirement
                if badge.get("points_required"):
                    if points >= badge["points_required"]:
                        earned = True

                # Check action requirements
                elif badge.get("requirement"):
                    requirements = badge["requirement"]
                    earned = all(
                        action_counts.get(act, 0) >= count
                        for act, count in requirements.items()
                    )

                # Special badges (handled elsewhere)
                elif badge.get("special"):
                    continue

                if earned:
                    current_badges.add(badge_id)
                    new_badges.append({
                        "id": badge_id,
                        "name": badge["name"],
                        "emoji": badge["emoji"],
                        "description": badge["description"]
                    })

            # Save new badges
            if new_badges:
                profile.badges_json = json.dumps(list(current_badges))
                db.commit()
                logger.info(f"User {user_hash[:8]} earned badges: {[b['name'] for b in new_badges]}")

            return new_badges

        except Exception as e:
            logger.error(f"Failed to check badges: {e}")
            db.rollback()
            return []
        finally:
            db.close()

    def get_badges(self, user_hash: str) -> Dict[str, Any]:
        """Get all badges for a user."""
        db = SessionLocal()
        try:
            profile = db.query(CivicProfile).filter(
                CivicProfile.user_hash == user_hash
            ).first()

            if not profile:
                return {"earned": [], "total_available": len(BADGES)}

            earned_ids = set(json.loads(profile.badges_json or "[]"))

            earned = []
            for badge_id in earned_ids:
                if badge_id in BADGES:
                    badge = BADGES[badge_id]
                    earned.append({
                        "id": badge_id,
                        "name": badge["name"],
                        "emoji": badge["emoji"],
                        "description": badge["description"],
                        "category": badge["category"]
                    })

            return {
                "earned": earned,
                "earned_count": len(earned),
                "total_available": len(BADGES)
            }

        finally:
            db.close()

    def format_whatsapp(self, data: Dict) -> str:
        """Format badges data for WhatsApp."""
        earned = data.get("earned", [])
        total = data.get("total_available", len(BADGES))
        count = data.get("earned_count", len(earned))

        if not earned:
            return f"🎖️ *Badges*\n\nYou haven't earned any badges yet!\n\nThere are {total} badges to collect. Start by reporting an issue or looking up politicians."

        response = f"🎖️ *Your Badges* ({count}/{total})\n\n"

        # Group by category
        by_category = {}
        for badge in earned:
            cat = badge.get("category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(badge)

        for category, badges in by_category.items():
            response += f"*{category.title()}:*\n"
            for badge in badges:
                response += f"  {badge['emoji']} {badge['name']}\n"
            response += "\n"

        remaining = total - count
        if remaining > 0:
            response += f"_{remaining} more badges to unlock!_"
        else:
            response += "_🎉 You've collected all badges!_"

        return response


# Singleton
badges_service = BadgesService()
