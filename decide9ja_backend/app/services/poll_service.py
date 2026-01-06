"""
Poll Service for Decide9ja.

Handles:
- Poll creation and management
- Poll distribution to eligible users
- Response collection and validation
- Queue management for poll delivery
"""
import logging
import json
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class PollStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class QueueStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    RESPONDED = "responded"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class Poll:
    """Represents a poll."""
    id: int
    question: str
    options: List[str]
    description: Optional[str] = None
    category: Optional[str] = None
    target_state: Optional[str] = None
    target_lga: Optional[str] = None
    target_senatorial_district: Optional[str] = None
    target_federal_constituency: Optional[str] = None
    target_age_range: Optional[str] = None
    target_gender: Optional[str] = None
    target_has_pvc: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_responses: Optional[int] = None
    priority: int = 0
    status: str = "active"
    response_count: int = 0


@dataclass
class PollResponse:
    """Represents a poll response."""
    poll_id: int
    phone_hash: str
    response: str
    response_index: Optional[int] = None
    user_state: Optional[str] = None
    user_lga: Optional[str] = None
    responded_at: datetime = field(default_factory=datetime.now)


class PollService:
    """Service for managing polls."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Lazy load database engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            import os
            self._engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./decide9ja.db'))
        return self._engine

    # =========================================
    # Poll CRUD Operations
    # =========================================

    def create_poll(
        self,
        question: str,
        options: List[str],
        category: str = None,
        target_state: str = None,
        target_lga: str = None,
        ends_at: datetime = None,
        max_responses: int = None,
        created_by: str = "admin",
        status: str = "draft"
    ) -> Optional[int]:
        """Create a new poll."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    INSERT INTO polls (
                        question, options, category, target_state, target_lga,
                        ends_at, max_responses, created_by, status
                    ) VALUES (
                        :question, :options, :category, :target_state, :target_lga,
                        :ends_at, :max_responses, :created_by, :status
                    )
                    RETURNING id
                '''), {
                    'question': question,
                    'options': json.dumps(options),
                    'category': category,
                    'target_state': target_state,
                    'target_lga': target_lga,
                    'ends_at': ends_at,
                    'max_responses': max_responses,
                    'created_by': created_by,
                    'status': status
                })
                conn.commit()
                row = result.fetchone()
                return row[0] if row else None

        except Exception as e:
            logger.error(f"Failed to create poll: {e}")
            return None

    def get_poll(self, poll_id: int) -> Optional[Poll]:
        """Get a poll by ID."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT p.id, p.question, p.options, p.description, p.category,
                           p.target_state, p.target_lga, p.target_senatorial_district,
                           p.target_federal_constituency, p.target_age_range,
                           p.target_gender, p.target_has_pvc,
                           p.starts_at, p.ends_at, p.max_responses,
                           p.priority, p.status,
                           (SELECT COUNT(*) FROM poll_responses pr WHERE pr.poll_id = p.id) as response_count
                    FROM polls p
                    WHERE p.id = :poll_id
                '''), {'poll_id': poll_id})

                row = result.fetchone()
                if row:
                    return self._row_to_poll(row)

        except Exception as e:
            logger.error(f"Failed to get poll: {e}")
        return None

    def get_active_polls(self, limit: int = 10) -> List[Poll]:
        """Get active polls."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT p.id, p.question, p.options, p.description, p.category,
                           p.target_state, p.target_lga, p.target_senatorial_district,
                           p.target_federal_constituency, p.target_age_range,
                           p.target_gender, p.target_has_pvc,
                           p.starts_at, p.ends_at, p.max_responses,
                           p.priority, p.status,
                           (SELECT COUNT(*) FROM poll_responses pr WHERE pr.poll_id = p.id) as response_count
                    FROM polls p
                    WHERE p.status = 'active'
                      AND (p.ends_at IS NULL OR p.ends_at > NOW())
                      AND (p.starts_at IS NULL OR p.starts_at <= NOW())
                    ORDER BY p.priority DESC, p.created_at DESC
                    LIMIT :limit
                '''), {'limit': limit})

                return [self._row_to_poll(row) for row in result]

        except Exception as e:
            logger.error(f"Failed to get active polls: {e}")
            return []

    def update_poll_status(self, poll_id: int, status: str) -> bool:
        """Update poll status."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                conn.execute(text('''
                    UPDATE polls SET status = :status, updated_at = NOW()
                    WHERE id = :poll_id
                '''), {'poll_id': poll_id, 'status': status})
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to update poll status: {e}")
            return False

    def _row_to_poll(self, row) -> Poll:
        """Convert database row to Poll object."""
        options = row[2]
        if isinstance(options, str):
            options = json.loads(options)

        return Poll(
            id=row[0],
            question=row[1],
            options=options,
            description=row[3],
            category=row[4],
            target_state=row[5],
            target_lga=row[6],
            target_senatorial_district=row[7],
            target_federal_constituency=row[8],
            target_age_range=row[9],
            target_gender=row[10],
            target_has_pvc=row[11],
            starts_at=row[12],
            ends_at=row[13],
            max_responses=row[14],
            priority=row[15],
            status=row[16],
            response_count=row[17] if len(row) > 17 else 0
        )

    # =========================================
    # Poll Distribution
    # =========================================

    def find_eligible_users(
        self,
        poll_id: int,
        limit: int = 1000
    ) -> List[str]:
        """Find users eligible for a poll who haven't responded yet."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            poll = self.get_poll(poll_id)
            if not poll:
                return []

            with engine.connect() as conn:
                # Build dynamic query based on targeting
                query = '''
                    SELECT DISTINCT u.phone_hash
                    FROM users u
                    WHERE u.phone_hash NOT IN (
                        SELECT pr.phone_hash FROM poll_responses pr WHERE pr.poll_id = :poll_id
                    )
                    AND u.phone_hash NOT IN (
                        SELECT pq.phone_hash FROM poll_queue pq
                        WHERE pq.poll_id = :poll_id AND pq.status IN ('pending', 'sent')
                    )
                '''
                params = {'poll_id': poll_id, 'limit': limit}

                if poll.target_state:
                    query += ' AND u.state = :target_state'
                    params['target_state'] = poll.target_state

                if poll.target_lga:
                    query += ' AND u.lga = :target_lga'
                    params['target_lga'] = poll.target_lga

                query += ' LIMIT :limit'

                result = conn.execute(text(query), params)
                return [row[0] for row in result]

        except Exception as e:
            logger.error(f"Failed to find eligible users: {e}")
            return []

    def queue_poll_for_users(
        self,
        poll_id: int,
        phone_hashes: List[str],
        expires_hours: int = 48
    ) -> int:
        """Queue a poll for delivery to users."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            expires_at = datetime.now() + timedelta(hours=expires_hours)
            queued = 0

            with engine.connect() as conn:
                for phone_hash in phone_hashes:
                    try:
                        conn.execute(text('''
                            INSERT INTO poll_queue (poll_id, phone_hash, expires_at)
                            VALUES (:poll_id, :phone_hash, :expires_at)
                            ON CONFLICT (poll_id, phone_hash) DO NOTHING
                        '''), {
                            'poll_id': poll_id,
                            'phone_hash': phone_hash,
                            'expires_at': expires_at
                        })
                        queued += 1
                    except Exception:
                        continue

                conn.commit()

            logger.info(f"Queued poll {poll_id} for {queued} users")
            return queued

        except Exception as e:
            logger.error(f"Failed to queue poll: {e}")
            return 0

    def get_pending_poll_for_user(self, phone_hash: str) -> Optional[Poll]:
        """Get the next pending poll for a user."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                # Get pending poll from queue
                result = conn.execute(text('''
                    SELECT pq.poll_id
                    FROM poll_queue pq
                    JOIN polls p ON pq.poll_id = p.id
                    WHERE pq.phone_hash = :phone_hash
                      AND pq.status = 'pending'
                      AND (pq.expires_at IS NULL OR pq.expires_at > NOW())
                      AND p.status = 'active'
                    ORDER BY p.priority DESC, pq.queued_at ASC
                    LIMIT 1
                '''), {'phone_hash': phone_hash})

                row = result.fetchone()
                if row:
                    # Mark as sent
                    conn.execute(text('''
                        UPDATE poll_queue
                        SET status = 'sent', sent_at = NOW(), attempts = attempts + 1
                        WHERE poll_id = :poll_id AND phone_hash = :phone_hash
                    '''), {'poll_id': row[0], 'phone_hash': phone_hash})
                    conn.commit()

                    return self.get_poll(row[0])

        except Exception as e:
            logger.error(f"Failed to get pending poll: {e}")
        return None

    # =========================================
    # Response Collection
    # =========================================

    def record_response(
        self,
        poll_id: int,
        phone_hash: str,
        response: str,
        user_state: str = None,
        user_lga: str = None,
        user_age_range: str = None,
        user_gender: str = None,
        user_has_pvc: bool = None
    ) -> Tuple[bool, str]:
        """
        Record a poll response.
        Returns (success, message).
        """
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            # Get poll to validate response
            poll = self.get_poll(poll_id)
            if not poll:
                return False, "Poll not found"

            if poll.status != 'active':
                return False, "This poll is no longer active"

            # Validate response is a valid option
            response_lower = response.lower().strip()
            response_index = None
            matched_option = None

            for i, option in enumerate(poll.options):
                if option.lower() == response_lower or str(i + 1) == response.strip():
                    response_index = i
                    matched_option = option
                    break

            if matched_option is None:
                # Try fuzzy matching for common responses
                option_map = {
                    'yes': ['yes', 'yeah', 'yep', 'sure', 'definitely', 'absolutely'],
                    'no': ['no', 'nope', 'nah', 'never'],
                    'undecided': ['undecided', 'not sure', 'maybe', 'idk', 'i don\'t know']
                }

                for option in poll.options:
                    option_lower = option.lower()
                    if option_lower in option_map:
                        if response_lower in option_map[option_lower]:
                            matched_option = option
                            response_index = poll.options.index(option)
                            break

            if matched_option is None:
                options_list = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(poll.options)])
                return False, f"Please select a valid option:\n{options_list}"

            with engine.connect() as conn:
                # Check if already responded
                existing = conn.execute(text('''
                    SELECT id FROM poll_responses
                    WHERE poll_id = :poll_id AND phone_hash = :phone_hash
                '''), {'poll_id': poll_id, 'phone_hash': phone_hash})

                if existing.fetchone():
                    return False, "You have already responded to this poll"

                # Record response
                conn.execute(text('''
                    INSERT INTO poll_responses (
                        poll_id, phone_hash, response, response_index,
                        user_state, user_lga, user_age_range, user_gender, user_has_pvc
                    ) VALUES (
                        :poll_id, :phone_hash, :response, :response_index,
                        :user_state, :user_lga, :user_age_range, :user_gender, :user_has_pvc
                    )
                '''), {
                    'poll_id': poll_id,
                    'phone_hash': phone_hash,
                    'response': matched_option,
                    'response_index': response_index,
                    'user_state': user_state,
                    'user_lga': user_lga,
                    'user_age_range': user_age_range,
                    'user_gender': user_gender,
                    'user_has_pvc': user_has_pvc
                })

                # Update queue status
                conn.execute(text('''
                    UPDATE poll_queue
                    SET status = 'responded', responded_at = NOW()
                    WHERE poll_id = :poll_id AND phone_hash = :phone_hash
                '''), {'poll_id': poll_id, 'phone_hash': phone_hash})

                conn.commit()

                return True, f"Thank you! Your response '{matched_option}' has been recorded."

        except Exception as e:
            logger.error(f"Failed to record response: {e}")
            return False, "Failed to record your response. Please try again."

    def has_user_responded(self, poll_id: int, phone_hash: str) -> bool:
        """Check if user has already responded to a poll."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT 1 FROM poll_responses
                    WHERE poll_id = :poll_id AND phone_hash = :phone_hash
                '''), {'poll_id': poll_id, 'phone_hash': phone_hash})

                return result.fetchone() is not None

        except Exception as e:
            logger.error(f"Failed to check response: {e}")
            return False

    # =========================================
    # Formatting
    # =========================================

    def format_poll_question(self, poll: Poll) -> str:
        """Format a poll for display to user."""
        message = f"📊 *POLL*\n\n{poll.question}\n\n"

        for i, option in enumerate(poll.options, 1):
            message += f"{i}. {option}\n"

        message += "\n_Reply with the number or text of your choice_"

        if poll.ends_at:
            time_left = poll.ends_at - datetime.now()
            if time_left.days > 0:
                message += f"\n\n⏰ Ends in {time_left.days} days"
            elif time_left.seconds > 3600:
                message += f"\n\n⏰ Ends in {time_left.seconds // 3600} hours"

        return message


# Singleton instance
poll_service = PollService()


# Convenience functions for message handler
def get_next_poll_for_user(phone_hash: str) -> Optional[str]:
    """Get the next poll question for a user."""
    poll = poll_service.get_pending_poll_for_user(phone_hash)
    if poll:
        return poll_service.format_poll_question(poll)
    return None


def process_poll_response(
    poll_id: int,
    phone_hash: str,
    response: str,
    user_state: str = None,
    user_lga: str = None
) -> str:
    """Process a user's poll response."""
    success, message = poll_service.record_response(
        poll_id=poll_id,
        phone_hash=phone_hash,
        response=response,
        user_state=user_state,
        user_lga=user_lga
    )
    return message
