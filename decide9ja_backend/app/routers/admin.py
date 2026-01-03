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
from app.services.analytics_service import analytics_service
from app.services.poll_service import poll_service, Poll
from app.services.poll_results_service import poll_results_service
from app.database import SessionLocal, Politician, Issue, NewsArticle

router = APIRouter(prefix="/api/admin", tags=["admin"])


# =====================
# Dashboard Endpoint
# =====================

@router.get("/dashboard")
async def get_dashboard():
    """Redirect to admin dashboard HTML."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/dashboard.html")


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
from typing import List
from datetime import datetime


# =====================
# New Metrics Endpoints (Phase 4)
# =====================

@router.get("/metrics")
async def get_metrics():
    """Get comprehensive platform metrics."""
    return analytics_service.get_dashboard_data()


@router.get("/metrics/users")
async def get_user_metrics():
    """Get user-related metrics."""
    return analytics_service.get_user_metrics().__dict__


@router.get("/metrics/conversations")
async def get_conversation_metrics():
    """Get conversation/query metrics."""
    return analytics_service.get_conversation_metrics().__dict__


@router.get("/metrics/geographic")
async def get_geographic_metrics():
    """Get geographic distribution of users."""
    return analytics_service.get_geographic_distribution()


@router.get("/metrics/intents")
async def get_intent_metrics(days: int = Query(30, ge=1, le=90)):
    """Get intent distribution over time."""
    return analytics_service.get_intent_distribution(days)


@router.get("/metrics/dau-trend")
async def get_dau_trend(days: int = Query(30, ge=1, le=90)):
    """Get DAU trend over time."""
    return analytics_service.get_dau_trend(days)


# =====================
# Poll Management Endpoints
# =====================

class PollCreate(BaseModel):
    question: str
    options: List[str]
    category: Optional[str] = None
    target_state: Optional[str] = None
    target_lga: Optional[str] = None
    ends_at: Optional[datetime] = None
    max_responses: Optional[int] = None


@router.post("/polls")
async def create_poll(poll_data: PollCreate):
    """Create a new poll."""
    poll_id = poll_service.create_poll(
        question=poll_data.question,
        options=poll_data.options,
        category=poll_data.category,
        target_state=poll_data.target_state,
        target_lga=poll_data.target_lga,
        ends_at=poll_data.ends_at,
        max_responses=poll_data.max_responses,
        status="draft"
    )

    if poll_id:
        return {"success": True, "poll_id": poll_id}
    raise HTTPException(status_code=500, detail="Failed to create poll")


@router.get("/polls")
async def list_polls(
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """List all polls."""
    if status == "active":
        polls = poll_service.get_active_polls(limit)
    else:
        # Get all polls (simplified - would need full implementation)
        polls = poll_service.get_active_polls(limit)

    return {
        "count": len(polls),
        "polls": [
            {
                "id": p.id,
                "question": p.question,
                "options": p.options,
                "category": p.category,
                "status": p.status,
                "response_count": p.response_count,
                "target_state": p.target_state,
                "ends_at": p.ends_at.isoformat() if p.ends_at else None
            }
            for p in polls
        ]
    }


@router.get("/polls/{poll_id}")
async def get_poll(poll_id: int):
    """Get a specific poll with results."""
    poll = poll_service.get_poll(poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    results = poll_results_service.get_poll_results(poll_id)

    return {
        "poll": {
            "id": poll.id,
            "question": poll.question,
            "options": poll.options,
            "category": poll.category,
            "status": poll.status,
            "response_count": poll.response_count,
            "target_state": poll.target_state,
            "ends_at": poll.ends_at.isoformat() if poll.ends_at else None
        },
        "results": {
            "total_responses": results.total_responses if results else 0,
            "options": [
                {"option": o.option, "count": o.count, "percentage": o.percentage}
                for o in (results.options if results else [])
            ]
        }
    }


@router.post("/polls/{poll_id}/activate")
async def activate_poll(poll_id: int):
    """Activate a poll for distribution."""
    success = poll_service.update_poll_status(poll_id, "active")
    if success:
        return {"success": True, "status": "active"}
    raise HTTPException(status_code=500, detail="Failed to activate poll")


@router.post("/polls/{poll_id}/pause")
async def pause_poll(poll_id: int):
    """Pause an active poll."""
    success = poll_service.update_poll_status(poll_id, "paused")
    if success:
        return {"success": True, "status": "paused"}
    raise HTTPException(status_code=500, detail="Failed to pause poll")


@router.post("/polls/{poll_id}/distribute")
async def distribute_poll(poll_id: int, limit: int = Query(100, ge=1, le=1000)):
    """Queue a poll for distribution to eligible users."""
    eligible_users = poll_service.find_eligible_users(poll_id, limit)
    if not eligible_users:
        return {"success": True, "queued": 0, "message": "No eligible users found"}

    queued = poll_service.queue_poll_for_users(poll_id, eligible_users)
    return {"success": True, "queued": queued}


@router.get("/polls/{poll_id}/results")
async def get_poll_results(poll_id: int):
    """Get detailed poll results with segmentation."""
    results = poll_results_service.get_poll_results(poll_id)
    if not results:
        raise HTTPException(status_code=404, detail="Poll not found")

    state_results = poll_results_service.get_results_by_state(poll_id)
    age_results = poll_results_service.get_results_by_age(poll_id)
    gender_results = poll_results_service.get_results_by_gender(poll_id)

    return {
        "poll_id": poll_id,
        "question": results.question,
        "total_responses": results.total_responses,
        "overall": [
            {"option": o.option, "count": o.count, "percentage": o.percentage}
            for o in results.options
        ],
        "by_state": [
            {
                "state": sr.segment_value,
                "responses": sr.total_responses,
                "has_enough_data": sr.has_enough_data,
                "options": [{"option": o.option, "percentage": o.percentage} for o in sr.options]
            }
            for sr in state_results
        ],
        "by_age": [
            {
                "age_range": ar.segment_value,
                "responses": ar.total_responses,
                "has_enough_data": ar.has_enough_data,
                "options": [{"option": o.option, "percentage": o.percentage} for o in ar.options]
            }
            for ar in age_results
        ],
        "by_gender": [
            {
                "gender": gr.segment_value,
                "responses": gr.total_responses,
                "has_enough_data": gr.has_enough_data,
                "options": [{"option": o.option, "percentage": o.percentage} for o in gr.options]
            }
            for gr in gender_results
        ]
    }


@router.get("/polls/metrics")
async def get_poll_metrics():
    """Get overall poll metrics."""
    return analytics_service.get_poll_metrics()
