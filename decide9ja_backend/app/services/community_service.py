"""
Community Service for Decide9ja.

Enables crowdsourced civic engagement:
- Issue reporting and tracking
- Community voting on priorities
- Crowdsourced updates on projects/issues
- Verification and moderation
- Local issue trends

All interactions are WhatsApp-compatible.
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class IssueCategory(str, Enum):
    """Community issue categories."""
    ROADS = "roads"
    ELECTRICITY = "electricity"
    WATER = "water"
    SECURITY = "security"
    SANITATION = "sanitation"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    DRAINAGE = "drainage"
    STREETLIGHTS = "streetlights"
    TRAFFIC = "traffic"
    CORRUPTION = "corruption"
    OTHER = "other"


class IssueStatus(str, Enum):
    """Issue lifecycle status."""
    REPORTED = "reported"
    VERIFIED = "verified"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"


class IssuePriority(str, Enum):
    """Issue priority based on community votes."""
    CRITICAL = "critical"   # 50+ votes
    HIGH = "high"           # 20-49 votes
    MEDIUM = "medium"       # 5-19 votes
    LOW = "low"             # <5 votes


class UpdateType(str, Enum):
    """Types of community updates."""
    STATUS_CHANGE = "status_change"
    PHOTO_UPDATE = "photo_update"
    COMMENT = "comment"
    VERIFICATION = "verification"
    OFFICIAL_RESPONSE = "official_response"


@dataclass
class CommunityIssue:
    """A community-reported issue."""
    id: str
    title: str
    description: str
    category: IssueCategory
    status: IssueStatus
    # Location
    ward: str
    lga: str
    state: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Reporter
    reporter_hash: str = "anonymous"
    reporter_name: Optional[str] = None
    # Media
    photo_urls: List[str] = field(default_factory=list)
    # Engagement
    upvotes: int = 0
    downvotes: int = 0
    comment_count: int = 0
    verification_count: int = 0
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    # Authority tracking
    responsible_authority: Optional[str] = None
    official_response: Optional[str] = None
    reference_number: Optional[str] = None


@dataclass
class IssueUpdate:
    """An update to a community issue."""
    id: str
    issue_id: str
    update_type: UpdateType
    content: str
    author_hash: str
    author_name: Optional[str] = None
    is_official: bool = False
    photo_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CommunityVote:
    """A vote on an issue."""
    issue_id: str
    voter_hash: str
    vote_type: str  # "up" or "down"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class IssueVerification:
    """A verification that an issue exists."""
    issue_id: str
    verifier_hash: str
    is_verified: bool = True
    comment: Optional[str] = None
    photo_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# Community Service
# =============================================================================

class CommunityService:
    """
    Service for community-driven civic reporting.

    Features:
    - Report issues via WhatsApp
    - Vote on issue priority
    - Verify issues exist
    - Track issue resolution
    - Get local issue trends
    """

    def __init__(self):
        self._issues: Dict[str, CommunityIssue] = {}
        self._updates: Dict[str, List[IssueUpdate]] = defaultdict(list)
        self._votes: Dict[str, Dict[str, str]] = defaultdict(dict)  # issue_id -> {voter_hash: vote_type}
        self._verifications: Dict[str, List[IssueVerification]] = defaultdict(list)

        # Counters for ID generation
        self._issue_counter = 0

        # Initialize sample data
        self._init_sample_issues()

    def _init_sample_issues(self):
        """Load sample community issues."""
        samples = [
            CommunityIssue(
                id="ISS001",
                title="Massive pothole on Agege Motor Road",
                description="Large pothole causing accidents near Ikeja Under Bridge",
                category=IssueCategory.ROADS,
                status=IssueStatus.VERIFIED,
                ward="Ward 3",
                lga="Ikeja",
                state="Lagos",
                address="Agege Motor Road, near Ikeja Under Bridge",
                upvotes=47,
                verification_count=12,
                responsible_authority="Lagos State Ministry of Works",
                created_at=datetime.utcnow() - timedelta(days=15)
            ),
            CommunityIssue(
                id="ISS002",
                title="No electricity for 2 weeks in Surulere",
                description="Entire Adeniran Ogunsanya street without power",
                category=IssueCategory.ELECTRICITY,
                status=IssueStatus.ACKNOWLEDGED,
                ward="Ward 7",
                lga="Surulere",
                state="Lagos",
                address="Adeniran Ogunsanya Street",
                upvotes=89,
                verification_count=34,
                responsible_authority="Eko Electricity Distribution Company",
                official_response="We are aware and working on transformer replacement",
                created_at=datetime.utcnow() - timedelta(days=5)
            ),
            CommunityIssue(
                id="ISS003",
                title="Blocked drainage causing flooding",
                description="Drainage blocked with refuse, floods entire market during rain",
                category=IssueCategory.DRAINAGE,
                status=IssueStatus.REPORTED,
                ward="Ward 2",
                lga="Oshodi-Isolo",
                state="Lagos",
                address="Mafoluku Market",
                upvotes=23,
                verification_count=8,
                created_at=datetime.utcnow() - timedelta(days=2)
            ),
        ]

        for issue in samples:
            self._issues[issue.id] = issue

    # -------------------------------------------------------------------------
    # Issue Reporting
    # -------------------------------------------------------------------------

    def report_issue(
        self,
        title: str,
        description: str,
        category: IssueCategory,
        state: str,
        lga: str,
        ward: Optional[str] = None,
        address: Optional[str] = None,
        reporter_hash: str = "anonymous",
        reporter_name: Optional[str] = None,
        photo_urls: List[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> CommunityIssue:
        """
        Report a new community issue.

        Args:
            title: Brief issue title
            description: Detailed description
            category: Issue category
            state: State name
            lga: LGA name
            ward: Ward name (optional)
            address: Specific address
            reporter_hash: Reporter identifier
            reporter_name: Reporter display name
            photo_urls: Photos of the issue
            latitude/longitude: GPS coordinates

        Returns:
            Created CommunityIssue
        """
        self._issue_counter += 1
        issue_id = f"ISS{self._issue_counter:05d}"

        # Determine responsible authority
        authority = self._determine_authority(category, state, lga)

        issue = CommunityIssue(
            id=issue_id,
            title=title[:100],
            description=description[:500],
            category=category,
            status=IssueStatus.REPORTED,
            ward=ward or "",
            lga=lga,
            state=state,
            address=address,
            latitude=latitude,
            longitude=longitude,
            reporter_hash=reporter_hash,
            reporter_name=reporter_name,
            photo_urls=photo_urls or [],
            responsible_authority=authority
        )

        self._issues[issue_id] = issue
        logger.info(f"New issue reported: {issue_id} - {title}")

        return issue

    def _determine_authority(
        self,
        category: IssueCategory,
        state: str,
        lga: str
    ) -> str:
        """Determine responsible authority for issue category."""
        authority_map = {
            IssueCategory.ROADS: f"{state} State Ministry of Works",
            IssueCategory.ELECTRICITY: "Electricity Distribution Company",
            IssueCategory.WATER: f"{state} Water Corporation",
            IssueCategory.SECURITY: "Nigeria Police Force",
            IssueCategory.SANITATION: f"{lga} Local Government",
            IssueCategory.HEALTHCARE: f"{state} Ministry of Health",
            IssueCategory.EDUCATION: f"{state} Ministry of Education",
            IssueCategory.DRAINAGE: f"{lga} Local Government",
            IssueCategory.STREETLIGHTS: f"{lga} Local Government",
            IssueCategory.TRAFFIC: f"{state} Traffic Management Authority",
        }

        return authority_map.get(category, f"{lga} Local Government")

    def format_issue_reported_whatsapp(self, issue: CommunityIssue) -> str:
        """Format issue confirmation for WhatsApp."""
        return f"""✅ *Issue Reported*

