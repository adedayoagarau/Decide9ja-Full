"""
Broadcast Messaging Service for Decide9ja.

Enables Tade to proactively message users with:
- Targeted campaigns (by state, LGA, age, interests)
- Scheduled digests (daily briefings, weekly summaries)
- Breaking news alerts
- Election reminders
- Civic engagement prompts

All messages are WhatsApp-compatible (text, limited formatting).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class MessagePriority(str, Enum):
    """Message priority levels."""
    BREAKING = "breaking"      # Immediate delivery
    HIGH = "high"              # Within 1 hour
    NORMAL = "normal"          # Within 4 hours
    LOW = "low"                # Batch with digest


class CampaignStatus(str, Enum):
    """Campaign lifecycle status."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class AudienceType(str, Enum):
    """Audience targeting types."""
    ALL = "all"                    # All users
    STATE = "state"                # Users in specific state(s)
    LGA = "lga"                    # Users in specific LGA(s)
    SENATORIAL = "senatorial"      # Users in senatorial district
    FEDERAL_CONST = "federal_const"  # Users in federal constituency
    INTERESTS = "interests"        # Users with specific interests
    FOLLOWED_POLITICIAN = "followed_politician"  # Users following a politician
    CUSTOM = "custom"              # Custom user list


@dataclass
class AudienceCriteria:
    """Defines who receives a broadcast."""
    audience_type: AudienceType = AudienceType.ALL
    states: List[str] = field(default_factory=list)
    lgas: List[str] = field(default_factory=list)
    senatorial_districts: List[str] = field(default_factory=list)
    federal_constituencies: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    followed_politicians: List[str] = field(default_factory=list)
    exclude_states: List[str] = field(default_factory=list)
    exclude_users: List[str] = field(default_factory=list)
    custom_user_hashes: List[str] = field(default_factory=list)
    # Engagement filters
    min_engagement_score: Optional[float] = None
    last_active_within_days: Optional[int] = None
    registered_after: Optional[datetime] = None
    has_voted: Optional[bool] = None

    def to_dict(self) -> Dict:
        return {
            "audience_type": self.audience_type.value,
            "states": self.states,
            "lgas": self.lgas,
            "senatorial_districts": self.senatorial_districts,
            "federal_constituencies": self.federal_constituencies,
            "interests": self.interests,
            "followed_politicians": self.followed_politicians,
            "exclude_states": self.exclude_states,
            "exclude_users": self.exclude_users,
            "custom_user_hashes": self.custom_user_hashes,
            "min_engagement_score": self.min_engagement_score,
            "last_active_within_days": self.last_active_within_days,
            "registered_after": self.registered_after.isoformat() if self.registered_after else None,
            "has_voted": self.has_voted
        }


@dataclass
class BroadcastMessage:
    """A message to be broadcast."""
    id: str
    title: str                     # Internal title (not sent)
    content: str                   # WhatsApp message content
    priority: MessagePriority = MessagePriority.NORMAL
    # Personalization placeholders: {name}, {state}, {lga}
    personalize: bool = True
    # Call to action
    cta_text: Optional[str] = None  # e.g., "Reply 1 to learn more"
    cta_options: List[str] = field(default_factory=list)
    # Metadata
    category: str = "general"       # news, election, civic, alert
    tags: List[str] = field(default_factory=list)
    source_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"


@dataclass
class Campaign:
    """A broadcast campaign."""
    id: str
    name: str
    message: BroadcastMessage
    audience: AudienceCriteria
    status: CampaignStatus = CampaignStatus.DRAFT
    # Scheduling
    scheduled_at: Optional[datetime] = None
    send_window_start: Optional[int] = None  # Hour (0-23)
    send_window_end: Optional[int] = None    # Hour (0-23)
    # Tracking
    total_recipients: int = 0
    sent_count: int = 0
    delivered_count: int = 0
    read_count: int = 0
    replied_count: int = 0
    failed_count: int = 0
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ScheduledDigest:
    """A recurring digest configuration."""
    id: str
    name: str
    frequency: str                  # daily, weekly, breaking
    send_time: str                  # HH:MM in WAT
    send_days: List[int] = field(default_factory=lambda: [0,1,2,3,4,5,6])  # 0=Mon
    audience: AudienceCriteria = field(default_factory=AudienceCriteria)
    content_type: str = "news"      # news, polls, representatives, mixed
    is_active: bool = True
    last_sent: Optional[datetime] = None


