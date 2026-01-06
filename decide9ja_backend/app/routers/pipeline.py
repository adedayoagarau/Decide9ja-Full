"""
Data Pipeline & Scraping Router
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel

from app.auth.api_keys import APIKey, require_api_key, get_api_key
from app.auth.rbac import Permission, check_permission
from app.services.data_pipeline import (
    DataPipelineService,
    PipelineScheduler,
    DataSource,
    PipelineStatus
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["data-pipeline"])


# =====================
# Pydantic Models
# =====================

class TriggerPipelineRequest(BaseModel):
    """Request to trigger a pipeline."""
    pipeline_name: str


class NewsSearchRequest(BaseModel):
    """Request to search news."""
    keyword: Optional[str] = None
    source: Optional[str] = None
    limit: int = 20


# =====================
# News Endpoints
# =====================

@router.get("/news")
async def get_news(
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = None,
    keyword: Optional[str] = None
):
    """
    Get recently scraped news articles.
    No authentication required for read access.
    """
    source_enum = None
    if source:
        try:
            source_enum = DataSource(source)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source: {source}. Valid sources: {[s.value for s in DataSource]}"
            )

    news = DataPipelineService.get_recent_news(
        limit=limit,
        source=source_enum,
        keyword=keyword
    )

    return {
        "total": len(news),
        "items": news
    }


@router.get("/news/sources")
async def get_news_sources():
    """Get list of available news sources."""
    sources = []
    for source, config in DataPipelineService.NEWS_SOURCES.items():
        sources.append({
            "code": source.value,
            "name": config["name"],
            "url": config["base_url"]
        })

    return {"sources": sources}


@router.get("/news/{source}")
async def get_news_by_source(
    source: str,
    limit: int = Query(20, ge=1, le=50)
):
    """Get news from a specific source."""
    try:
        source_enum = DataSource(source)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source: {source}"
        )

    news = DataPipelineService.get_recent_news(
        limit=limit,
        source=source_enum
    )

    return {
        "source": source,
        "total": len(news),
        "items": news
    }


# =====================
# Pipeline Management (Admin)
# =====================

@router.post("/run/news")
async def run_news_pipeline(
    background_tasks: BackgroundTasks,
    api_key: APIKey = Depends(require_api_key)
):
    """
    Trigger the news scraping pipeline.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    # Run in background
    async def run_pipeline():
        try:
            await DataPipelineService.run_news_pipeline()
        except Exception as e:
            logger.error(f"Background news pipeline failed: {e}")

    background_tasks.add_task(run_pipeline)

    return {
        "success": True,
        "message": "News pipeline triggered. Check /pipeline/runs for status."
    }


@router.post("/run/elections")
async def run_elections_pipeline(
    background_tasks: BackgroundTasks,
    api_key: APIKey = Depends(require_api_key)
):
    """
    Trigger the elections data pipeline.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    async def run_pipeline():
        try:
            await DataPipelineService.scrape_inec_elections()
        except Exception as e:
            logger.error(f"Background elections pipeline failed: {e}")

    background_tasks.add_task(run_pipeline)

    return {
        "success": True,
        "message": "Elections pipeline triggered."
    }


@router.get("/runs")
async def get_pipeline_runs(
    pipeline_name: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get pipeline execution history.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_LOGS):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    runs = DataPipelineService.get_pipeline_runs(
        pipeline_name=pipeline_name,
        limit=limit
    )

    return {
        "total": len(runs),
        "runs": runs
    }


@router.get("/runs/{run_id}")
async def get_pipeline_run(
    run_id: str,
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get details of a specific pipeline run.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_LOGS):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    runs = DataPipelineService.get_pipeline_runs(limit=1000)
    run = next((r for r in runs if r["run_id"] == run_id), None)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return run


@router.get("/stats")
async def get_pipeline_stats(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get pipeline statistics.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.ANALYTICS_READ):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return DataPipelineService.get_pipeline_stats()


# =====================
# Scheduler Management (Admin)
# =====================

@router.get("/scheduler/status")
async def get_scheduler_status(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get scheduler status.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return PipelineScheduler.get_schedule_status()


@router.post("/scheduler/start")
async def start_scheduler(
    background_tasks: BackgroundTasks,
    api_key: APIKey = Depends(require_api_key)
):
    """
    Start the pipeline scheduler.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    # Schedule default pipelines
    await PipelineScheduler.schedule_pipeline(
        "news_scraper",
        DataPipelineService.run_news_pipeline,
        interval_minutes=60
    )

    # Start scheduler in background
    background_tasks.add_task(PipelineScheduler.start)

    return {
        "success": True,
        "message": "Scheduler started"
    }


@router.post("/scheduler/stop")
async def stop_scheduler(
    api_key: APIKey = Depends(require_api_key)
):
    """
    Stop the pipeline scheduler.
    Requires admin role.
    """
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    PipelineScheduler.stop()

    return {
        "success": True,
        "message": "Scheduler stopped"
    }


# =====================
# Article Fetch Endpoint
# =====================

@router.post("/fetch-article")
async def fetch_article_content(
    url: str = Query(..., description="Article URL to fetch"),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Fetch full content of a news article.
    Requires API access.
    """
    # Validate URL domain
    from urllib.parse import urlparse
    parsed = urlparse(url)
    allowed_domains = [
        "punchng.com",
        "guardian.ng",
        "vanguardngr.com",
        "premiumtimesng.com",
        "channelstv.com",
        "saharareporters.com",
        "thistday.com"
    ]

    if not any(domain in parsed.netloc for domain in allowed_domains):
        raise HTTPException(
            status_code=400,
            detail="URL domain not in allowed list for scraping"
        )

    content = await DataPipelineService.fetch_article_content(url)

    if not content:
        raise HTTPException(
            status_code=404,
            detail="Could not fetch article content"
        )

    return {
        "url": url,
        "content": content,
        "word_count": len(content.split())
    }
