"""
Analytics Dashboard Service for Decide9ja
Provides data aggregation and visualization endpoints for admin dashboard
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum
from collections import defaultdict

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TimeRange(str, Enum):
    """Time range options for analytics."""
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    THIS_MONTH = "month"
    THIS_YEAR = "year"
    ALL_TIME = "all"


class DashboardMetrics(BaseModel):
    """Core dashboard metrics."""
    total_users: int
    active_users_today: int
    active_users_week: int
    total_messages: int
    messages_today: int
    avg_response_time_ms: float
    issues_reported: int
    issues_resolved: int
    factchecks_published: int
    broadcasts_sent: int


class UserEngagementData(BaseModel):
    """User engagement metrics."""
    period: str
    new_users: int
    returning_users: int
    messages_sent: int
    avg_session_length_seconds: float
    top_queries: List[Dict[str, Any]]


class GeographicData(BaseModel):
    """Geographic distribution data."""
    by_state: Dict[str, int]
    by_lga: Dict[str, int]


class AnalyticsDashboardService:
    """
    Service for aggregating and serving dashboard analytics.
    """

    # In-memory metrics storage (would be database in production)
    _metrics_cache: Dict[str, Any] = {}
    _last_refresh: Optional[datetime] = None
    CACHE_TTL_SECONDS = 300  # 5 minutes

    @classmethod
    def _get_time_range_dates(cls, time_range: TimeRange) -> Tuple[datetime, datetime]:
        """Get start and end dates for a time range."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        ranges = {
            TimeRange.TODAY: (today_start, now),
            TimeRange.YESTERDAY: (
                today_start - timedelta(days=1),
                today_start
            ),
            TimeRange.LAST_7_DAYS: (
                today_start - timedelta(days=7),
                now
            ),
            TimeRange.LAST_30_DAYS: (
                today_start - timedelta(days=30),
                now
            ),
            TimeRange.LAST_90_DAYS: (
                today_start - timedelta(days=90),
                now
            ),
            TimeRange.THIS_MONTH: (
                today_start.replace(day=1),
                now
            ),
            TimeRange.THIS_YEAR: (
                today_start.replace(month=1, day=1),
                now
            ),
            TimeRange.ALL_TIME: (
                datetime(2024, 1, 1),
                now
            )
        }

        return ranges.get(time_range, (today_start - timedelta(days=7), now))

    @classmethod
    async def get_overview_metrics(cls, db=None) -> DashboardMetrics:
        """Get high-level overview metrics for dashboard."""
        # In production, these would come from database queries
        # For now, return sample structure

        metrics = DashboardMetrics(
            total_users=0,
            active_users_today=0,
            active_users_week=0,
            total_messages=0,
            messages_today=0,
            avg_response_time_ms=0.0,
            issues_reported=0,
            issues_resolved=0,
            factchecks_published=0,
            broadcasts_sent=0
        )

        try:
            if db:
                from app.database import User, Interaction, CommunityIssue

                # Total users
                metrics.total_users = db.query(User).count()

                # Active users
                today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                week_ago = today - timedelta(days=7)

                metrics.active_users_today = db.query(User).filter(
                    User.last_active >= today
                ).count()

                metrics.active_users_week = db.query(User).filter(
                    User.last_active >= week_ago
                ).count()

                # Messages
                metrics.total_messages = db.query(Interaction).count()
                metrics.messages_today = db.query(Interaction).filter(
                    Interaction.created_at >= today
                ).count()

                # Average response time
                from sqlalchemy import func
                avg_result = db.query(func.avg(Interaction.response_time_ms)).scalar()
                metrics.avg_response_time_ms = float(avg_result) if avg_result else 0.0

                # Issues
                metrics.issues_reported = db.query(CommunityIssue).count()
                metrics.issues_resolved = db.query(CommunityIssue).filter(
                    CommunityIssue.status == "resolved"
                ).count()

        except Exception as e:
            logger.error(f"Error fetching overview metrics: {e}")

        return metrics

    @classmethod
    async def get_message_trends(
        cls,
        time_range: TimeRange = TimeRange.LAST_7_DAYS,
        db=None
    ) -> Dict[str, Any]:
        """Get message volume trends over time."""
        start_date, end_date = cls._get_time_range_dates(time_range)

        # Determine granularity based on range
        if time_range in [TimeRange.TODAY, TimeRange.YESTERDAY]:
            granularity = "hour"
        elif time_range in [TimeRange.LAST_7_DAYS, TimeRange.THIS_MONTH]:
            granularity = "day"
        else:
            granularity = "week"

        data_points = []

        try:
            if db:
                from app.database import Interaction
                from sqlalchemy import func

                if granularity == "hour":
                    # Hourly data
                    results = db.query(
                        func.date_trunc('hour', Interaction.created_at).label('period'),
                        func.count(Interaction.id).label('count')
                    ).filter(
                        Interaction.created_at >= start_date,
                        Interaction.created_at <= end_date
                    ).group_by('period').order_by('period').all()

                elif granularity == "day":
                    # Daily data
                    results = db.query(
                        func.date(Interaction.created_at).label('period'),
                        func.count(Interaction.id).label('count')
                    ).filter(
                        Interaction.created_at >= start_date,
                        Interaction.created_at <= end_date
                    ).group_by('period').order_by('period').all()

                else:
                    # Weekly data
                    results = db.query(
                        func.date_trunc('week', Interaction.created_at).label('period'),
                        func.count(Interaction.id).label('count')
                    ).filter(
                        Interaction.created_at >= start_date,
                        Interaction.created_at <= end_date
                    ).group_by('period').order_by('period').all()

                data_points = [
                    {
                        "period": r.period.isoformat() if hasattr(r.period, 'isoformat') else str(r.period),
                        "count": r.count
                    }
                    for r in results
                ]

        except Exception as e:
            logger.error(f"Error fetching message trends: {e}")

        return {
            "time_range": time_range.value,
            "granularity": granularity,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "data_points": data_points
        }

    @classmethod
    async def get_top_queries(
        cls,
        limit: int = 20,
        time_range: TimeRange = TimeRange.LAST_7_DAYS,
        db=None
    ) -> List[Dict[str, Any]]:
        """Get most common user queries."""
        start_date, end_date = cls._get_time_range_dates(time_range)
        top_queries = []

        try:
            if db:
                from app.database import Interaction
                from sqlalchemy import func

                # This is a simplified approach - in production you'd use
                # more sophisticated query clustering/categorization
                results = db.query(
                    Interaction.query,
                    func.count(Interaction.id).label('count')
                ).filter(
                    Interaction.created_at >= start_date,
                    Interaction.created_at <= end_date
                ).group_by(
                    Interaction.query
                ).order_by(
                    func.count(Interaction.id).desc()
                ).limit(limit).all()

                top_queries = [
                    {"query": r.query[:100], "count": r.count}
                    for r in results
                ]

        except Exception as e:
            logger.error(f"Error fetching top queries: {e}")

        return top_queries

    @classmethod
    async def get_geographic_distribution(
        cls,
        time_range: TimeRange = TimeRange.LAST_30_DAYS,
        db=None
    ) -> Dict[str, Any]:
        """Get geographic distribution of users."""
        start_date, end_date = cls._get_time_range_dates(time_range)

        by_state = {}
        by_lga = {}

        try:
            if db:
                from app.database import User
                from sqlalchemy import func

                # By state
                state_results = db.query(
                    User.state,
                    func.count(User.id).label('count')
                ).filter(
                    User.state.isnot(None)
                ).group_by(
                    User.state
                ).order_by(
                    func.count(User.id).desc()
                ).all()

                by_state = {r.state: r.count for r in state_results}

                # By LGA
                lga_results = db.query(
                    User.lga,
                    func.count(User.id).label('count')
                ).filter(
                    User.lga.isnot(None)
                ).group_by(
                    User.lga
                ).order_by(
                    func.count(User.id).desc()
                ).limit(50).all()

                by_lga = {r.lga: r.count for r in lga_results}

        except Exception as e:
            logger.error(f"Error fetching geographic distribution: {e}")

        return {
            "time_range": time_range.value,
            "by_state": by_state,
            "by_lga": by_lga,
            "total_states": len(by_state),
            "total_lgas": len(by_lga)
        }

    @classmethod
    async def get_issue_analytics(
        cls,
        time_range: TimeRange = TimeRange.LAST_30_DAYS,
        db=None
    ) -> Dict[str, Any]:
        """Get community issue analytics."""
        start_date, end_date = cls._get_time_range_dates(time_range)

        analytics = {
            "total": 0,
            "by_status": {},
            "by_category": {},
            "by_priority": {},
            "resolution_rate": 0.0,
            "avg_resolution_time_hours": None,
            "trending_locations": []
        }

        try:
            if db:
                from app.database import CommunityIssue
                from sqlalchemy import func

                # Total issues in range
                total = db.query(CommunityIssue).filter(
                    CommunityIssue.created_at >= start_date,
                    CommunityIssue.created_at <= end_date
                ).count()
                analytics["total"] = total

                # By status
                status_results = db.query(
                    CommunityIssue.status,
                    func.count(CommunityIssue.id).label('count')
                ).filter(
                    CommunityIssue.created_at >= start_date,
                    CommunityIssue.created_at <= end_date
                ).group_by(CommunityIssue.status).all()

                analytics["by_status"] = {r.status: r.count for r in status_results}

                # By category
                category_results = db.query(
                    CommunityIssue.category,
                    func.count(CommunityIssue.id).label('count')
                ).filter(
                    CommunityIssue.created_at >= start_date,
                    CommunityIssue.created_at <= end_date
                ).group_by(CommunityIssue.category).all()

                analytics["by_category"] = {r.category: r.count for r in category_results}

                # Resolution rate
                resolved = analytics["by_status"].get("resolved", 0)
                if total > 0:
                    analytics["resolution_rate"] = round(resolved / total * 100, 1)

        except Exception as e:
            logger.error(f"Error fetching issue analytics: {e}")

        return analytics

    @classmethod
    async def get_broadcast_analytics(
        cls,
        time_range: TimeRange = TimeRange.LAST_30_DAYS,
        db=None
    ) -> Dict[str, Any]:
        """Get broadcast campaign analytics."""
        from app.services.broadcast import BroadcastService, BroadcastStatus

        campaigns = BroadcastService.list_campaigns()

        start_date, end_date = cls._get_time_range_dates(time_range)

        total_campaigns = len(campaigns)
        total_recipients = sum(c.sent_count for c in campaigns)
        total_delivered = sum(c.delivered_count for c in campaigns)

        by_status = defaultdict(int)
        for c in campaigns:
            by_status[c.status.value] += 1

        return {
            "total_campaigns": total_campaigns,
            "total_recipients": total_recipients,
            "total_delivered": total_delivered,
            "delivery_rate": round(total_delivered / total_recipients * 100, 1) if total_recipients > 0 else 0,
            "by_status": dict(by_status),
            "time_range": time_range.value
        }

    @classmethod
    async def get_factcheck_analytics(
        cls,
        time_range: TimeRange = TimeRange.LAST_30_DAYS,
        db=None
    ) -> Dict[str, Any]:
        """Get fact-checking analytics."""
        from app.services.factcheck import FactCheckService, FactCheckVerdict, FactCheckStatus

        factchecks = FactCheckService.list_factchecks()

        by_verdict = defaultdict(int)
        by_status = defaultdict(int)
        by_category = defaultdict(int)

        for fc in factchecks:
            if fc.verdict:
                by_verdict[fc.verdict.value] += 1
            by_status[fc.status.value] += 1
            if hasattr(fc, 'category') and fc.category:
                by_category[fc.category] += 1

        published_count = by_status.get("published", 0)

        return {
            "total": len(factchecks),
            "published": published_count,
            "pending": by_status.get("pending", 0),
            "by_verdict": dict(by_verdict),
            "by_status": dict(by_status),
            "by_category": dict(by_category),
            "time_range": time_range.value
        }

    @classmethod
    async def get_response_time_analytics(
        cls,
        time_range: TimeRange = TimeRange.LAST_7_DAYS,
        db=None
    ) -> Dict[str, Any]:
        """Get response time analytics."""
        start_date, end_date = cls._get_time_range_dates(time_range)

        analytics = {
            "avg_ms": 0,
            "median_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "min_ms": 0,
            "max_ms": 0,
            "distribution": []
        }

        try:
            if db:
                from app.database import Interaction
                from sqlalchemy import func

                # Basic stats
                stats = db.query(
                    func.avg(Interaction.response_time_ms).label('avg'),
                    func.min(Interaction.response_time_ms).label('min'),
                    func.max(Interaction.response_time_ms).label('max')
                ).filter(
                    Interaction.created_at >= start_date,
                    Interaction.created_at <= end_date
                ).first()

                if stats:
                    analytics["avg_ms"] = round(float(stats.avg or 0), 1)
                    analytics["min_ms"] = int(stats.min or 0)
                    analytics["max_ms"] = int(stats.max or 0)

                # Response time distribution (buckets)
                buckets = [
                    (0, 100, "< 100ms"),
                    (100, 500, "100-500ms"),
                    (500, 1000, "500ms-1s"),
                    (1000, 3000, "1-3s"),
                    (3000, float('inf'), "> 3s")
                ]

                distribution = []
                for low, high, label in buckets:
                    count = db.query(Interaction).filter(
                        Interaction.created_at >= start_date,
                        Interaction.created_at <= end_date,
                        Interaction.response_time_ms >= low,
                        Interaction.response_time_ms < high
                    ).count()
                    distribution.append({"range": label, "count": count})

                analytics["distribution"] = distribution

        except Exception as e:
            logger.error(f"Error fetching response time analytics: {e}")

        return analytics

    @classmethod
    async def get_user_retention(
        cls,
        cohort_weeks: int = 8,
        db=None
    ) -> Dict[str, Any]:
        """Get user retention cohort data."""
        # This would calculate weekly retention cohorts
        # Simplified version for now
        cohorts = []

        # Sample structure
        for week in range(cohort_weeks):
            cohort_start = datetime.utcnow() - timedelta(weeks=week+1)
            cohort_end = cohort_start + timedelta(weeks=1)

            cohorts.append({
                "cohort_week": f"Week -{week+1}",
                "start_date": cohort_start.strftime("%Y-%m-%d"),
                "initial_users": 0,
                "week_1_retention": 0.0,
                "week_2_retention": 0.0,
                "week_4_retention": 0.0
            })

        return {
            "cohort_weeks": cohort_weeks,
            "cohorts": cohorts
        }

    @classmethod
    async def get_full_dashboard(
        cls,
        time_range: TimeRange = TimeRange.LAST_7_DAYS,
        db=None
    ) -> Dict[str, Any]:
        """Get all dashboard data in one call."""
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "time_range": time_range.value,
            "overview": (await cls.get_overview_metrics(db)).model_dump(),
            "message_trends": await cls.get_message_trends(time_range, db),
            "top_queries": await cls.get_top_queries(20, time_range, db),
            "geographic": await cls.get_geographic_distribution(time_range, db),
            "issues": await cls.get_issue_analytics(time_range, db),
            "broadcasts": await cls.get_broadcast_analytics(time_range, db),
            "factchecks": await cls.get_factcheck_analytics(time_range, db),
            "response_times": await cls.get_response_time_analytics(time_range, db)
        }

    @classmethod
    async def export_dashboard_report(
        cls,
        time_range: TimeRange = TimeRange.LAST_30_DAYS,
        format: str = "json",
        db=None
    ) -> str:
        """Export dashboard report in JSON or CSV format."""
        import json

        data = await cls.get_full_dashboard(time_range, db)

        if format == "json":
            return json.dumps(data, indent=2, default=str)

        elif format == "csv":
            # Convert to flat CSV format
            lines = ["Metric,Value"]

            overview = data.get("overview", {})
            for key, value in overview.items():
                lines.append(f"{key},{value}")

            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported format: {format}")
