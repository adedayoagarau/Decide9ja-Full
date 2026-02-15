"""
Decide9ja Unified Crawler Service

Consolidates all crawling functionality from:
- decide9ja_scraper/ (INEC election data)
- decide9ja-crawler/ (Azure Functions news crawler)
- decide9ja-functions/news_crawler/ (additional news crawler)
- app/services/news_scraper*.py (multiple news scrapers)
- app/services/archiving_scraper.py (Internet Archive)

This single service handles ALL data ingestion:
1. News crawling (Nigerian political news)
2. Election data (INEC results)
3. Historical data (Internet Archive, Wikipedia)
4. Budget data (BudgIT APIs)
5. Knowledge base updates (Wikidata)

Run as: python -m app.services.unified_crawler
"""

import os
import json
import asyncio
import logging
import hashlib
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

import httpx
import feedparser
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Database
from sqlalchemy.orm import Session
from app.database import SessionLocal, NewsArticle
from app.database_v2 import (
    KnowledgeEntity, KnowledgeRelation, ElectionResult,
    BudgetAllocation, ConstituencyProject
)

# Services
from app.services.embeddings import get_embedding
from app.services.fuzzy_match import extract_politicians_from_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===========================================
# CONFIGURATION
# ===========================================

class CrawlerConfig:
    """Centralized crawler configuration."""

    # News Sources
    NEWS_SOURCES = {
        "premium_times": {
            "name": "Premium Times",
            "base_url": "https://www.premiumtimesng.com",
            "rss_url": "https://www.premiumtimesng.com/feed",
            "politics_url": "https://www.premiumtimesng.com/category/news/top-news/feed",
            "category": "politics",
            "reliability": "high",
        },
        "punch": {
            "name": "Punch Nigeria",
            "base_url": "https://punchng.com",
            "rss_url": "https://punchng.com/feed/",
            "politics_url": "https://punchng.com/topics/politics/feed/",
            "category": "politics",
            "reliability": "high",
        },
        "vanguard": {
            "name": "Vanguard Nigeria",
            "base_url": "https://www.vanguardngr.com",
            "rss_url": "https://www.vanguardngr.com/feed/",
            "politics_url": "https://www.vanguardngr.com/category/politics/feed/",
            "category": "politics",
            "reliability": "high",
        },
        "guardian": {
            "name": "The Guardian Nigeria",
            "base_url": "https://guardian.ng",
            "rss_url": "https://guardian.ng/feed/",
            "politics_url": "https://guardian.ng/category/politics/feed/",
            "category": "politics",
            "reliability": "high",
        },
        "thisday": {
            "name": "ThisDay Live",
            "base_url": "https://www.thisdaylive.com",
            "rss_url": "https://www.thisdaylive.com/index.php/feed/",
            "politics_url": "https://www.thisdaylive.com/index.php/category/politics/feed/",
            "category": "politics",
            "reliability": "high",
        },
    }

    # Rate limiting
    REQUEST_DELAY_SECONDS = 2
    MAX_CONCURRENT_REQUESTS = 3
    MAX_ARTICLES_PER_SOURCE = 50

    # INEC Configuration
    INEC_BASE_URL = "https://www.inecnigeria.org"
    INEC_RESULTS_API = "https://inecelectionresults.ng"

    # BudgIT Configuration
    BUDGIT_API_URL = "https://yourbudgit.com/api"

    # Wikidata Configuration
    WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"


# ===========================================
# DATA MODELS
# ===========================================

@dataclass
class CrawledArticle:
    """Standardized article format from any source."""
    url: str
    title: str
    source: str
    source_name: str
    excerpt: str = ""
    full_text: str = ""
    published_date: str = ""
    author: str = ""
    category: str = "politics"
    image_url: str = ""
    politicians_mentioned: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)

    @property
    def article_id(self) -> str:
        """Generate unique ID from URL."""
        return hashlib.md5(self.url.encode()).hexdigest()[:20]


class CrawlerStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    PAUSED = "paused"


# ===========================================
# BASE CRAWLER
# ===========================================

