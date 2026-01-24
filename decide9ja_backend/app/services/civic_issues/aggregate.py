"""
Issue Aggregate Service - Community patterns and trending issues.
Database-backed, called by IssueAggregateAgent.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict

from sqlalchemy import func
from app.database import SessionLocal, CommunityIssue

logger = logging.getLogger(__name__)


class IssueAggregateService:
    """Database-backed issue aggregation service."""

    def get_trending(
        self,
        state: Optional[str] = None,
        lga: Optional[str] = None,
        days: int = 30,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get trending issues (most reports/upvotes).

        Returns issues grouped by category with counts.
        """
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            query = db.query(
                CommunityIssue.category,
                CommunityIssue.state,
                func.count(CommunityIssue.id).label("count"),
                func.sum(CommunityIssue.upvotes).label("total_upvotes")
            ).filter(
                CommunityIssue.created_at > cutoff
            )

            location_label = "Nationwide"
            if state:
                query = query.filter(CommunityIssue.state == state)
                location_label = state
            if lga:
                query = query.filter(CommunityIssue.lga == lga)
                location_label = f"{lga}, {state}"

            results = query.group_by(
                CommunityIssue.category,
                CommunityIssue.state
            ).order_by(
                func.count(CommunityIssue.id).desc()
            ).limit(limit).all()

            trending = []
            for row in results:
                trending.append({
                    "category": row.category,
                    "state": row.state,
                    "count": row.count,
                    "upvotes": row.total_upvotes or 0
                })

            return {
                "location": location_label,
                "period_days": days,
                "trending": trending
            }

        finally:
            db.close()

    def get_local_issues(
        self,
        state: str,
        lga: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get issues in a specific location."""
        db = SessionLocal()
        try:
            query = db.query(CommunityIssue).filter(
                CommunityIssue.state == state,
                CommunityIssue.status.in_(["reported", "verified", "acknowledged", "in_progress"])
            )

            location_label = state
            if lga:
                query = query.filter(CommunityIssue.lga == lga)
                location_label = f"{lga}, {state}"
            if category:
                query = query.filter(CommunityIssue.category == category)

            issues = query.order_by(
                CommunityIssue.upvotes.desc(),
                CommunityIssue.created_at.desc()
            ).limit(limit).all()

            return {
                "location": location_label,
                "issues": [
                    {
                        "issue_id": issue.issue_id,
                        "title": issue.title,
                        "category": issue.category,
                        "status": issue.status,
                        "upvotes": issue.upvotes or 0,
                        "created_at": issue.created_at.isoformat() if issue.created_at else None
                    }
                    for issue in issues
                ],
                "total": len(issues)
            }

        finally:
            db.close()

    def get_stats(
        self,
        state: Optional[str] = None,
        lga: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get issue statistics for a location."""
        db = SessionLocal()
        try:
            query = db.query(CommunityIssue)

            if state:
                query = query.filter(CommunityIssue.state == state)
            if lga:
                query = query.filter(CommunityIssue.lga == lga)

            total = query.count()
            resolved = query.filter(CommunityIssue.status == "resolved").count()
            verified = query.filter(CommunityIssue.status == "verified").count()

            # Category breakdown
            by_category = defaultdict(int)
            for issue in query.all():
                by_category[issue.category] += 1

            return {
                "total_issues": total,
                "resolved": resolved,
                "verified": verified,
                "resolution_rate": round(resolved / total * 100, 1) if total > 0 else 0,
                "by_category": dict(by_category)
            }

        finally:
            db.close()

    def format_trending(self, data: Dict) -> str:
        """Format trending issues for WhatsApp."""
        location = data.get("location", "Nationwide")
        trending = data.get("trending", [])
        days = data.get("period_days", 30)

        if not trending:
            return f"📊 *Trending Issues in {location}*\n\nNo issues reported in the last {days} days."

        response = f"📊 *Trending Issues in {location}* (Last {days} days)\n\n"

        for i, item in enumerate(trending[:7], 1):
            response += f"{i}. *{item['category'].title()}*\n"
            response += f"   {item['count']} reports • {item['upvotes']} upvotes\n\n"

        response += "_Report an issue: 'I want to report a problem'_"

        return response

    def format_local_issues(self, data: Dict) -> str:
        """Format local issues for WhatsApp."""
        location = data.get("location", "Your area")
        issues = data.get("issues", [])

        if not issues:
            return f"📍 *Issues in {location}*\n\nNo open issues reported yet.\n\nBe the first! Say 'report an issue' to get started."

        response = f"📍 *Issues in {location}*\n\n"

        for issue in issues[:5]:
            # Priority indicator
            upvotes = issue.get("upvotes", 0)
            if upvotes >= 20:
                priority = "🔴"
            elif upvotes >= 5:
                priority = "🟡"
            else:
                priority = "⚪"

            response += f"{priority} *{issue['title'][:40]}*\n"
            response += f"   {issue['category'].title()} • {upvotes} upvotes\n\n"

        response += "_Reply with issue ID for details_"

        return response


# Singleton
issue_aggregate_service = IssueAggregateService()
