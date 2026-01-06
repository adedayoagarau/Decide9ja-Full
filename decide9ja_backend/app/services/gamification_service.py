"""
Gamification Service for Decide9ja.

Encourages civic engagement through:
- Points for civic actions
- Badges for achievements
- Streaks for daily engagement
- Leaderboards by location
- Levels and titles

All rewards are WhatsApp-deliverable.
"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class CivicAction(str, Enum):
    """Actions that earn points."""
    # Basic engagement
    DAILY_LOGIN = "daily_login"                     # 5 pts
    ASK_QUESTION = "ask_question"                   # 10 pts
    READ_NEWS = "read_news"                         # 5 pts
    COMPLETE_QUIZ = "complete_quiz"                 # 20 pts
    SHARE_FACT_CHECK = "share_fact_check"           # 15 pts

    # Community actions
    REPORT_ISSUE = "report_issue"                   # 25 pts
    VERIFY_ISSUE = "verify_issue"                   # 15 pts
    VOTE_ON_ISSUE = "vote_on_issue"                 # 5 pts
    UPDATE_ISSUE = "update_issue"                   # 10 pts
    ISSUE_RESOLVED = "issue_resolved"               # 50 pts (if your issue gets resolved)

    # Political engagement
    FOLLOW_POLITICIAN = "follow_politician"         # 10 pts
    TRACK_BILL = "track_bill"                       # 10 pts
    ATTEND_EVENT = "attend_event"                   # 30 pts
    REGISTER_TO_VOTE = "register_to_vote"           # 100 pts
    VERIFY_PVC = "verify_pvc"                       # 50 pts

    # Social
    REFER_FRIEND = "refer_friend"                   # 50 pts
    FRIEND_JOINED = "friend_joined"                 # 25 pts

    # Streaks
    STREAK_7_DAYS = "streak_7_days"                 # 50 pts bonus
    STREAK_30_DAYS = "streak_30_days"               # 200 pts bonus
    STREAK_100_DAYS = "streak_100_days"             # 500 pts bonus


# Points awarded for each action
ACTION_POINTS = {
    CivicAction.DAILY_LOGIN: 5,
    CivicAction.ASK_QUESTION: 10,
    CivicAction.READ_NEWS: 5,
    CivicAction.COMPLETE_QUIZ: 20,
    CivicAction.SHARE_FACT_CHECK: 15,
    CivicAction.REPORT_ISSUE: 25,
    CivicAction.VERIFY_ISSUE: 15,
    CivicAction.VOTE_ON_ISSUE: 5,
    CivicAction.UPDATE_ISSUE: 10,
    CivicAction.ISSUE_RESOLVED: 50,
    CivicAction.FOLLOW_POLITICIAN: 10,
    CivicAction.TRACK_BILL: 10,
    CivicAction.ATTEND_EVENT: 30,
    CivicAction.REGISTER_TO_VOTE: 100,
    CivicAction.VERIFY_PVC: 50,
    CivicAction.REFER_FRIEND: 50,
    CivicAction.FRIEND_JOINED: 25,
    CivicAction.STREAK_7_DAYS: 50,
    CivicAction.STREAK_30_DAYS: 200,
    CivicAction.STREAK_100_DAYS: 500,
}


class BadgeCategory(str, Enum):
    """Badge categories."""
    ENGAGEMENT = "engagement"
    COMMUNITY = "community"
    KNOWLEDGE = "knowledge"
    VOTING = "voting"
    SOCIAL = "social"
    SPECIAL = "special"


@dataclass
class Badge:
    """An achievement badge."""
    id: str
    name: str
    description: str
    emoji: str
    category: BadgeCategory
    points_required: int = 0
    actions_required: Dict[str, int] = field(default_factory=dict)
    is_secret: bool = False


@dataclass
class UserCivicProfile:
    """User's civic engagement profile."""
    user_hash: str
    display_name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    # Points
    total_points: int = 0
    points_this_month: int = 0
    points_this_week: int = 0
    # Level
    level: int = 1
    title: str = "Civic Observer"
    # Streaks
    current_streak: int = 0
    longest_streak: int = 0
    last_active_date: Optional[date] = None
    # Badges
    badges: List[str] = field(default_factory=list)
    # Action counts
    action_counts: Dict[str, int] = field(default_factory=dict)
    # Timestamps
    joined_at: datetime = field(default_factory=datetime.utcnow)
    last_points_earned: Optional[datetime] = None


