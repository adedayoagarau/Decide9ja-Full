"""
Decide9ja Web Scrapers.

Contains crawlers for:
- OSGF (Office of Secretary to the Government of the Federation)
- Ministry websites
- Project tracking sites (Tracka, BudgIT)
"""

from .ministry_crawler import (
    MinistryCrawler,
    run_full_crawl,
    run_crawl_sync,
    MINISTRY_URLS,
    ALTERNATIVE_SOURCES,
)

__all__ = [
    "MinistryCrawler",
    "run_full_crawl",
    "run_crawl_sync",
    "MINISTRY_URLS",
    "ALTERNATIVE_SOURCES",
]
