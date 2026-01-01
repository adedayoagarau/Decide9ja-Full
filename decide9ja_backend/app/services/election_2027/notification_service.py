"""
Push Notification Service for 2027 Election System
==================================================

Sends targeted notifications to users about:
1. Followed candidate updates (news, statements, polls)
2. Poll participation reminders
3. Breaking political news
4. INEC announcements

Notification Channels:
- WhatsApp (primary)
- SMS (fallback)
- Email (optional)
"""
import os
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    CANDIDATE_UPDATE = "candidate_update"
    POLL_REMINDER = "poll_reminder"
    POLL_RESULTS = "poll_results"
    BREAKING_NEWS = "breaking_news"
    INEC_ANNOUNCEMENT = "inec_announcement"
    WEEKLY_DIGEST = "weekly_digest"
    TRENDING_TOPIC = "trending_topic"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"           # Can wait for digest
    MEDIUM = "medium"     # Send within hours
    HIGH = "high"         # Send immediately
    BREAKING = "breaking" # Interrupt user


@dataclass
class Notification:
    """A notification to be sent."""
    id: str
    user_phone: str
    notification_type: NotificationType
    title: str
    message: str
    data: Dict = field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class NotificationService:
    """
    Manages push notifications for the election system.

    Integrates with:
    - WhatsApp Business API for messaging
    - User preferences for notification frequency
    - Candidate tracking for targeted updates
    """

    def __init__(self, whatsapp_client=None, db_session=None):
        self.whatsapp = whatsapp_client
        self.db = db_session
        self.pending_notifications: List[Notification] = []
        self.sent_log: Dict[str, List[str]] = {}  # user_hash -> [notification_ids]

    # === NOTIFICATION CREATION ===

    def create_candidate_update(
        self,
        candidate_id: str,
        candidate_name: str,
        update_type: str,
        headline: str,
        summary: str
    ) -> List[Notification]:
        """
        Create notifications for all users following a candidate.
        """
        from app.services.election_2027.candidate_tracker import get_candidate_tracker

        notifications = []
        tracker = get_candidate_tracker()

        # Get all users following this candidate
        for user_hash, followed_ids in tracker.user_follows.items():
            if candidate_id in followed_ids:
                # We need to reverse-lookup phone from hash (in production, store mapping)
                notif = Notification(
                    id=self._generate_id(),
                    user_phone=user_hash,  # In production, lookup actual phone
                    notification_type=NotificationType.CANDIDATE_UPDATE,
                    title=f"📢 {candidate_name} Update",
                    message=self._format_candidate_update(
                        candidate_name, update_type, headline, summary
                    ),
                    data={
                        "candidate_id": candidate_id,
                        "update_type": update_type
                    },
                    priority=NotificationPriority.HIGH if update_type == "breaking" else NotificationPriority.MEDIUM
                )
                notifications.append(notif)
                self.pending_notifications.append(notif)

        logger.info(f"Created {len(notifications)} notifications for {candidate_name} update")
        return notifications

    def create_poll_reminder(
        self,
        poll_id: str,
        poll_title: str,
        target_users: List[str] = None
    ) -> List[Notification]:
        """Create poll participation reminders."""
        from app.services.election_2027.polling_system import get_polling_system

        notifications = []
        ps = get_polling_system()

        # Get users who haven't voted
        # In production, query database for eligible users
        if target_users:
            for user_phone in target_users:
                user_hash = hashlib.sha256(user_phone.encode()).hexdigest()
                if not ps.has_voted(poll_id, user_hash):
                    notif = Notification(
                        id=self._generate_id(),
                        user_phone=user_phone,
                        notification_type=NotificationType.POLL_REMINDER,
                        title="📊 Your Voice Matters!",
                        message=self._format_poll_reminder(poll_title),
                        data={"poll_id": poll_id},
                        priority=NotificationPriority.MEDIUM
                    )
                    notifications.append(notif)
                    self.pending_notifications.append(notif)

        return notifications

    def create_breaking_news(
        self,
        headline: str,
        summary: str,
        related_entities: List[str] = None,
        target_states: List[str] = None
    ) -> List[Notification]:
        """Create breaking news notifications."""
        notifications = []

        # In production, query users based on:
        # - followed entities (candidates, parties)
        # - user state (for state-specific news)
        # - notification preferences

        # For now, create a template notification
        notif = Notification(
            id=self._generate_id(),
            user_phone="broadcast",  # Special marker for broadcast
            notification_type=NotificationType.BREAKING_NEWS,
            title="🔴 Breaking News",
            message=self._format_breaking_news(headline, summary),
            data={
                "headline": headline,
                "related_entities": related_entities or [],
                "target_states": target_states or []
            },
            priority=NotificationPriority.BREAKING
        )

        notifications.append(notif)
        self.pending_notifications.append(notif)

        return notifications

    def create_weekly_digest(self, user_phone: str) -> Notification:
        """Create a weekly digest for a user."""
        from app.services.election_2027.candidate_tracker import get_candidate_tracker

        tracker = get_candidate_tracker()
        candidates = tracker.get_followed_candidates(user_phone)

        notif = Notification(
            id=self._generate_id(),
            user_phone=user_phone,
            notification_type=NotificationType.WEEKLY_DIGEST,
            title="📬 Your Weekly Politics Update",
            message=self._format_weekly_digest(candidates),
            data={"followed_count": len(candidates)},
            priority=NotificationPriority.LOW
        )

        self.pending_notifications.append(notif)
        return notif

    # === NOTIFICATION SENDING ===

    async def send_notification(self, notification: Notification) -> Tuple[bool, str]:
        """Send a single notification via WhatsApp."""
        try:
            # Check if we have WhatsApp client
            if self.whatsapp:
                # Send via WhatsApp Business API
                result = await self._send_whatsapp(notification)
            else:
                # Log for manual sending or use fallback
                logger.info(f"Would send to {notification.user_phone}: {notification.message[:50]}...")
                result = (True, "Logged for sending")

            if result[0]:
                notification.sent_at = datetime.now()
                self._log_sent(notification)

            return result

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return (False, str(e))

    async def send_pending(self, priority_filter: NotificationPriority = None) -> Dict:
        """Send all pending notifications, optionally filtered by priority."""
        results = {"sent": 0, "failed": 0, "skipped": 0}

        for notif in self.pending_notifications[:]:
            if priority_filter and notif.priority != priority_filter:
                results["skipped"] += 1
                continue

            success, message = await self.send_notification(notif)
            if success:
                results["sent"] += 1
                self.pending_notifications.remove(notif)
            else:
                results["failed"] += 1

        logger.info(f"Send results: {results}")
        return results

    async def send_breaking_immediately(self) -> Dict:
        """Send all breaking priority notifications immediately."""
        return await self.send_pending(priority_filter=NotificationPriority.BREAKING)

    # === MESSAGE FORMATTING ===

    def _format_candidate_update(
        self,
        candidate_name: str,
        update_type: str,
        headline: str,
        summary: str
    ) -> str:
        """Format candidate update message for WhatsApp."""
        emoji_map = {
            "news": "📰",
            "statement": "💬",
            "event": "📅",
            "poll": "📊",
            "breaking": "🔴"
        }
        emoji = emoji_map.get(update_type, "📢")

        message = f"{emoji} *{candidate_name}*\n\n"
        message += f"*{headline}*\n\n"
        message += f"{summary[:200]}..." if len(summary) > 200 else summary
        message += "\n\nReply with their name for more updates."

        return message

    def _format_poll_reminder(self, poll_title: str) -> str:
        """Format poll reminder message."""
        return f"""📊 *New Poll Available!*

{poll_title}

Your opinion matters in shaping Nigeria's future. Take 30 seconds to vote!

Reply 'vote' to participate."""

    def _format_breaking_news(self, headline: str, summary: str) -> str:
        """Format breaking news message."""
        return f"""🔴 *BREAKING NEWS*

*{headline}*

{summary[:250]}...

Reply 'more' for full story."""

    def _format_weekly_digest(self, candidates: list) -> str:
        """Format weekly digest message."""
        message = "📬 *Your Weekly Politics Update*\n\n"

        if candidates:
            message += "*Your Followed Candidates:*\n"
            for c in candidates[:5]:
                trending = "🔥" if c.trending else ""
                message += f"• {c.name} ({c.party}) {trending}\n"
                if c.latest_news:
                    message += f"  Latest: {c.latest_news[0].get('title', '')[:40]}...\n"
        else:
            message += "You're not following any candidates yet.\n"
            message += "Try: 'Follow Tinubu' or 'Follow Peter Obi'\n"

        message += "\n📊 *This Week's Poll:* Who should win 2027?\n"
        message += "Reply 'polls' to participate.\n\n"
        message += "Reply 'trending' for hot topics."

        return message

    # === HELPERS ===

    def _generate_id(self) -> str:
        """Generate unique notification ID."""
        import uuid
        return f"notif_{uuid.uuid4().hex[:12]}"

    def _log_sent(self, notification: Notification):
        """Log sent notification for tracking."""
        user_hash = hashlib.sha256(notification.user_phone.encode()).hexdigest()
        if user_hash not in self.sent_log:
            self.sent_log[user_hash] = []
        self.sent_log[user_hash].append(notification.id)

    async def _send_whatsapp(self, notification: Notification) -> Tuple[bool, str]:
        """Send via Twilio WhatsApp."""
        from app.services.twilio_whatsapp import send_message

        try:
            # Send via Twilio
            result = send_message(
                to=notification.user_phone,
                text=notification.message
            )

            if "error" in result:
                return (False, result["error"])

            return (True, result.get("sid", "sent"))
        except Exception as e:
            logger.error(f"Twilio WhatsApp error: {e}")
            return (False, str(e))

    # === BATCH OPERATIONS ===

    async def send_digest_to_all_users(self) -> Dict:
        """Send weekly digest to all registered users."""
        # In production, query database for all users with notifications enabled
        results = {"sent": 0, "failed": 0}

        # Placeholder - would iterate over users
        logger.info("Would send weekly digest to all users")

        return results

    async def notify_candidate_followers(
        self,
        candidate_id: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM
    ) -> int:
        """Send a message to all followers of a candidate."""
        from app.services.election_2027.candidate_tracker import get_candidate_tracker, get_candidate

        tracker = get_candidate_tracker()
        candidate = get_candidate(candidate_id)

        if not candidate:
            return 0

        count = 0
        for user_hash, followed_ids in tracker.user_follows.items():
            if candidate.id in followed_ids:
                notif = Notification(
                    id=self._generate_id(),
                    user_phone=user_hash,
                    notification_type=NotificationType.CANDIDATE_UPDATE,
                    title=f"📢 {candidate.name}",
                    message=message,
                    data={"candidate_id": candidate_id},
                    priority=priority
                )
                self.pending_notifications.append(notif)
                count += 1

        return count


# === SINGLETON INSTANCE ===
_notification_service = None

def get_notification_service() -> NotificationService:
    """Get or create notification service singleton."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# === CONVENIENCE FUNCTIONS ===

async def notify_breaking_news(headline: str, summary: str) -> int:
    """Quick function to send breaking news."""
    service = get_notification_service()
    notifications = service.create_breaking_news(headline, summary)
    await service.send_breaking_immediately()
    return len(notifications)


async def notify_candidate_update(
    candidate_id: str,
    candidate_name: str,
    headline: str,
    summary: str
) -> int:
    """Quick function to notify about candidate update."""
    service = get_notification_service()
    notifications = service.create_candidate_update(
        candidate_id, candidate_name, "news", headline, summary
    )
    await service.send_pending()
    return len(notifications)


async def send_poll_reminders(poll_id: str, poll_title: str, users: List[str]) -> int:
    """Send poll reminders to users."""
    service = get_notification_service()
    notifications = service.create_poll_reminder(poll_id, poll_title, users)
    await service.send_pending()
    return len(notifications)
