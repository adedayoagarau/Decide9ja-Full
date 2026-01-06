"""
Analytics Service for Decide9ja.

Provides:
- User metrics (DAU, WAU, MAU)
- Message/query analytics
- Geographic distribution
- Intent distribution
- Profile completeness tracking
- Real-time monitoring
"""
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class DailyMetrics:
    """Daily aggregated metrics."""
    date: date
    total_users: int = 0
    new_users: int = 0
    active_users: int = 0  # DAU
    returning_users: int = 0
    total_messages: int = 0
    total_queries: int = 0
    successful_queries: int = 0
    fallback_queries: int = 0
    polls_sent: int = 0
    polls_responded: int = 0


@dataclass
class WeeklyMetrics:
    """Weekly aggregated metrics."""
    week_start: date
    week_end: date
    total_users: int = 0
    new_users: int = 0
    active_users: int = 0  # WAU
    total_messages: int = 0
    total_queries: int = 0
    avg_dau: float = 0


@dataclass
class UserMetrics:
    """User-related metrics."""
    total_users: int = 0
    new_users_today: int = 0
    new_users_week: int = 0
    new_users_month: int = 0
    dau: int = 0
    wau: int = 0
    mau: int = 0
    users_by_state: Dict[str, int] = field(default_factory=dict)
    users_by_profile_tier: Dict[str, int] = field(default_factory=dict)
    pvc_holders: int = 0


@dataclass
class ConversationMetrics:
    """Conversation/query metrics."""
    messages_today: int = 0
    messages_week: int = 0
    messages_month: int = 0
    queries_today: int = 0
    avg_response_time_ms: int = 0
    fallback_rate: float = 0
    top_intents: List[Dict[str, Any]] = field(default_factory=list)
    top_queries: List[str] = field(default_factory=list)


