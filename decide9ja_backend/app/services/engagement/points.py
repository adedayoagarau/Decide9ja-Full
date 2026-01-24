"""
Points Service - Award and track civic points.
Database-backed, called by PointsAgent.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.database import SessionLocal, CivicProfile, PointTransaction

logger = logging.getLogger(__name__)


# Points awarded per action
POINT_VALUES = {
    "daily_login": 5,
    "ask_question": 10,
    "report_issue": 25,
    "issue_with_photo": 35,
    "verify_issue": 15,
    "vote_on_issue": 5,
    "lookup_politician": 5,
    "compare_candidates": 10,
    "check_promise": 5,
    "share_info": 10,
    "complete_onboarding": 50,
    "refer_user": 50,
    "issue_resolved": 100,
    "streak_bonus_7": 50,
    "streak_bonus_30": 200,
    "streak_bonus_100": 500,
}

# Milestones to announce
MILESTONES = [50, 100, 250, 500, 1000, 2500, 5000, 10000]


class PointsService:
    """Database-backed points service."""

    def award_points(
        self,
        user_hash: str,
        action: str,
        multiplier: float = 1.0,
        metadata: Dict = None
    ) -> Dict[str, Any]:
        """
        Award points for an action.

        Returns dict with: awarded, new_total, milestone_hit
        """
        points = POINT_VALUES.get(action, 0)
        if points == 0:
            return {"awarded": 0, "new_total": 0}

        final_points = int(points * multiplier)

        db = SessionLocal()
        try:
            # Get or create profile
            profile = db.query(CivicProfile).filter(
                CivicProfile.user_hash == user_hash
            ).first()

            if not profile:
                profile = CivicProfile(
                    user_hash=user_hash,
                    total_points=0,
                    level=1,
                    title="Civic Observer"
                )
                db.add(profile)
                db.flush()

            old_total = profile.total_points or 0

            # Update points
            profile.total_points = old_total + final_points
            profile.points_this_week = (profile.points_this_week or 0) + final_points
            profile.points_this_month = (profile.points_this_month or 0) + final_points
            profile.last_points_earned = datetime.utcnow()

            # Update action counts
            action_counts = json.loads(profile.action_counts_json or "{}")
            action_counts[action] = action_counts.get(action, 0) + 1
            profile.action_counts_json = json.dumps(action_counts)

            # Record transaction
            tx = PointTransaction(
                transaction_id=f"TXN-{user_hash[:8]}-{datetime.utcnow().timestamp()}",
                user_hash=user_hash,
                action=action,
                points=final_points,
                description=action.replace("_", " ").title(),
                metadata_json=json.dumps(metadata or {})
            )
            db.add(tx)

            db.commit()

            new_total = profile.total_points

            # Check milestones
            milestone_hit = None
            for milestone in MILESTONES:
                if new_total >= milestone > old_total:
                    milestone_hit = milestone
                    break

            return {
                "awarded": final_points,
                "multiplier": multiplier,
                "new_total": new_total,
                "milestone_hit": milestone_hit,
                "action": action
            }

        except Exception as e:
            logger.error(f"Failed to award points: {e}")
            db.rollback()
            return {"awarded": 0, "error": str(e)}
        finally:
            db.close()

    def get_points(self, user_hash: str) -> Dict[str, Any]:
        """Get user's point summary."""
        db = SessionLocal()
        try:
            profile = db.query(CivicProfile).filter(
                CivicProfile.user_hash == user_hash
            ).first()

            if not profile:
                return {"total_points": 0, "rank": 0, "recent": []}

            # Get rank
            rank = db.query(CivicProfile).filter(
                CivicProfile.total_points > profile.total_points
            ).count() + 1

            # Get recent transactions
            recent = db.query(PointTransaction).filter(
                PointTransaction.user_hash == user_hash
            ).order_by(PointTransaction.created_at.desc()).limit(10).all()

            return {
                "total_points": profile.total_points or 0,
                "points_this_week": profile.points_this_week or 0,
                "points_this_month": profile.points_this_month or 0,
                "level": profile.level or 1,
                "title": profile.title or "Civic Observer",
                "rank": rank,
                "recent": [
                    {
                        "action": tx.action,
                        "points": tx.points,
                        "created_at": tx.created_at.isoformat() if tx.created_at else None
                    }
                    for tx in recent
                ]
            }

        finally:
            db.close()

    def format_whatsapp(self, data: Dict) -> str:
        """Format points data for WhatsApp."""
        response = f"🏆 *Your Civic Points*\n\n"
        response += f"⭐ Total: *{data['total_points']:,}* points\n"
        response += f"📊 Rank: #{data['rank']:,} nationally\n"
        response += f"📈 This week: {data['points_this_week']:,} pts\n\n"

        if data.get("recent"):
            response += "*Recent Activity:*\n"
            for tx in data["recent"][:5]:
                response += f"• +{tx['points']} - {tx['action'].replace('_', ' ').title()}\n"

        response += "\n_Keep engaging to earn more!_"
        return response


# Singleton
points_service = PointsService()
