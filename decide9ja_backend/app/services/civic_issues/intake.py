"""
Issue Intake Service - Report new community issues.
Database-backed, called by IssueIntakeAgent.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.database import SessionLocal, CommunityIssue

logger = logging.getLogger(__name__)


# Issue categories
CATEGORIES = {
    "roads": "Roads/Potholes",
    "electricity": "Electricity (NEPA)",
    "water": "Water Supply",
    "security": "Security",
    "sanitation": "Sanitation/Waste",
    "healthcare": "Healthcare",
    "education": "Education",
    "drainage": "Drainage/Flooding",
    "streetlights": "Street Lights",
    "traffic": "Traffic",
    "other": "Other"
}

# Authority routing
AUTHORITY_MAP = {
    "roads": "{state} State Ministry of Works",
    "electricity": "Electricity Distribution Company",
    "water": "{state} Water Corporation",
    "security": "Nigeria Police Force",
    "sanitation": "{lga} Local Government",
    "healthcare": "{state} Ministry of Health",
    "education": "{state} Ministry of Education",
    "drainage": "{lga} Local Government",
    "streetlights": "{lga} Local Government",
    "traffic": "{state} Traffic Management Authority",
    "other": "{lga} Local Government"
}


class IssueIntakeService:
    """Database-backed issue intake service."""

    def report_issue(
        self,
        reporter_hash: str,
        title: str,
        description: str,
        category: str,
        state: str,
        lga: str,
        ward: Optional[str] = None,
        address: Optional[str] = None,
        photo_urls: list = None,
        reporter_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report a new community issue.

        Returns dict with: issue_id, similar_count, authority
        """
        db = SessionLocal()
        try:
            # Generate issue ID
            count = db.query(CommunityIssue).count()
            issue_id = f"ISS{count + 1:05d}"

            # Determine responsible authority
            authority = self._get_authority(category, state, lga)

            # Check for similar issues
            similar = self._find_similar(db, category, state, lga)

            # Create issue
            issue = CommunityIssue(
                issue_id=issue_id,
                title=title[:200],
                description=description[:500],
                category=category,
                state=state,
                lga=lga,
                ward=ward,
                address=address,
                reporter_hash=reporter_hash,
                reporter_name=reporter_name,
                status="reported",
                responsible_authority=authority,
                photo_urls_json=json.dumps(photo_urls or [])
            )
            db.add(issue)
            db.commit()

            logger.info(f"New issue reported: {issue_id} - {title[:50]}")

            return {
                "success": True,
                "issue_id": issue_id,
                "category": CATEGORIES.get(category, category),
                "authority": authority,
                "similar_count": similar["count"],
                "state": state,
                "lga": lga
            }

        except Exception as e:
            logger.error(f"Failed to report issue: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def _get_authority(self, category: str, state: str, lga: str) -> str:
        """Determine responsible authority."""
        template = AUTHORITY_MAP.get(category, "{lga} Local Government")
        return template.format(state=state, lga=lga)

    def _find_similar(self, db, category: str, state: str, lga: str) -> Dict:
        """Find similar issues in the area."""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=90)

        count = db.query(CommunityIssue).filter(
            CommunityIssue.category == category,
            CommunityIssue.state == state,
            CommunityIssue.lga == lga,
            CommunityIssue.created_at > cutoff
        ).count()

        return {"count": count}

    def format_whatsapp(self, data: Dict) -> str:
        """Format issue report confirmation for WhatsApp."""
        if not data.get("success"):
            return f"❌ Failed to report issue: {data.get('error', 'Unknown error')}"

        response = f"✅ *Issue Reported*\n\n"
        response += f"📋 Reference: #{data['issue_id']}\n"
        response += f"📍 Location: {data['lga']}, {data['state']}\n"
        response += f"📁 Category: {data['category']}\n\n"

        if data.get("similar_count", 0) > 0:
            response += f"👥 *{data['similar_count']} other people* reported similar issues in your area!\n\n"

        response += f"🏛️ Flagged to: {data['authority']}\n\n"
        response += f"Share this reference number: #{data['issue_id']}\n\n"
        response += "_Say 'my reports' to check status anytime._"

        return response


# Singleton
issue_intake_service = IssueIntakeService()