class BaseCrawler:
    """Base class for all crawlers."""

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Decide9ja/1.0 (Nigerian Political Intelligence; +https://decide9ja.com)"
            }
        )
        self.status = CrawlerStatus.IDLE
        self.stats = {
            "articles_crawled": 0,
            "articles_saved": 0,
            "errors": 0,
            "last_run": None,
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Clean up resources."""
        await self.client.aclose()
        self.db.close()

    async def fetch_url(self, url: str, retries: int = 3) -> Optional[str]:
        """Fetch URL with retry logic."""
        for attempt in range(retries):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                return response.text
            except Exception as e:
                logger.warning(f"Fetch attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(CrawlerConfig.REQUEST_DELAY_SECONDS * (attempt + 1))
        return None

    def article_exists(self, article_id: str) -> bool:
        """Check if article already exists in database."""
        return self.db.query(NewsArticle).filter(
            NewsArticle.article_id == article_id
        ).first() is not None

    async def save_article(self, article: CrawledArticle) -> bool:
        """Save crawled article to database."""
        if self.article_exists(article.article_id):
            logger.debug(f"Article already exists: {article.title[:50]}")
            return False

        try:
            db_article = NewsArticle(
                article_id=article.article_id,
                title=article.title,
                url=article.url,
                source=article.source,
                source_name=article.source_name,
                excerpt=article.excerpt,
                full_text=article.full_text,
                politicians_json=json.dumps(article.politicians_mentioned),
                topics_json=json.dumps(article.topics),
                published_date=article.published_date,
                is_processed=False,
                is_indexed=False,
            )
            self.db.add(db_article)
            self.db.commit()
            self.stats["articles_saved"] += 1
            logger.info(f"Saved article: {article.title[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to save article: {e}")
            self.db.rollback()
            self.stats["errors"] += 1
            return False


# ===========================================
# NEWS CRAWLER
# ===========================================

class NewsCrawler(BaseCrawler):
    """Crawls Nigerian news sources for political news."""

    def __init__(self, db: Session = None):
        super().__init__(db)
        self.sources = CrawlerConfig.NEWS_SOURCES

    async def crawl_rss_feed(self, source_key: str) -> List[CrawledArticle]:
        """Crawl RSS feed for a news source."""
        source = self.sources.get(source_key)
        if not source:
            logger.error(f"Unknown source: {source_key}")
            return []

        articles = []
        rss_url = source.get("politics_url") or source.get("rss_url")

        try:
            html = await self.fetch_url(rss_url)
            if not html:
                return []

            feed = feedparser.parse(html)

            for entry in feed.entries[:CrawlerConfig.MAX_ARTICLES_PER_SOURCE]:
                article = CrawledArticle(
                    url=entry.get("link", ""),
                    title=entry.get("title", ""),
                    source=source_key,
                    source_name=source["name"],
                    excerpt=self._clean_html(entry.get("summary", "")),
                    published_date=entry.get("published", ""),
                )

                # Skip if already exists
                if self.article_exists(article.article_id):
                    continue

                articles.append(article)
                self.stats["articles_crawled"] += 1

                # Rate limiting
                await asyncio.sleep(CrawlerConfig.REQUEST_DELAY_SECONDS)

        except Exception as e:
            logger.error(f"Error crawling {source_key}: {e}")
            self.stats["errors"] += 1

        return articles

    async def crawl_article_content(self, article: CrawledArticle) -> CrawledArticle:
        """Fetch and parse full article content."""
        try:
            html = await self.fetch_url(article.url)
            if not html:
                return article

            soup = BeautifulSoup(html, "lxml")

            # Try common article selectors
            content_selectors = [
                "article .entry-content",
                "article .post-content",
                ".article-content",
                ".post-body",
                ".entry-content",
                "article p",
            ]

            for selector in content_selectors:
                content = soup.select(selector)
                if content:
                    article.full_text = " ".join(
                        p.get_text(strip=True) for p in content
                    )
                    break

            # Extract politicians mentioned
            if article.full_text:
                article.politicians_mentioned = extract_politicians_from_text(
                    article.full_text
                )

        except Exception as e:
            logger.error(f"Error fetching article content: {e}")

        return article

    async def crawl_all_sources(self) -> List[CrawledArticle]:
        """Crawl all configured news sources."""
        self.status = CrawlerStatus.RUNNING
        all_articles = []

        for source_key in self.sources:
            logger.info(f"Crawling {source_key}...")
            articles = await self.crawl_rss_feed(source_key)

            # Fetch full content for each article
            for article in articles:
                article = await self.crawl_article_content(article)
                if await self.save_article(article):
                    all_articles.append(article)

        self.status = CrawlerStatus.IDLE
        self.stats["last_run"] = datetime.utcnow().isoformat()
        logger.info(f"Crawl complete. Saved {len(all_articles)} new articles.")
        return all_articles

    def _clean_html(self, html: str) -> str:
        """Remove HTML tags from text."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(strip=True)


# ===========================================
# ELECTION DATA CRAWLER
# ===========================================

class ElectionCrawler(BaseCrawler):
    """Crawls INEC election results."""

    async def crawl_election_results(
        self,
        year: int,
        election_type: str,
        state: str = None
    ) -> List[Dict]:
        """
        Crawl election results from INEC.

        Args:
            year: Election year (e.g., 2023)
            election_type: presidential, gubernatorial, senatorial, house_of_reps
            state: Optional state filter
        """
        self.status = CrawlerStatus.RUNNING
        results = []

        # This would connect to INEC's API or scrape their results pages
        # For now, this is a placeholder for the actual implementation
        logger.info(f"Crawling {year} {election_type} results...")

        # The actual implementation would:
        # 1. Fetch state-by-state results
        # 2. Parse LGA-level data
        # 3. Extract candidate votes
        # 4. Save to ElectionResult table

        self.status = CrawlerStatus.IDLE
        return results


# ===========================================
# HISTORICAL DATA CRAWLER
# ===========================================

class HistoricalCrawler(BaseCrawler):
    """Crawls historical data from Internet Archive and Wikipedia."""

    async def crawl_wayback_machine(self, url: str, target_date: str) -> Optional[str]:
        """Fetch historical version of a page from Wayback Machine."""
        wayback_url = f"https://web.archive.org/web/{target_date}/{url}"
        return await self.fetch_url(wayback_url)

    async def crawl_wikipedia_article(self, title: str) -> Optional[Dict]:
        """Fetch Wikipedia article content."""
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

        try:
            response = await self.client.get(api_url)
            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get("title"),
                    "extract": data.get("extract"),
                    "url": data.get("content_urls", {}).get("desktop", {}).get("page"),
                }
        except Exception as e:
            logger.error(f"Wikipedia fetch error for {title}: {e}")

        return None

    async def crawl_wikidata_entity(self, qid: str) -> Optional[Dict]:
        """Fetch Wikidata entity."""
        api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

        try:
            response = await self.client.get(api_url)
            if response.status_code == 200:
                data = response.json()
                return data.get("entities", {}).get(qid)
        except Exception as e:
            logger.error(f"Wikidata fetch error for {qid}: {e}")

        return None


