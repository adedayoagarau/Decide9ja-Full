"""
Notification Service for Decide9ja.

Enables proactive WhatsApp messaging for:
- Breaking political news alerts
- Election reminders
- Poll invitations
- Weekly digests

Requires PHONE_ENCRYPTION_KEY to be set for decryption.
"""
import logging
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    BREAKING_NEWS = "breaking_news"
    ELECTION_REMINDER = "election_reminder"
    POLL_INVITE = "poll_invite"
    WEEKLY_DIGEST = "weekly_digest"
    CUSTOM = "custom"


@dataclass
class Notification:
    """A notification to be sent."""
    user_id: int
    phone_hash: str
    notification_type: NotificationType
    message: str
    title: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    priority: int = 0


@dataclass
class NotificationResult:
    """Result of sending a notification."""
    success: bool
    message_sid: Optional[str] = None
    error: Optional[str] = None


class NotificationService:
    """Service for sending proactive WhatsApp notifications."""

    def __init__(self):
        self._engine = None
        self._twilio_client = None

    def _get_engine(self):
        """Lazy load database engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            self._engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./decide9ja.db'))
        return self._engine

    def _get_twilio_client(self):
        """Get or create Twilio client."""
        if self._twilio_client is None:
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')

            if not account_sid or not auth_token:
                logger.warning("Twilio credentials not configured")
                return None

            try:
                from twilio.rest import Client
                self._twilio_client = Client(account_sid, auth_token)
            except ImportError:
                logger.error("twilio library not installed")
                return None

        return self._twilio_client

    def can_send_notifications(self) -> bool:
        """Check if notifications can be sent."""
        from app.utils.encryption import can_send_proactive_messages

        if not can_send_proactive_messages():
            logger.warning("PHONE_ENCRYPTION_KEY not set - notifications disabled")
            return False

        if not self._get_twilio_client():
            logger.warning("Twilio not configured - notifications disabled")
            return False

        return True

    # =========================================
    # Queue Management
    # =========================================

    def queue_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        message: str,
        title: str = None,
        data: Dict[str, Any] = None,
        scheduled_for: datetime = None,
        priority: int = 0
    ) -> bool:
        """Queue a notification for a user."""
        try:
            from sqlalchemy import text
            import json
            engine = self._get_engine()

            with engine.connect() as conn:
                conn.execute(text('''
                    SELECT queue_notification(
                        :user_id, :type, :message, :title, :data, :scheduled, :priority
                    )
                '''), {
                    'user_id': user_id,
                    'type': notification_type.value,
                    'message': message,
                    'title': title,
                    'data': json.dumps(data or {}),
                    'scheduled': scheduled_for or datetime.now(),
                    'priority': priority
                })
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to queue notification: {e}")
            return False

    def queue_bulk_notification(
        self,
        notification_type: NotificationType,
        message: str,
        title: str = None,
        data: Dict[str, Any] = None,
        target_state: str = None,
        target_lga: str = None,
        limit: int = 1000
    ) -> int:
        """Queue notification for multiple users based on criteria."""
        try:
            from sqlalchemy import text
            import json
            engine = self._get_engine()

            queued = 0
            with engine.connect() as conn:
                # Find eligible users
                query = '''
                    SELECT id, phone_hash FROM users
                    WHERE notifications_enabled = true
                      AND encrypted_phone IS NOT NULL
                '''
                params = {'limit': limit}

                if target_state:
                    query += ' AND state = :state'
                    params['state'] = target_state

                if target_lga:
                    query += ' AND lga = :lga'
                    params['lga'] = target_lga

                query += ' LIMIT :limit'

                result = conn.execute(text(query), params)

                for row in result:
                    success = self.queue_notification(
                        user_id=row[0],
                        notification_type=notification_type,
                        message=message,
                        title=title,
                        data=data
                    )
                    if success:
                        queued += 1

            logger.info(f"Queued {queued} notifications of type {notification_type.value}")
            return queued

        except Exception as e:
            logger.error(f"Failed to queue bulk notifications: {e}")
            return 0

    def get_pending_notifications(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending notifications ready to be sent."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT nq.id, nq.user_id, nq.notification_type, nq.title,
                           nq.message, nq.data, nq.priority, u.encrypted_phone
                    FROM notification_queue nq
                    JOIN users u ON nq.user_id = u.id
                    WHERE nq.status = 'pending'
                      AND nq.scheduled_for <= NOW()
                      AND nq.attempts < nq.max_attempts
                      AND u.encrypted_phone IS NOT NULL
                    ORDER BY nq.priority DESC, nq.scheduled_for ASC
                    LIMIT :limit
                '''), {'limit': limit})

                return [
                    {
                        'id': row[0],
                        'user_id': row[1],
                        'notification_type': row[2],
                        'title': row[3],
                        'message': row[4],
                        'data': row[5],
                        'priority': row[6],
                        'encrypted_phone': row[7]
                    }
                    for row in result
                ]

        except Exception as e:
            logger.error(f"Failed to get pending notifications: {e}")
            return []

    # =========================================
    # Sending
    # =========================================

    def send_notification(self, notification_id: int) -> NotificationResult:
        """Send a single notification by ID."""
        try:
            from sqlalchemy import text
            from app.utils.encryption import decrypt_phone
            engine = self._get_engine()

            with engine.connect() as conn:
                # Get notification details
                result = conn.execute(text('''
                    SELECT nq.message, nq.title, u.encrypted_phone, u.name
                    FROM notification_queue nq
                    JOIN users u ON nq.user_id = u.id
                    WHERE nq.id = :id
                '''), {'id': notification_id})

                row = result.fetchone()
                if not row:
                    return NotificationResult(success=False, error="Notification not found")

                message, title, encrypted_phone, user_name = row

                # Decrypt phone number
                phone = decrypt_phone(encrypted_phone)
                if not phone:
                    self._mark_failed(conn, notification_id, "Could not decrypt phone")
                    return NotificationResult(success=False, error="Decryption failed")

                # Format message
                full_message = self._format_message(message, title, user_name)

                # Send via Twilio
                result = self._send_whatsapp(phone, full_message)

                if result.success:
                    self._mark_sent(conn, notification_id, result.message_sid)
                else:
                    self._mark_failed(conn, notification_id, result.error)

                conn.commit()
                return result

        except Exception as e:
            logger.error(f"Failed to send notification {notification_id}: {e}")
            return NotificationResult(success=False, error=str(e))

    def _send_whatsapp(self, phone: str, message: str) -> NotificationResult:
        """Send a WhatsApp message via Twilio."""
        client = self._get_twilio_client()
        if not client:
            return NotificationResult(success=False, error="Twilio not configured")

        try:
            from_number = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

            msg = client.messages.create(
                body=message,
                from_=from_number,
                to=f"whatsapp:{phone}"
            )

            logger.info(f"Sent WhatsApp to {phone[:8]}...: {msg.sid}")
            return NotificationResult(success=True, message_sid=msg.sid)

        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            return NotificationResult(success=False, error=str(e))

    def _format_message(self, message: str, title: str = None, user_name: str = None) -> str:
        """Format notification message."""
        parts = []

        if title:
            parts.append(f"*{title}*\n")

        if user_name:
            message = message.replace("{name}", user_name)

        parts.append(message)
        parts.append("\n\n_Reply STOP to unsubscribe_")

        return "".join(parts)

    def _mark_sent(self, conn, notification_id: int, message_sid: str):
        """Mark notification as sent."""
        from sqlalchemy import text
        conn.execute(text('''
            UPDATE notification_queue
            SET status = 'sent', sent_at = NOW(), attempts = attempts + 1
            WHERE id = :id
        '''), {'id': notification_id})

    def _mark_failed(self, conn, notification_id: int, error: str):
        """Mark notification as failed."""
        from sqlalchemy import text
        conn.execute(text('''
            UPDATE notification_queue
            SET attempts = attempts + 1, last_attempt_at = NOW(), error_message = :error,
                status = CASE WHEN attempts + 1 >= max_attempts THEN 'failed' ELSE 'pending' END
            WHERE id = :id
        '''), {'id': notification_id, 'error': error})

    # =========================================
    # Process Queue (for scheduler)
    # =========================================

    def process_queue(self, batch_size: int = 50) -> Dict[str, int]:
        """Process pending notifications. Call this from scheduler."""
        if not self.can_send_notifications():
            return {'sent': 0, 'failed': 0, 'error': 'Notifications disabled'}

        pending = self.get_pending_notifications(batch_size)
        sent = 0
        failed = 0

        for notif in pending:
            result = self.send_notification(notif['id'])
            if result.success:
                sent += 1
            else:
                failed += 1

        logger.info(f"Processed notifications: {sent} sent, {failed} failed")
        return {'sent': sent, 'failed': failed}

    # =========================================
    # Convenience Methods
    # =========================================

    def send_breaking_news(
        self,
        headline: str,
        summary: str,
        article_url: str = None,
        target_state: str = None
    ) -> int:
        """Send breaking news alert to users."""
        message = f"🚨 *BREAKING*\n\n{headline}\n\n{summary}"

        if article_url:
            message += f"\n\nRead more: {article_url}"

        return self.queue_bulk_notification(
            notification_type=NotificationType.BREAKING_NEWS,
            message=message,
            title="Breaking News",
            data={'url': article_url} if article_url else None,
            target_state=target_state
        )

    def send_election_reminder(
        self,
        election_name: str,
        election_date: str,
        message: str = None,
        target_state: str = None
    ) -> int:
        """Send election reminder."""
        if not message:
            message = f"🗳️ Reminder: {election_name} is on {election_date}.\n\nMake sure your PVC is ready!"

        return self.queue_bulk_notification(
            notification_type=NotificationType.ELECTION_REMINDER,
            message=message,
            title="Election Reminder",
            data={'election': election_name, 'date': election_date},
            target_state=target_state
        )

    def send_poll_invite(
        self,
        poll_id: int,
        poll_question: str,
        user_id: int
    ) -> bool:
        """Send poll invitation to a specific user."""
        message = f"📊 *Quick Poll*\n\n{poll_question}\n\nReply to participate!"

        return self.queue_notification(
            user_id=user_id,
            notification_type=NotificationType.POLL_INVITE,
            message=message,
            title="New Poll",
            data={'poll_id': poll_id}
        )


# Singleton instance
notification_service = NotificationService()


# Convenience functions
def send_breaking_news(headline: str, summary: str, **kwargs) -> int:
    """Send breaking news alert."""
    return notification_service.send_breaking_news(headline, summary, **kwargs)


def process_notification_queue(batch_size: int = 50) -> Dict[str, int]:
    """Process pending notifications (for scheduler)."""
    return notification_service.process_queue(batch_size)
