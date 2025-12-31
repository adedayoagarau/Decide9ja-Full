"""
Analytics Service for Decide9ja.
Tracks usage metrics and generates insights.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import Counter

from app.database import SessionLocal, Interaction, Issue, NewsArticle, Politician

logger = logging.getLogger(__name__)


def get_usage_stats(days: int = 7) -> Dict[str, Any]:
    """Get usage statistics for the past N days."""
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=days)
        
        # Total interactions
        total_interactions = db.query(Interaction).filter(
            Interaction.created_at >= cutoff
        ).count()
        
        # Interactions by day
        interactions = db.query(Interaction).filter(
            Interaction.created_at >= cutoff
        ).all()
        
        by_day = Counter()
        by_intent = Counter()
        
        for i in interactions:
            day = i.created_at.strftime("%Y-%m-%d") if i.created_at else "unknown"
            by_day[day] += 1
            if i.intent:
                by_intent[i.intent] += 1
        
        # Issues stats
        active_issues = db.query(Issue).filter(Issue.status == "active").count()
        severe_issues = db.query(Issue).filter(
            Issue.status == "active",
            Issue.severity == "severe"
        ).count()
        
        # News stats
        news_count = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff
        ).count()
        
        # Politician count
        politician_count = db.query(Politician).count()
        
        return {
            "period_days": days,
            "total_interactions": total_interactions,
            "interactions_by_day": dict(sorted(by_day.items())),
            "top_intents": dict(by_intent.most_common(10)),
            "active_issues": active_issues,
            "severe_issues": severe_issues,
            "news_articles_scraped": news_count,
            "politicians_tracked": politician_count,
            "generated_at": datetime.now().isoformat(),
        }
        
    finally:
        db.close()


def get_top_queries(days: int = 7, limit: int = 20) -> List[Dict]:
    """Get most common query patterns."""
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=days)
        
        interactions = db.query(Interaction).filter(
            Interaction.created_at >= cutoff
        ).all()
        
        # Extract query patterns (first 50 chars)
        patterns = Counter()
        for i in interactions:
            if i.query:
                # Normalize query
                q = i.query.lower().strip()[:50]
                patterns[q] += 1
        
        return [
            {"query": q, "count": c}
            for q, c in patterns.most_common(limit)
        ]
        
    finally:
        db.close()


def get_unique_users(days: int = 7) -> int:
    """Estimate unique users based on interaction patterns."""
    # In production, this would use user hashes
    # For now, estimate based on session gaps
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=days)
        
        interactions = db.query(Interaction).filter(
            Interaction.created_at >= cutoff
        ).order_by(Interaction.created_at).all()
        
        if not interactions:
            return 0
        
        # Count "sessions" - gaps of 30+ minutes = new session
        sessions = 1
        last_time = interactions[0].created_at if interactions[0].created_at else datetime.now()
        
        for i in interactions[1:]:
            if i.created_at and (i.created_at - last_time) > timedelta(minutes=30):
                sessions += 1
            if i.created_at:
                last_time = i.created_at
        
        # Rough estimate: sessions / average sessions per user
        estimated_users = max(1, sessions // 3)
        return estimated_users
        
    finally:
        db.close()


def get_issue_analytics() -> Dict[str, Any]:
    """Get analytics about tracked issues."""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        # Issues by domain
        domain_counts = db.query(
            Issue.domain,
            func.count(Issue.id).label("count")
        ).filter(
            Issue.status == "active"
        ).group_by(Issue.domain).all()
        
        # Issues by severity
        severity_counts = db.query(
            Issue.severity,
            func.count(Issue.id).label("count")
        ).filter(
            Issue.status == "active"
        ).group_by(Issue.severity).all()
        
        # Recent issues
        recent = db.query(Issue).filter(
            Issue.status == "active"
        ).order_by(Issue.last_updated.desc()).limit(10).all()
        
        return {
            "by_domain": {d[0]: d[1] for d in domain_counts},
            "by_severity": {s[0]: s[1] for s in severity_counts},
            "recent_issues": [
                {
                    "id": i.issue_id,
                    "title": i.title,
                    "domain": i.domain,
                    "severity": i.severity,
                    "updated": i.last_updated.isoformat() if i.last_updated else None,
                }
                for i in recent
            ],
        }
        
    finally:
        db.close()


def log_interaction(
    query: str,
    response: str,
    intent: Optional[str] = None,
    context_used: Optional[str] = None,
    response_time_ms: Optional[int] = None,
):
    """Log a user interaction for analytics."""
    db = SessionLocal()
    try:
        interaction = Interaction(
            query=query[:500],
            response=response[:2000],
            intent=intent,
            context_used=context_used[:500] if context_used else None,
            response_time_ms=response_time_ms,
        )
        db.add(interaction)
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to log interaction: {e}")
        db.rollback()
    finally:
        db.close()


def generate_daily_report() -> Dict[str, Any]:
    """Generate a daily report for admin review."""
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "usage": get_usage_stats(days=1),
        "unique_users_estimate": get_unique_users(days=1),
        "top_queries": get_top_queries(days=1, limit=10),
        "issues": get_issue_analytics(),
    }


def generate_weekly_report() -> Dict[str, Any]:
    """Generate a weekly report for admin review."""
    return {
        "week_ending": datetime.now().strftime("%Y-%m-%d"),
        "usage": get_usage_stats(days=7),
        "unique_users_estimate": get_unique_users(days=7),
        "top_queries": get_top_queries(days=7, limit=20),
        "issues": get_issue_analytics(),
    }
