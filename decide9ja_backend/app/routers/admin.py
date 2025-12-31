"""
Admin API Router
Endpoints for dashboard analytics and moderation.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.analytics import (
    get_usage_stats,
    get_top_queries,
    get_unique_users,
    get_issue_analytics,
    generate_daily_report,
    generate_weekly_report,
)
from app.database import SessionLocal, Politician, Issue, NewsArticle

router = APIRouter(prefix="/api/admin", tags=["admin"])


# =====================
# Analytics Endpoints
# =====================

@router.get("/stats")
async def get_stats(days: int = Query(7, ge=1, le=90)):
    """Get usage statistics for the past N days."""
    return get_usage_stats(days=days)


@router.get("/queries")
async def get_queries(days: int = Query(7, ge=1, le=90), limit: int = Query(20, ge=1, le=100)):
    """Get top queries for the past N days."""
    return {
        "period_days": days,
        "queries": get_top_queries(days=days, limit=limit)
    }


@router.get("/users")
async def get_users_estimate(days: int = Query(7, ge=1, le=90)):
    """Get estimated unique users for the past N days."""
    return {
        "period_days": days,
        "estimated_users": get_unique_users(days=days)
    }


@router.get("/issues/analytics")
async def get_issues_analytics():
    """Get issue tracking analytics."""
    return get_issue_analytics()


@router.get("/report/daily")
async def get_daily_report():
    """Generate daily analytics report."""
    return generate_daily_report()


@router.get("/report/weekly")
async def get_weekly_report():
    """Generate weekly analytics report."""
    return generate_weekly_report()


# =====================
# Overview Dashboard
# =====================

@router.get("/overview")
async def get_admin_overview():
    """Get comprehensive admin dashboard overview."""
    db = SessionLocal()
    try:
        # Quick counts
        politician_count = db.query(Politician).count()
        issue_count = db.query(Issue).filter(Issue.status == "active").count()
        severe_count = db.query(Issue).filter(
            Issue.status == "active",
            Issue.severity == "severe"
        ).count()
        news_count = db.query(NewsArticle).count()
        
        # Get usage stats
        usage = get_usage_stats(days=7)
        
        return {
            "counts": {
                "politicians": politician_count,
                "active_issues": issue_count,
                "severe_issues": severe_count,
                "news_articles": news_count,
            },
            "usage_7d": usage,
            "estimated_users_7d": get_unique_users(days=7),
        }
        
    finally:
        db.close()


# =====================
# Content Management
# =====================

@router.get("/politicians")
async def list_politicians(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    party: Optional[str] = None,
    state: Optional[str] = None,
):
    """List politicians for admin management."""
    db = SessionLocal()
    try:
        query = db.query(Politician)
        
        if party:
            query = query.filter(Politician.party == party)
        if state:
            query = query.filter(Politician.state == state)
        
        total = query.count()
        politicians = query.offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "politicians": [
                {
                    "slug": p.slug,
                    "name": p.name,
                    "party": p.party,
                    "position": p.position,
                    "state": p.state,
                }
                for p in politicians
            ]
        }
        
    finally:
        db.close()


@router.get("/news")
async def list_news(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    processed: Optional[bool] = None,
):
    """List news articles for admin review."""
    db = SessionLocal()
    try:
        query = db.query(NewsArticle)
        
        if source:
            query = query.filter(NewsArticle.source == source)
        if processed is not None:
            query = query.filter(NewsArticle.is_processed == processed)
        
        total = query.count()
        articles = query.order_by(NewsArticle.scraped_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "articles": [
                {
                    "id": a.article_id,
                    "title": a.title,
                    "source": a.source_name,
                    "url": a.url,
                    "scraped_at": a.scraped_at.isoformat() if a.scraped_at else None,
                    "is_processed": a.is_processed,
                }
                for a in articles
            ]
        }
        
    finally:
        db.close()


# =====================
# System Health
# =====================

@router.get("/health")
async def admin_health_check():
    """Detailed health check for admin."""
    db = SessionLocal()
    try:
        from app.database import Document
        
        politicians = db.query(Politician).count()
        documents = db.query(Document).count()
        issues = db.query(Issue).count()
        news = db.query(NewsArticle).count()
        
        return {
            "status": "healthy",
            "database": {
                "politicians": politicians,
                "documents": documents,
                "issues": issues,
                "news_articles": news,
            },
            "services": {
                "rag": "ok",
                "llm": "ok" if os.getenv("ANTHROPIC_API_KEY") else "missing_key",
                "scheduler": "unknown",  # Would need to check scheduler health
            }
        }
        
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
    finally:
        db.close()


import os
