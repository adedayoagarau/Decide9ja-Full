"""
Engagement System - Database-backed civic engagement features.

Modular services:
- points.py: Award and track civic points
- badges.py: Achievement badges
- streaks.py: Daily engagement streaks
- leaderboard.py: Rankings by location
"""

from app.services.engagement.points import PointsService, points_service
from app.services.engagement.badges import BadgesService, badges_service
from app.services.engagement.streaks import StreakService, streak_service
from app.services.engagement.leaderboard import LeaderboardService, leaderboard_service

__all__ = [
    "PointsService", "points_service",
    "BadgesService", "badges_service",
    "StreakService", "streak_service",
    "LeaderboardService", "leaderboard_service",
]
