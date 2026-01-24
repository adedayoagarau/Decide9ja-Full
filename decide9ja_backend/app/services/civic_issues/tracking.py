"""
Issue Tracking Service - Track status of reported issues.
Database-backed, called by IssueTrackingAgent.
"""

import logging
from typing import Dict, Any, Optional, List

from app.database import SessionLocal, CommunityIssue

logger = logging.getLogger(__name__)


STATUS_EMOJI = {
    "reported": "📝",
    "verified": "✅",
    "acknowledged": "👀",
    "in_progress": "🔧",
    "resolved": "✨",
    "closed": "🔒",
    "rejected": "❌"
}


class IssueTrackingService:
    """Database-backed issue tracking service."""

    def get_issue(self, issue_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific issue by ID."""
        db = SessionLocal()
        try:
            # Clean issue ID
            clean_id = issue_id.upper().replace("#", "").strip()
            if not clean_id.startswith("ISS"):
                clean_id = f"ISS{clean_id}"

            issue = db.query(CommunityIssue).filter(
                CommunityIssue.issue_id == clean_id
            ).first()

            if not issue:
                return None

            return self._issue_to_dict(issue)

        finally:
            db.close()

    def get_user_issues(
        self,
        user_hash: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get all issues reported by a user."""
        db = SessionLocal()
        try:
            issues = db.query(CommunityIssue).filter(
                CommunityIssue.reporter_hash == user_hash
            ).order_by(
                CommunityIssue.created_at.desc()
            ).limit(limit).all()

            return [self._issue_to_dict(issue) for issue in issues]

        finally:
            db.close()

    def upvote_issue(self, issue_id: str, user_hash: str) -> Dict[str, Any]:
        """Upvote an issue ("me too" / verify)."""
        db = SessionLocal()
        try:
            issue = db.query(CommunityIssue).filter(
                CommunityIssue.issue_id == issue_id
            ).first()

            if not issue:
                return {"success": False, "error": "Issue not found"}

            # Increment upvotes
            issue.upvotes = (issue.upvotes or 0) + 1
            issue.verification_count = (issue.verification_count or 0) + 1

            # Auto-verify if enough confirmations
            if issue.verification_count >= 3 and issue.status == "reported":
                issue.status = "verified"

            db.commit()

            return {
                "success": True,
                "issue_id": issue_id,
                "upvotes": issue.upvotes,
                "status": issue.status
            }

        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def _issue_to_dict(self, issue: CommunityIssue) -> Dict[str, Any]:
        """Convert issue model to dict."""
        return {
            "issue_id": issue.issue_id,
            "title": issue.title,
            "description": issue.description,
            "category": issue.category,
            "status": issue.status,
            "state": issue.state,
            "lga": issue.lga,
            "address": issue.address,
            "upvotes": issue.upvotes or 0,
            "verification_count": issue.verification_count or 0,
            "responsible_authority": issue.responsible_authority,
            "official_response": issue.official_response,
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else None
        }

    def format_issue_detail(self, issue: Dict) -> str:
        """Format single issue for WhatsApp."""
        if not issue:
            return "Issue not found. Check the ID and try again."

        emoji = STATUS_EMOJI.get(issue["status"], "📝")

        response = f"{emoji} *Issue #{issue['issue_id']}*\n\n"
        response += f"*{issue['title']}*\n\n"
        response += f"📍 {issue['lga']}, {issue['state']}\n"
        response += f"📁 {issue['category'].title()}\n"
        response += f"📊 Status: {issue['status'].replace('_', ' ').title()}\n\n"

        if issue.get("description"):
            response += f"_{issue['description'][:150]}_\n\n"

        if issue.get("responsible_authority"):
            response += f"🏛️ Flagged to: {issue['responsible_authority']}\n"

        if issue.get("official_response"):
            response += f"\n💬 *Official Response:*\n_{issue['official_response'][:150]}_\n"

        response += f"\n👥 {issue['verification_count']} people verified this"
        response += f"\n👍 {issue['upvotes']} upvotes"

        response += "\n\nReply:\n• \"upvote\" to support\n• \"verify\" to confirm"

        return response

    def format_user_issues(self, issues: List[Dict]) -> str:
        """Format user's issues list for WhatsApp."""
        if not issues:
            return "📋 *Your Reports*\n\nYou haven't reported any issues yet.\n\nTo report a problem, say:\n• 'report bad road'\n• 'no light in my area'"

        response = "📋 *Your Recent Reports*\n\n"

        for issue in issues[:5]:
            emoji = STATUS_EMOJI.get(issue["status"], "📝")
            response += f"{emoji} *#{issue['issue_id']}* - {issue['category'].title()}\n"
            response += f"   {issue['lga']}, {issue['state']}\n"
            response += f"   Status: {issue['status'].replace('_', ' ').title()}\n\n"

        response += "_Reply with an issue ID for details_"

        return response


# Singleton
issue_tracking_service = IssueTrackingService()