# =============================================================================
# Broadcast Service
# =============================================================================

class BroadcastService:
    """
    Service for managing broadcast messages and campaigns.

    Features:
    - Create and schedule campaigns
    - Target specific audiences
    - Personalize messages
    - Track delivery and engagement
    - Rate limiting and compliance
    """

    def __init__(self):
        self._campaigns: Dict[str, Campaign] = {}
        self._digests: Dict[str, ScheduledDigest] = {}
        self._message_queue: List[Dict] = []
        self._sent_log: List[Dict] = []

        # Rate limiting
        self.max_messages_per_hour = 1000
        self.max_messages_per_user_per_day = 3

        # Initialize default digests
        self._init_default_digests()

    def _init_default_digests(self):
        """Set up default scheduled digests."""
        # Daily morning briefing
        self._digests["daily_briefing"] = ScheduledDigest(
            id="daily_briefing",
            name="Daily Morning Briefing",
            frequency="daily",
            send_time="07:00",
            send_days=[0, 1, 2, 3, 4, 5, 6],
            content_type="news",
            is_active=True
        )

        # Weekly summary (Sundays)
        self._digests["weekly_summary"] = ScheduledDigest(
            id="weekly_summary",
            name="Weekly Political Summary",
            frequency="weekly",
            send_time="09:00",
            send_days=[6],  # Sunday
            content_type="mixed",
            is_active=True
        )

        # Breaking news (on-demand, no schedule)
        self._digests["breaking_news"] = ScheduledDigest(
            id="breaking_news",
            name="Breaking News Alerts",
            frequency="breaking",
            send_time="",
            content_type="news",
            is_active=True
        )

    # -------------------------------------------------------------------------
    # Campaign Management
    # -------------------------------------------------------------------------

    def create_campaign(
        self,
        name: str,
        content: str,
        audience: AudienceCriteria,
        title: str = "",
        priority: MessagePriority = MessagePriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        category: str = "general",
        cta_text: Optional[str] = None,
        cta_options: List[str] = None,
        created_by: str = "admin"
    ) -> Campaign:
        """
        Create a new broadcast campaign.

        Args:
            name: Campaign name (internal)
            content: Message content with optional {placeholders}
            audience: Targeting criteria
            title: Message title (internal)
            priority: Delivery priority
            scheduled_at: When to send (None = draft)
            category: Message category
            cta_text: Call to action prompt
            cta_options: Reply options
            created_by: Creator identifier

        Returns:
            Created Campaign object
        """
        campaign_id = self._generate_id("campaign")
        message_id = self._generate_id("message")

        message = BroadcastMessage(
            id=message_id,
            title=title or name,
            content=content,
            priority=priority,
            cta_text=cta_text,
            cta_options=cta_options or [],
            category=category,
            created_by=created_by
        )

        campaign = Campaign(
            id=campaign_id,
            name=name,
            message=message,
            audience=audience,
            status=CampaignStatus.SCHEDULED if scheduled_at else CampaignStatus.DRAFT,
            scheduled_at=scheduled_at
        )

        self._campaigns[campaign_id] = campaign
        logger.info(f"Created campaign: {campaign_id} - {name}")

        return campaign

    def schedule_campaign(
        self,
        campaign_id: str,
        scheduled_at: datetime,
        send_window_start: int = 8,
        send_window_end: int = 20
    ) -> bool:
        """Schedule a draft campaign for sending."""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return False

        if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.PAUSED]:
            return False

        campaign.scheduled_at = scheduled_at
        campaign.send_window_start = send_window_start
        campaign.send_window_end = send_window_end
        campaign.status = CampaignStatus.SCHEDULED

        logger.info(f"Scheduled campaign {campaign_id} for {scheduled_at}")
        return True

    def pause_campaign(self, campaign_id: str) -> bool:
        """Pause an active campaign."""
        campaign = self._campaigns.get(campaign_id)
        if not campaign or campaign.status != CampaignStatus.SENDING:
            return False

        campaign.status = CampaignStatus.PAUSED
        return True

    def cancel_campaign(self, campaign_id: str) -> bool:
        """Cancel a campaign."""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return False

        if campaign.status in [CampaignStatus.COMPLETED]:
            return False

        campaign.status = CampaignStatus.CANCELLED
        return True

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get campaign by ID."""
        return self._campaigns.get(campaign_id)

    def list_campaigns(
        self,
        status: Optional[CampaignStatus] = None,
        limit: int = 50
    ) -> List[Campaign]:
        """List campaigns, optionally filtered by status."""
        campaigns = list(self._campaigns.values())

        if status:
            campaigns = [c for c in campaigns if c.status == status]

        # Sort by created_at descending
        campaigns.sort(key=lambda c: c.created_at, reverse=True)

        return campaigns[:limit]

    # -------------------------------------------------------------------------
    # Audience Resolution
    # -------------------------------------------------------------------------

    def resolve_audience(self, criteria: AudienceCriteria) -> List[Dict]:
        """
        Resolve audience criteria to list of recipient users.

        Returns list of user dicts with: phone_hash, name, state, lga
        """
        import os
        from sqlalchemy import create_engine, text

        try:
            engine = create_engine(os.getenv('DATABASE_URL'))

            with engine.connect() as conn:
                # Build dynamic query based on criteria
                conditions = ["is_active = true"]
                params = {}

                if criteria.audience_type == AudienceType.ALL:
                    pass  # No additional filters

                elif criteria.audience_type == AudienceType.STATE:
                    if criteria.states:
                        placeholders = [f":state_{i}" for i in range(len(criteria.states))]
                        conditions.append(f"LOWER(state) IN ({', '.join(placeholders)})")
                        for i, state in enumerate(criteria.states):
                            params[f"state_{i}"] = state.lower()

                elif criteria.audience_type == AudienceType.LGA:
                    if criteria.lgas:
                        placeholders = [f":lga_{i}" for i in range(len(criteria.lgas))]
                        conditions.append(f"LOWER(lga) IN ({', '.join(placeholders)})")
                        for i, lga in enumerate(criteria.lgas):
                            params[f"lga_{i}"] = lga.lower()

                elif criteria.audience_type == AudienceType.CUSTOM:
                    if criteria.custom_user_hashes:
                        placeholders = [f":hash_{i}" for i in range(len(criteria.custom_user_hashes))]
                        conditions.append(f"phone_hash IN ({', '.join(placeholders)})")
                        for i, h in enumerate(criteria.custom_user_hashes):
                            params[f"hash_{i}"] = h

                # Exclusions
                if criteria.exclude_states:
                    placeholders = [f":ex_state_{i}" for i in range(len(criteria.exclude_states))]
                    conditions.append(f"LOWER(state) NOT IN ({', '.join(placeholders)})")
                    for i, state in enumerate(criteria.exclude_states):
                        params[f"ex_state_{i}"] = state.lower()

                if criteria.exclude_users:
                    placeholders = [f":ex_user_{i}" for i in range(len(criteria.exclude_users))]
                    conditions.append(f"phone_hash NOT IN ({', '.join(placeholders)})")
                    for i, h in enumerate(criteria.exclude_users):
                        params[f"ex_user_{i}"] = h

                # Activity filters
                if criteria.last_active_within_days:
                    conditions.append("last_active_at >= NOW() - INTERVAL :active_days DAY")
                    params["active_days"] = criteria.last_active_within_days

                if criteria.registered_after:
                    conditions.append("created_at >= :reg_after")
                    params["reg_after"] = criteria.registered_after

                where_clause = " AND ".join(conditions)

                query = text(f"""
                    SELECT phone_hash, name, state, lga,
                           senatorial_district, federal_constituency,
                           preferences_json
                    FROM users
                    WHERE {where_clause}
                    LIMIT 10000
                """)

                result = conn.execute(query, params)
                users = [dict(row._mapping) for row in result]

                # Additional filtering for interests/followed politicians
                if criteria.interests:
                    users = self._filter_by_interests(users, criteria.interests)

                if criteria.followed_politicians:
                    users = self._filter_by_followed(users, criteria.followed_politicians, conn)

                return users

        except Exception as e:
            logger.error(f"Error resolving audience: {e}")
            return []

    def _filter_by_interests(self, users: List[Dict], interests: List[str]) -> List[Dict]:
        """Filter users by interests from preferences_json."""
        filtered = []
        for user in users:
            prefs = user.get("preferences_json") or {}
            user_interests = prefs.get("interests", [])
            if any(i.lower() in [ui.lower() for ui in user_interests] for i in interests):
                filtered.append(user)
        return filtered

    def _filter_by_followed(self, users: List[Dict], politicians: List[str], conn) -> List[Dict]:
        """Filter users who follow specific politicians."""
        from sqlalchemy import text

        user_hashes = [u["phone_hash"] for u in users]
        if not user_hashes:
            return []

        # Query user_follows table
        query = text("""
            SELECT DISTINCT uf.user_phone_hash
            FROM user_follows uf
            JOIN candidates_2027 c ON uf.candidate_id = c.id
            WHERE uf.user_phone_hash = ANY(:hashes)
            AND c.slug = ANY(:politicians)
        """)

        result = conn.execute(query, {
            "hashes": user_hashes,
            "politicians": politicians
        })

        following_hashes = {row[0] for row in result}
        return [u for u in users if u["phone_hash"] in following_hashes]

    def get_audience_count(self, criteria: AudienceCriteria) -> int:
        """Get estimated recipient count for audience criteria."""
        users = self.resolve_audience(criteria)
        return len(users)

    # -------------------------------------------------------------------------
    # Message Sending
    # -------------------------------------------------------------------------

    def send_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """
        Execute a campaign - resolve audience and queue messages.

        Returns sending status and stats.
        """
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return {"success": False, "error": "Campaign not found"}

        if campaign.status not in [CampaignStatus.SCHEDULED, CampaignStatus.PAUSED]:
            return {"success": False, "error": f"Campaign status is {campaign.status}"}

        # Resolve audience
        recipients = self.resolve_audience(campaign.audience)
        campaign.total_recipients = len(recipients)

        if not recipients:
            return {"success": False, "error": "No recipients match criteria"}

        campaign.status = CampaignStatus.SENDING
        campaign.started_at = datetime.utcnow()

        # Queue messages for each recipient
        queued = 0
        for recipient in recipients:
            message_content = self._personalize_message(
                campaign.message.content,
                recipient
            )

            # Add CTA if present
            if campaign.message.cta_text:
                message_content += f"\n\n{campaign.message.cta_text}"
                if campaign.message.cta_options:
                    for i, opt in enumerate(campaign.message.cta_options, 1):
                        message_content += f"\n{i}. {opt}"

            self._message_queue.append({
                "campaign_id": campaign_id,
                "recipient_hash": recipient["phone_hash"],
                "content": message_content,
                "priority": campaign.message.priority.value,
                "queued_at": datetime.utcnow().isoformat(),
                "status": "queued"
            })
            queued += 1

        logger.info(f"Campaign {campaign_id}: Queued {queued} messages")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "recipients": campaign.total_recipients,
            "queued": queued,
            "status": "sending"
        }

    def _personalize_message(self, content: str, recipient: Dict) -> str:
        """Replace placeholders with recipient data."""
        replacements = {
            "{name}": recipient.get("name", "there"),
            "{state}": recipient.get("state", "your state"),
            "{lga}": recipient.get("lga", "your LGA"),
            "{senatorial}": recipient.get("senatorial_district", ""),
            "{constituency}": recipient.get("federal_constituency", "")
        }

        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)

        return content

    def send_breaking_news(
        self,
        content: str,
        title: str = "Breaking News",
        audience: AudienceCriteria = None,
        source_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send immediate breaking news alert.

        Args:
            content: News content
            title: Internal title
            audience: Target audience (default: all)
            source_url: Source link

        Returns:
            Sending result
        """
        if audience is None:
            audience = AudienceCriteria(audience_type=AudienceType.ALL)

        campaign = self.create_campaign(
            name=f"Breaking: {title}",
            content=content,
            audience=audience,
            priority=MessagePriority.BREAKING,
            category="breaking_news",
            scheduled_at=datetime.utcnow()
        )

        return self.send_campaign(campaign.id)

    def send_to_user(
        self,
        user_hash: str,
        content: str,
        category: str = "direct"
    ) -> Dict[str, Any]:
        """
        Send a direct message to a specific user.

        Args:
            user_hash: User's phone hash
            content: Message content
            category: Message category

        Returns:
            Sending result
        """
        self._message_queue.append({
            "campaign_id": None,
            "recipient_hash": user_hash,
            "content": content,
            "priority": MessagePriority.HIGH.value,
            "queued_at": datetime.utcnow().isoformat(),
            "status": "queued",
            "category": category
        })

        return {"success": True, "queued": 1}

    # -------------------------------------------------------------------------
    # Digest Management
    # -------------------------------------------------------------------------

    def get_digest(self, digest_id: str) -> Optional[ScheduledDigest]:
        """Get a scheduled digest configuration."""
        return self._digests.get(digest_id)

    def update_digest(
        self,
        digest_id: str,
        send_time: Optional[str] = None,
        send_days: Optional[List[int]] = None,
        audience: Optional[AudienceCriteria] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """Update a digest configuration."""
        digest = self._digests.get(digest_id)
        if not digest:
            return False

        if send_time is not None:
            digest.send_time = send_time
        if send_days is not None:
            digest.send_days = send_days
        if audience is not None:
            digest.audience = audience
        if is_active is not None:
            digest.is_active = is_active

        return True

    def list_digests(self) -> List[ScheduledDigest]:
        """List all configured digests."""
        return list(self._digests.values())

    # -------------------------------------------------------------------------
    # Queue Processing
    # -------------------------------------------------------------------------

    def get_pending_messages(self, limit: int = 100) -> List[Dict]:
        """Get pending messages from queue for sending."""
        pending = [m for m in self._message_queue if m["status"] == "queued"]

        # Sort by priority
        priority_order = {
            MessagePriority.BREAKING.value: 0,
            MessagePriority.HIGH.value: 1,
            MessagePriority.NORMAL.value: 2,
            MessagePriority.LOW.value: 3
        }
        pending.sort(key=lambda m: priority_order.get(m["priority"], 2))

        return pending[:limit]

    def mark_sent(self, recipient_hash: str, campaign_id: Optional[str] = None) -> bool:
        """Mark a message as sent."""
        for msg in self._message_queue:
            if msg["recipient_hash"] == recipient_hash:
                if campaign_id is None or msg["campaign_id"] == campaign_id:
                    msg["status"] = "sent"
                    msg["sent_at"] = datetime.utcnow().isoformat()

                    # Update campaign stats
                    if campaign_id:
                        campaign = self._campaigns.get(campaign_id)
                        if campaign:
                            campaign.sent_count += 1
                    return True
        return False

    def mark_delivered(self, recipient_hash: str, campaign_id: Optional[str] = None) -> bool:
        """Mark a message as delivered."""
        for msg in self._message_queue:
            if msg["recipient_hash"] == recipient_hash and msg["status"] == "sent":
                if campaign_id is None or msg["campaign_id"] == campaign_id:
                    msg["status"] = "delivered"

                    if campaign_id:
                        campaign = self._campaigns.get(campaign_id)
                        if campaign:
                            campaign.delivered_count += 1
                    return True
        return False

    def mark_failed(self, recipient_hash: str, error: str, campaign_id: Optional[str] = None) -> bool:
        """Mark a message as failed."""
        for msg in self._message_queue:
            if msg["recipient_hash"] == recipient_hash:
                if campaign_id is None or msg["campaign_id"] == campaign_id:
                    msg["status"] = "failed"
                    msg["error"] = error

                    if campaign_id:
                        campaign = self._campaigns.get(campaign_id)
                        if campaign:
                            campaign.failed_count += 1
                    return True
        return False

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_campaign_stats(self, campaign_id: str) -> Optional[Dict]:
        """Get detailed stats for a campaign."""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return None

        delivery_rate = (
            campaign.delivered_count / campaign.sent_count * 100
            if campaign.sent_count > 0 else 0
        )

        reply_rate = (
            campaign.replied_count / campaign.delivered_count * 100
            if campaign.delivered_count > 0 else 0
        )

        return {
            "campaign_id": campaign_id,
            "name": campaign.name,
            "status": campaign.status.value,
            "total_recipients": campaign.total_recipients,
            "sent": campaign.sent_count,
            "delivered": campaign.delivered_count,
            "read": campaign.read_count,
            "replied": campaign.replied_count,
            "failed": campaign.failed_count,
            "delivery_rate": round(delivery_rate, 1),
            "reply_rate": round(reply_rate, 1),
            "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
            "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None
        }

    def get_queue_stats(self) -> Dict:
        """Get message queue statistics."""
        total = len(self._message_queue)
        by_status = {}
        by_priority = {}

        for msg in self._message_queue:
            status = msg["status"]
            priority = msg["priority"]

            by_status[status] = by_status.get(status, 0) + 1
            by_priority[priority] = by_priority.get(priority, 0) + 1

        return {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority
        }

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_part = hashlib.md5(str(datetime.utcnow().timestamp()).encode()).hexdigest()[:8]
        return f"{prefix}_{timestamp}_{random_part}"


# =============================================================================
# Message Templates
# =============================================================================

class BroadcastTemplates:
    """Pre-built message templates for common broadcasts."""

    DAILY_BRIEFING = """Good morning{name_greeting}! Here's your daily political update:

{headlines}

Reply "more" for details on any story.

— Tade, Decide9ja"""

    WEEKLY_SUMMARY = """Weekly Political Summary ({date_range}):

📊 Top Stories:
{top_stories}

🗳️ Election Updates:
{election_updates}

📈 Trending Topics:
{trending}

Have a great week!
— Tade"""

    BREAKING_NEWS = """⚠️ BREAKING: {headline}

{summary}

Source: {source}

Reply "details" for more."""

    ELECTION_REMINDER = """🗳️ Election Reminder

{election_type} elections are {days_until} days away ({date}).

{action_items}

Are you ready to vote? Reply YES or NO."""

    REPRESENTATIVE_UPDATE = """📢 Update from {representative_name} ({position}):

{update_content}

Source: {source}

Reply "profile" to see their full record."""

    POLL_INVITATION = """📊 Quick Poll

{question}

{options}

Reply with your choice number."""

    CIVIC_TIP = """💡 Civic Tip of the Day

{tip_content}

{call_to_action}

— Tade"""

    @classmethod
    def format_daily_briefing(cls, name: str, headlines: List[str]) -> str:
        name_greeting = f", {name}" if name else ""
        headlines_text = "\n".join([f"• {h}" for h in headlines[:5]])
        return cls.DAILY_BRIEFING.format(
            name_greeting=name_greeting,
            headlines=headlines_text
        )

    @classmethod
    def format_breaking_news(cls, headline: str, summary: str, source: str) -> str:
        return cls.BREAKING_NEWS.format(
            headline=headline,
            summary=summary[:200],
            source=source
        )

    @classmethod
    def format_election_reminder(
        cls,
        election_type: str,
        date: str,
        days_until: int,
        action_items: List[str]
    ) -> str:
        actions = "\n".join([f"✓ {a}" for a in action_items])
        return cls.ELECTION_REMINDER.format(
            election_type=election_type,
            date=date,
            days_until=days_until,
            action_items=actions
        )


# =============================================================================
# Singleton Instance
# =============================================================================

_broadcast_service: Optional[BroadcastService] = None


def get_broadcast_service() -> BroadcastService:
    """Get singleton broadcast service instance."""
    global _broadcast_service
    if _broadcast_service is None:
        _broadcast_service = BroadcastService()
    return _broadcast_service
