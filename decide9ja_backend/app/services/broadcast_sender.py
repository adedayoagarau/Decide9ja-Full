"""
Broadcast Sender Service for Decide9ja.

Processes the broadcast message queue and sends messages via Twilio.
Handles:
- Queue processing with rate limiting
- Phone number lookup from user hash
- Delivery tracking and retries
- Daily digest generation and sending
- Breaking news distribution

Integrates with Twilio WhatsApp API.
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class SendConfig:
    """Broadcast sending configuration."""
    # Rate limits
    MAX_MESSAGES_PER_SECOND = 10
    MAX_MESSAGES_PER_MINUTE = 200
    MAX_MESSAGES_PER_HOUR = 1000

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAYS = [60, 300, 900]  # 1min, 5min, 15min

    # Time windows (WAT = UTC+1)
    QUIET_HOURS_START = 22  # 10pm
    QUIET_HOURS_END = 7     # 7am

    # Batch sizes
    BATCH_SIZE = 50
    BATCH_DELAY_SECONDS = 5


# =============================================================================
# Broadcast Sender Service
# =============================================================================

class BroadcastSender:
    """
    Service for sending broadcast messages via Twilio.

    Features:
    - Process message queue with rate limiting
    - Respect quiet hours
    - Track delivery status
    - Handle retries for failed sends
    """

    def __init__(self):
        self._messages_sent_this_minute = 0
        self._last_minute_reset = datetime.utcnow()
        self._is_processing = False

    # -------------------------------------------------------------------------
    # Phone Number Resolution
    # -------------------------------------------------------------------------

    def get_phone_from_hash(self, user_hash: str) -> Optional[str]:
        """
        Get phone number from user hash.

        Note: In production, you'd query a secure lookup table.
        Phone numbers are hashed for storage, but you need the
        reverse lookup for sending.

        Returns phone in format: +234XXXXXXXXXX
        """
        from sqlalchemy import create_engine, text

        try:
            engine = create_engine(os.getenv('DATABASE_URL'))

            with engine.connect() as conn:
                # Query users table for phone
                # Note: This requires storing encrypted phone, not just hash
                result = conn.execute(text("""
                    SELECT phone_encrypted
                    FROM users
                    WHERE phone_hash = :hash
                    LIMIT 1
                """), {"hash": user_hash})

                row = result.fetchone()
                if row and row[0]:
                    # Decrypt phone number
                    return self._decrypt_phone(row[0])

        except Exception as e:
            logger.error(f"Phone lookup error: {e}")

        return None

    def _decrypt_phone(self, encrypted: str) -> Optional[str]:
        """
        Decrypt phone number.

        In production, use proper encryption (e.g., Fernet).
        This is a placeholder.
        """
        # TODO: Implement proper decryption
        # For now, return as-is if it looks like a phone
        if encrypted and encrypted.startswith("+"):
            return encrypted
        return None

    # -------------------------------------------------------------------------
    # Message Sending
    # -------------------------------------------------------------------------

    def send_message(
        self,
        phone: str,
        content: str,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Send a single message via Twilio.

        Args:
            phone: Phone number (+234XXXXXXXXXX)
            content: Message content
            priority: Message priority

        Returns:
            Send result with SID or error
        """
        from app.services.twilio_whatsapp import send_message, format_for_whatsapp

        # Check quiet hours for non-breaking messages
        if priority != "breaking" and self._is_quiet_hours():
            return {
                "success": False,
                "error": "quiet_hours",
                "retry_at": self._get_next_send_time().isoformat()
            }

        # Check rate limit
        if not self._check_rate_limit():
            return {
                "success": False,
                "error": "rate_limited",
                "retry_in_seconds": 60
            }

        # Format and send
        formatted = format_for_whatsapp(content)
        result = send_message(phone, formatted)

        if result.get("sid"):
            self._messages_sent_this_minute += 1
            return {
                "success": True,
                "sid": result["sid"],
                "status": result.get("status", "sent")
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "unknown")
            }

    def send_to_user(
        self,
        user_hash: str,
        content: str,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Send message to user by hash.

        Args:
            user_hash: User's phone hash
            content: Message content
            priority: Message priority

        Returns:
            Send result
        """
        phone = self.get_phone_from_hash(user_hash)

        if not phone:
            return {
                "success": False,
                "error": "phone_not_found",
                "user_hash": user_hash[:8] + "..."
            }

        return self.send_message(phone, content, priority)

    # -------------------------------------------------------------------------
    # Queue Processing
    # -------------------------------------------------------------------------

    async def process_queue(self, limit: int = 100) -> Dict[str, Any]:
        """
        Process pending messages from broadcast queue.

        Returns processing statistics.
        """
        if self._is_processing:
            return {"error": "Already processing"}

        self._is_processing = True

        from app.services.broadcast_service import get_broadcast_service

        service = get_broadcast_service()
        pending = service.get_pending_messages(limit=limit)

        stats = {
            "processed": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

        try:
            for msg in pending:
                # Check if we should stop (quiet hours, rate limit)
                if self._is_quiet_hours() and msg.get("priority") != "breaking":
                    stats["skipped"] += 1
                    continue

                if not self._check_rate_limit():
                    # Wait before continuing
                    await asyncio.sleep(60)
                    self._reset_rate_limit()

                # Get phone and send
                user_hash = msg.get("recipient_hash")
                content = msg.get("content")
                campaign_id = msg.get("campaign_id")

                result = self.send_to_user(
                    user_hash=user_hash,
                    content=content,
                    priority=msg.get("priority", "normal")
                )

                stats["processed"] += 1

                if result.get("success"):
                    stats["sent"] += 1
                    service.mark_sent(user_hash, campaign_id)
                else:
                    stats["failed"] += 1
                    error = result.get("error", "unknown")
                    stats["errors"].append(error)
                    service.mark_failed(user_hash, error, campaign_id)

                # Small delay between messages
                await asyncio.sleep(0.1)

        finally:
            self._is_processing = False

        return stats

    async def process_queue_batch(self) -> Dict[str, Any]:
        """Process queue in batches with delays."""
        total_stats = {
            "batches": 0,
            "total_sent": 0,
            "total_failed": 0
        }

        while True:
            stats = await self.process_queue(limit=SendConfig.BATCH_SIZE)

            if stats.get("processed", 0) == 0:
                break  # No more messages

            total_stats["batches"] += 1
            total_stats["total_sent"] += stats.get("sent", 0)
            total_stats["total_failed"] += stats.get("failed", 0)

            # Wait between batches
            await asyncio.sleep(SendConfig.BATCH_DELAY_SECONDS)

        return total_stats

    # -------------------------------------------------------------------------
    # Digest Sending
    # -------------------------------------------------------------------------

    async def send_daily_digests(self) -> Dict[str, Any]:
        """
        Generate and send daily digests to subscribed users.

        Called by scheduler at 7am WAT.
        """
        from app.services.news_digest_service import get_news_digest_service, DigestFrequency
        from app.services.broadcast_service import get_broadcast_service

        digest_service = get_news_digest_service()
        broadcast_service = get_broadcast_service()

        # Get users who should receive digest at this time
        current_hour = (datetime.utcnow().hour + 1) % 24  # WAT = UTC+1
        send_time = f"{current_hour:02d}:00"

        users = digest_service.get_users_for_digest(
            frequency=DigestFrequency.DAILY,
            send_time=send_time
        )

        stats = {
            "users_targeted": len(users),
            "digests_sent": 0,
            "failed": 0
        }

        for user_hash in users:
            try:
                # Get user context
                user_context = self._get_user_context(user_hash)

                # Generate digest
                digest = digest_service.generate_daily_digest(user_hash, user_context)

                # Send via Twilio
                result = self.send_to_user(
                    user_hash=user_hash,
                    content=digest.content,
                    priority="normal"
                )

                if result.get("success"):
                    stats["digests_sent"] += 1
                else:
                    stats["failed"] += 1

                # Small delay
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Digest send error for {user_hash[:8]}: {e}")
                stats["failed"] += 1

        return stats

    async def send_weekly_summaries(self) -> Dict[str, Any]:
        """
        Generate and send weekly summaries.

        Called by scheduler on Sundays at 9am WAT.
        """
        from app.services.news_digest_service import get_news_digest_service, DigestFrequency

        digest_service = get_news_digest_service()

        users = digest_service.get_users_for_digest(
            frequency=DigestFrequency.WEEKLY,
            send_time="09:00"
        )

        stats = {
            "users_targeted": len(users),
            "summaries_sent": 0,
            "failed": 0
        }

        for user_hash in users:
            try:
                user_context = self._get_user_context(user_hash)
                digest = digest_service.generate_weekly_digest(user_hash, user_context)

                result = self.send_to_user(
                    user_hash=user_hash,
                    content=digest.content,
                    priority="normal"
                )

                if result.get("success"):
                    stats["summaries_sent"] += 1
                else:
                    stats["failed"] += 1

                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Weekly summary error for {user_hash[:8]}: {e}")
                stats["failed"] += 1

        return stats

    async def send_breaking_news(
        self,
        content: str,
        target_states: List[str] = None
    ) -> Dict[str, Any]:
        """
        Send breaking news to all users or targeted states.

        Bypasses quiet hours for urgent news.
        """
        from app.services.broadcast_service import (
            get_broadcast_service, AudienceCriteria, AudienceType
        )

        service = get_broadcast_service()

        # Build audience
        if target_states:
            audience = AudienceCriteria(
                audience_type=AudienceType.STATE,
                states=target_states
            )
        else:
            audience = AudienceCriteria(audience_type=AudienceType.ALL)

        # Resolve recipients
        recipients = service.resolve_audience(audience)

        stats = {
            "recipients": len(recipients),
            "sent": 0,
            "failed": 0
        }

        for recipient in recipients:
            result = self.send_to_user(
                user_hash=recipient["phone_hash"],
                content=content,
                priority="breaking"
            )

            if result.get("success"):
                stats["sent"] += 1
            else:
                stats["failed"] += 1

            await asyncio.sleep(0.05)  # Faster for breaking news

        return stats

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours (10pm - 7am WAT)."""
        wat_hour = (datetime.utcnow().hour + 1) % 24
        return wat_hour >= SendConfig.QUIET_HOURS_START or wat_hour < SendConfig.QUIET_HOURS_END

    def _get_next_send_time(self) -> datetime:
        """Get next valid send time after quiet hours."""
        now = datetime.utcnow()
        wat_hour = (now.hour + 1) % 24

        if wat_hour >= SendConfig.QUIET_HOURS_START:
            # Next day at 7am WAT (6am UTC)
            next_send = now.replace(hour=6, minute=0, second=0, microsecond=0)
            next_send += timedelta(days=1)
        elif wat_hour < SendConfig.QUIET_HOURS_END:
            # Today at 7am WAT
            next_send = now.replace(hour=6, minute=0, second=0, microsecond=0)
        else:
            next_send = now

        return next_send

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = datetime.utcnow()

        # Reset counter if minute has passed
        if (now - self._last_minute_reset).total_seconds() >= 60:
            self._reset_rate_limit()

        return self._messages_sent_this_minute < SendConfig.MAX_MESSAGES_PER_MINUTE

    def _reset_rate_limit(self):
        """Reset rate limit counter."""
        self._messages_sent_this_minute = 0
        self._last_minute_reset = datetime.utcnow()

    def _get_user_context(self, user_hash: str) -> Optional[Dict]:
        """Get user context for personalization."""
        from sqlalchemy import create_engine, text

        try:
            engine = create_engine(os.getenv('DATABASE_URL'))

            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT name, state, lga, preferences_json
                    FROM users
                    WHERE phone_hash = :hash
                """), {"hash": user_hash})

                row = result.fetchone()
                if row:
                    return {
                        "name": row[0],
                        "state": row[1],
                        "lga": row[2],
                        "preferences": row[3] or {}
                    }
        except Exception as e:
            logger.error(f"User context lookup error: {e}")

        return None


# =============================================================================
# Scheduled Job Functions
# =============================================================================

async def job_process_broadcast_queue():
    """Scheduled job: Process broadcast message queue."""
    sender = get_broadcast_sender()
    stats = await sender.process_queue_batch()
    logger.info(f"Broadcast queue processed: {stats}")
    return stats


async def job_send_daily_digests():
    """Scheduled job: Send daily news digests at 7am WAT."""
    sender = get_broadcast_sender()
    stats = await sender.send_daily_digests()
    logger.info(f"Daily digests sent: {stats}")
    return stats


async def job_send_weekly_summaries():
    """Scheduled job: Send weekly summaries on Sunday 9am WAT."""
    sender = get_broadcast_sender()
    stats = await sender.send_weekly_summaries()
    logger.info(f"Weekly summaries sent: {stats}")
    return stats


def register_broadcast_jobs(scheduler):
    """
    Register broadcast jobs with the scheduler.

    Args:
        scheduler: APScheduler instance
    """
    # Process queue every 5 minutes
    scheduler.add_job(
        job_process_broadcast_queue,
        'interval',
        minutes=5,
        id='broadcast_queue_processor',
        name='Process Broadcast Queue',
        replace_existing=True
    )

    # Daily digest at 6am UTC (7am WAT)
    scheduler.add_job(
        job_send_daily_digests,
        'cron',
        hour=6,
        minute=0,
        id='daily_digest_sender',
        name='Send Daily Digests',
        replace_existing=True
    )

    # Weekly summary on Sundays at 8am UTC (9am WAT)
    scheduler.add_job(
        job_send_weekly_summaries,
        'cron',
        day_of_week='sun',
        hour=8,
        minute=0,
        id='weekly_summary_sender',
        name='Send Weekly Summaries',
        replace_existing=True
    )

    logger.info("Broadcast jobs registered with scheduler")


# =============================================================================
# Singleton Instance
# =============================================================================

_broadcast_sender: Optional[BroadcastSender] = None


def get_broadcast_sender() -> BroadcastSender:
    """Get singleton broadcast sender instance."""
    global _broadcast_sender
    if _broadcast_sender is None:
        _broadcast_sender = BroadcastSender()
    return _broadcast_sender
