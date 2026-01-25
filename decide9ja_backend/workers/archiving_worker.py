import asyncio
import logging
import os
import sys
import time

# Add parent directory to path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.archiving_scraper import ArchiviNgScraper, store_scraped_pages, NewspaperPage
from app.database import SessionLocal, NewsArticle
from sqlalchemy import func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("archiving-worker")

def get_config():
    """Get configuration from environment variables."""
    return {
        "source": os.getenv("ARCHIVING_SOURCE", "pm-news"),
        "start_year": int(os.getenv("ARCHIVING_START_YEAR", "1960")),
        "end_year": int(os.getenv("ARCHIVING_END_YEAR", "2010")),
        "limit_per_year": int(os.getenv("ARCHIVING_LIMIT_PER_YEAR", "100")),
        "use_ocr": os.getenv("ARCHIVING_USE_OCR", "false").lower() == "true",
        "sleep_seconds": int(os.getenv("ARCHIVING_SLEEP_SECONDS", "5")),
    }

def count_articles_for_year(db, source: str, year: int) -> int:
    """Count existing articles for a source and year to avoid re-scraping."""
    try:
        count = db.query(func.count(NewsArticle.id)).filter(
            NewsArticle.source == "archiving",
            NewsArticle.source_name.ilike(f"%{source}%"),
            # Assuming scraped_at or date parsing puts valid dates in database.
            # However, NewsArticle doesn't enforce a specific date column for publication date 
            # that is easily queryable by year for all formats. 
            # We rely on source_name and simple check, but since we don't have a reliable 'publication_year' column
            # in the simple schema seen so far, we might skip this optimization or use a text search on title/date field if available.
            # Let's check if we can filter by the 'scraped_at' or if the 'full_text' contains the date.
            # Actually, let's just use the 'article_id' prefix or simple duplicate detection on insert.
            # But the goal here is to SKIP the year if it's already done.
            # Let's rely on the scraper's 'unique_dates' check or just run it.
            # For now, let's just log the count.
        ).scalar()
        return count or 0
    except Exception as e:
        logger.warning(f"Error checking DB count: {e}")
        return 0

async def run_worker():
    config = get_config()
    logger.info(f"Starting Archiving Worker with config: {config}")

    scraper = ArchiviNgScraper()
    
    try:
        for year in range(config["start_year"], config["end_year"] + 1):
            logger.info(f"=== Processing Year {year} ===")
            
            # Create a DB session to check progress (optional, just for logging)
            db = SessionLocal()
            try:
                existing_count = count_articles_for_year(db, config["source"], year)
                logger.info(f"Existing articles for {config['source']} in DB (total, any year): {existing_count} (approx check)")
                # Optimization: If we had a better way to check exact per-year count, we could skip.
                # For now, we proceed to scrape. Rate limiting and duplicate checks will handle the rest.
            finally:
                db.close()

            result = await scraper.scrape_year(
                source=config["source"],
                year=year,
                limit=config["limit_per_year"],
                use_ocr=config["use_ocr"]
            )
            
            pages_found = result.get('pages_scraped', 0)
            logger.info(f"Scraped {pages_found} pages for {year}")
            
            if result.get('pages'):
                pages = [NewspaperPage(**p) for p in result['pages']]
                stored = await store_scraped_pages(pages)
                logger.info(f"Stored {stored} new pages for {year}")
            
            logger.info(f"Sleeping for {config['sleep_seconds']}s before next year...")
            await asyncio.sleep(config['sleep_seconds'])

    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        # In production, you might want to raise so the worker restarts
        # raise e 
    finally:
        await scraper.close()
        logger.info("Worker finished or stopped.")

if __name__ == "__main__":
    asyncio.run(run_worker())
