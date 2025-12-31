"""
Scheduler Service for Decide9ja.
Runs background tasks on schedule:
- News scraping every hour
- Issue extraction every 2 hours
- Card regeneration daily
"""
import os
import schedule
import time
import logging
from datetime import datetime
import threading

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_news_pipeline():
    """Run the news scraping and indexing pipeline."""
    try:
        logger.info("Starting scheduled news pipeline...")
        from app.services.news_pipeline import run_news_pipeline as _run_pipeline
        result = _run_pipeline()
        logger.info(f"News pipeline complete: {result}")
        return result
    except Exception as e:
        logger.error(f"News pipeline error: {e}")
        return None


def run_issue_extraction():
    """Run issue extraction from news articles."""
    try:
        logger.info("Starting scheduled issue extraction...")
        from app.services.issue_pipeline import run_issue_extraction_pipeline
        result = run_issue_extraction_pipeline()
        logger.info(f"Issue extraction complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Issue extraction error: {e}")
        return None


def regenerate_cards():
    """Regenerate politician and jurisdiction cards."""
    try:
        logger.info("Starting scheduled card regeneration...")
        from app.services.card_generator import generate_all_politician_cards, save_cards_to_rag
        from app.services.jurisdiction_generator import generate_jurisdiction_cards, save_jurisdiction_cards_to_rag
        
        # Politician cards
        cards = generate_all_politician_cards()
        save_cards_to_rag(cards)
        logger.info(f"Regenerated {len(cards)} politician cards")
        
        return len(cards)
    except Exception as e:
        logger.error(f"Card regeneration error: {e}")
        return None


def regenerate_dossiers():
    """Regenerate issue dossiers."""
    try:
        logger.info("Starting scheduled dossier regeneration...")
        from app.services.dossier_generator import generate_issue_dossiers, save_dossiers_to_rag
        
        dossiers = generate_issue_dossiers()
        save_dossiers_to_rag(dossiers)
        logger.info(f"Regenerated {len(dossiers)} issue dossiers")
        
        return len(dossiers)
    except Exception as e:
        logger.error(f"Dossier regeneration error: {e}")
        return None


def setup_schedule():
    """Set up the job schedule."""
    # News scraping - every hour
    schedule.every(1).hours.do(run_news_pipeline)
    
    # Issue extraction - every 1 hour (Synchronized)
    schedule.every(1).hours.do(run_issue_extraction)
    
    # Dossier regeneration - every 1 hour (Increased frequency)
    schedule.every(1).hours.do(regenerate_dossiers)
    
    # Card regeneration - once daily at 3 AM
    schedule.every().day.at("03:00").do(regenerate_cards)
    
    logger.info("Schedule configured:")
    logger.info("  - News scraping: every 1 hour")
    logger.info("  - Issue extraction: every 2 hours")
    logger.info("  - Dossier regeneration: every 4 hours")
    logger.info("  - Card regeneration: daily at 3 AM")


def run_scheduler():
    """Run the scheduler in the foreground."""
    print("=" * 50)
    print("DECIDE9JA SCHEDULER SERVICE")
    print("=" * 50)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    setup_schedule()
    
    # Run news pipeline immediately on start
    print("\nRunning initial news scrape...")
    run_news_pipeline()
    
    print("\nScheduler running. Press Ctrl+C to stop.\n")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


def start_scheduler_thread():
    """Start the scheduler in a background thread."""
    def _run():
        setup_schedule()
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info("Scheduler started in background thread")
    return thread


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Decide9ja Scheduler Service")
    parser.add_argument("--once", action="store_true", help="Run all jobs once and exit")
    parser.add_argument("--news", action="store_true", help="Run news pipeline only")
    parser.add_argument("--issues", action="store_true", help="Run issue extraction only")
    parser.add_argument("--cards", action="store_true", help="Regenerate cards only")
    
    args = parser.parse_args()
    
    if args.once:
        print("Running all jobs once...")
        run_news_pipeline()
        run_issue_extraction()
        regenerate_dossiers()
        print("Done!")
    elif args.news:
        run_news_pipeline()
    elif args.issues:
        run_issue_extraction()
    elif args.cards:
        regenerate_cards()
    else:
        run_scheduler()
