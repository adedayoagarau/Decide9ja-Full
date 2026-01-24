"""
Leaderboard Service - Rankings by location.
Database-backed, called by LeaderboardAgent.
"""

import logging
from typing import Dict, Any, List, Optional

from app.database import SessionLocal, CivicProfile

logger = logging.getLogger(__name__)


class LeaderboardService:
    """Database-backed leaderboard service."""

    def get_leaderboard(
        self,
        state: Optional[str] = None,
        lga: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get leaderboard rankings.

        Args:
            state: Filter by state
            lga: Filter by LGA
            limit: Number of entries

        Returns:
            Dict with top entries and metadata
        """
        db = SessionLocal()
        try:
            query = db.query(CivicProfile).filter(
                CivicProfile.total_points > 0
            )

            # Apply filters
            location_label = "National"
            if state:
                query = query.filter(CivicProfile.state == state)
                location_label = state
            if lga:
                query = query.filter(CivicProfile.lga == lga)
                location_label = f"{lga}, {state}"

            # Get top entries
            top_entries = query.order_by(
                CivicProfile.total_points.desc()
            ).limit(limit).all()

            # Get total count
            total_count = query.count()

            entries = []
            for i, profile in enumerate(top_entries, 1):
                # Anonymize name
                name = profile.display_name or "Anonymous"
                if name and len(name) > 1:
                    anon_name = name[0].upper() + "***"
                else:
                    anon_name = "A***"

                entries.append({
                    "rank": i,
                    "user_hash": profile.user_hash,
                    "display_name": anon_name,
                    "points": profile.total_points or 0,
                    "level": profile.level or 1,
                    "state": profile.state,
                    "lga": profile.lga
                })

            return {
                "location": location_label,
                "entries": entries,
                "total_participants": total_count
            }

        finally:
            db.close()

    def get_user_rank(
        self,
        user_hash: str,
        state: Optional[str] = None,
        lga: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get user's rank in the leaderboard."""
        db = SessionLocal()
        try:
            profile = db.query(CivicProfile).filter(
                CivicProfile.user_hash == user_hash
            ).first()

            if not profile:
                return {"rank": None, "total": 0}

            # Build query for counting users ahead
            query = db.query(CivicProfile).filter(
                CivicProfile.total_points > (profile.total_points or 0)
            )

            if state:
                query = query.filter(CivicProfile.state == state)
            if lga:
                query = query.filter(CivicProfile.lga == lga)

            rank = query.count() + 1

            # Get total participants
            total_query = db.query(CivicProfile).filter(
                CivicProfile.total_points > 0
            )
            if state:
                total_query = total_query.filter(CivicProfile.state == state)
            if lga:
                total_query = total_query.filter(CivicProfile.lga == lga)

            total = total_query.count()

            return {
                "rank": rank,
                "total": total,
                "percentile": round((1 - rank / total) * 100, 1) if total > 0 else 0
            }

        finally:
            db.close()

    def format_whatsapp(
        self,
        data: Dict,
        user_hash: Optional[str] = None
    ) -> str:
        """Format leaderboard for WhatsApp."""
        location = data.get("location", "National")
        entries = data.get("entries", [])

        response = f"🏆 *{location} Leaderboard*\n\n"

        if not entries:
            return response + "No rankings yet. Be the first to earn points!"

        for entry in entries:
            rank = entry["rank"]

            # Medal emojis for top 3
            if rank == 1:
                medal = "🥇"
            elif rank == 2:
                medal = "🥈"
            elif rank == 3:
                medal = "🥉"
            else:
                medal = f"{rank}."

            # Check if current user
            is_me = user_hash and entry.get("user_hash") == user_hash
            marker = " ← You" if is_me else ""

            name = entry["display_name"]
            points = entry["points"]

            response += f"{medal} *{name}* - {points:,} pts{marker}\n"

        response += f"\n_{data.get('total_participants', 0)} total participants_"
        response += "\n\n_Say 'my lga leaderboard' or 'state leaderboard' for local rankings_"

        return response


# Singleton
leaderboard_service = LeaderboardService()
