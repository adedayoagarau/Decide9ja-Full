"""
Streak Service - Track daily engagement streaks.
Database-backed, called by StreakAgent.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any

from app.database import SessionLocal, CivicProfile

logger = logging.getLogger(__name__)


class StreakService:
    """Database-backed streak tracking."""

    def log_activity(self, user_hash: str) -> Dict[str, Any]:
        """
        Log daily activity and update streak.
        Called by gatekeeper on each message.

        Returns: current_streak, is_new_day, milestone, streak_broken
        """
        today = date.today()

        db = SessionLocal()
        try:
            profile = db.query(CivicProfile).filter(
                CivicProfile.user_hash == user_hash
            ).first()

            if not profile:
                # Create new profile
                profile = CivicProfile(
                    user_hash=user_hash,
                    current_streak=1,
                    longest_streak=1,
                    last_active_date=datetime.combine(today, datetime.min.time()),
                    total_points=0,
                    level=1,
                    title="Civic Observer"
                )
                db.add(profile)
                db.commit()
                return {
                    "current_streak": 1,
                    "is_new_day": True,
                    "milestone": None
                }

            last_active = profile.last_active_date.date() if profile.last_active_date else None
            current_streak = profile.current_streak or 0
            longest_streak = profile.longest_streak or 0

            # Same day - no change
            if last_active == today:
                return {
                    "current_streak": current_streak,
                    "is_new_day": False,
                    "milestone": None
                }

            # Calculate days since last active
            if last_active:
                days_gap = (today - last_active).days
            else:
                days_gap = 999  # First time

            result = {}

            if days_gap == 1:
                # Consecutive day - increment streak
                new_streak = current_streak + 1
                new_longest = max(longest_streak, new_streak)

                profile.current_streak = new_streak
                profile.longest_streak = new_longest
                profile.last_active_date = datetime.combine(today, datetime.min.time())

                # Check milestones
                milestone = None
                if new_streak in [7, 14, 30, 60, 100]:
                    milestone = new_streak

                result = {
                    "current_streak": new_streak,
                    "is_new_day": True,
                    "milestone": milestone,
                    "multiplier": self._get_multiplier(new_streak)
                }

            elif days_gap > 1:
                # Streak broken - reset to 1
                previous = current_streak
                profile.current_streak = 1
                profile.last_active_date = datetime.combine(today, datetime.min.time())

                result = {
                    "current_streak": 1,
                    "is_new_day": True,
                    "streak_broken": True if previous >= 3 else False,
                    "previous_streak": previous,
                    "multiplier": 1.0
                }

            else:
                # First activity
                profile.current_streak = 1
                profile.longest_streak = max(1, longest_streak)
                profile.last_active_date = datetime.combine(today, datetime.min.time())
                result = {
                    "current_streak": 1,
                    "is_new_day": True,
                    "milestone": None
                }

            db.commit()
            return result

        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
            db.rollback()
            return {"current_streak": 0, "error": str(e)}
        finally:
            db.close()

    def _get_multiplier(self, streak: int) -> float:
        """Get point multiplier based on streak."""
        if streak >= 30:
            return 2.0
        elif streak >= 7:
            return 1.5
        return 1.0

    def get_streak(self, user_hash: str) -> Dict[str, Any]:
        """Get user's streak data."""
        db = SessionLocal()
        try:
            profile = db.query(CivicProfile).filter(
                CivicProfile.user_hash == user_hash
            ).first()

            if not profile:
                return {
                    "current_streak": 0,
                    "longest_streak": 0,
                    "multiplier": 1.0
                }

            current = profile.current_streak or 0
            return {
                "current_streak": current,
                "longest_streak": profile.longest_streak or 0,
                "last_active": profile.last_active_date.isoformat() if profile.last_active_date else None,
                "multiplier": self._get_multiplier(current)
            }

        finally:
            db.close()

    def format_whatsapp(self, data: Dict) -> str:
        """Format streak data for WhatsApp."""
        current = data.get("current_streak", 0)
        longest = data.get("longest_streak", 0)

        # Streak emoji based on length
        if current >= 30:
            emoji = "🔥🔥🔥"
        elif current >= 7:
            emoji = "🔥🔥"
        elif current >= 1:
            emoji = "🔥"
        else:
            emoji = "❄️"

        response = f"{emoji} *Your Streak*\n\n"
        response += f"Current: *{current} days*\n"
        response += f"Longest: *{longest} days*\n\n"

        multiplier = data.get("multiplier", 1.0)
        if multiplier > 1:
            response += f"💪 You have *{multiplier}x point multiplier* active!\n"

        if current > 0:
            response += f"\n_Come back tomorrow to keep it going!_"
        else:
            response += f"\n_Start your streak by engaging daily!_"

        return response


# Singleton
streak_service = StreakService()
