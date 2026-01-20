"""
Background Research Job
=======================
Runs every 6 hours to research and cache political data.

This job:
1. Gets prioritized research tasks from orchestrator
2. Crawls news sources for each entity
3. Extracts structured data using LLM
4. Saves to knowledge cache

Can be run via:
- APScheduler (recommended for simple deployments)
- Celery (for distributed processing)
- Cron (external scheduler)
- Manual invocation

Usage:
    # Run once
    python -m app.jobs.research_job

    # Start scheduler
    python -m app.jobs.research_job --scheduler
"""

import asyncio
import argparse
import logging
from datetime import datetime
from typing import List, Dict

from app.agents.registry import registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Job configuration
MAX_TASKS_PER_CYCLE = 10  # Limit LLM costs
RATE_LIMIT_DELAY = 5  # Seconds between entities
CYCLE_INTERVAL_HOURS = 6


async def run_research_cycle():
    """
    Main research cycle - runs every 6 hours.

    Flow:
    1. Get research tasks from orchestrator (what needs updating)
    2. For each task:
       a. Crawl sources for articles
       b. Fetch full article content
       c. Extract structured data with LLM
       d. Save to cache
    3. Log statistics
    """
    cycle_start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info(f"RESEARCH CYCLE STARTED: {cycle_start.isoformat()}")
    logger.info("=" * 60)

    # Load agents
    try:
        # Import to ensure registration
        from app.agents.tier6_analytics.research_orchestrator import ResearchOrchestratorAgent
        from app.agents.tier6_analytics.source_crawler import SourceCrawlerAgent
        from app.agents.tier6_analytics.data_extractor import DataExtractorAgent
        from app.agents.tier6_analytics.knowledge_cache import KnowledgeCacheAgent

        orchestrator = registry.get("research_orchestrator")
        crawler = registry.get("source_crawler")
        extractor = registry.get("data_extractor")
        cache = registry.get("knowledge_cache")

        if not all([orchestrator, crawler, extractor, cache]):
            logger.error("Failed to load required agents")
            return

    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}")
        return

    # Get research tasks
    try:
        tasks = await orchestrator.get_next_research_tasks()
        logger.info(f"Research tasks queued: {len(tasks)}")
    except Exception as e:
        logger.error(f"Failed to get research tasks: {e}")
        return

    # Process tasks (limited per cycle to control costs)
    stats = {
        "tasks_processed": 0,
        "profiles_cached": 0,
        "promises_cached": 0,
        "articles_crawled": 0,
        "errors": 0
    }

    for task in tasks[:MAX_TASKS_PER_CYCLE]:
        try:
            entity = task["entity"]
            task_type = task["type"]

            logger.info(f"\n--- Researching: {entity} ({task_type}) ---")

            # 1. Crawl sources for articles
            articles = await crawler.crawl_for_entity(entity, max_per_source=3)
            stats["articles_crawled"] += len(articles)

            if not articles:
                logger.warning(f"No articles found for {entity}")
                continue

            logger.info(f"Found {len(articles)} articles")

            # 2. Fetch full content for top articles
            articles_with_content = []
            for article in articles[:5]:  # Limit to save time
                try:
                    content = await crawler.fetch_article_content(article["url"])
                    article["content"] = content.get("content", "")
                    if article["content"]:
                        articles_with_content.append(article)
                except Exception as e:
                    logger.debug(f"Failed to fetch {article['url']}: {e}")
                    continue

            if not articles_with_content:
                logger.warning(f"No article content retrieved for {entity}")
                continue

            # 3. Extract structured data
            if task_type == "full_profile":
                # Full profile extraction
                data = await extractor.extract_politician_data(
                    articles_with_content,
                    entity
                )

                if data and data.get("name"):
                    # 4. Save to cache
                    sources = [a["url"] for a in articles_with_content]
                    await cache.save_politician(
                        name=entity,
                        data=data,
                        sources=sources
                    )
                    stats["profiles_cached"] += 1

                    # Also save promises separately for fast lookup
                    if data.get("promises"):
                        saved = await cache.save_promises(entity, data["promises"])
                        stats["promises_cached"] += saved

                    logger.info(f"Cached profile for {entity} with {len(data.get('promises', []))} promises")

            elif task_type == "refresh":
                # Incremental refresh - just update promises and news
                existing = await cache.get_politician(entity)

                if existing and existing.get("data"):
                    # Check promise statuses against new articles
                    promises = await cache.get_promises(entity)

                    for promise in promises[:5]:  # Limit checks
                        status = await extractor.extract_promise_status(
                            promise,
                            articles_with_content
                        )
                        if status.get("status") != "unknown":
                            await cache.update_promise_status(
                                promise["id"],
                                status["status"],
                                status["evidence"]
                            )
                            logger.debug(f"Updated promise status: {status['status']}")

                    # Extract and save news summaries
                    news_items = await extractor.extract_news_summary(
                        articles_with_content,
                        topic=entity
                    )
                    if news_items:
                        for item in news_items:
                            item["politician_name"] = entity
                        await cache.save_news(news_items)

                    logger.info(f"Refreshed {entity} with {len(news_items)} news items")

            elif task_type == "topic_research":
                # Topic-based research (e.g., "education policy")
                news_items = await extractor.extract_news_summary(
                    articles_with_content,
                    topic=entity
                )
                if news_items:
                    await cache.save_news(news_items)
                    logger.info(f"Cached {len(news_items)} news items for topic: {entity}")

            stats["tasks_processed"] += 1

            # Rate limiting
            await asyncio.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            logger.error(f"Research failed for {task.get('entity')}: {e}")
            stats["errors"] += 1
            continue

    # Log cycle summary
    cycle_end = datetime.utcnow()
    duration = (cycle_end - cycle_start).total_seconds()

    logger.info("\n" + "=" * 60)
    logger.info("RESEARCH CYCLE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info(f"Tasks processed: {stats['tasks_processed']}/{len(tasks[:MAX_TASKS_PER_CYCLE])}")
    logger.info(f"Profiles cached: {stats['profiles_cached']}")
    logger.info(f"Promises cached: {stats['promises_cached']}")
    logger.info(f"Articles crawled: {stats['articles_crawled']}")
    logger.info(f"Errors: {stats['errors']}")

    # Get cache stats
    try:
        cache_stats = await cache.get_cache_stats()
        logger.info(f"Cache status: {cache_stats}")
    except:
        pass

    return stats


async def run_single_entity_research(entity_name: str):
    """
    Research a single entity on demand.

    Useful for:
    - Testing the pipeline
    - Immediate research when user asks about unknown entity
    """
    logger.info(f"Single entity research: {entity_name}")

    # Import and get agents
    from app.agents.tier6_analytics.source_crawler import SourceCrawlerAgent
    from app.agents.tier6_analytics.data_extractor import DataExtractorAgent
    from app.agents.tier6_analytics.knowledge_cache import KnowledgeCacheAgent

    crawler = registry.get("source_crawler")
    extractor = registry.get("data_extractor")
    cache = registry.get("knowledge_cache")

    if not all([crawler, extractor, cache]):
        logger.error("Failed to load agents")
        return None

    # Crawl
    articles = await crawler.crawl_for_entity(entity_name, max_per_source=3)
    if not articles:
        logger.warning(f"No articles found for {entity_name}")
        return None

    # Fetch content
    for article in articles[:5]:
        content = await crawler.fetch_article_content(article["url"])
        article["content"] = content.get("content", "")

    articles_with_content = [a for a in articles if a.get("content")]

    if not articles_with_content:
        return None

    # Extract
    data = await extractor.extract_politician_data(articles_with_content, entity_name)

    # Cache
    if data and data.get("name"):
        sources = [a["url"] for a in articles_with_content]
        await cache.save_politician(entity_name, data, sources)

        if data.get("promises"):
            await cache.save_promises(entity_name, data["promises"])

    return data


def start_scheduler():
    """Start the APScheduler for periodic research cycles"""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        return

    scheduler = AsyncIOScheduler()

    # Run research cycle every 6 hours
    scheduler.add_job(
        run_research_cycle,
        IntervalTrigger(hours=CYCLE_INTERVAL_HOURS),
        id="research_cycle",
        name="Autonomous Research Cycle",
        replace_existing=True
    )

    # Run immediately on start
    scheduler.add_job(
        run_research_cycle,
        id="research_cycle_initial",
        name="Initial Research Cycle"
    )

    logger.info(f"Starting scheduler - research cycle every {CYCLE_INTERVAL_HOURS} hours")
    scheduler.start()

    # Keep the scheduler running
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decide9ja Research Job")
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="Start the scheduler for periodic research cycles"
    )
    parser.add_argument(
        "--entity",
        type=str,
        help="Research a single entity immediately"
    )

    args = parser.parse_args()

    if args.scheduler:
        start_scheduler()
    elif args.entity:
        asyncio.run(run_single_entity_research(args.entity))
    else:
        # Run single cycle
        asyncio.run(run_research_cycle())
