"""
DEPRECATED: This scheduler has been replaced by scheduler_unified.py

Please use the new unified scheduler instead:
    python -m app.scheduler_unified

This file is kept for backwards compatibility but will be removed in a future version.

Original description:
Scheduler for Decide9ja background jobs.
Runs news scraping, indexing, and other periodic tasks.
"""
import warnings
warnings.warn(
    "app.scheduler is deprecated. Use app.scheduler_unified instead.",
    DeprecationWarning,
    stacklevel=2
)
import os
import sys
import time
import logging
from datetime import datetime

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_news_scraper():
    """Scrape news from all sources and store in database."""
    logger.info("🗞️ Starting scheduled news scrape...")
    
    try:
        from app.services.news_pipeline import run_news_pipeline
        result = run_news_pipeline()
        logger.info(f"✅ News pipeline complete: {result}")
    except Exception as e:
        logger.error(f"❌ News pipeline failed: {e}")


def index_news_for_rag():
    """Generate embeddings for new articles."""
    logger.info("🔍 Starting news indexing...")
    
    try:
        from app.services.news_pipeline import index_articles_for_rag
        count = index_articles_for_rag(batch_size=30)
        logger.info(f"✅ Indexed {count} articles")
    except Exception as e:
        logger.error(f"❌ Indexing failed: {e}")


def cleanup_old_news():
    """Remove news older than 30 days."""
    logger.info("🧹 Cleaning up old news...")
    
    try:
        from datetime import timedelta
        from app.database import SessionLocal, NewsArticle
        
        db = SessionLocal()
        cutoff = datetime.now() - timedelta(days=30)
        
        deleted = db.query(NewsArticle).filter(
            NewsArticle.scraped_at < cutoff
        ).delete()
        
        db.commit()
        db.close()
        
        logger.info(f"✅ Deleted {deleted} old articles")
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")


def health_check():
    """Log scheduler health."""
    logger.info(f"💓 Scheduler heartbeat - {datetime.now().isoformat()}")


def extract_issues_from_news():
    """Run issue extraction on unprocessed news articles."""
    logger.info("🔍 Starting issue extraction...")
    
    try:
        from app.services.issue_pipeline import run_issue_extraction_pipeline
        issues = run_issue_extraction_pipeline(limit=50)
        logger.info(f"✅ Extracted {len(issues)} issues from news")
    except Exception as e:
        logger.error(f"❌ Issue extraction failed: {e}")


def create_scheduler() -> BackgroundScheduler:
    """Create and configure the scheduler."""
    scheduler = BackgroundScheduler(timezone="Africa/Lagos")
    
    # News scraping - every hour
    scheduler.add_job(
        run_news_scraper,
        IntervalTrigger(hours=1),
        id="news_scraper",
        name="Scrape Nigerian political news",
        replace_existing=True
    )
    
    # Index new articles - every 2 hours
    scheduler.add_job(
        index_news_for_rag,
        IntervalTrigger(hours=2),
        id="news_indexer",
        name="Index news for RAG",
        replace_existing=True
    )
    
    # Extract issues from news - every 3 hours
    scheduler.add_job(
        extract_issues_from_news,
        IntervalTrigger(hours=3),
        id="issue_extractor",
        name="Extract issues from news articles",
        replace_existing=True
    )
    
    # Cleanup old news - daily at 3 AM
    scheduler.add_job(
        cleanup_old_news,
        CronTrigger(hour=3, minute=0),
        id="news_cleanup",
        name="Clean up old news articles",
        replace_existing=True
    )
    
    # Health check - every 30 minutes
    scheduler.add_job(
        health_check,
        IntervalTrigger(minutes=30),
        id="health_check",
        name="Scheduler health check",
        replace_existing=True
    )
    
    return scheduler


def start_scheduler():
    """Start the background scheduler."""
    logger.info("🚀 Starting Decide9ja Scheduler...")
    
    scheduler = create_scheduler()
    scheduler.start()
    
    logger.info("📅 Scheduled jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"   - {job.name} ({job.id}): {job.trigger}")
    
    # Run initial news scrape
    logger.info("Running initial news scrape...")
    run_news_scraper()
    
    return scheduler


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Decide9ja Scheduler")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--news", action="store_true", help="Run news scraper only")
    
    args = parser.parse_args()
    
    if args.news:
        run_news_scraper()
    elif args.once:
        run_news_scraper()
        index_news_for_rag()
    else:
        scheduler = start_scheduler()
        
        try:
            # Keep the main thread alive
            logger.info("Scheduler running. Press Ctrl+C to stop.")
            while True:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down scheduler...")
            scheduler.shutdown()
