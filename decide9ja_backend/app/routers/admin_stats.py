"""
Admin Stats API Router
======================
Provides data for the admin dashboard:
- Pipeline health & last-run stats
- User activity metrics
- Learning system stats
- Database record counts
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin Stats"])


@router.get("/stats/overview")
async def get_overview_stats() -> Dict[str, Any]:
    """
    Get high-level platform stats for the admin dashboard.
    """
    from app.database import SessionLocal, Document, Interaction, Politician, Budget, Bill, Transaction, Finding, NewsArticle

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        stats = {
            "timestamp": now.isoformat(),
            "database": {
                "documents": db.query(Document).count(),
                "politicians": db.query(Politician).count(),
                "bills": db.query(Bill).count(),
                "budgets": db.query(Budget).count(),
                "transactions": db.query(Transaction).count(),
                "findings": db.query(Finding).count(),
                "news_articles": db.query(NewsArticle).count(),
                "interactions": db.query(Interaction).count(),
            },
            "activity": {
                "queries_24h": db.query(Interaction).filter(Interaction.created_at >= last_24h).count(),
                "queries_7d": db.query(Interaction).filter(Interaction.created_at >= last_7d).count(),
                "unique_users_7d": _count_unique_users(db, last_7d),
            },
            "content_freshness": {
                "latest_news": _get_latest_timestamp(db, NewsArticle, "scraped_at"),
                "latest_bill": _get_latest_timestamp(db, Bill, "last_action_date"),
                "latest_transaction": _get_latest_timestamp(db, Transaction, "created_at"),
                "latest_interaction": _get_latest_timestamp(db, Interaction, "created_at"),
            }
        }
        return stats
    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        return {"error": str(e)}
    finally:
        db.close()


@router.get("/stats/pipelines")
async def get_pipeline_stats() -> Dict[str, Any]:
    """Get pipeline health and last-run stats."""
    try:
        from app.scheduler_unified import get_scheduler_status
        status = get_scheduler_status()

        # Convert metrics to a jobs-like format for the dashboard
        jobs = []
        for job_id, metrics in (status.get("metrics") or {}).items():
            jobs.append({
                "id": job_id,
                "name": job_id.replace("_", " ").title(),
                "last_run": metrics.get("last_run"),
                "last_status": metrics.get("last_status"),
                "total_runs": metrics.get("total_runs", 0),
                "successful": metrics.get("successful_runs", 0),
                "failed": metrics.get("failed_runs", 0),
                "next_run": None,  # Not tracked at module level
            })

        status["jobs"] = jobs
        return {"pipelines": status}
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats/learning")
async def get_learning_stats() -> Dict[str, Any]:
    """Get learning system stats (feedback, knowledge gaps, patterns)."""
    try:
        from app.services.learning_service import get_learning_service
        service = get_learning_service()
        stats = service.get_learning_stats()
        return {"learning": stats}
    except Exception as e:
        return {"learning": {"error": str(e)}}


@router.get("/stats/top-queries")
async def get_top_queries(days: int = 7, limit: int = 20) -> Dict[str, Any]:
    """Get most common queries in the last N days."""
    from app.database import SessionLocal, Interaction
    from sqlalchemy import func

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.query(Interaction.query, func.count(Interaction.id).label("count"))
            .filter(Interaction.created_at >= cutoff)
            .group_by(Interaction.query)
            .order_by(func.count(Interaction.id).desc())
            .limit(limit)
            .all()
        )
        return {
            "period_days": days,
            "top_queries": [{"query": q, "count": c} for q, c in rows]
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@router.get("/stats/activity-timeline")
async def get_activity_timeline(days: int = 30) -> Dict[str, Any]:
    """Get daily query count for the last N days."""
    from app.database import SessionLocal, Interaction
    from sqlalchemy import func, cast, Date

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.query(
                cast(Interaction.created_at, Date).label("date"),
                func.count(Interaction.id).label("count")
            )
            .filter(Interaction.created_at >= cutoff)
            .group_by(cast(Interaction.created_at, Date))
            .order_by(cast(Interaction.created_at, Date))
            .all()
        )
        return {
            "period_days": days,
            "timeline": [{"date": str(d), "queries": c} for d, c in rows]
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@router.get("/stats/bills-summary")
async def get_bills_summary() -> Dict[str, Any]:
    """Get summary of tracked legislation."""
    from app.database import SessionLocal, Bill
    from sqlalchemy import func

    db = SessionLocal()
    try:
        total = db.query(Bill).count()
        by_status = (
            db.query(Bill.status, func.count(Bill.id))
            .group_by(Bill.status)
            .all()
        )
        by_category = (
            db.query(Bill.category, func.count(Bill.id))
            .group_by(Bill.category)
            .order_by(func.count(Bill.id).desc())
            .limit(10)
            .all()
        )
        by_chamber = (
            db.query(Bill.chamber, func.count(Bill.id))
            .group_by(Bill.chamber)
            .all()
        )
        return {
            "total_bills": total,
            "by_status": {s: c for s, c in by_status if s},
            "by_category": {cat: c for cat, c in by_category if cat},
            "by_chamber": {ch: c for ch, c in by_chamber if ch},
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


# ─── Helpers ─────────────────────────────────────────────────────────

def _count_unique_users(db, since):
    from app.database import Interaction
    from sqlalchemy import func
    try:
        result = db.query(func.count(func.distinct(Interaction.user_id))).filter(
            Interaction.created_at >= since,
            Interaction.user_id.isnot(None)
        ).scalar()
        return result or 0
    except:
        return 0


def _get_latest_timestamp(db, model, field_name):
    from sqlalchemy import func
    try:
        col = getattr(model, field_name)
        result = db.query(func.max(col)).scalar()
        return result.isoformat() if result else None
    except:
        return None
