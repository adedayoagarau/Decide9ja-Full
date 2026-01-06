"""
Analytics Dashboard Router
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.api_keys import APIKey, require_api_key
from app.auth.rbac import Permission, check_permission
from app.services.dashboard import AnalyticsDashboardService, TimeRange

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def require_analytics_permission(api_key: APIKey = Depends(require_api_key)):
    """Dependency to check analytics permission."""
    if not check_permission(api_key.role, Permission.ANALYTICS_READ):
        raise HTTPException(
            status_code=403,
            detail="Analytics read permission required"
        )
    return api_key


# =====================
# Overview Endpoints
# =====================

@router.get("/overview")
async def get_dashboard_overview(
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get high-level dashboard overview metrics.
    Includes total users, messages, issues, and broadcasts.
    """
    metrics = await AnalyticsDashboardService.get_overview_metrics(db)
    return metrics.model_dump()


@router.get("/full")
async def get_full_dashboard(
    time_range: str = Query("7d", description="Time range: today, yesterday, 7d, 30d, 90d, month, year, all"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get complete dashboard data in one call.
    Includes all metrics, trends, and analytics.
    """
    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time range. Valid options: {[t.value for t in TimeRange]}"
        )

    return await AnalyticsDashboardService.get_full_dashboard(range_enum, db)


# =====================
# Trend Endpoints
# =====================

@router.get("/trends/messages")
async def get_message_trends(
    time_range: str = Query("7d"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get message volume trends over time.
    Returns data points for charting.
    """
    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        range_enum = TimeRange.LAST_7_DAYS

    return await AnalyticsDashboardService.get_message_trends(range_enum, db)


@router.get("/trends/response-times")
async def get_response_time_trends(
    time_range: str = Query("7d"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get response time analytics.
    Includes average, percentiles, and distribution.
    """
    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        range_enum = TimeRange.LAST_7_DAYS

    return await AnalyticsDashboardService.get_response_time_analytics(range_enum, db)


# =====================
# User Analytics
# =====================

@router.get("/users/top-queries")
async def get_top_queries(
    limit: int = Query(20, ge=1, le=100),
    time_range: str = Query("7d"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get most common user queries.
    Useful for understanding user needs.
    """
    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        range_enum = TimeRange.LAST_7_DAYS

    queries = await AnalyticsDashboardService.get_top_queries(limit, range_enum, db)

    return {
        "time_range": time_range,
        "limit": limit,
        "queries": queries
    }


@router.get("/users/geographic")
async def get_geographic_distribution(
    time_range: str = Query("30d"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get geographic distribution of users.
    Shows users by state and LGA.
    """
    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        range_enum = TimeRange.LAST_30_DAYS

    return await AnalyticsDashboardService.get_geographic_distribution(range_enum, db)


@router.get("/users/retention")
async def get_user_retention(
    weeks: int = Query(8, ge=1, le=52),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get user retention cohort data.
    Shows how many users return week over week.
    """
    return await AnalyticsDashboardService.get_user_retention(weeks, db)


# =====================
# Feature Analytics
# =====================

@router.get("/issues")
async def get_issue_analytics(
    time_range: str = Query("30d"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get community issue analytics.
    Includes status, categories, and resolution metrics.
    """
    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        range_enum = TimeRange.LAST_30_DAYS

    return await AnalyticsDashboardService.get_issue_analytics(range_enum, db)


@router.get("/broadcasts")
async def get_broadcast_analytics(
    time_range: str = Query("30d"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get broadcast campaign analytics.
    Includes delivery rates and campaign performance.
    """
    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        range_enum = TimeRange.LAST_30_DAYS

    return await AnalyticsDashboardService.get_broadcast_analytics(range_enum, db)


@router.get("/factchecks")
async def get_factcheck_analytics(
    time_range: str = Query("30d"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get fact-checking analytics.
    Includes verdict distribution and processing metrics.
    """
    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        range_enum = TimeRange.LAST_30_DAYS

    return await AnalyticsDashboardService.get_factcheck_analytics(range_enum, db)


# =====================
# Export Endpoints
# =====================

@router.get("/export")
async def export_dashboard(
    time_range: str = Query("30d"),
    format: str = Query("json", regex="^(json|csv)$"),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Export dashboard report.
    Requires analytics export permission.
    """
    if not check_permission(api_key.role, Permission.ANALYTICS_EXPORT):
        raise HTTPException(
            status_code=403,
            detail="Analytics export permission required"
        )

    try:
        range_enum = TimeRange(time_range)
    except ValueError:
        range_enum = TimeRange.LAST_30_DAYS

    report = await AnalyticsDashboardService.export_dashboard_report(
        range_enum,
        format,
        db
    )

    if format == "csv":
        return Response(
            content=report,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=dashboard-report-{time_range}.csv"
            }
        )

    return {
        "format": format,
        "time_range": time_range,
        "data": report if format == "json" else None
    }


# =====================
# Real-time Endpoints
# =====================

@router.get("/realtime/active-users")
async def get_realtime_active_users(
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get count of currently active users.
    Active defined as interaction within last 5 minutes.
    """
    from datetime import datetime, timedelta
    from app.database import User

    five_min_ago = datetime.utcnow() - timedelta(minutes=5)

    try:
        active_count = db.query(User).filter(
            User.last_active >= five_min_ago
        ).count()
    except Exception:
        active_count = 0

    return {
        "active_users": active_count,
        "timestamp": datetime.utcnow().isoformat(),
        "window_minutes": 5
    }


@router.get("/realtime/messages")
async def get_realtime_messages(
    minutes: int = Query(5, ge=1, le=60),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(require_analytics_permission)
):
    """
    Get messages from the last N minutes.
    Useful for real-time monitoring.
    """
    from datetime import datetime, timedelta
    from app.database import Interaction

    cutoff = datetime.utcnow() - timedelta(minutes=minutes)

    try:
        messages = db.query(Interaction).filter(
            Interaction.created_at >= cutoff
        ).order_by(Interaction.created_at.desc()).limit(100).all()

        message_data = [
            {
                "id": m.id,
                "query": m.query[:100] if m.query else "",
                "response_time_ms": m.response_time_ms,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    except Exception as e:
        logger.error(f"Error fetching realtime messages: {e}")
        message_data = []

    return {
        "window_minutes": minutes,
        "count": len(message_data),
        "messages": message_data
    }


# =====================
# Health & Status
# =====================

@router.get("/health")
async def dashboard_health_check(
    db: Session = Depends(get_db)
):
    """
    Check dashboard service health.
    No authentication required.
    """
    status = {
        "status": "healthy",
        "database_connected": False,
        "services": {}
    }

    # Check database
    try:
        from app.database import User
        db.query(User).limit(1).all()
        status["database_connected"] = True
    except Exception as e:
        status["database_connected"] = False
        status["status"] = "degraded"

    # Check services
    services = ["broadcast", "factcheck", "constituency", "localization"]
    for service in services:
        try:
            exec(f"from app.services.{service} import *")
            status["services"][service] = "available"
        except Exception:
            status["services"][service] = "unavailable"

    return status
