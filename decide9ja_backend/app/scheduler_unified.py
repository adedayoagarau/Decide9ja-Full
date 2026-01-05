"""
Unified Scheduler for Decide9ja Background Jobs.

This module consolidates all scheduled tasks with:
- Robust error handling with fallbacks
- Retry logic with exponential backoff
- Job overlap prevention
- Health monitoring
- Proper async/sync handling

Usage:
    python -m app.scheduler_unified          # Run scheduler
    python -m app.scheduler_unified --once   # Run all jobs once
    python -m app.scheduler_unified --job news  # Run specific job

Jobs:
    - news_scraper: Scrape Nigerian political news (every 1 hour)
    - news_indexer: Generate embeddings for RAG (every 2 hours)
    - issue_extractor: Extract issues from news (every 3 hours)
    - dossier_generator: Regenerate issue dossiers (every 4 hours)
    - card_generator: Regenerate politician cards (daily at 3 AM)
    - news_cleanup: Remove old news articles (daily at 3 AM)
    - health_check: Log scheduler health (every 15 minutes)
"""

import os
import sys
import time
import json
import logging
import functools
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field, asdict
from enum import Enum

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Job Status Tracking
# =============================================================================

class JobStatus(Enum):
    """Job execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    FALLBACK = "fallback"


@dataclass
class JobResult:
    """Result of a job execution."""
    job_id: str
    status: JobStatus
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    retry_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        result = asdict(self)
        result['status'] = self.status.value
        return result


@dataclass
class JobMetrics:
    """Metrics for job monitoring."""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    fallback_runs: int = 0
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    average_duration: float = 0.0


# Global metrics storage (in production, use Redis or database)
_job_metrics: Dict[str, JobMetrics] = {}


def get_job_metrics(job_id: str) -> JobMetrics:
    """Get metrics for a specific job."""
    if job_id not in _job_metrics:
        _job_metrics[job_id] = JobMetrics()
    return _job_metrics[job_id]


def update_job_metrics(result: JobResult):
    """Update metrics after job execution."""
    metrics = get_job_metrics(result.job_id)
    metrics.total_runs += 1
    metrics.last_run = result.timestamp
    metrics.last_status = result.status.value

    if result.status == JobStatus.SUCCESS:
        metrics.successful_runs += 1
    elif result.status == JobStatus.FAILED:
        metrics.failed_runs += 1
        metrics.last_error = result.message
    elif result.status == JobStatus.FALLBACK:
        metrics.fallback_runs += 1

    # Update average duration
    if metrics.total_runs > 1:
        metrics.average_duration = (
            (metrics.average_duration * (metrics.total_runs - 1) + result.duration_seconds)
            / metrics.total_runs
        )
    else:
        metrics.average_duration = result.duration_seconds


# =============================================================================
# Retry Decorator with Exponential Backoff
# =============================================================================

def with_retry(
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
    fallback_func: Optional[Callable] = None
):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exceptions: Tuple of exceptions to catch and retry
        fallback_func: Optional fallback function if all retries fail
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> JobResult:
            job_id = func.__name__
            start_time = time.time()
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time

                    job_result = JobResult(
                        job_id=job_id,
                        status=JobStatus.SUCCESS,
                        message=f"Completed successfully",
                        data=result if isinstance(result, dict) else {"result": result},
                        duration_seconds=duration,
                        retry_count=attempt
                    )
                    update_job_metrics(job_result)
                    return job_result

                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"Job {job_id} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Job {job_id} failed after {max_retries + 1} attempts: {e}"
                        )

            # All retries exhausted - try fallback
            duration = time.time() - start_time

            if fallback_func is not None:
                try:
                    logger.info(f"Job {job_id}: Executing fallback function...")
                    fallback_result = fallback_func(*args, **kwargs)

                    job_result = JobResult(
                        job_id=job_id,
                        status=JobStatus.FALLBACK,
                        message=f"Fallback executed after {max_retries + 1} failures",
                        data=fallback_result if isinstance(fallback_result, dict) else {"result": fallback_result},
                        duration_seconds=duration,
                        retry_count=max_retries + 1
                    )
                    update_job_metrics(job_result)
                    return job_result

                except Exception as fallback_error:
                    logger.error(f"Job {job_id}: Fallback also failed: {fallback_error}")

            # Complete failure
            job_result = JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                message=str(last_exception),
                duration_seconds=duration,
                retry_count=max_retries + 1
            )
            update_job_metrics(job_result)
            return job_result

        return wrapper
    return decorator


# =============================================================================
# Fallback Functions
# =============================================================================

def fallback_news_scraper():
    """Fallback when news scraper fails - try RSS feeds only."""
    logger.info("Fallback: Attempting RSS-only news collection...")
    try:
        import feedparser

        RSS_FEEDS = [
            ("Premium Times", "https://www.premiumtimesng.com/feed"),
            ("Punch", "https://punchng.com/feed/"),
            ("Vanguard", "https://www.vanguardngr.com/feed/"),
        ]

        articles = []
        for name, url in RSS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    articles.append({
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "source": name,
                        "published": entry.get("published", ""),
                    })
            except Exception as e:
                logger.warning(f"RSS fallback failed for {name}: {e}")
                continue

        return {"fallback_articles": len(articles), "source": "rss_only"}
    except Exception as e:
        logger.error(f"RSS fallback failed completely: {e}")
        return {"fallback_articles": 0, "error": str(e)}


def fallback_news_indexer():
    """Fallback when indexer fails - mark articles for later processing."""
    logger.info("Fallback: Marking articles for deferred indexing...")
    try:
        from app.database import SessionLocal, NewsArticle

        db = SessionLocal()
        try:
            # Just count unindexed articles for reporting
            count = db.query(NewsArticle).filter(
                NewsArticle.is_indexed == False
            ).count()
            return {"deferred_articles": count, "action": "marked_for_later"}
        finally:
            db.close()
    except Exception as e:
        return {"error": str(e), "action": "none"}


def fallback_issue_extractor():
    """Fallback when issue extraction fails - use keyword-based extraction."""
    logger.info("Fallback: Using keyword-based issue detection...")
    try:
        from app.database import SessionLocal, NewsArticle

        ISSUE_KEYWORDS = {
            "power": ["blackout", "grid collapse", "nerc", "electricity", "power outage"],
            "security": ["kidnap", "bandit", "terrorist", "attack", "robbery"],
            "economy": ["naira", "inflation", "fuel", "subsidy", "price increase"],
            "health": ["hospital", "disease", "outbreak", "health crisis"],
            "infrastructure": ["road", "bridge", "flood", "collapse"],
        }

        db = SessionLocal()
        try:
            articles = db.query(NewsArticle).filter(
                NewsArticle.is_processed == False
            ).limit(20).all()

            detected_issues = []
            for article in articles:
                text = f"{article.title} {article.excerpt or ''}".lower()
                for domain, keywords in ISSUE_KEYWORDS.items():
                    if any(kw in text for kw in keywords):
                        detected_issues.append({
                            "domain": domain,
                            "article_id": article.article_id,
                            "title": article.title
                        })
                        break

                # Mark as processed even in fallback
                article.is_processed = True

            db.commit()
            return {"keyword_detected_issues": len(detected_issues), "method": "keyword_fallback"}
        finally:
            db.close()
    except Exception as e:
        return {"error": str(e), "method": "failed"}


def fallback_dossier_generator():
    """Fallback when dossier generation fails - skip but log."""
    logger.info("Fallback: Dossier generation skipped, will retry next cycle...")
    return {"action": "skipped", "reason": "will_retry_next_cycle"}


def fallback_card_generator():
    """Fallback when card generation fails - use cached cards."""
    logger.info("Fallback: Using existing cached politician cards...")
    try:
        from app.database import SessionLocal, Document

        db = SessionLocal()
        try:
            # Count existing cards
            count = db.query(Document).filter(
                Document.doc_type == "politician_card"
            ).count()
            return {"cached_cards": count, "action": "using_cached"}
        finally:
            db.close()
    except Exception as e:
        return {"error": str(e), "action": "none"}


# =============================================================================
# Job Implementations
# =============================================================================

@with_retry(max_retries=3, base_delay=5.0, fallback_func=fallback_news_scraper)
def run_news_scraper():
    """
    Scrape news from all Nigerian political news sources.
    Frequency: Every 1 hour
    """
    logger.info("🗞️ Starting news scraper job...")

    from app.services.news_pipeline import run_news_pipeline
    result = run_news_pipeline()

    logger.info(f"✅ News scraper complete: {result}")
    return result


@with_retry(max_retries=3, base_delay=5.0, fallback_func=fallback_news_indexer)
def run_news_indexer():
    """
    Generate embeddings for unindexed news articles.
    Frequency: Every 2 hours
    """
    logger.info("🔍 Starting news indexer job...")

    from app.services.news_pipeline import index_articles_for_rag
    count = index_articles_for_rag(batch_size=50)

    logger.info(f"✅ News indexer complete: {count} articles indexed")
    return {"indexed": count}


@with_retry(max_retries=2, base_delay=10.0, fallback_func=fallback_issue_extractor)
def run_issue_extractor():
    """
    Extract political issues from unprocessed news articles using Claude.
    Frequency: Every 3 hours
    """
    logger.info("🔍 Starting issue extractor job...")

    from app.services.issue_pipeline import run_issue_extraction_pipeline
    issues = run_issue_extraction_pipeline(limit=50)

    logger.info(f"✅ Issue extractor complete: {len(issues)} issues extracted")
    return {"issues_extracted": len(issues)}


@with_retry(max_retries=2, base_delay=5.0, fallback_func=fallback_dossier_generator)
def run_dossier_generator():
    """
    Regenerate issue dossiers for RAG retrieval.
    Frequency: Every 4 hours
    """
    logger.info("📋 Starting dossier generator job...")

    from app.services.dossier_generator import generate_issue_dossiers, save_dossiers_to_rag

    dossiers = generate_issue_dossiers()
    if dossiers:
        save_dossiers_to_rag(dossiers)

    logger.info(f"✅ Dossier generator complete: {len(dossiers)} dossiers generated")
    return {"dossiers_generated": len(dossiers)}


@with_retry(max_retries=2, base_delay=5.0, fallback_func=fallback_card_generator)
def run_card_generator():
    """
    Regenerate politician cards for RAG retrieval.
    Frequency: Daily at 3 AM
    """
    logger.info("🃏 Starting card generator job...")

    from app.services.card_generator import generate_all_politician_cards, save_cards_to_rag

    cards = generate_all_politician_cards()
    if cards:
        count = save_cards_to_rag(cards)
    else:
        count = 0

    logger.info(f"✅ Card generator complete: {count} cards generated")
    return {"cards_generated": count}


@with_retry(max_retries=1, base_delay=2.0)
def run_news_cleanup():
    """
    Remove news articles older than 30 days.
    Frequency: Daily at 3 AM
    """
    logger.info("🧹 Starting news cleanup job...")

    from app.database import SessionLocal, NewsArticle

    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=30)
        deleted = db.query(NewsArticle).filter(
            NewsArticle.scraped_at < cutoff
        ).delete()
        db.commit()

        logger.info(f"✅ News cleanup complete: {deleted} old articles deleted")
        return {"deleted": deleted}
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@with_retry(max_retries=2, base_delay=5.0)
def run_notification_processor():
    """
    Process pending notifications in the queue.
    Frequency: Every 5 minutes
    """
    logger.info("📬 Starting notification processor job...")

    try:
        from app.services.notification_service import get_notification_service
        from app.utils.async_helpers import run_async_safely

        service = get_notification_service()
        result = run_async_safely(service.process_pending_notifications(batch_size=50))

        logger.info(f"✅ Notification processor complete: {result}")
        return result

    except ImportError:
        logger.warning("Notification service not available, skipping")
        return {"skipped": True, "reason": "service_not_available"}
    except Exception as e:
        logger.error(f"Notification processor error: {e}")
        raise


@with_retry(max_retries=2, base_delay=10.0)
def run_daily_digest():
    """
    Send daily digest notifications to all subscribed users.
    Frequency: Daily at 7 AM
    """
    logger.info("📊 Starting daily digest job...")

    try:
        from app.services.notification_service import get_notification_service
        from app.utils.async_helpers import run_async_safely

        service = get_notification_service()
        result = run_async_safely(service.send_all_daily_digests())

        logger.info(f"✅ Daily digest complete: {result}")
        return result

    except ImportError:
        logger.warning("Notification service not available, skipping")
        return {"skipped": True, "reason": "service_not_available"}
    except Exception as e:
        logger.error(f"Daily digest error: {e}")
        raise


def run_health_check():
    """
    Log scheduler health and job metrics.
    Frequency: Every 15 minutes
    """
    logger.info(f"💓 Scheduler heartbeat - {datetime.now().isoformat()}")

    # Log metrics summary
    metrics_summary = {}
    for job_id, metrics in _job_metrics.items():
        metrics_summary[job_id] = {
            "total": metrics.total_runs,
            "success": metrics.successful_runs,
            "failed": metrics.failed_runs,
            "fallback": metrics.fallback_runs,
            "last_status": metrics.last_status,
            "avg_duration": f"{metrics.average_duration:.2f}s"
        }

    if metrics_summary:
        logger.info(f"📊 Job Metrics: {json.dumps(metrics_summary, indent=2)}")

    return JobResult(
        job_id="health_check",
        status=JobStatus.SUCCESS,
        message="Heartbeat OK",
        data={"metrics": metrics_summary}
    )


# =============================================================================
# Scheduler Event Listeners
# =============================================================================

def job_error_listener(event):
    """Handle job execution errors."""
    logger.error(f"Job {event.job_id} raised an error: {event.exception}")


def job_executed_listener(event):
    """Log successful job execution."""
    logger.debug(f"Job {event.job_id} executed successfully")


def job_missed_listener(event):
    """Handle missed job executions."""
    logger.warning(f"Job {event.job_id} missed scheduled execution time")


# =============================================================================
# Scheduler Factory
# =============================================================================

def create_scheduler() -> BackgroundScheduler:
    """
    Create and configure the unified scheduler.

    All jobs have:
    - max_instances=1 to prevent overlap
    - misfire_grace_time for handling delays
    - coalesce=True to combine missed runs
    """
    scheduler = BackgroundScheduler(
        timezone="Africa/Lagos",
        job_defaults={
            'coalesce': True,           # Combine multiple missed runs into one
            'max_instances': 1,         # Prevent job overlap
            'misfire_grace_time': 300,  # 5 minute grace period
        }
    )

    # Add event listeners
    scheduler.add_listener(job_error_listener, EVENT_JOB_ERROR)
    scheduler.add_listener(job_executed_listener, EVENT_JOB_EXECUTED)
    scheduler.add_listener(job_missed_listener, EVENT_JOB_MISSED)

    # === News Scraping - Every 1 hour ===
    scheduler.add_job(
        run_news_scraper,
        IntervalTrigger(hours=1),
        id="news_scraper",
        name="Scrape Nigerian political news",
        replace_existing=True
    )

    # === News Indexing - Every 2 hours ===
    scheduler.add_job(
        run_news_indexer,
        IntervalTrigger(hours=2),
        id="news_indexer",
        name="Index news articles for RAG",
        replace_existing=True
    )

    # === Issue Extraction - Every 3 hours ===
    scheduler.add_job(
        run_issue_extractor,
        IntervalTrigger(hours=3),
        id="issue_extractor",
        name="Extract issues from news articles",
        replace_existing=True
    )

    # === Dossier Generation - Every 4 hours ===
    scheduler.add_job(
        run_dossier_generator,
        IntervalTrigger(hours=4),
        id="dossier_generator",
        name="Regenerate issue dossiers",
        replace_existing=True
    )

    # === Card Generation - Daily at 3 AM ===
    scheduler.add_job(
        run_card_generator,
        CronTrigger(hour=3, minute=0),
        id="card_generator",
        name="Regenerate politician cards",
        replace_existing=True
    )

    # === News Cleanup - Daily at 3 AM ===
    scheduler.add_job(
        run_news_cleanup,
        CronTrigger(hour=3, minute=30),  # 30 min after card gen
        id="news_cleanup",
        name="Clean up old news articles",
        replace_existing=True
    )

    # === Health Check - Every 15 minutes ===
    scheduler.add_job(
        run_health_check,
        IntervalTrigger(minutes=15),
        id="health_check",
        name="Scheduler health check",
        replace_existing=True
    )

    # === Notification Queue Processing - Every 5 minutes ===
    scheduler.add_job(
        run_notification_processor,
        IntervalTrigger(minutes=5),
        id="notification_processor",
        name="Process notification queue",
        replace_existing=True
    )

    # === Daily Digest - Every day at 7 AM ===
    scheduler.add_job(
        run_daily_digest,
        CronTrigger(hour=7, minute=0),
        id="daily_digest",
        name="Send daily digest notifications",
        replace_existing=True
    )

    return scheduler


def start_scheduler():
    """Start the unified scheduler."""
    logger.info("=" * 60)
    logger.info("🚀 Starting Decide9ja Unified Scheduler")
    logger.info("=" * 60)

    scheduler = create_scheduler()
    scheduler.start()

    logger.info("")
    logger.info("📅 Scheduled Jobs:")
    logger.info("-" * 60)
    for job in scheduler.get_jobs():
        logger.info(f"  • {job.name}")
        logger.info(f"    ID: {job.id}")
        logger.info(f"    Trigger: {job.trigger}")
        logger.info(f"    Next run: {job.next_run_time}")
        logger.info("")
    logger.info("-" * 60)

    # Run initial health check
    run_health_check()

    return scheduler


def run_job_once(job_name: str):
    """Run a specific job once."""
    jobs = {
        "news": run_news_scraper,
        "index": run_news_indexer,
        "issues": run_issue_extractor,
        "dossiers": run_dossier_generator,
        "cards": run_card_generator,
        "cleanup": run_news_cleanup,
        "health": run_health_check,
        "notifications": run_notification_processor,
        "digest": run_daily_digest,
    }

    if job_name not in jobs:
        print(f"Unknown job: {job_name}")
        print(f"Available jobs: {', '.join(jobs.keys())}")
        return

    print(f"Running job: {job_name}")
    result = jobs[job_name]()
    print(f"Result: {result}")
    return result


def run_all_jobs_once():
    """Run all jobs once (for testing)."""
    print("=" * 60)
    print("Running all jobs once...")
    print("=" * 60)

    jobs = [
        ("News Scraper", run_news_scraper),
        ("News Indexer", run_news_indexer),
        ("Issue Extractor", run_issue_extractor),
        ("Dossier Generator", run_dossier_generator),
        ("Card Generator", run_card_generator),
        ("News Cleanup", run_news_cleanup),
    ]

    results = {}
    for name, func in jobs:
        print(f"\n▶ Running {name}...")
        try:
            result = func()
            results[name] = result
            print(f"  ✅ {name}: {result}")
        except Exception as e:
            results[name] = {"error": str(e)}
            print(f"  ❌ {name}: {e}")

    print("\n" + "=" * 60)
    print("Summary:")
    for name, result in results.items():
        status = "✅" if isinstance(result, JobResult) and result.status == JobStatus.SUCCESS else "⚠️"
        print(f"  {status} {name}")
    print("=" * 60)

    return results


# =============================================================================
# API for External Access (e.g., from FastAPI admin endpoints)
# =============================================================================

def get_scheduler_status() -> dict:
    """Get current scheduler status for monitoring."""
    return {
        "metrics": {
            job_id: {
                "total_runs": m.total_runs,
                "successful_runs": m.successful_runs,
                "failed_runs": m.failed_runs,
                "fallback_runs": m.fallback_runs,
                "last_run": m.last_run,
                "last_status": m.last_status,
                "last_error": m.last_error,
                "average_duration_seconds": m.average_duration,
            }
            for job_id, m in _job_metrics.items()
        },
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Decide9ja Unified Scheduler")
    parser.add_argument("--once", action="store_true", help="Run all jobs once and exit")
    parser.add_argument("--job", type=str, help="Run specific job (news, index, issues, dossiers, cards, cleanup, health)")
    parser.add_argument("--status", action="store_true", help="Show scheduler status")

    args = parser.parse_args()

    if args.status:
        status = get_scheduler_status()
        print(json.dumps(status, indent=2))
    elif args.job:
        run_job_once(args.job)
    elif args.once:
        run_all_jobs_once()
    else:
        scheduler = start_scheduler()

        try:
            logger.info("Scheduler running. Press Ctrl+C to stop.")
            while True:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler stopped.")