# ===========================================
# BUDGET DATA CRAWLER
# ===========================================

class BudgetCrawler(BaseCrawler):
    """Crawls budget data from BudgIT and related sources."""

    async def crawl_faac_distributions(self, year: int, month: int) -> List[Dict]:
        """Crawl FAAC distribution data."""
        # This would connect to BudgIT's API or scrape their data
        logger.info(f"Crawling FAAC data for {year}/{month}...")
        return []

    async def crawl_constituency_projects(self, state: str, year: int) -> List[Dict]:
        """Crawl constituency project data."""
        logger.info(f"Crawling constituency projects for {state} ({year})...")
        return []


# ===========================================
# UNIFIED CRAWLER SCHEDULER
# ===========================================

class UnifiedCrawlerScheduler:
    """
    Manages all crawler schedules.
    Runs as a background service on Railway.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.crawlers = {
            "news": NewsCrawler,
            "election": ElectionCrawler,
            "historical": HistoricalCrawler,
            "budget": BudgetCrawler,
        }
        self.running = False

    def setup_schedules(self):
        """Configure crawler schedules."""

        # News crawling - every 30 minutes
        self.scheduler.add_job(
            self._run_news_crawler,
            trigger=IntervalTrigger(minutes=30),
            id="news_crawler",
            name="News Crawler",
            replace_existing=True,
        )

        # Election data - daily at 2 AM
        self.scheduler.add_job(
            self._run_election_crawler,
            trigger=CronTrigger(hour=2, minute=0),
            id="election_crawler",
            name="Election Crawler",
            replace_existing=True,
        )

        # Historical backfill - weekly on Sunday at 3 AM
        self.scheduler.add_job(
            self._run_historical_crawler,
            trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="historical_crawler",
            name="Historical Crawler",
            replace_existing=True,
        )

        # Budget data - daily at 4 AM
        self.scheduler.add_job(
            self._run_budget_crawler,
            trigger=CronTrigger(hour=4, minute=0),
            id="budget_crawler",
            name="Budget Crawler",
            replace_existing=True,
        )

        logger.info("Crawler schedules configured")

    async def _run_news_crawler(self):
        """Run news crawler job."""
        async with NewsCrawler() as crawler:
            await crawler.crawl_all_sources()

    async def _run_election_crawler(self):
        """Run election crawler job."""
        async with ElectionCrawler() as crawler:
            # Crawl recent elections
            current_year = datetime.now().year
            await crawler.crawl_election_results(current_year, "gubernatorial")

    async def _run_historical_crawler(self):
        """Run historical crawler job."""
        async with HistoricalCrawler() as crawler:
            # Crawl Nigerian political Wikipedia articles
            articles = [
                "Nigerian_presidential_election,_2023",
                "Bola_Tinubu",
                "Atiku_Abubakar",
                "Nigerian_Senate",
            ]
            for article in articles:
                await crawler.crawl_wikipedia_article(article)
                await asyncio.sleep(1)

    async def _run_budget_crawler(self):
        """Run budget crawler job."""
        async with BudgetCrawler() as crawler:
            current_year = datetime.now().year
            await crawler.crawl_faac_distributions(current_year, datetime.now().month)

    def start(self):
        """Start the scheduler."""
        self.setup_schedules()
        self.scheduler.start()
        self.running = True
        logger.info("Unified Crawler Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        self.running = False
        logger.info("Unified Crawler Scheduler stopped")

    async def run_now(self, crawler_type: str):
        """Manually trigger a crawler."""
        crawler_map = {
            "news": self._run_news_crawler,
            "election": self._run_election_crawler,
            "historical": self._run_historical_crawler,
            "budget": self._run_budget_crawler,
        }

        if crawler_type in crawler_map:
            await crawler_map[crawler_type]()
        else:
            raise ValueError(f"Unknown crawler type: {crawler_type}")


# ===========================================
# CLI ENTRY POINT
# ===========================================

async def main():
    """Main entry point for crawler service."""
    import argparse

    parser = argparse.ArgumentParser(description="Decide9ja Unified Crawler")
    parser.add_argument("--mode", choices=["schedule", "once", "news", "election", "historical", "budget"],
                        default="schedule", help="Crawler mode")
    args = parser.parse_args()

    if args.mode == "schedule":
        # Run as scheduled service
        scheduler = UnifiedCrawlerScheduler()
        scheduler.start()

        # Keep running
        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            scheduler.stop()

    elif args.mode == "once":
        # Run all crawlers once
        scheduler = UnifiedCrawlerScheduler()
        await scheduler.run_now("news")
        await scheduler.run_now("election")
        await scheduler.run_now("historical")
        await scheduler.run_now("budget")

    else:
        # Run specific crawler
        scheduler = UnifiedCrawlerScheduler()
        await scheduler.run_now(args.mode)


if __name__ == "__main__":
    asyncio.run(main())