📋 Reference: #{issue.id}
📍 Location: {issue.lga}, {issue.state}
📁 Category: {issue.category.value.title()}

*{issue.title}*

Your report has been logged. Others can now vote to prioritize this issue.

🏛️ Flagged to: {issue.responsible_authority}

Share this reference number to help others verify: #{issue.id}

— Decide9ja"""

    # -------------------------------------------------------------------------
    # Voting
    # -------------------------------------------------------------------------

    def vote_issue(
        self,
        issue_id: str,
        voter_hash: str,
        vote_type: str = "up"
    ) -> Dict[str, Any]:
        """
        Vote on an issue to prioritize it.

        Args:
            issue_id: Issue to vote on
            voter_hash: Voter identifier
            vote_type: "up" or "down"

        Returns:
            Vote result with new counts
        """
        issue = self._issues.get(issue_id)
        if not issue:
            return {"success": False, "error": "Issue not found"}

        # Check for existing vote
        existing_vote = self._votes[issue_id].get(voter_hash)

        if existing_vote == vote_type:
            return {
                "success": False,
                "error": "You already voted this way",
                "upvotes": issue.upvotes,
                "downvotes": issue.downvotes
            }

        # Remove previous vote if exists
        if existing_vote:
            if existing_vote == "up":
                issue.upvotes -= 1
            else:
                issue.downvotes -= 1

        # Apply new vote
        if vote_type == "up":
            issue.upvotes += 1
        else:
            issue.downvotes += 1

        self._votes[issue_id][voter_hash] = vote_type
        issue.updated_at = datetime.utcnow()

        # Update priority based on votes
        self._update_priority(issue)

        return {
            "success": True,
            "issue_id": issue_id,
            "vote": vote_type,
            "upvotes": issue.upvotes,
            "downvotes": issue.downvotes,
            "priority": self._get_priority(issue).value
        }

    def _update_priority(self, issue: CommunityIssue):
        """Update issue priority based on votes."""
        # Priority is reflected in status and upvotes
        # If many votes, it gets more attention
        pass

    def _get_priority(self, issue: CommunityIssue) -> IssuePriority:
        """Calculate issue priority from votes."""
        net_votes = issue.upvotes - issue.downvotes

        if net_votes >= 50:
            return IssuePriority.CRITICAL
        elif net_votes >= 20:
            return IssuePriority.HIGH
        elif net_votes >= 5:
            return IssuePriority.MEDIUM
        else:
            return IssuePriority.LOW

    # -------------------------------------------------------------------------
    # Verification
    # -------------------------------------------------------------------------

    def verify_issue(
        self,
        issue_id: str,
        verifier_hash: str,
        is_verified: bool = True,
        comment: Optional[str] = None,
        photo_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify that an issue exists.

        Args:
            issue_id: Issue to verify
            verifier_hash: Verifier identifier
            is_verified: True if issue confirmed, False if not found
            comment: Optional verification comment
            photo_url: Optional photo proof

        Returns:
            Verification result
        """
        issue = self._issues.get(issue_id)
        if not issue:
            return {"success": False, "error": "Issue not found"}

        # Check for existing verification
        for v in self._verifications[issue_id]:
            if v.verifier_hash == verifier_hash:
                return {"success": False, "error": "You already verified this issue"}

        verification = IssueVerification(
            issue_id=issue_id,
            verifier_hash=verifier_hash,
            is_verified=is_verified,
            comment=comment,
            photo_url=photo_url
        )

        self._verifications[issue_id].append(verification)

        if is_verified:
            issue.verification_count += 1
            # Auto-verify if enough confirmations
            if issue.verification_count >= 3 and issue.status == IssueStatus.REPORTED:
                issue.status = IssueStatus.VERIFIED
                issue.updated_at = datetime.utcnow()

        return {
            "success": True,
            "issue_id": issue_id,
            "verification_count": issue.verification_count,
            "status": issue.status.value
        }

    # -------------------------------------------------------------------------
    # Updates
    # -------------------------------------------------------------------------

    def add_update(
        self,
        issue_id: str,
        content: str,
        author_hash: str,
        author_name: Optional[str] = None,
        update_type: UpdateType = UpdateType.COMMENT,
        is_official: bool = False,
        photo_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add an update to an issue.

        Args:
            issue_id: Issue to update
            content: Update content
            author_hash: Author identifier
            author_name: Author display name
            update_type: Type of update
            is_official: If from government/authority
            photo_url: Optional photo

        Returns:
            Update result
        """
        issue = self._issues.get(issue_id)
        if not issue:
            return {"success": False, "error": "Issue not found"}

        update_id = f"UPD{len(self._updates[issue_id]) + 1:04d}"

        update = IssueUpdate(
            id=update_id,
            issue_id=issue_id,
            update_type=update_type,
            content=content[:500],
            author_hash=author_hash,
            author_name=author_name,
            is_official=is_official,
            photo_url=photo_url
        )

        self._updates[issue_id].append(update)
        issue.comment_count += 1
        issue.updated_at = datetime.utcnow()

        # Handle official responses
        if is_official and update_type == UpdateType.OFFICIAL_RESPONSE:
            issue.official_response = content
            if issue.status == IssueStatus.REPORTED:
                issue.status = IssueStatus.ACKNOWLEDGED

        return {
            "success": True,
            "update_id": update_id,
            "issue_id": issue_id
        }

    def mark_resolved(
        self,
        issue_id: str,
        resolution_note: str,
        resolved_by: str
    ) -> Dict[str, Any]:
        """Mark an issue as resolved."""
        issue = self._issues.get(issue_id)
        if not issue:
            return {"success": False, "error": "Issue not found"}

        issue.status = IssueStatus.RESOLVED
        issue.resolved_at = datetime.utcnow()
        issue.updated_at = datetime.utcnow()

        # Add resolution update
        self.add_update(
            issue_id=issue_id,
            content=resolution_note,
            author_hash=resolved_by,
            update_type=UpdateType.STATUS_CHANGE,
            is_official=True
        )

        return {
            "success": True,
            "issue_id": issue_id,
            "status": "resolved"
        }

    # -------------------------------------------------------------------------
    # Issue Retrieval
    # -------------------------------------------------------------------------

    def get_issue(self, issue_id: str) -> Optional[CommunityIssue]:
        """Get issue by ID."""
        return self._issues.get(issue_id)

    def get_issue_updates(self, issue_id: str, limit: int = 10) -> List[IssueUpdate]:
        """Get updates for an issue."""
        updates = self._updates.get(issue_id, [])
        return sorted(updates, key=lambda u: u.created_at, reverse=True)[:limit]

    def get_local_issues(
        self,
        state: str,
        lga: str,
        category: Optional[IssueCategory] = None,
        status: Optional[IssueStatus] = None,
        limit: int = 10
    ) -> List[CommunityIssue]:
        """Get issues in a location."""
        results = []

        state_lower = state.lower()
        lga_lower = lga.lower()

        for issue in self._issues.values():
            if issue.state.lower() != state_lower:
                continue
            if issue.lga.lower() != lga_lower:
                continue
            if category and issue.category != category:
                continue
            if status and issue.status != status:
                continue
            results.append(issue)

        # Sort by upvotes (priority)
        results.sort(key=lambda i: i.upvotes, reverse=True)
        return results[:limit]

    def get_trending_issues(
        self,
        state: Optional[str] = None,
        limit: int = 5
    ) -> List[CommunityIssue]:
        """Get trending issues (most votes in last 7 days)."""
        cutoff = datetime.utcnow() - timedelta(days=7)
        results = []

        for issue in self._issues.values():
            if issue.created_at < cutoff:
                continue
            if state and issue.state.lower() != state.lower():
                continue
            if issue.status not in [IssueStatus.REPORTED, IssueStatus.VERIFIED, IssueStatus.ACKNOWLEDGED]:
                continue
            results.append(issue)

        results.sort(key=lambda i: i.upvotes, reverse=True)
        return results[:limit]

    # -------------------------------------------------------------------------
    # WhatsApp Formatting
    # -------------------------------------------------------------------------

    def format_issue_detail_whatsapp(self, issue: CommunityIssue) -> str:
        """Format issue detail for WhatsApp."""
        priority = self._get_priority(issue)
        status_emoji = {
            IssueStatus.REPORTED: "📋",
            IssueStatus.VERIFIED: "✅",
            IssueStatus.ACKNOWLEDGED: "👁️",
            IssueStatus.IN_PROGRESS: "🔧",
            IssueStatus.RESOLVED: "✨",
            IssueStatus.CLOSED: "📁",
            IssueStatus.REJECTED: "❌"
        }

        priority_emoji = {
            IssuePriority.CRITICAL: "🔴",
            IssuePriority.HIGH: "🟠",
            IssuePriority.MEDIUM: "🟡",
            IssuePriority.LOW: "⚪"
        }

        emoji = status_emoji.get(issue.status, "📋")
        p_emoji = priority_emoji.get(priority, "⚪")

        lines = [
            f"{emoji} *Issue #{issue.id}*\n",
            f"*{issue.title}*\n",
            f"{issue.description}\n",
            f"📍 {issue.lga}, {issue.state}",
            f"📁 {issue.category.value.title()}",
            f"📊 Status: {issue.status.value.replace('_', ' ').title()}",
            f"{p_emoji} Priority: {priority.value.title()} ({issue.upvotes} votes)\n",
            f"🏛️ Responsible: {issue.responsible_authority or 'TBD'}"
        ]

        if issue.official_response:
            lines.append(f"\n💬 *Official Response:*\n{issue.official_response[:150]}...")

        lines.append(f"\n👥 {issue.verification_count} people verified this")
        lines.append(f"💬 {issue.comment_count} updates")

        lines.append("\nReply:\n• \"upvote\" to prioritize\n• \"verify\" to confirm\n• \"update\" to add info")

        return "\n".join(lines)

    def format_issues_list_whatsapp(
        self,
        issues: List[CommunityIssue],
        location: str
    ) -> str:
        """Format issues list for WhatsApp."""
        if not issues:
            return f"No open issues reported in {location}. You can report one by saying \"report issue\"."

        lines = [f"📋 *Community Issues in {location}*\n"]

        for i, issue in enumerate(issues[:5], 1):
            priority = self._get_priority(issue)
            priority_emoji = {
                IssuePriority.CRITICAL: "🔴",
                IssuePriority.HIGH: "🟠",
                IssuePriority.MEDIUM: "🟡",
                IssuePriority.LOW: "⚪"
            }
            p_emoji = priority_emoji.get(priority, "⚪")

            lines.append(f"{i}. {p_emoji} *{issue.title[:40]}*")
            lines.append(f"   {issue.category.value.title()} • {issue.upvotes} votes")
            lines.append("")

        lines.append("Reply with number for details, or \"report\" to add a new issue.")

        return "\n".join(lines)

    def format_trending_whatsapp(
        self,
        issues: List[CommunityIssue],
        area: str
    ) -> str:
        """Format trending issues for WhatsApp."""
        if not issues:
            return f"No trending issues in {area} this week."

        lines = [f"🔥 *Trending Issues in {area}*\n"]

        for i, issue in enumerate(issues, 1):
            lines.append(f"{i}. *{issue.title[:50]}*")
            lines.append(f"   📍 {issue.lga} • 👍 {issue.upvotes} votes")
            lines.append("")

        lines.append("These issues have the most community attention this week.")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(
        self,
        state: Optional[str] = None,
        lga: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get community reporting statistics."""
        issues = list(self._issues.values())

        if state:
            issues = [i for i in issues if i.state.lower() == state.lower()]
        if lga:
            issues = [i for i in issues if i.lga.lower() == lga.lower()]

        by_category = defaultdict(int)
        by_status = defaultdict(int)

        for issue in issues:
            by_category[issue.category.value] += 1
            by_status[issue.status.value] += 1

        total_votes = sum(i.upvotes + i.downvotes for i in issues)
        resolved = len([i for i in issues if i.status == IssueStatus.RESOLVED])

        return {
            "total_issues": len(issues),
            "resolved": resolved,
            "resolution_rate": round(resolved / len(issues) * 100, 1) if issues else 0,
            "total_votes": total_votes,
            "by_category": dict(by_category),
            "by_status": dict(by_status)
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_community_service: Optional[CommunityService] = None


def get_community_service() -> CommunityService:
    """Get singleton community service instance."""
    global _community_service
    if _community_service is None:
        _community_service = CommunityService()
    return _community_service
