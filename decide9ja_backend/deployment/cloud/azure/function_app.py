"""
Decide9ja Azure Functions App
Timer-triggered functions for news scraping and processing

Functions:
- news_scraper: Runs every hour to scrape news
- news_indexer: Runs every 2 hours to index articles
- issue_extractor: Runs every 3 hours to extract issues

Deployment:
    func azure functionapp publish decide9ja-scheduler

Local testing:
    func start
"""
import os
import sys
import json
import logging
import azure.functions as func

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = func.FunctionApp()

# ============================================
# NEWS SCRAPER - Every Hour
# ============================================

@app.timer_trigger(
    schedule="0 0 * * * *",  # Every hour at minute 0
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True
)
def news_scraper(timer: func.TimerRequest) -> None:
    """
    Scrape news from Nigerian political news sources.
    Runs every hour.
    """
    logging.info("Starting news scraper function")

    try:
        from app.services.news_pipeline import run_news_pipeline

        result = run_news_pipeline(extract_issues=False)

        logging.info(f"News scraper completed: {json.dumps(result)}")

        if result.get("error"):
            logging.error(f"News scraper error: {result['error']}")

    except Exception as e:
        logging.exception(f"News scraper failed: {e}")
        raise


# ============================================
# NEWS INDEXER - Every 2 Hours
# ============================================

@app.timer_trigger(
    schedule="0 30 */2 * * *",  # Every 2 hours at minute 30
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True
)
def news_indexer(timer: func.TimerRequest) -> None:
    """
    Generate embeddings for unindexed news articles.
    Runs every 2 hours.
    """
    logging.info("Starting news indexer function")

    try:
        from app.services.news_pipeline import index_articles_for_rag

        count = index_articles_for_rag(batch_size=50)

        logging.info(f"News indexer completed: indexed {count} articles")

    except Exception as e:
        logging.exception(f"News indexer failed: {e}")
        raise


# ============================================
# ISSUE EXTRACTOR - Every 3 Hours
# ============================================

@app.timer_trigger(
    schedule="0 0 */3 * * *",  # Every 3 hours at minute 0
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True
)
def issue_extractor(timer: func.TimerRequest) -> None:
    """
    Extract political issues from unprocessed news articles.
    Runs every 3 hours.
    """
    logging.info("Starting issue extractor function")

    try:
        from app.services.issue_pipeline import run_issue_extraction_pipeline

        issues = run_issue_extraction_pipeline(limit=50)

        logging.info(f"Issue extractor completed: extracted {len(issues)} issues")

    except Exception as e:
        logging.exception(f"Issue extractor failed: {e}")
        raise


# ============================================
# NEWS AGENT PROCESSOR - Every 5 Minutes
# ============================================

@app.timer_trigger(
    schedule="0 */5 * * * *",  # Every 5 minutes
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True
)
def news_agent_processor(timer: func.TimerRequest) -> None:
    """
    Process articles through NewsAgent for continuous updates.
    Runs every 5 minutes with a small batch.
    """
    logging.info("Starting news agent processor")

    try:
        import asyncio
        from app.services.news_agent import NewsAgent

        async def process():
            with NewsAgent() as agent:
                return await agent.process_unprocessed_articles(limit=10)

        stats = asyncio.run(process())

        logging.info(f"News agent processor completed: {json.dumps(stats)}")

    except Exception as e:
        logging.exception(f"News agent processor failed: {e}")
        raise


# ============================================
# DAILY DIGEST - 7 AM WAT
# ============================================

@app.timer_trigger(
    schedule="0 0 6 * * *",  # 6 AM UTC = 7 AM WAT
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True
)
def daily_digest(timer: func.TimerRequest) -> None:
    """
    Send daily digest to subscribed users.
    Runs at 7 AM WAT (6 AM UTC).
    """
    logging.info("Starting daily digest function")

    try:
        import asyncio
        from app.services.broadcast_sender import get_broadcast_sender

        async def send_digests():
            sender = get_broadcast_sender()
            return await sender.send_daily_digests()

        result = asyncio.run(send_digests())

        logging.info(f"Daily digest completed: {json.dumps(result)}")

    except ImportError:
        logging.warning("Broadcast sender not available, skipping daily digest")
    except Exception as e:
        logging.exception(f"Daily digest failed: {e}")
        raise


# ============================================
# NEWS CLEANUP - Daily at 3 AM
# ============================================

@app.timer_trigger(
    schedule="0 0 3 * * *",  # 3 AM daily
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True
)
def news_cleanup(timer: func.TimerRequest) -> None:
    """
    Clean up old news articles (older than 30 days).
    Runs daily at 3 AM.
    """
    logging.info("Starting news cleanup function")

    try:
        from datetime import datetime, timedelta
        from app.database import SessionLocal, NewsArticle

        db = SessionLocal()
        try:
            cutoff = datetime.now() - timedelta(days=30)
            deleted = db.query(NewsArticle).filter(
                NewsArticle.scraped_at < cutoff
            ).delete()
            db.commit()

            logging.info(f"News cleanup completed: deleted {deleted} old articles")
        finally:
            db.close()

    except Exception as e:
        logging.exception(f"News cleanup failed: {e}")
        raise


# ============================================
# HEALTH CHECK HTTP TRIGGER
# ============================================

@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint for monitoring.
    """
    try:
        from app.scheduler_unified import get_scheduler_status

        status = get_scheduler_status()

        return func.HttpResponse(
            json.dumps({
                "status": "healthy",
                "scheduler": status
            }),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "status": "unhealthy",
                "error": str(e)
            }),
            mimetype="application/json",
            status_code=500
        )


# ============================================
# MANUAL TRIGGER - HTTP
# ============================================

@app.route(route="trigger/{job_name}", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """
    Manually trigger a specific job via HTTP.

    Usage:
        POST /api/trigger/news?code=<function_key>
        POST /api/trigger/issues?code=<function_key>
    """
    job_name = req.route_params.get("job_name")

    jobs = {
        "news": news_scraper,
        "index": news_indexer,
        "issues": issue_extractor,
        "cleanup": news_cleanup,
    }

    if job_name not in jobs:
        return func.HttpResponse(
            json.dumps({
                "error": f"Unknown job: {job_name}",
                "available": list(jobs.keys())
            }),
            mimetype="application/json",
            status_code=400
        )

    try:
        # Create a mock timer request
        mock_timer = func.TimerRequest(past_due=False)
        jobs[job_name](mock_timer)

        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "job": job_name
            }),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "job": job_name,
                "error": str(e)
            }),
            mimetype="application/json",
            status_code=500
        )
