#!/usr/bin/env python3
"""
Archivi.ng Railway Worker
=========================
Long-running worker for Railway that scrapes archivi.ng continuously.
Tracks progress in database so it can resume if restarted.

Deploy to Railway:
    railway up --service archiving-worker

Environment variables needed:
    DATABASE_URL - PostgreSQL connection string
    ANTHROPIC_API_KEY - For OCR (optional)
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Configuration from environment
SOURCE = os.getenv("ARCHIVING_SOURCE", "pm-news")
START_YEAR = int(os.getenv("ARCHIVING_START_YEAR", "1960"))
END_YEAR = int(os.getenv("ARCHIVING_END_YEAR", "2010"))
LIMIT_PER_YEAR = int(os.getenv("ARCHIVING_LIMIT_PER_YEAR", "100"))
USE_OCR = os.getenv("ARCHIVING_USE_OCR", "false").lower() == "true"
SLEEP_BETWEEN_YEARS = int(os.getenv("ARCHIVING_SLEEP_SECONDS", "5"))


def get_scrape_progress(db):
    """Get the last completed year from database."""
    from sqlalchemy import text

    result = db.execute(text("""
        SELECT MAX(CAST(
            CASE
                WHEN scraped_at IS NOT NULL
                THEN EXTRACT(YEAR FROM scraped_at)::text
                ELSE '1959'
            END AS INTEGER
        )) as last_year
        FROM news_articles
        WHERE source = 'archiving'
    """)).scalar()

    return result or START_YEAR - 1


def mark_year_complete(db, year: int, pages_count: int, politicians: list):
    """Record that a year has been scraped (for tracking)."""
    from sqlalchemy import text

    # We can use the news_articles table itself as progress tracker
    # since each article has scraped_at timestamp
    logger.info(f"Year {year} complete: {pages_count} pages, {len(politicians)} politicians")


async def scrape_single_year(scraper, year: int, db):
    """Scrape a single year and store results."""
    from app.services.archiving_scraper import store_scraped_pages, NewspaperPage

    logger.info(f"{'='*50}")
    logger.info(f"SCRAPING {SOURCE.upper()} - {year}")
    logger.info(f"{'='*50}")

    try:
        result = await scraper.scrape_year(
            source=SOURCE,
            year=year,
            limit=LIMIT_PER_YEAR,
            use_ocr=USE_OCR
        )

        if "error" in result:
            logger.error(f"Year {year} error: {result['error']}")
            return False

        pages_count = result.get("pages_scraped", 0)
        politicians = result.get("politicians_found", [])

        logger.info(f"Year {year}: {pages_count} pages, {len(politicians)} politicians")

        # Store in database
        if result.get("pages"):
            pages = [NewspaperPage(**p) for p in result["pages"]]
            stored = await store_scraped_pages(pages, db)
            logger.info(f"Stored {stored} pages in database")

        mark_year_complete(db, year, pages_count, politicians)
        return True

    except Exception as e:
        logger.error(f"Error scraping {year}: {e}")
        return False


async def run_worker():
    """Main worker loop."""
    from app.services.archiving_scraper import ArchiviNgScraper, SOURCES
    from app.database import SessionLocal

    logger.info("=" * 60)
    logger.info("ARCHIVI.NG RAILWAY WORKER STARTING")
    logger.info("=" * 60)
    logger.info(f"Source: {SOURCE}")
    logger.info(f"Year range: {START_YEAR} - {END_YEAR}")
    logger.info(f"Limit per year: {LIMIT_PER_YEAR}")
    logger.info(f"OCR enabled: {USE_OCR}")
    logger.info("=" * 60)

    # Validate source
    source_info = SOURCES.get(SOURCE)
    if not source_info:
        logger.error(f"Unknown source: {SOURCE}")
        return

    db = SessionLocal()
    scraper = ArchiviNgScraper()

    try:
        # Find where we left off
        last_completed = get_scrape_progress(db)
        start_from = max(last_completed + 1, START_YEAR)

        if start_from > END_YEAR:
            logger.info("All years already scraped! Worker complete.")
            return

        logger.info(f"Resuming from year {start_from} (last completed: {last_completed})")

        # Scrape remaining years
        for year in range(start_from, END_YEAR + 1):
            success = await scrape_single_year(scraper, year, db)

            if success:
                db.commit()
                logger.info(f"Year {year} committed to database")
            else:
                logger.warning(f"Year {year} had issues, continuing...")

            # Brief pause between years
            if year < END_YEAR:
                logger.info(f"Sleeping {SLEEP_BETWEEN_YEARS}s before next year...")
                await asyncio.sleep(SLEEP_BETWEEN_YEARS)

        logger.info("=" * 60)
        logger.info("ALL YEARS COMPLETE!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise
    finally:
        await scraper.close()
        db.close()


def main():
    """Entry point."""
    # Check required env vars
    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL environment variable required")
        sys.exit(1)

    logger.info("Starting archivi.ng worker...")
    asyncio.run(run_worker())
    logger.info("Worker finished.")


if __name__ == "__main__":
    main()
