"""
Scheduler Status Router for Decide9ja.

Provides API endpoints to monitor scheduler health and job metrics.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Dict, Any

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """
    Get current scheduler status and job metrics.

    Returns:
        - metrics: Per-job execution statistics
        - health: Overall scheduler health
        - timestamp: Current server time
    """
    try:
        from app.scheduler_unified import get_scheduler_status as get_status
        status = get_status()

        # Calculate health score
        metrics = status.get("metrics", {})
        total_jobs = len(metrics)
        healthy_jobs = sum(
            1 for m in metrics.values()
            if m.get("last_status") in ["success", "fallback", None]
        )

        health_score = (healthy_jobs / total_jobs * 100) if total_jobs > 0 else 100

        return {
            "health": {
                "status": "healthy" if health_score >= 80 else "degraded" if health_score >= 50 else "unhealthy",
                "score": health_score,
                "total_jobs": total_jobs,
                "healthy_jobs": healthy_jobs,
            },
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        # Scheduler module not available
        return {
            "health": {
                "status": "unknown",
                "message": "Scheduler module not loaded",
            },
            "metrics": {},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scheduler status: {str(e)}"
        )


@router.get("/jobs")
async def list_jobs() -> Dict[str, Any]:
    """
    List all scheduled jobs and their configurations.

    Returns:
        - jobs: List of job configurations
    """
    jobs = [
        {
            "id": "news_scraper",
            "name": "News Scraper",
            "description": "Scrape Nigerian political news from all sources",
            "frequency": "Every 1 hour",
            "has_fallback": True,
            "fallback_description": "RSS-only collection if scraping fails",
        },
        {
            "id": "news_indexer",
            "name": "News Indexer",
            "description": "Generate embeddings for RAG retrieval",
            "frequency": "Every 2 hours",
            "has_fallback": True,
            "fallback_description": "Mark articles for deferred indexing",
        },
        {
            "id": "issue_extractor",
            "name": "Issue Extractor",
            "description": "Extract political issues from news using Claude AI",
            "frequency": "Every 3 hours",
            "has_fallback": True,
            "fallback_description": "Keyword-based issue detection",
        },
        {
            "id": "dossier_generator",
            "name": "Dossier Generator",
            "description": "Regenerate issue dossiers for RAG",
            "frequency": "Every 4 hours",
            "has_fallback": True,
            "fallback_description": "Skip and retry next cycle",
        },
        {
            "id": "card_generator",
            "name": "Card Generator",
            "description": "Regenerate politician cards for RAG",
            "frequency": "Daily at 3:00 AM",
            "has_fallback": True,
            "fallback_description": "Use cached politician cards",
        },
        {
            "id": "news_cleanup",
            "name": "News Cleanup",
            "description": "Remove news articles older than 30 days",
            "frequency": "Daily at 3:30 AM",
            "has_fallback": False,
            "fallback_description": None,
        },
        {
            "id": "health_check",
            "name": "Health Check",
            "description": "Log scheduler health and metrics",
            "frequency": "Every 15 minutes",
            "has_fallback": False,
            "fallback_description": None,
        },
    ]

    return {
        "jobs": jobs,
        "total": len(jobs),
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str) -> Dict[str, Any]:
    """
    Manually trigger a specific job (admin only).

    Args:
        job_id: The ID of the job to trigger

    Returns:
        - result: Job execution result
    """
    try:
        from app.scheduler_unified import run_job_once

        valid_jobs = ["news", "index", "issues", "dossiers", "cards", "cleanup", "health"]

        if job_id not in valid_jobs:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid job_id. Must be one of: {', '.join(valid_jobs)}"
            )

        result = run_job_once(job_id)

        return {
            "job_id": job_id,
            "triggered": True,
            "result": result.to_dict() if hasattr(result, 'to_dict') else result,
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Scheduler module not available"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger job: {str(e)}"
        )
