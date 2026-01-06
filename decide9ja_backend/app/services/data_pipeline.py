"""
Data Pipeline & Scrapers for Decide9ja
Handles news scraping, politician updates, and data synchronization
"""
import os
import re
import json
import hashlib
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from enum import Enum
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class DataSource(str, Enum):
    """Data sources for scraping."""
    INEC = "inec"
    NASS = "nass"
    PUNCH = "punch"
    GUARDIAN = "guardian"
    THISDAY = "thisday"
    VANGUARD = "vanguard"
    PREMIUM_TIMES = "premium_times"
    CHANNELS = "channels"
    SAHARA_REPORTERS = "sahara_reporters"


class ScrapedItem(BaseModel):
    """A scraped data item."""
    source: DataSource
    item_type: str  # news, politician, election, factcheck
    title: str
    content: str
    url: str
    published_at: Optional[datetime] = None
    scraped_at: datetime
    content_hash: str
    metadata: Dict[str, Any] = {}


class PipelineRun(BaseModel):
    """Record of a pipeline execution."""
    run_id: str
    pipeline_name: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: PipelineStatus
    items_scraped: int = 0
    items_stored: int = 0
    errors: List[str] = []
    duration_seconds: Optional[float] = None


class DataPipelineService:
    """
    Service for managing data pipelines and scrapers.
    """

    # In-memory storage
    _runs: Dict[str, PipelineRun] = {}
    _scraped_hashes: set = set()  # For deduplication
    _news_cache: List[ScrapedItem] = []

    # Source configurations
    NEWS_SOURCES = {
        DataSource.PUNCH: {
            "name": "Punch Nigeria",
            "base_url": "https://punchng.com",
            "politics_url": "https://punchng.com/topics/politics/",
            "selectors": {
                "articles": "article.post-item",
                "title": "h2.post-title a",
                "link": "h2.post-title a",
                "date": "time.post-date"
            }
        },
        DataSource.GUARDIAN: {
            "name": "The Guardian Nigeria",
            "base_url": "https://guardian.ng",
            "politics_url": "https://guardian.ng/category/politics/",
            "selectors": {
                "articles": "article",
                "title": "h2 a",
                "link": "h2 a",
                "date": ".post-date"
            }
        },
        DataSource.VANGUARD: {
            "name": "Vanguard News",
            "base_url": "https://www.vanguardngr.com",
            "politics_url": "https://www.vanguardngr.com/category/politics/",
            "selectors": {
                "articles": "article",
                "title": ".entry-title a",
                "link": ".entry-title a",
                "date": ".entry-date"
            }
        },
        DataSource.PREMIUM_TIMES: {
            "name": "Premium Times",
            "base_url": "https://www.premiumtimesng.com",
            "politics_url": "https://www.premiumtimesng.com/category/news/politics",
            "selectors": {
                "articles": "article.jeg_post",
                "title": ".jeg_post_title a",
                "link": ".jeg_post_title a",
                "date": ".jeg_meta_date"
            }
        },
        DataSource.CHANNELS: {
            "name": "Channels TV",
            "base_url": "https://www.channelstv.com",
            "politics_url": "https://www.channelstv.com/category/politics/",
            "selectors": {
                "articles": "article",
                "title": "h2 a",
                "link": "h2 a",
                "date": ".date"
            }
        }
    }

    # Official data sources
    OFFICIAL_SOURCES = {
        DataSource.INEC: {
            "name": "INEC Nigeria",
            "base_url": "https://inecnigeria.org",
            "endpoints": {
                "elections": "/elections/",
                "results": "/election-results/",
                "voter_education": "/voter-education/"
            }
        },
        DataSource.NASS: {
            "name": "National Assembly",
            "base_url": "https://nass.gov.ng",
            "endpoints": {
                "members": "/members/",
                "bills": "/documents/bills/",
                "proceedings": "/documents/votes-proceedings/"
            }
        }
    }

    @classmethod
    def _generate_run_id(cls) -> str:
        """Generate unique run ID."""
        import uuid
        return f"run_{uuid.uuid4().hex[:12]}"

    @classmethod
    def _hash_content(cls, content: str) -> str:
        """Generate hash for content deduplication."""
        return hashlib.md5(content.encode()).hexdigest()

    @classmethod
    async def _fetch_url(cls, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch URL content with proper error handling."""
        try:
            import httpx

            headers = {
                "User-Agent": "Decide9ja Bot/1.0 (https://decide9ja.ng; civic education)",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-NG,en;q=0.9"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    follow_redirects=True
                )

                if response.status_code == 200:
                    return response.text
                else:
                    logger.warning(f"Failed to fetch {url}: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    @classmethod
    async def scrape_news_source(cls, source: DataSource) -> List[ScrapedItem]:
        """Scrape news from a single source."""
        if source not in cls.NEWS_SOURCES:
            logger.warning(f"Unknown news source: {source}")
            return []

        config = cls.NEWS_SOURCES[source]
        items = []

        try:
            html = await cls._fetch_url(config["politics_url"])
            if not html:
                return []

            # Parse HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            selectors = config["selectors"]
            articles = soup.select(selectors["articles"])[:20]  # Limit to 20

            for article in articles:
                try:
                    # Extract title
                    title_elem = article.select_one(selectors["title"])
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    # Extract link
                    link_elem = article.select_one(selectors["link"])
                    if not link_elem:
                        continue
                    link = link_elem.get("href", "")
                    if not link.startswith("http"):
                        link = urljoin(config["base_url"], link)

                    # Extract date if available
                    date_elem = article.select_one(selectors["date"])
                    published_at = None
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        published_at = cls._parse_date(date_text)

                    # Create content hash for deduplication
                    content_hash = cls._hash_content(f"{title}{link}")

                    if content_hash in cls._scraped_hashes:
                        continue  # Skip duplicates

                    item = ScrapedItem(
                        source=source,
                        item_type="news",
                        title=title,
                        content="",  # Would need to fetch full article
                        url=link,
                        published_at=published_at,
                        scraped_at=datetime.utcnow(),
                        content_hash=content_hash,
                        metadata={
                            "source_name": config["name"]
                        }
                    )

                    items.append(item)
                    cls._scraped_hashes.add(content_hash)

                except Exception as e:
                    logger.error(f"Error parsing article from {source}: {e}")
                    continue

            logger.info(f"Scraped {len(items)} articles from {source.value}")

        except ImportError:
            logger.error("beautifulsoup4 not installed. Run: pip install beautifulsoup4")
        except Exception as e:
            logger.error(f"Error scraping {source}: {e}")

        return items

    @classmethod
    def _parse_date(cls, date_text: str) -> Optional[datetime]:
        """Parse date from various formats."""
        import re

        date_text = date_text.strip()

        # Common patterns
        patterns = [
            (r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})",
             "%d %b %Y"),
            (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
            (r"(\d{1,2})/(\d{1,2})/(\d{4})", "%m/%d/%Y"),
        ]

        for pattern, date_format in patterns:
            match = re.search(pattern, date_text, re.IGNORECASE)
            if match:
                try:
                    # Reconstruct date string based on groups
                    if "Jan" in pattern:
                        date_str = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                    else:
                        date_str = match.group(0)
                    return datetime.strptime(date_str, date_format)
                except ValueError:
                    continue

        # Handle relative dates
        if "hour" in date_text.lower() or "minute" in date_text.lower():
            return datetime.utcnow()
        if "yesterday" in date_text.lower():
            return datetime.utcnow() - timedelta(days=1)
        if "day" in date_text.lower():
            match = re.search(r"(\d+)\s*day", date_text.lower())
            if match:
                days = int(match.group(1))
                return datetime.utcnow() - timedelta(days=days)

        return None

    @classmethod
    async def run_news_pipeline(cls) -> PipelineRun:
        """Run the news scraping pipeline."""
        run = PipelineRun(
            run_id=cls._generate_run_id(),
            pipeline_name="news_scraper",
            started_at=datetime.utcnow(),
            status=PipelineStatus.RUNNING
        )
        cls._runs[run.run_id] = run

        all_items = []
        errors = []

        # Scrape each source concurrently
        tasks = [
            cls.scrape_news_source(source)
            for source in cls.NEWS_SOURCES.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for source, result in zip(cls.NEWS_SOURCES.keys(), results):
            if isinstance(result, Exception):
                errors.append(f"{source.value}: {str(result)}")
            else:
                all_items.extend(result)

        # Store items
        cls._news_cache = all_items

        # Update run status
        run.finished_at = datetime.utcnow()
        run.items_scraped = len(all_items)
        run.items_stored = len(all_items)
        run.errors = errors
        run.duration_seconds = (run.finished_at - run.started_at).total_seconds()

        if errors and not all_items:
            run.status = PipelineStatus.FAILED
        elif errors:
            run.status = PipelineStatus.PARTIAL
        else:
            run.status = PipelineStatus.SUCCESS

        logger.info(
            f"News pipeline completed: {run.items_scraped} items, "
            f"{len(errors)} errors, {run.duration_seconds:.1f}s"
        )

        return run

    @classmethod
    async def scrape_inec_elections(cls) -> List[Dict[str, Any]]:
        """Scrape election information from INEC."""
        # Note: In production, this would scrape the actual INEC website
        # For now, return sample data structure
        elections = [
            {
                "name": "Presidential Election 2027",
                "type": "Presidential",
                "date": "2027-02-25",
                "registration_deadline": "2026-12-31",
                "status": "upcoming",
                "source": "INEC"
            },
            {
                "name": "Governorship Elections 2027",
                "type": "Governorship",
                "date": "2027-03-11",
                "states": ["All 36 states + FCT"],
                "status": "upcoming",
                "source": "INEC"
            }
        ]

        logger.info(f"Retrieved {len(elections)} elections from INEC")
        return elections

    @classmethod
    async def scrape_nass_members(cls) -> List[Dict[str, Any]]:
        """Scrape National Assembly member information."""
        # Note: In production, this would scrape the actual NASS website
        # For now, return sample structure
        members = []

        logger.info(f"Retrieved {len(members)} NASS members")
        return members

    @classmethod
    async def fetch_article_content(cls, url: str) -> Optional[str]:
        """Fetch full article content from URL."""
        html = await cls._fetch_url(url)
        if not html:
            return None

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted elements
            for element in soup.find_all(["script", "style", "nav", "footer", "aside"]):
                element.decompose()

            # Try to find article content
            article = (
                soup.find("article") or
                soup.find(class_=re.compile(r"post-content|article-body|entry-content")) or
                soup.find("main")
            )

            if article:
                # Extract text
                paragraphs = article.find_all("p")
                content = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                return content[:5000]  # Limit to 5000 chars

            return None

        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None

    @classmethod
    def get_recent_news(
        cls,
        limit: int = 20,
        source: Optional[DataSource] = None,
        keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recently scraped news items."""
        items = cls._news_cache

        if source:
            items = [i for i in items if i.source == source]

        if keyword:
            keyword_lower = keyword.lower()
            items = [i for i in items if keyword_lower in i.title.lower()]

        # Sort by scraped date
        items = sorted(items, key=lambda x: x.scraped_at, reverse=True)

        return [
            {
                "title": i.title,
                "url": i.url,
                "source": i.source.value,
                "source_name": i.metadata.get("source_name", i.source.value),
                "published_at": i.published_at.isoformat() if i.published_at else None,
                "scraped_at": i.scraped_at.isoformat()
            }
            for i in items[:limit]
        ]

    @classmethod
    def get_pipeline_runs(
        cls,
        pipeline_name: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get pipeline execution history."""
        runs = list(cls._runs.values())

        if pipeline_name:
            runs = [r for r in runs if r.pipeline_name == pipeline_name]

        runs = sorted(runs, key=lambda x: x.started_at, reverse=True)

        return [
            {
                "run_id": r.run_id,
                "pipeline_name": r.pipeline_name,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "status": r.status.value,
                "items_scraped": r.items_scraped,
                "items_stored": r.items_stored,
                "errors": r.errors,
                "duration_seconds": r.duration_seconds
            }
            for r in runs[:limit]
        ]

    @classmethod
    def get_pipeline_stats(cls) -> Dict[str, Any]:
        """Get pipeline statistics."""
        runs = list(cls._runs.values())
        total_runs = len(runs)
        successful_runs = len([r for r in runs if r.status == PipelineStatus.SUCCESS])
        failed_runs = len([r for r in runs if r.status == PipelineStatus.FAILED])

        total_items = sum(r.items_scraped for r in runs)
        avg_duration = (
            sum(r.duration_seconds or 0 for r in runs) / total_runs
            if total_runs > 0 else 0
        )

        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "partial_runs": total_runs - successful_runs - failed_runs,
            "success_rate": round(successful_runs / total_runs * 100, 1) if total_runs > 0 else 0,
            "total_items_scraped": total_items,
            "average_duration_seconds": round(avg_duration, 1),
            "news_cache_size": len(cls._news_cache),
            "unique_hashes": len(cls._scraped_hashes)
        }


class PipelineScheduler:
    """
    Scheduler for running data pipelines.
    """

    _scheduled_pipelines: Dict[str, Dict] = {}
    _running: bool = False

    @classmethod
    async def schedule_pipeline(
        cls,
        name: str,
        pipeline_func: Callable,
        interval_minutes: int = 60
    ):
        """Schedule a pipeline to run at regular intervals."""
        cls._scheduled_pipelines[name] = {
            "func": pipeline_func,
            "interval_minutes": interval_minutes,
            "last_run": None,
            "next_run": datetime.utcnow()
        }
        logger.info(f"Scheduled pipeline '{name}' every {interval_minutes} minutes")

    @classmethod
    async def start(cls):
        """Start the scheduler."""
        if cls._running:
            logger.warning("Scheduler already running")
            return

        cls._running = True
        logger.info("Pipeline scheduler started")

        while cls._running:
            try:
                now = datetime.utcnow()

                for name, config in cls._scheduled_pipelines.items():
                    if config["next_run"] <= now:
                        logger.info(f"Running scheduled pipeline: {name}")

                        try:
                            await config["func"]()
                            config["last_run"] = now
                            config["next_run"] = now + timedelta(minutes=config["interval_minutes"])
                        except Exception as e:
                            logger.error(f"Scheduled pipeline '{name}' failed: {e}")
                            config["next_run"] = now + timedelta(minutes=5)  # Retry in 5 min

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)

    @classmethod
    def stop(cls):
        """Stop the scheduler."""
        cls._running = False
        logger.info("Pipeline scheduler stopped")

    @classmethod
    def get_schedule_status(cls) -> Dict[str, Any]:
        """Get current scheduler status."""
        return {
            "running": cls._running,
            "pipelines": {
                name: {
                    "interval_minutes": config["interval_minutes"],
                    "last_run": config["last_run"].isoformat() if config["last_run"] else None,
                    "next_run": config["next_run"].isoformat() if config["next_run"] else None
                }
                for name, config in cls._scheduled_pipelines.items()
            }
        }
