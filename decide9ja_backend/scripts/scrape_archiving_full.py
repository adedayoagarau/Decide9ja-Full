#!/usr/bin/env python3
"""
Full-Range Archivi.ng Scraper
=============================
Scrapes PM News from 1960 to 2010 in sequence.

Usage:
    python scripts/scrape_archiving_full.py --start 1960 --end 2010 --limit 100 --ocr
    python scripts/scrape_archiving_full.py --start 1990 --end 2000  # Subset
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def scrape_full_range(
    start_year: int = 1960,
    end_year: int = 2010,
    source: str = "pm-news",
    limit_per_year: int = 100,
    use_ocr: bool = False,
    store: bool = True
):
    """Scrape archivi.ng from start_year to end_year."""
    from app.services.archiving_scraper import (
        ArchiviNgScraper,
        store_scraped_pages,
        NewspaperPage,
        SOURCES
    )

    scraper = ArchiviNgScraper()

    # Validate source
    source_info = SOURCES.get(source)
    if not source_info:
        logger.error(f"Unknown source: {source}. Available: {list(SOURCES.keys())}")
        return {"error": f"Unknown source: {source}"}

    # Clamp years to source availability
    actual_start = max(start_year, source_info["start_year"])
    actual_end = min(end_year, source_info["end_year"])

    if actual_start > actual_end:
        logger.error(
            f"{source} not available for {start_year}-{end_year}. "
            f"Available: {source_info['start_year']}-{source_info['end_year']}"
        )
        return {"error": "No data available for specified year range"}

    total_stats = {
        "source": source,
        "source_name": source_info["name"],
        "start_year": actual_start,
        "end_year": actual_end,
        "years_processed": 0,
        "total_pages": 0,
        "total_stored": 0,
        "politicians_found": set(),
        "errors": [],
        "started_at": datetime.now().isoformat(),
    }

    logger.info("=" * 60)
    logger.info(f"ARCHIVI.NG FULL SCRAPE: {source}")
    logger.info(f"Years: {actual_start} to {actual_end}")
    logger.info(f"Limit per year: {limit_per_year}")
    logger.info(f"OCR enabled: {use_ocr}")
    logger.info(f"Store to DB: {store}")
    logger.info("=" * 60)

    try:
        for year in range(actual_start, actual_end + 1):
            logger.info(f"\n{'='*50}")
            logger.info(f"SCRAPING {source.upper()} - {year}")
            logger.info(f"{'='*50}")

            try:
                result = await scraper.scrape_year(
                    source=source,
                    year=year,
                    limit=limit_per_year,
                    use_ocr=use_ocr
                )

                if "error" in result:
                    logger.warning(f"Year {year} error: {result['error']}")
                    total_stats["errors"].append({"year": year, "error": result["error"]})
                    continue

                pages_count = result.get("pages_scraped", 0)
                politicians = result.get("politicians_found", [])

                logger.info(f"Year {year}: {pages_count} pages, {len(politicians)} politicians")

                total_stats["years_processed"] += 1
                total_stats["total_pages"] += pages_count
                total_stats["politicians_found"].update(politicians)

                # Store in database
                if store and result.get("pages"):
                    pages = [NewspaperPage(**p) for p in result["pages"]]
                    stored = await store_scraped_pages(pages)
                    total_stats["total_stored"] += stored
                    logger.info(f"Stored {stored} pages in database")

            except Exception as e:
                logger.error(f"Error scraping {year}: {e}")
                total_stats["errors"].append({"year": year, "error": str(e)})

            # Brief pause between years
            await asyncio.sleep(2)

    finally:
        await scraper.close()

    total_stats["politicians_found"] = list(total_stats["politicians_found"])
    total_stats["completed_at"] = datetime.now().isoformat()

    return total_stats


def main():
    parser = argparse.ArgumentParser(
        description="Scrape archivi.ng PM News from 1960-2010",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all years (default)
  python scripts/scrape_archiving_full.py

  # Scrape specific year range
  python scripts/scrape_archiving_full.py --start 1990 --end 1999

  # Scrape with OCR (uses Claude Vision API)
  python scripts/scrape_archiving_full.py --start 1999 --end 1999 --ocr --limit 10

  # Dry run without storing to database
  python scripts/scrape_archiving_full.py --no-store --output results.json
        """
    )
    parser.add_argument(
        "--start", type=int, default=1960,
        help="Start year (default: 1960)"
    )
    parser.add_argument(
        "--end", type=int, default=2010,
        help="End year (default: 2010)"
    )
    parser.add_argument(
        "--source", type=str, default="pm-news",
        help="Source slug (default: pm-news)"
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max pages per year (default: 100)"
    )
    parser.add_argument(
        "--ocr", action="store_true",
        help="Use Claude Vision OCR for text extraction"
    )
    parser.add_argument(
        "--no-store", action="store_true",
        help="Don't store in database (dry run)"
    )
    parser.add_argument(
        "--output", type=str,
        help="Save results to JSON file"
    )

    args = parser.parse_args()

    # Validate years
    if args.start > args.end:
        parser.error(f"Start year ({args.start}) must be <= end year ({args.end})")

    logger.info(f"Starting full-range scrape: {args.source} {args.start}-{args.end}")
    logger.info(f"OCR: {args.ocr}, Limit per year: {args.limit}")

    result = asyncio.run(scrape_full_range(
        start_year=args.start,
        end_year=args.end,
        source=args.source,
        limit_per_year=args.limit,
        use_ocr=args.ocr,
        store=not args.no_store
    ))

    # Print summary
    print("\n" + "=" * 60)
    print("SCRAPE COMPLETE")
    print("=" * 60)
    print(f"Years processed: {result.get('years_processed', 0)}")
    print(f"Total pages scraped: {result.get('total_pages', 0)}")
    print(f"Total pages stored: {result.get('total_stored', 0)}")
    print(f"Unique politicians found: {len(result.get('politicians_found', []))}")
    print(f"Errors: {len(result.get('errors', []))}")

    if result.get('politicians_found'):
        print(f"\nTop politicians: {result['politicians_found'][:20]}")

    if result.get('errors'):
        print(f"\nErrors encountered:")
        for err in result['errors']:
            print(f"  - {err['year']}: {err['error']}")

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(result, indent=2))
        print(f"\nResults saved to: {args.output}")

    # Exit with error code if there were issues
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