class AnalyticsService:
    """Service for platform analytics."""

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
    # User Metrics
    # =========================================

    def get_user_metrics(self) -> UserMetrics:
        """Get comprehensive user metrics."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            today = date.today()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            with engine.connect() as conn:
                metrics = UserMetrics()

                # Total users
                result = conn.execute(text('SELECT COUNT(*) FROM users'))
                metrics.total_users = result.scalar() or 0

                # New users by period
                result = conn.execute(text('''
                    SELECT COUNT(*) FROM users WHERE DATE(created_at) = :today
                '''), {'today': today})
                metrics.new_users_today = result.scalar() or 0

                result = conn.execute(text('''
                    SELECT COUNT(*) FROM users WHERE DATE(created_at) >= :week_ago
                '''), {'week_ago': week_ago})
                metrics.new_users_week = result.scalar() or 0

                result = conn.execute(text('''
                    SELECT COUNT(*) FROM users WHERE DATE(created_at) >= :month_ago
                '''), {'month_ago': month_ago})
                metrics.new_users_month = result.scalar() or 0

                # Active users (from interactions table)
                try:
                    result = conn.execute(text('''
                        SELECT COUNT(DISTINCT phone_hash) FROM interactions
                        WHERE DATE(timestamp) = :today
                    '''), {'today': today})
                    metrics.dau = result.scalar() or 0

                    result = conn.execute(text('''
                        SELECT COUNT(DISTINCT phone_hash) FROM interactions
                        WHERE DATE(timestamp) >= :week_ago
                    '''), {'week_ago': week_ago})
                    metrics.wau = result.scalar() or 0

                    result = conn.execute(text('''
                        SELECT COUNT(DISTINCT phone_hash) FROM interactions
                        WHERE DATE(timestamp) >= :month_ago
                    '''), {'month_ago': month_ago})
                    metrics.mau = result.scalar() or 0
                except Exception:
                    # Interactions table might not exist
                    pass

                # Users by state
                try:
                    result = conn.execute(text('''
                        SELECT state, COUNT(*) as count FROM users
                        WHERE state IS NOT NULL
                        GROUP BY state
                        ORDER BY count DESC
                        LIMIT 20
                    '''))
                    metrics.users_by_state = {row[0]: row[1] for row in result}
                except Exception:
                    pass

                # PVC holders
                try:
                    result = conn.execute(text('''
                        SELECT COUNT(*) FROM users WHERE has_pvc = true
                    '''))
                    metrics.pvc_holders = result.scalar() or 0
                except Exception:
                    pass

                return metrics

        except Exception as e:
            logger.error(f"Failed to get user metrics: {e}")
            return UserMetrics()

    def get_dau_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get DAU trend for the last N days."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT DATE(timestamp) as day, COUNT(DISTINCT phone_hash) as dau
                    FROM interactions
                    WHERE DATE(timestamp) >= :start_date
                    GROUP BY DATE(timestamp)
                    ORDER BY day DESC
                '''), {'start_date': date.today() - timedelta(days=days)})

                return [{'date': str(row[0]), 'dau': row[1]} for row in result]

        except Exception as e:
            logger.error(f"Failed to get DAU trend: {e}")
            return []

    # =========================================
    # Conversation Metrics
    # =========================================

    def get_conversation_metrics(self) -> ConversationMetrics:
        """Get conversation/query metrics."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            today = date.today()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            metrics = ConversationMetrics()

            with engine.connect() as conn:
                # Message counts from interactions table
                try:
                    result = conn.execute(text('''
                        SELECT COUNT(*) FROM interactions WHERE DATE(timestamp) = :today
                    '''), {'today': today})
                    metrics.messages_today = result.scalar() or 0

                    result = conn.execute(text('''
                        SELECT COUNT(*) FROM interactions WHERE DATE(timestamp) >= :week_ago
                    '''), {'week_ago': week_ago})
                    metrics.messages_week = result.scalar() or 0

                    result = conn.execute(text('''
                        SELECT COUNT(*) FROM interactions WHERE DATE(timestamp) >= :month_ago
                    '''), {'month_ago': month_ago})
                    metrics.messages_month = result.scalar() or 0
                except Exception:
                    pass

                # Query metrics from query_log
                try:
                    result = conn.execute(text('''
                        SELECT COUNT(*) FROM query_log WHERE DATE(queried_at) = :today
                    '''), {'today': today})
                    metrics.queries_today = result.scalar() or 0

                    result = conn.execute(text('''
                        SELECT AVG(response_time_ms) FROM query_log
                        WHERE DATE(queried_at) >= :week_ago
                    '''), {'week_ago': week_ago})
                    metrics.avg_response_time_ms = int(result.scalar() or 0)

                    # Fallback rate
                    result = conn.execute(text('''
                        SELECT
                            COALESCE(SUM(CASE WHEN fallback_used THEN 1 ELSE 0 END), 0) as fallbacks,
                            COUNT(*) as total
                        FROM query_log
                        WHERE DATE(queried_at) >= :week_ago
                    '''), {'week_ago': week_ago})
                    row = result.fetchone()
                    if row and row[1] > 0:
                        metrics.fallback_rate = round(row[0] / row[1] * 100, 1)

                    # Top intents
                    result = conn.execute(text('''
                        SELECT intent, COUNT(*) as count
                        FROM query_log
                        WHERE DATE(queried_at) >= :month_ago
                          AND intent IS NOT NULL
                        GROUP BY intent
                        ORDER BY count DESC
                        LIMIT 10
                    '''), {'month_ago': month_ago})
                    metrics.top_intents = [
                        {'intent': row[0], 'count': row[1]}
                        for row in result
                    ]
                except Exception:
                    pass

                return metrics

        except Exception as e:
            logger.error(f"Failed to get conversation metrics: {e}")
            return ConversationMetrics()

    def get_intent_distribution(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get intent distribution for the last N days."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT
                        intent,
                        COUNT(*) as count,
                        ROUND(COUNT(*)::numeric / NULLIF(SUM(COUNT(*)) OVER (), 0) * 100, 1) as percentage,
                        AVG(response_time_ms) as avg_response_time,
                        SUM(CASE WHEN fallback_used THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100 as fallback_rate
                    FROM query_log
                    WHERE queried_at >= :start_date
                      AND intent IS NOT NULL
                    GROUP BY intent
                    ORDER BY count DESC
                '''), {'start_date': date.today() - timedelta(days=days)})

                return [
                    {
                        'intent': row[0],
                        'count': row[1],
                        'percentage': float(row[2]) if row[2] else 0,
                        'avg_response_time_ms': int(row[3]) if row[3] else 0,
                        'fallback_rate': float(row[4]) if row[4] else 0
                    }
                    for row in result
                ]

        except Exception as e:
            logger.error(f"Failed to get intent distribution: {e}")
            return []

    # =========================================
    # Geographic Distribution
    # =========================================

    def get_geographic_distribution(self) -> Dict[str, Any]:
        """Get user distribution by state."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT state, COUNT(*) as count
                    FROM users
                    WHERE state IS NOT NULL
                    GROUP BY state
                    ORDER BY count DESC
                '''))

                states = {row[0]: row[1] for row in result}
                total = sum(states.values())

                return {
                    'total_with_state': total,
                    'states': states,
                    'top_5': dict(list(states.items())[:5])
                }

        except Exception as e:
            logger.error(f"Failed to get geographic distribution: {e}")
            return {'total_with_state': 0, 'states': {}, 'top_5': {}}

    # =========================================
    # Poll Analytics
    # =========================================

    def get_poll_metrics(self) -> Dict[str, Any]:
        """Get poll-related metrics."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            today = date.today()

            with engine.connect() as conn:
                result = conn.execute(text('''
                    SELECT
                        (SELECT COUNT(*) FROM polls) as total_polls,
                        (SELECT COUNT(*) FROM polls WHERE status = 'active') as active_polls,
                        (SELECT COUNT(*) FROM poll_responses) as total_responses,
                        (SELECT COUNT(*) FROM poll_responses WHERE DATE(responded_at) = :today) as responses_today,
                        (SELECT AVG(response_count) FROM (
                            SELECT COUNT(*) as response_count
                            FROM poll_responses
                            GROUP BY poll_id
                        ) as subq) as avg_responses_per_poll
                '''), {'today': today})

                row = result.fetchone()

                return {
                    'total_polls': row[0] or 0,
                    'active_polls': row[1] or 0,
                    'total_responses': row[2] or 0,
                    'responses_today': row[3] or 0,
                    'avg_responses_per_poll': round(float(row[4]), 1) if row[4] else 0
                }

        except Exception as e:
            logger.error(f"Failed to get poll metrics: {e}")
            return {
                'total_polls': 0,
                'active_polls': 0,
                'total_responses': 0,
                'responses_today': 0,
                'avg_responses_per_poll': 0
            }

    # =========================================
    # Record Metrics
    # =========================================

    def log_query(
        self,
        intent: str,
        user_state: str = None,
        user_lga: str = None,
        response_time_ms: int = None,
        was_successful: bool = True,
        fallback_used: bool = False,
        sources_used: List[str] = None
    ):
        """Log a query for analytics."""
        try:
            from sqlalchemy import text
            import json
            engine = self._get_engine()

            with engine.connect() as conn:
                conn.execute(text('''
                    INSERT INTO query_log (
                        intent, user_state, user_lga, response_time_ms,
                        was_successful, fallback_used, sources_used
                    ) VALUES (
                        :intent, :user_state, :user_lga, :response_time_ms,
                        :was_successful, :fallback_used, :sources_used
                    )
                '''), {
                    'intent': intent,
                    'user_state': user_state,
                    'user_lga': user_lga,
                    'response_time_ms': response_time_ms,
                    'was_successful': was_successful,
                    'fallback_used': fallback_used,
                    'sources_used': json.dumps(sources_used or [])
                })
                conn.commit()

        except Exception as e:
            logger.warning(f"Failed to log query: {e}")

    def record_daily_metrics(self, metric_date: date = None):
        """Record daily aggregated metrics."""
        try:
            from sqlalchemy import text
            engine = self._get_engine()

            if metric_date is None:
                metric_date = date.today()

            with engine.connect() as conn:
                conn.execute(text('''
                    SELECT record_daily_metrics(:metric_date)
                '''), {'metric_date': metric_date})
                conn.commit()

        except Exception as e:
            logger.warning(f"Failed to record daily metrics: {e}")

    # =========================================
    # Dashboard Data
    # =========================================

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all data needed for admin dashboard."""
        return {
            'user_metrics': self.get_user_metrics().__dict__,
            'conversation_metrics': self.get_conversation_metrics().__dict__,
            'geographic_distribution': self.get_geographic_distribution(),
            'poll_metrics': self.get_poll_metrics(),
            'dau_trend': self.get_dau_trend(30),
            'intent_distribution': self.get_intent_distribution(30),
            'generated_at': datetime.now().isoformat()
        }


# Singleton instance
analytics_service = AnalyticsService()


# Convenience functions
def get_dashboard_data() -> Dict[str, Any]:
    """Get dashboard data."""
    return analytics_service.get_dashboard_data()


def log_query(intent: str, **kwargs):
    """Log a query for analytics."""
    analytics_service.log_query(intent, **kwargs)
