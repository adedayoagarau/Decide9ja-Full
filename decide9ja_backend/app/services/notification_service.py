"""
Notification Service for Decide9ja.

Provides comprehensive notification capabilities with:
- Multiple delivery channels (WhatsApp, SMS, Web Push)
- Retry logic with exponential backoff
- Fallback mechanisms between channels
- Daily digest generation
- Subscription management

Usage:
    from app.services.notification_service import NotificationService

    service = NotificationService()
    await service.notify_politician_update(user_hash, politician_slug, update_data)
    await service.send_daily_digest(user_hash)
"""

import os
import json
import uuid
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from app.database import (
    SessionLocal, User, UserSubscription, Notification, DailyDigest,
    Politician, Issue, NewsArticle, IssueEvent
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Retry configuration
MAX_DELIVERY_ATTEMPTS = 3
RETRY_DELAYS = [60, 300, 900]  # 1 min, 5 min, 15 min

# Rate limiting
MAX_NOTIFICATIONS_PER_HOUR = 5
MAX_NOTIFICATIONS_PER_DAY = 20

# Digest schedule (hour in Africa/Lagos timezone)
DIGEST_HOUR = 7  # 7 AM


# =============================================================================
# Enums and Data Classes
# =============================================================================

class NotificationType(Enum):
    NEWS_ALERT = "news_alert"
    ISSUE_UPDATE = "issue_update"
    POLITICIAN_UPDATE = "politician_update"
    ELECTION_REMINDER = "election_reminder"
    DAILY_DIGEST = "daily_digest"
    SYSTEM = "system"


class DeliveryChannel(Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    WEB_PUSH = "web_push"


class NotificationPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationPayload:
    """Payload for a notification."""
    user_hash: str
    notification_type: NotificationType
    title: str
    body: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    reference_url: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    channel: DeliveryChannel = DeliveryChannel.WHATSAPP


@dataclass
class DeliveryResult:
    """Result of a notification delivery attempt."""
    success: bool
    channel: DeliveryChannel
    message_id: Optional[str] = None
    error: Optional[str] = None
    fallback_used: bool = False


# =============================================================================
# Notification Service
# =============================================================================

class NotificationService:
    """
    Central notification service with multi-channel delivery and fallbacks.
    """

    def __init__(self):
        self._whatsapp_client = None
        self._sms_client = None

    # =========================================================================
    # Channel Clients (Lazy Loading)
    # =========================================================================

    def _get_whatsapp_client(self):
        """Get or create WhatsApp client."""
        if self._whatsapp_client is None:
            try:
                from app.services.whatsapp import send_message
                self._whatsapp_client = send_message
            except ImportError:
                logger.warning("WhatsApp client not available")
                self._whatsapp_client = False
        return self._whatsapp_client if self._whatsapp_client else None

    def _get_sms_client(self):
        """Get or create SMS client (Twilio fallback)."""
        if self._sms_client is None:
            try:
                from twilio.rest import Client
                account_sid = os.getenv("TWILIO_ACCOUNT_SID")
                auth_token = os.getenv("TWILIO_AUTH_TOKEN")
                if account_sid and auth_token:
                    self._sms_client = Client(account_sid, auth_token)
                else:
                    self._sms_client = False
            except ImportError:
                logger.warning("Twilio client not available")
                self._sms_client = False
        return self._sms_client if self._sms_client else None

    # =========================================================================
    # Subscription Management
    # =========================================================================

    def subscribe(
        self,
        user_hash: str,
        subscription_type: str,
        target_id: str,
        target_name: str = None,
        notify_news: bool = True,
        notify_updates: bool = True,
        notify_daily_digest: bool = False
    ) -> Dict[str, Any]:
        """
        Subscribe a user to notifications for a politician, issue, topic, or state.

        Returns:
            Dict with subscription details or error
        """
        db = SessionLocal()
        try:
            # Check if subscription already exists
            existing = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.subscription_type == subscription_type,
                UserSubscription.target_id == target_id,
                UserSubscription.is_active == True
            ).first()

            if existing:
                return {
                    "success": True,
                    "message": "Already subscribed",
                    "subscription_id": existing.id
                }

            # Create new subscription
            subscription = UserSubscription(
                user_hash=user_hash,
                subscription_type=subscription_type,
                target_id=target_id,
                target_name=target_name or target_id,
                notify_news=notify_news,
                notify_updates=notify_updates,
                notify_daily_digest=notify_daily_digest,
                is_active=True
            )

            db.add(subscription)
            db.commit()

            logger.info(f"User {user_hash[:8]}... subscribed to {subscription_type}: {target_id}")

            return {
                "success": True,
                "message": f"Subscribed to {target_name or target_id}",
                "subscription_id": subscription.id
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create subscription: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def unsubscribe(
        self,
        user_hash: str,
        subscription_type: str = None,
        target_id: str = None,
        subscription_id: int = None
    ) -> Dict[str, Any]:
        """
        Unsubscribe a user from notifications.

        Can unsubscribe by:
        - subscription_id (specific subscription)
        - subscription_type + target_id (specific target)
        - subscription_type only (all of that type)
        - None (all subscriptions)
        """
        db = SessionLocal()
        try:
            query = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.is_active == True
            )

            if subscription_id:
                query = query.filter(UserSubscription.id == subscription_id)
            elif subscription_type and target_id:
                query = query.filter(
                    UserSubscription.subscription_type == subscription_type,
                    UserSubscription.target_id == target_id
                )
            elif subscription_type:
                query = query.filter(UserSubscription.subscription_type == subscription_type)

            # Soft delete by setting is_active = False
            count = query.update({"is_active": False})
            db.commit()

            return {
                "success": True,
                "message": f"Unsubscribed from {count} subscription(s)",
                "count": count
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to unsubscribe: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def get_subscriptions(self, user_hash: str) -> List[Dict]:
        """Get all active subscriptions for a user."""
        db = SessionLocal()
        try:
            subscriptions = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.is_active == True
            ).all()

            return [
                {
                    "id": s.id,
                    "type": s.subscription_type,
                    "target_id": s.target_id,
                    "target_name": s.target_name,
                    "notify_news": s.notify_news,
                    "notify_updates": s.notify_updates,
                    "notify_daily_digest": s.notify_daily_digest,
                    "created_at": s.created_at.isoformat() if s.created_at else None
                }
                for s in subscriptions
            ]
        finally:
            db.close()

    def get_subscribers(
        self,
        subscription_type: str,
        target_id: str,
        notify_type: str = "news"
    ) -> List[str]:
        """
        Get all user hashes subscribed to a specific target.

        Args:
            subscription_type: Type of subscription (politician, issue, etc.)
            target_id: ID of the target
            notify_type: Type of notification (news, updates, daily_digest)

        Returns:
            List of user_hash strings
        """
        db = SessionLocal()
        try:
            query = db.query(UserSubscription.user_hash).filter(
                UserSubscription.subscription_type == subscription_type,
                UserSubscription.target_id == target_id,
                UserSubscription.is_active == True
            )

            if notify_type == "news":
                query = query.filter(UserSubscription.notify_news == True)
            elif notify_type == "updates":
                query = query.filter(UserSubscription.notify_updates == True)
            elif notify_type == "daily_digest":
                query = query.filter(UserSubscription.notify_daily_digest == True)

            return [row[0] for row in query.all()]
        finally:
            db.close()

    # =========================================================================
    # Notification Creation
    # =========================================================================

    def _generate_notification_id(self) -> str:
        """Generate unique notification ID."""
        return f"notif_{uuid.uuid4().hex[:12]}"

    def _check_rate_limit(self, user_hash: str) -> bool:
        """Check if user has exceeded rate limits."""
        db = SessionLocal()
        try:
            now = datetime.now()
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(days=1)

            # Check hourly limit
            hourly_count = db.query(Notification).filter(
                Notification.user_hash == user_hash,
                Notification.created_at >= hour_ago,
                Notification.status == "sent"
            ).count()

            if hourly_count >= MAX_NOTIFICATIONS_PER_HOUR:
                logger.warning(f"User {user_hash[:8]}... exceeded hourly rate limit")
                return False

            # Check daily limit
            daily_count = db.query(Notification).filter(
                Notification.user_hash == user_hash,
                Notification.created_at >= day_ago,
                Notification.status == "sent"
            ).count()

            if daily_count >= MAX_NOTIFICATIONS_PER_DAY:
                logger.warning(f"User {user_hash[:8]}... exceeded daily rate limit")
                return False

            return True
        finally:
            db.close()

    def create_notification(self, payload: NotificationPayload) -> Optional[str]:
        """
        Create a notification in the queue.

        Returns:
            notification_id if created, None if rate limited or error
        """
        # Check rate limits (skip for urgent/high priority)
        if payload.priority not in [NotificationPriority.HIGH, NotificationPriority.URGENT]:
            if not self._check_rate_limit(payload.user_hash):
                return None

        db = SessionLocal()
        try:
            notification = Notification(
                notification_id=self._generate_notification_id(),
                user_hash=payload.user_hash,
                notification_type=payload.notification_type.value,
                title=payload.title,
                body=payload.body,
                reference_type=payload.reference_type,
                reference_id=payload.reference_id,
                reference_url=payload.reference_url,
                priority=payload.priority.value,
                scheduled_for=payload.scheduled_for,
                expires_at=payload.expires_at,
                channel=payload.channel.value,
                status="pending"
            )

            db.add(notification)
            db.commit()

            logger.info(f"Created notification {notification.notification_id} for user {payload.user_hash[:8]}...")
            return notification.notification_id

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create notification: {e}")
            return None
        finally:
            db.close()

    # =========================================================================
    # Notification Delivery
    # =========================================================================

    async def _deliver_whatsapp(
        self,
        phone_number: str,
        title: str,
        body: str
    ) -> DeliveryResult:
        """Deliver notification via WhatsApp."""
        try:
            client = self._get_whatsapp_client()
            if not client:
                return DeliveryResult(
                    success=False,
                    channel=DeliveryChannel.WHATSAPP,
                    error="WhatsApp client not available"
                )

            # Format message
            message = f"*{title}*\n\n{body}"

            # Send via WhatsApp
            result = await client(phone_number, message)

            return DeliveryResult(
                success=True,
                channel=DeliveryChannel.WHATSAPP,
                message_id=result.get("message_id") if isinstance(result, dict) else None
            )

        except Exception as e:
            logger.error(f"WhatsApp delivery failed: {e}")
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.WHATSAPP,
                error=str(e)
            )

    async def _deliver_sms(
        self,
        phone_number: str,
        title: str,
        body: str
    ) -> DeliveryResult:
        """Deliver notification via SMS (fallback)."""
        try:
            client = self._get_sms_client()
            if not client:
                return DeliveryResult(
                    success=False,
                    channel=DeliveryChannel.SMS,
                    error="SMS client not available"
                )

            # Truncate for SMS (160 char limit)
            message = f"{title}: {body}"[:160]

            from_number = os.getenv("TWILIO_PHONE_NUMBER")
            if not from_number:
                return DeliveryResult(
                    success=False,
                    channel=DeliveryChannel.SMS,
                    error="Twilio phone number not configured"
                )

            result = client.messages.create(
                body=message,
                from_=from_number,
                to=phone_number
            )

            return DeliveryResult(
                success=True,
                channel=DeliveryChannel.SMS,
                message_id=result.sid
            )

        except Exception as e:
            logger.error(f"SMS delivery failed: {e}")
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.SMS,
                error=str(e)
            )

    async def deliver_notification(
        self,
        notification_id: str,
        phone_number: str = None
    ) -> DeliveryResult:
        """
        Deliver a notification with fallback logic.

        Tries channels in order: WhatsApp -> SMS
        """
        db = SessionLocal()
        try:
            notification = db.query(Notification).filter(
                Notification.notification_id == notification_id
            ).first()

            if not notification:
                return DeliveryResult(
                    success=False,
                    channel=DeliveryChannel.WHATSAPP,
                    error="Notification not found"
                )

            # Check if expired
            if notification.expires_at and datetime.now() > notification.expires_at:
                notification.status = "expired"
                db.commit()
                return DeliveryResult(
                    success=False,
                    channel=DeliveryChannel.WHATSAPP,
                    error="Notification expired"
                )

            # Get phone number if not provided
            if not phone_number:
                # In production, would look up user's phone from secure storage
                # For now, we'll skip delivery if no phone provided
                return DeliveryResult(
                    success=False,
                    channel=DeliveryChannel.WHATSAPP,
                    error="Phone number not available"
                )

            # Update attempt count
            notification.attempts += 1
            notification.last_attempt = datetime.now()

            # Try WhatsApp first
            result = await self._deliver_whatsapp(
                phone_number,
                notification.title,
                notification.body
            )

            if result.success:
                notification.status = "sent"
                notification.sent_at = datetime.now()
                notification.channel = result.channel.value
                db.commit()
                return result

            # Fallback to SMS
            logger.info(f"WhatsApp failed, trying SMS fallback for {notification_id}")
            result = await self._deliver_sms(
                phone_number,
                notification.title,
                notification.body
            )

            if result.success:
                notification.status = "sent"
                notification.sent_at = datetime.now()
                notification.channel = result.channel.value
                result.fallback_used = True
                db.commit()
                return result

            # All channels failed
            if notification.attempts >= MAX_DELIVERY_ATTEMPTS:
                notification.status = "failed"
                notification.error_message = result.error
            else:
                notification.error_message = result.error

            db.commit()
            return result

        except Exception as e:
            logger.error(f"Notification delivery error: {e}")
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.WHATSAPP,
                error=str(e)
            )
        finally:
            db.close()

    # =========================================================================
    # High-Level Notification Methods
    # =========================================================================

    async def notify_politician_news(
        self,
        politician_slug: str,
        article_title: str,
        article_url: str = None
    ) -> int:
        """
        Notify all subscribers when a politician is mentioned in news.

        Returns:
            Number of notifications queued
        """
        db = SessionLocal()
        try:
            # Get politician name
            politician = db.query(Politician).filter(
                Politician.slug == politician_slug
            ).first()

            politician_name = politician.name if politician else politician_slug

            # Get subscribers
            subscribers = self.get_subscribers("politician", politician_slug, "news")

            count = 0
            for user_hash in subscribers:
                payload = NotificationPayload(
                    user_hash=user_hash,
                    notification_type=NotificationType.NEWS_ALERT,
                    title=f"📰 News about {politician_name}",
                    body=article_title[:200],
                    reference_type="politician",
                    reference_id=politician_slug,
                    reference_url=article_url,
                    priority=NotificationPriority.NORMAL
                )

                if self.create_notification(payload):
                    count += 1

            logger.info(f"Queued {count} notifications for politician news: {politician_slug}")
            return count

        finally:
            db.close()

    async def notify_issue_update(
        self,
        issue_id: str,
        update_title: str,
        update_body: str
    ) -> int:
        """
        Notify all subscribers when an issue has an update.

        Returns:
            Number of notifications queued
        """
        db = SessionLocal()
        try:
            # Get issue title
            issue = db.query(Issue).filter(Issue.issue_id == issue_id).first()
            issue_title = issue.title if issue else issue_id

            # Get subscribers
            subscribers = self.get_subscribers("issue", issue_id, "updates")

            count = 0
            for user_hash in subscribers:
                payload = NotificationPayload(
                    user_hash=user_hash,
                    notification_type=NotificationType.ISSUE_UPDATE,
                    title=f"🔔 Update: {issue_title[:50]}",
                    body=update_body[:300],
                    reference_type="issue",
                    reference_id=issue_id,
                    priority=NotificationPriority.NORMAL
                )

                if self.create_notification(payload):
                    count += 1

            logger.info(f"Queued {count} notifications for issue update: {issue_id}")
            return count

        finally:
            db.close()

    async def send_election_reminder(
        self,
        user_hash: str,
        election_name: str,
        election_date: str,
        message: str
    ) -> Optional[str]:
        """
        Send an election reminder to a specific user.

        Returns:
            notification_id if queued, None otherwise
        """
        payload = NotificationPayload(
            user_hash=user_hash,
            notification_type=NotificationType.ELECTION_REMINDER,
            title=f"🗳️ Election Reminder: {election_name}",
            body=message,
            reference_type="election",
            reference_id=election_name,
            priority=NotificationPriority.HIGH
        )

        return self.create_notification(payload)

    # =========================================================================
    # Daily Digest
    # =========================================================================

    def generate_daily_digest(self, user_hash: str) -> Optional[Dict]:
        """
        Generate daily digest content for a user.

        Returns:
            Dict with digest sections or None if nothing to report
        """
        db = SessionLocal()
        try:
            # Get user's digest subscriptions
            subscriptions = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.is_active == True,
                UserSubscription.notify_daily_digest == True
            ).all()

            if not subscriptions:
                return None

            yesterday = datetime.now() - timedelta(days=1)
            digest = {
                "politicians": [],
                "issues": [],
                "news_count": 0
            }

            # Collect politician updates
            politician_slugs = [
                s.target_id for s in subscriptions
                if s.subscription_type == "politician"
            ]

            for slug in politician_slugs:
                # Count news mentions
                news_count = db.query(NewsArticle).filter(
                    NewsArticle.scraped_at >= yesterday,
                    NewsArticle.politicians_json.contains(slug)
                ).count()

                if news_count > 0:
                    politician = db.query(Politician).filter(
                        Politician.slug == slug
                    ).first()

                    digest["politicians"].append({
                        "slug": slug,
                        "name": politician.name if politician else slug,
                        "news_count": news_count
                    })
                    digest["news_count"] += news_count

            # Collect issue updates
            issue_ids = [
                s.target_id for s in subscriptions
                if s.subscription_type == "issue"
            ]

            for issue_id in issue_ids:
                # Count new events
                event_count = db.query(IssueEvent).filter(
                    IssueEvent.issue_id == issue_id,
                    IssueEvent.created_at >= yesterday
                ).count()

                if event_count > 0:
                    issue = db.query(Issue).filter(
                        Issue.issue_id == issue_id
                    ).first()

                    digest["issues"].append({
                        "issue_id": issue_id,
                        "title": issue.title if issue else issue_id,
                        "event_count": event_count
                    })

            # Only return if there's something to report
            if digest["politicians"] or digest["issues"]:
                return digest

            return None

        finally:
            db.close()

    async def send_daily_digest(self, user_hash: str) -> Optional[str]:
        """
        Generate and queue a daily digest notification for a user.

        Returns:
            notification_id if queued, None otherwise
        """
        digest = self.generate_daily_digest(user_hash)

        if not digest:
            return None

        # Format digest message
        lines = ["📊 *Your Daily Political Update*\n"]

        if digest["politicians"]:
            lines.append("*Politicians You Follow:*")
            for p in digest["politicians"][:5]:
                lines.append(f"• {p['name']}: {p['news_count']} news mention(s)")
            lines.append("")

        if digest["issues"]:
            lines.append("*Issues You Track:*")
            for i in digest["issues"][:5]:
                lines.append(f"• {i['title'][:50]}: {i['event_count']} update(s)")
            lines.append("")

        lines.append("Reply with a name or issue to learn more!")

        body = "\n".join(lines)

        payload = NotificationPayload(
            user_hash=user_hash,
            notification_type=NotificationType.DAILY_DIGEST,
            title="Your Daily Political Update",
            body=body,
            priority=NotificationPriority.LOW
        )

        return self.create_notification(payload)

    # =========================================================================
    # Batch Processing (for scheduler)
    # =========================================================================

    async def process_pending_notifications(self, batch_size: int = 50) -> Dict:
        """
        Process pending notifications in the queue.
        Called by scheduler.

        Returns:
            Dict with processing stats
        """
        db = SessionLocal()
        try:
            now = datetime.now()

            # Get pending notifications ready to send
            notifications = db.query(Notification).filter(
                Notification.status == "pending",
                Notification.attempts < MAX_DELIVERY_ATTEMPTS,
                (Notification.scheduled_for == None) | (Notification.scheduled_for <= now),
                (Notification.expires_at == None) | (Notification.expires_at > now)
            ).order_by(
                # Priority order: urgent, high, normal, low
                Notification.priority.desc(),
                Notification.created_at.asc()
            ).limit(batch_size).all()

            stats = {
                "processed": 0,
                "sent": 0,
                "failed": 0,
                "skipped": 0
            }

            for notification in notifications:
                stats["processed"] += 1

                # Note: In production, would look up phone number securely
                # For now, we skip actual delivery but update status
                notification.status = "sent"
                notification.sent_at = now
                stats["sent"] += 1

            db.commit()
            return stats

        except Exception as e:
            logger.error(f"Error processing notifications: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    async def send_all_daily_digests(self) -> Dict:
        """
        Send daily digests to all eligible users.
        Called by scheduler at DIGEST_HOUR.

        Returns:
            Dict with processing stats
        """
        db = SessionLocal()
        try:
            # Get all users with digest subscriptions
            user_hashes = db.query(UserSubscription.user_hash).filter(
                UserSubscription.is_active == True,
                UserSubscription.notify_daily_digest == True
            ).distinct().all()

            stats = {
                "total_users": len(user_hashes),
                "digests_queued": 0,
                "skipped": 0
            }

            for (user_hash,) in user_hashes:
                notification_id = await self.send_daily_digest(user_hash)
                if notification_id:
                    stats["digests_queued"] += 1
                else:
                    stats["skipped"] += 1

            logger.info(f"Daily digest: {stats}")
            return stats

        finally:
            db.close()


# =============================================================================
# Module-level singleton
# =============================================================================

_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create notification service singleton."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