@dataclass
class PointTransaction:
    """A point earning transaction."""
    id: str
    user_hash: str
    action: CivicAction
    points: int
    description: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Badges Definition
# =============================================================================

BADGES = {
    # Engagement badges
    "first_step": Badge(
        id="first_step",
        name="First Step",
        description="Asked your first question",
        emoji="👣",
        category=BadgeCategory.ENGAGEMENT,
        actions_required={"ask_question": 1}
    ),
    "curious_citizen": Badge(
        id="curious_citizen",
        name="Curious Citizen",
        description="Asked 10 questions",
        emoji="🔍",
        category=BadgeCategory.ENGAGEMENT,
        actions_required={"ask_question": 10}
    ),
    "news_junkie": Badge(
        id="news_junkie",
        name="News Junkie",
        description="Read 50 news updates",
        emoji="📰",
        category=BadgeCategory.ENGAGEMENT,
        actions_required={"read_news": 50}
    ),

    # Community badges
    "watchdog": Badge(
        id="watchdog",
        name="Community Watchdog",
        description="Reported your first issue",
        emoji="👁️",
        category=BadgeCategory.COMMUNITY,
        actions_required={"report_issue": 1}
    ),
    "verifier": Badge(
        id="verifier",
        name="Verified Verifier",
        description="Verified 5 community issues",
        emoji="✅",
        category=BadgeCategory.COMMUNITY,
        actions_required={"verify_issue": 5}
    ),
    "problem_solver": Badge(
        id="problem_solver",
        name="Problem Solver",
        description="Your reported issue got resolved",
        emoji="🏆",
        category=BadgeCategory.COMMUNITY,
        actions_required={"issue_resolved": 1}
    ),
    "advocate": Badge(
        id="advocate",
        name="Community Advocate",
        description="100+ votes on community issues",
        emoji="📢",
        category=BadgeCategory.COMMUNITY,
        actions_required={"vote_on_issue": 100}
    ),

    # Knowledge badges
    "quiz_master": Badge(
        id="quiz_master",
        name="Quiz Master",
        description="Completed 10 civic quizzes",
        emoji="🧠",
        category=BadgeCategory.KNOWLEDGE,
        actions_required={"complete_quiz": 10}
    ),
    "fact_checker": Badge(
        id="fact_checker",
        name="Fact Checker",
        description="Shared 10 fact-checks",
        emoji="🔬",
        category=BadgeCategory.KNOWLEDGE,
        actions_required={"share_fact_check": 10}
    ),

    # Voting badges
    "registered_voter": Badge(
        id="registered_voter",
        name="Registered Voter",
        description="Confirmed voter registration",
        emoji="🗳️",
        category=BadgeCategory.VOTING,
        actions_required={"register_to_vote": 1}
    ),
    "pvc_holder": Badge(
        id="pvc_holder",
        name="PVC Holder",
        description="Verified PVC possession",
        emoji="🪪",
        category=BadgeCategory.VOTING,
        actions_required={"verify_pvc": 1}
    ),

    # Social badges
    "connector": Badge(
        id="connector",
        name="Civic Connector",
        description="Referred 3 friends",
        emoji="🤝",
        category=BadgeCategory.SOCIAL,
        actions_required={"refer_friend": 3}
    ),
    "influencer": Badge(
        id="influencer",
        name="Civic Influencer",
        description="10 friends joined through your referral",
        emoji="⭐",
        category=BadgeCategory.SOCIAL,
        actions_required={"friend_joined": 10}
    ),

    # Streak badges
    "week_warrior": Badge(
        id="week_warrior",
        name="Week Warrior",
        description="7-day engagement streak",
        emoji="🔥",
        category=BadgeCategory.ENGAGEMENT,
        actions_required={"streak_7_days": 1}
    ),
    "monthly_champion": Badge(
        id="monthly_champion",
        name="Monthly Champion",
        description="30-day engagement streak",
        emoji="💪",
        category=BadgeCategory.ENGAGEMENT,
        actions_required={"streak_30_days": 1}
    ),
    "civic_hero": Badge(
        id="civic_hero",
        name="Civic Hero",
        description="100-day engagement streak",
        emoji="🦸",
        category=BadgeCategory.ENGAGEMENT,
        actions_required={"streak_100_days": 1}
    ),

    # Level badges
    "level_5": Badge(
        id="level_5",
        name="Rising Star",
        description="Reached Level 5",
        emoji="⭐",
        category=BadgeCategory.SPECIAL,
        points_required=500
    ),
    "level_10": Badge(
        id="level_10",
        name="Civic Champion",
        description="Reached Level 10",
        emoji="🏅",
        category=BadgeCategory.SPECIAL,
        points_required=2000
    ),
    "level_25": Badge(
        id="level_25",
        name="Democracy Defender",
        description="Reached Level 25",
        emoji="🛡️",
        category=BadgeCategory.SPECIAL,
        points_required=10000
    ),
}


