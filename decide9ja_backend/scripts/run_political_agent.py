#!/usr/bin/env python3
"""
Political Data Agent Runner

Runs the Political Data Agent to:
1. Collect news from Nigerian sources
2. Process and analyze content
3. Update candidate profiles
4. Compute trending topics

Set up as a cron job:
    # Run daily at 6 AM
    0 6 * * * cd /home/user/Decide9ja-Full/decide9ja_backend && python scripts/run_political_agent.py

    # Or run every 4 hours
    0 */4 * * * cd /home/user/Decide9ja-Full/decide9ja_backend && python scripts/run_political_agent.py
"""
import sys
import os
import asyncio
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'/tmp/political_agent_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def run_agent():
    """Run the political data agent."""
    from app.services.election_2027.political_data_agent import PoliticalDataAgent

    logger.info("=" * 60)
    logger.info(f"Starting Political Data Agent Run at {datetime.now()}")
    logger.info("=" * 60)

    try:
        # Initialize agent
        agent = PoliticalDataAgent()

        # Run the agent
        result = await agent.run()

        # Log results
        logger.info(f"Collection Phase: {result.get('collection', {})}")
        logger.info(f"Processing Phase: {result.get('processing', {})}")
        logger.info(f"Candidate Updates: {result.get('candidate_updates', {})}")
        logger.info(f"Trends: {result.get('trends', {})}")

        # Summary
        collected = result.get('collection', {}).get('total_collected', 0)
        processed = result.get('processing', {}).get('total_processed', 0)

        logger.info("-" * 60)
        logger.info(f"SUMMARY: Collected {collected} items, Processed {processed}")
        logger.info("-" * 60)

        return result

    except Exception as e:
        logger.exception(f"Agent run failed: {e}")
        return {"error": str(e)}


async def run_quick_update():
    """Run a quick update (just check RSS feeds)."""
    from app.services.election_2027.political_data_agent import PoliticalDataAgent

    logger.info("Running quick update (RSS only)...")

    agent = PoliticalDataAgent()
    collected = await agent.collect(hours_back=4)  # Just last 4 hours

    logger.info(f"Quick update collected {collected} items")
    return collected


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Run Political Data Agent')
    parser.add_argument('--quick', action='store_true', help='Quick update (RSS only)')
    parser.add_argument('--test', action='store_true', help='Test run (no database writes)')
    args = parser.parse_args()

    if args.quick:
        result = asyncio.run(run_quick_update())
    else:
        result = asyncio.run(run_agent())

    logger.info(f"Agent run completed at {datetime.now()}")
    return result


if __name__ == "__main__":
    main()