# Levels and titles
LEVELS = [
    (0, 1, "Civic Observer"),
    (100, 2, "Engaged Citizen"),
    (250, 3, "Active Participant"),
    (500, 4, "Community Voice"),
    (750, 5, "Rising Star"),
    (1000, 6, "Civic Advocate"),
    (1500, 7, "Community Leader"),
    (2000, 8, "Civic Champion"),
    (3000, 9, "Democracy Builder"),
    (4000, 10, "Civic Guardian"),
    (5000, 11, "Community Hero"),
    (7500, 12, "Civic Legend"),
    (10000, 13, "Democracy Defender"),
    (15000, 14, "National Voice"),
    (20000, 15, "Civic Icon"),
    (30000, 16, "Master Citizen"),
    (50000, 17, "Civic Sage"),
    (75000, 18, "Democracy Champion"),
    (100000, 19, "Legendary Citizen"),
    (150000, 20, "Civic Elder"),
]


# =============================================================================
# Gamification Service
# =============================================================================

class GamificationService:
    """
    Service for civic engagement gamification.

    Features:
    - Award points for actions
    - Track and award badges
    - Manage streaks
    - Calculate levels
    - Generate leaderboards
    """

    def __init__(self):
        self._profiles: Dict[str, UserCivicProfile] = {}
        self._transactions: List[PointTransaction] = []
        self._transaction_counter = 0

    # -------------------------------------------------------------------------
    # Profile Management
    # -------------------------------------------------------------------------

    def get_profile(self, user_hash: str) -> UserCivicProfile:
        """Get or create user's civic profile."""
        if user_hash not in self._profiles:
            self._profiles[user_hash] = UserCivicProfile(user_hash=user_hash)
        return self._profiles[user_hash]

    def update_profile(
        self,
        user_hash: str,
        display_name: Optional[str] = None,
        state: Optional[str] = None,
        lga: Optional[str] = None
    ) -> UserCivicProfile:
        """Update user profile details."""
        profile = self.get_profile(user_hash)

        if display_name:
            profile.display_name = display_name
        if state:
            profile.state = state
        if lga:
            profile.lga = lga

        return profile

    # -------------------------------------------------------------------------
    # Points System
    # -------------------------------------------------------------------------

    def award_points(
        self,
        user_hash: str,
        action: CivicAction,
        description: str = "",
        metadata: Dict = None
    ) -> Dict[str, Any]:
        """
        Award points for a civic action.

        Args:
            user_hash: User identifier
            action: The action performed
            description: Description of the action
            metadata: Additional context

        Returns:
            Award result with points, badges, level ups
        """
        profile = self.get_profile(user_hash)
        points = ACTION_POINTS.get(action, 0)

        if points == 0:
            return {"success": False, "error": "Unknown action"}

        # Create transaction
        self._transaction_counter += 1
        transaction = PointTransaction(
            id=f"TXN{self._transaction_counter:08d}",
            user_hash=user_hash,
            action=action,
            points=points,
            description=description or action.value.replace("_", " ").title(),
            metadata=metadata or {}
        )
        self._transactions.append(transaction)

        # Update profile
        profile.total_points += points
        profile.points_this_month += points
        profile.points_this_week += points
        profile.last_points_earned = datetime.utcnow()

        # Update action count
        action_key = action.value
        profile.action_counts[action_key] = profile.action_counts.get(action_key, 0) + 1

        # Check for streak
        streak_bonus = self._update_streak(profile)

        # Check for level up
        old_level = profile.level
        new_level, new_title = self._calculate_level(profile.total_points)
        profile.level = new_level
        profile.title = new_title
        leveled_up = new_level > old_level

        # Check for new badges
        new_badges = self._check_badges(profile)
        for badge_id in new_badges:
            if badge_id not in profile.badges:
                profile.badges.append(badge_id)

        result = {
            "success": True,
            "points_earned": points,
            "total_points": profile.total_points,
            "level": profile.level,
            "title": profile.title,
            "leveled_up": leveled_up,
            "new_badges": [BADGES[b].name for b in new_badges] if new_badges else [],
            "streak": profile.current_streak
        }

        if streak_bonus:
            result["streak_bonus"] = streak_bonus

        return result

    def _update_streak(self, profile: UserCivicProfile) -> Optional[int]:
        """Update user's engagement streak."""
        today = date.today()
        bonus_points = 0

        if profile.last_active_date is None:
            # First activity
            profile.current_streak = 1
            profile.longest_streak = 1
        elif profile.last_active_date == today:
            # Already active today, no change
            pass
        elif profile.last_active_date == today - timedelta(days=1):
            # Consecutive day
            profile.current_streak += 1
            profile.longest_streak = max(profile.longest_streak, profile.current_streak)

            # Check for streak milestones
            if profile.current_streak == 7:
                bonus_points = ACTION_POINTS[CivicAction.STREAK_7_DAYS]
                profile.action_counts["streak_7_days"] = profile.action_counts.get("streak_7_days", 0) + 1
            elif profile.current_streak == 30:
                bonus_points = ACTION_POINTS[CivicAction.STREAK_30_DAYS]
                profile.action_counts["streak_30_days"] = profile.action_counts.get("streak_30_days", 0) + 1
            elif profile.current_streak == 100:
                bonus_points = ACTION_POINTS[CivicAction.STREAK_100_DAYS]
                profile.action_counts["streak_100_days"] = profile.action_counts.get("streak_100_days", 0) + 1
        else:
            # Streak broken
            profile.current_streak = 1

        profile.last_active_date = today

        if bonus_points:
            profile.total_points += bonus_points
            return bonus_points

        return None

    def _calculate_level(self, total_points: int) -> tuple:
        """Calculate level and title from points."""
        for points_required, level, title in reversed(LEVELS):
            if total_points >= points_required:
                return level, title
        return 1, "Civic Observer"

    def _check_badges(self, profile: UserCivicProfile) -> List[str]:
        """Check which new badges user qualifies for."""
        new_badges = []

        for badge_id, badge in BADGES.items():
            if badge_id in profile.badges:
                continue

            # Check points requirement
            if badge.points_required > 0:
                if profile.total_points >= badge.points_required:
                    new_badges.append(badge_id)
                continue

            # Check action requirements
            if badge.actions_required:
                qualified = True
                for action, count in badge.actions_required.items():
                    if profile.action_counts.get(action, 0) < count:
                        qualified = False
                        break
                if qualified:
                    new_badges.append(badge_id)

        return new_badges

    # -------------------------------------------------------------------------
    # Leaderboards
    # -------------------------------------------------------------------------

    def get_leaderboard(
        self,
        state: Optional[str] = None,
        lga: Optional[str] = None,
        period: str = "all_time",  # all_time, monthly, weekly
        limit: int = 10
    ) -> List[Dict]:
        """Get leaderboard rankings."""
        profiles = list(self._profiles.values())

        # Filter by location
        if state:
            profiles = [p for p in profiles if p.state and p.state.lower() == state.lower()]
        if lga:
            profiles = [p for p in profiles if p.lga and p.lga.lower() == lga.lower()]

        # Sort by appropriate points
        if period == "weekly":
            profiles.sort(key=lambda p: p.points_this_week, reverse=True)
            points_key = "points_this_week"
        elif period == "monthly":
            profiles.sort(key=lambda p: p.points_this_month, reverse=True)
            points_key = "points_this_month"
        else:
            profiles.sort(key=lambda p: p.total_points, reverse=True)
            points_key = "total_points"

        leaderboard = []
        for i, profile in enumerate(profiles[:limit], 1):
            leaderboard.append({
                "rank": i,
                "display_name": profile.display_name or f"Citizen {profile.user_hash[:4]}",
                "points": getattr(profile, points_key),
                "level": profile.level,
                "title": profile.title,
                "badges_count": len(profile.badges),
                "state": profile.state,
                "lga": profile.lga
            })

        return leaderboard

    def get_user_rank(
        self,
        user_hash: str,
        state: Optional[str] = None,
        lga: Optional[str] = None
    ) -> Dict:
        """Get user's rank on leaderboard."""
        profiles = list(self._profiles.values())

        if state:
            profiles = [p for p in profiles if p.state and p.state.lower() == state.lower()]
        if lga:
            profiles = [p for p in profiles if p.lga and p.lga.lower() == lga.lower()]

        profiles.sort(key=lambda p: p.total_points, reverse=True)

        for i, profile in enumerate(profiles, 1):
            if profile.user_hash == user_hash:
                return {
                    "rank": i,
                    "total_users": len(profiles),
                    "percentile": round((1 - i / len(profiles)) * 100, 1) if profiles else 0
                }

        return {"rank": None, "total_users": len(profiles), "percentile": 0}

    # -------------------------------------------------------------------------
    # WhatsApp Formatting
    # -------------------------------------------------------------------------

    def format_profile_whatsapp(self, user_hash: str) -> str:
        """Format user profile for WhatsApp."""
        profile = self.get_profile(user_hash)

        # Get rank
        rank_info = self.get_user_rank(user_hash, profile.state, profile.lga)

        lines = [
            f"🏆 *Your Civic Profile*\n",
            f"🎖️ Level {profile.level}: {profile.title}",
            f"⭐ {profile.total_points:,} points",
            f"🔥 {profile.current_streak} day streak",
        ]

        if rank_info["rank"]:
            location = profile.lga or profile.state or "Nigeria"
            lines.append(f"📊 Rank #{rank_info['rank']} in {location}")

        lines.append(f"\n🏅 *Badges ({len(profile.badges)}):*")
        if profile.badges:
            for badge_id in profile.badges[:5]:
                badge = BADGES.get(badge_id)
                if badge:
                    lines.append(f"  {badge.emoji} {badge.name}")
            if len(profile.badges) > 5:
                lines.append(f"  ... and {len(profile.badges) - 5} more")
        else:
            lines.append("  No badges yet. Keep engaging!")

        lines.append("\n📈 *This Week:*")
        lines.append(f"  • {profile.points_this_week} points earned")

        # Next level
        next_level_points = None
        for points_req, level, _ in LEVELS:
            if level == profile.level + 1:
                next_level_points = points_req
                break

        if next_level_points:
            remaining = next_level_points - profile.total_points
            lines.append(f"\n⏫ {remaining:,} points to next level")

        return "\n".join(lines)

    def format_points_earned_whatsapp(self, result: Dict) -> str:
        """Format points earned notification for WhatsApp."""
        lines = [f"✨ +{result['points_earned']} points!"]

        if result.get("streak_bonus"):
            lines.append(f"🔥 +{result['streak_bonus']} streak bonus!")

        if result.get("leveled_up"):
            lines.append(f"\n🎉 *LEVEL UP!*")
            lines.append(f"You're now Level {result['level']}: {result['title']}")

        if result.get("new_badges"):
            lines.append(f"\n🏅 *New Badge{'s' if len(result['new_badges']) > 1 else ''}!*")
            for badge_name in result["new_badges"]:
                lines.append(f"  • {badge_name}")

        lines.append(f"\n⭐ Total: {result['total_points']:,} points")

        return "\n".join(lines)

    def format_leaderboard_whatsapp(
        self,
        leaderboard: List[Dict],
        location: str,
        period: str = "all_time"
    ) -> str:
        """Format leaderboard for WhatsApp."""
        period_label = {
            "all_time": "All Time",
            "monthly": "This Month",
            "weekly": "This Week"
        }.get(period, "All Time")

        lines = [f"🏆 *{location} Leaderboard*", f"📅 {period_label}\n"]

        rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}

        for entry in leaderboard:
            emoji = rank_emoji.get(entry["rank"], f"{entry['rank']}.")
            name = entry["display_name"]
            points = entry["points"]
            level = entry["level"]

            lines.append(f"{emoji} *{name}*")
            lines.append(f"   ⭐ {points:,} pts • Lv.{level}")
            lines.append("")

        if not leaderboard:
            lines.append("No rankings yet. Be the first!")

        lines.append("Reply \"my rank\" to see your position.")

        return "\n".join(lines)

    def format_badges_whatsapp(self, user_hash: str) -> str:
        """Format user's badges for WhatsApp."""
        profile = self.get_profile(user_hash)

        lines = [f"🏅 *Your Badges* ({len(profile.badges)}/{len(BADGES)})\n"]

        # Group by category
        by_category = defaultdict(list)
        for badge_id in profile.badges:
            badge = BADGES.get(badge_id)
            if badge:
                by_category[badge.category.value].append(badge)

        # Show earned badges
        for category, badges in by_category.items():
            lines.append(f"*{category.title()}:*")
            for badge in badges:
                lines.append(f"  {badge.emoji} {badge.name}")
            lines.append("")

        # Show next available badges
        lines.append("*Next to unlock:*")
        shown = 0
        for badge_id, badge in BADGES.items():
            if badge_id in profile.badges:
                continue
            if badge.is_secret:
                continue
            if shown >= 3:
                break

            # Show requirement
            if badge.points_required:
                remaining = badge.points_required - profile.total_points
                if remaining > 0:
                    lines.append(f"  🔒 {badge.name} ({remaining:,} pts needed)")
                    shown += 1
            elif badge.actions_required:
                for action, count in badge.actions_required.items():
                    current = profile.action_counts.get(action, 0)
                    if current < count:
                        lines.append(f"  🔒 {badge.name} ({current}/{count} {action.replace('_', ' ')})")
                        shown += 1
                        break

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Get gamification statistics."""
        profiles = list(self._profiles.values())

        if not profiles:
            return {
                "total_users": 0,
                "total_points_awarded": 0,
                "total_badges_earned": 0,
                "avg_points": 0,
                "avg_streak": 0
            }

        total_points = sum(p.total_points for p in profiles)
        total_badges = sum(len(p.badges) for p in profiles)
        avg_streak = sum(p.current_streak for p in profiles) / len(profiles)

        # Level distribution
        level_dist = defaultdict(int)
        for p in profiles:
            level_dist[p.level] += 1

        return {
            "total_users": len(profiles),
            "total_points_awarded": total_points,
            "total_badges_earned": total_badges,
            "avg_points": round(total_points / len(profiles), 1),
            "avg_streak": round(avg_streak, 1),
            "level_distribution": dict(level_dist),
            "top_level": max(p.level for p in profiles) if profiles else 0
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_gamification_service: Optional[GamificationService] = None


def get_gamification_service() -> GamificationService:
    """Get singleton gamification service instance."""
    global _gamification_service
    if _gamification_service is None:
        _gamification_service = GamificationService()
    return _gamification_service
