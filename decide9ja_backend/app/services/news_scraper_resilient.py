"""
Resilient Nigerian News Scraper for Decide9ja.

This module provides robust news scraping with:
- Retry logic with exponential backoff
- Source health tracking (skip consistently failing sources)
- Rate limiting between requests
- Fallback to RSS when scraping fails
- Comprehensive error handling and logging

Usage:
    from app.services.news_scraper_resilient import ResilientNewsScraper

    scraper = ResilientNewsScraper()
    articles = scraper.scrape_all_sources()
"""

import os
import re
import json
import time
import logging
import hashlib
import functools
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from threading import Lock

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Rate limiting: minimum seconds between requests to same domain
RATE_LIMIT_SECONDS = 2.0

# Retry configuration
MAX_RETRIES = 3
BASE_RETRY_DELAY = 2.0
MAX_RETRY_DELAY = 30.0

# Source health thresholds
MAX_CONSECUTIVE_FAILURES = 5
HEALTH_RECOVERY_HOURS = 1

# Request timeout
REQUEST_TIMEOUT = 15


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class NewsArticle:
    """Scraped news article."""
    id: str
    title: str
    url: str
    source: str
    source_name: str
    excerpt: str
    published_date: Optional[str]
    scraped_at: str
    politicians_mentioned: List[str]
    topics: List[str]
    full_text: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourceHealth:
    """Health status of a news source."""
    source_key: str
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_error: Optional[str] = None
    is_healthy: bool = True
    using_fallback: bool = False


@dataclass
class ScrapeResult:
    """Result of scraping a source."""
    source_key: str
    articles: List[NewsArticle] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None
    used_fallback: bool = False
    retry_count: int = 0
    duration_seconds: float = 0.0


# =============================================================================
# Source Configuration
# =============================================================================

NEWS_SOURCES = {
    "premium_times": {
        "name": "Premium Times",
        "base_url": "https://www.premiumtimesng.com",
        "politics_url": "https://www.premiumtimesng.com/category/news/political-news",
        "rss_url": "https://www.premiumtimesng.com/feed",
        "selectors": {
            "articles": "article",
            "title": "h3 a, h2 a, .entry-title a, .td-module-title a",
            "link": "h3 a, h2 a, .entry-title a, .td-module-title a",
            "excerpt": "p, .excerpt, .td-excerpt",
            "date": "time, .td-post-date"
        }
    },
    "punch": {
        "name": "Punch NG",
        "base_url": "https://punchng.com",
        "politics_url": "https://punchng.com/topics/politics/",
        "rss_url": "https://punchng.com/feed/",
        "selectors": {
            "articles": "article, .post",
            "title": "h3 a, h2 a, .entry-title a, .post-title a",
            "link": "h3 a, h2 a, .entry-title a, .post-title a",
            "excerpt": "p, .excerpt, .entry-summary",
            "date": "time, .date"
        }
    },
    "sahara_reporters": {
        "name": "Sahara Reporters",
        "base_url": "https://saharareporters.com",
        "politics_url": "https://saharareporters.com/politics",
        "rss_url": "https://saharareporters.com/rss.xml",
        "selectors": {
            "articles": "article, .node--type-article, .views-row, .card",
            "title": "h2 a, h3 a, .field--name-title a, .card-title a",
            "link": "h2 a, h3 a, .field--name-title a, .card-title a",
            "excerpt": ".field--name-body p, .teaser-text, .card-text",
            "date": "time, .field--name-created"
        }
    },
    "vanguard": {
        "name": "Vanguard",
        "base_url": "https://www.vanguardngr.com",
        "politics_url": "https://www.vanguardngr.com/category/politics/",
        "rss_url": "https://www.vanguardngr.com/feed/",
        "selectors": {
            "articles": "article, .entry",
            "title": "h3 a, h2 a, .entry-title a",
            "link": "h3 a, h2 a, .entry-title a",
            "excerpt": "p, .entry-summary",
            "date": "time"
        }
    },
    "channels": {
        "name": "Channels TV",
        "base_url": "https://www.channelstv.com",
        "politics_url": "https://www.channelstv.com/category/politics/",
        "rss_url": "https://www.channelstv.com/feed/",
        "selectors": {
            "articles": "article, .post",
            "title": "h2 a, h3 a, .entry-title a",
            "link": "h2 a, h3 a, .entry-title a",
            "excerpt": "p, .entry-content p",
            "date": "time"
        }
    },
    "thecable": {
        "name": "The Cable",
        "base_url": "https://www.thecable.ng",
        "politics_url": "https://www.thecable.ng/category/politics",
        "rss_url": "https://www.thecable.ng/feed",
        "selectors": {
            "articles": ".td-block-span6, .td-module-container, article, .post-item",
            "title": "h3 a, .td-module-title a, .entry-title a",
            "link": "h3 a, .td-module-title a, .entry-title a",
            "excerpt": ".td-excerpt, .entry-summary, p",
            "date": "time, .td-post-date, .date"
        }
    },
    "dailytrust": {
        "name": "Daily Trust",
        "base_url": "https://dailytrust.com",
        "politics_url": "https://dailytrust.com/category/politics/",
        "rss_url": "https://dailytrust.com/feed/",
        "selectors": {
            "articles": ".jeg_post, article, .post, .article-item",
            "title": ".jeg_post_title a, h2 a, h3 a, .title a",
            "link": ".jeg_post_title a, h2 a, h3 a, .title a",
            "excerpt": ".jeg_post_excerpt, p, .excerpt",
            "date": ".jeg_meta_date, time"
        }
    },
    "guardian": {
        "name": "The Guardian Nigeria",
        "base_url": "https://guardian.ng",
        "politics_url": "https://guardian.ng/category/politics/",
        "rss_url": "https://guardian.ng/feed/",
        "selectors": {
            "articles": ".single-post, article, .post, .item",
            "title": "h2 a, h3 a, .post-title a, .title a",
            "link": "h2 a, h3 a, .post-title a, .title a",
            "excerpt": ".post-excerpt, p",
            "date": "time, .post-date"
        }
    }
}


# Politicians and topics to track
TRACKED_POLITICIANS = [
    "Tinubu", "Bola Tinubu", "Atiku", "Peter Obi", "Kwankwaso",
    "Akpabio", "Godswill Akpabio", "Abbas", "Tajudeen Abbas",
    "Shettima", "Kashim Shettima", "Fubara", "Wike", "Sanwo-Olu",
    "El-Rufai", "Adelabu", "Fashola", "Osinbajo", "Buhari",
    "Makinde", "Adeleke", "Ganduje", "Umahi", "Soludo"
]

POLITICAL_TOPICS = [
    "naira", "fuel", "subsidy", "budget", "election", "INEC",
    "NASS", "senate", "house of reps", "governor", "minister",
    "security", "economy", "corruption", "EFCC", "police",
    "power", "grid collapse", "nerc", "disco", "electricity",
    "road", "highway", "infrastructure", "flooding", "healthcare"
]


# =============================================================================
# Helper Functions
# =============================================================================

def get_headers() -> Dict[str, str]:
    """Get randomized headers to avoid detection."""
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
    ]
    import random
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
    }


def generate_article_id(url: str) -> str:
    """Generate unique ID from URL."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def extract_politicians(text: str) -> List[str]:
    """Extract mentioned politicians from text."""
    mentioned = []
    text_lower = text.lower()

    for politician in TRACKED_POLITICIANS:
        if politician.lower() in text_lower:
            mentioned.append(politician)

    return list(set(mentioned))


def extract_topics(text: str) -> List[str]:
    """Extract political topics from text."""
    topics = []
    text_lower = text.lower()

    for topic in POLITICAL_TOPICS:
        if topic.lower() in text_lower:
            topics.append(topic)

    return list(set(topics))


# =============================================================================
# Resilient News Scraper Class
# =============================================================================

class ResilientNewsScraper:
    """
    Resilient news scraper with retry logic, rate limiting, and fallbacks.
    """

    def __init__(self):
        self.source_health: Dict[str, SourceHealth] = {}
        self.last_request_time: Dict[str, float] = {}
        self._lock = Lock()

        # Initialize source health
        for source_key in NEWS_SOURCES:
            self.source_health[source_key] = SourceHealth(source_key=source_key)

    def _rate_limit(self, domain: str):
        """Apply rate limiting for a domain."""
        with self._lock:
            now = time.time()
            last_time = self.last_request_time.get(domain, 0)
            elapsed = now - last_time

            if elapsed < RATE_LIMIT_SECONDS:
                sleep_time = RATE_LIMIT_SECONDS - elapsed
                time.sleep(sleep_time)

            self.last_request_time[domain] = time.time()

    def _update_source_health(self, source_key: str, success: bool, error: Optional[str] = None):
        """Update health status for a source."""
        health = self.source_health[source_key]

        if success:
            health.consecutive_failures = 0
            health.total_successes += 1
            health.last_success = datetime.now()
            health.is_healthy = True
            health.using_fallback = False
        else:
            health.consecutive_failures += 1
            health.total_failures += 1
            health.last_failure = datetime.now()
            health.last_error = error

            # Mark as unhealthy if too many consecutive failures
            if health.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                health.is_healthy = False
                logger.warning(
                    f"Source {source_key} marked unhealthy after {health.consecutive_failures} failures"
                )

    def _should_skip_source(self, source_key: str) -> bool:
        """Check if a source should be skipped due to health issues."""
        health = self.source_health[source_key]

        if health.is_healthy:
            return False

        # Check if enough time has passed for recovery attempt
        if health.last_failure:
            recovery_time = health.last_failure + timedelta(hours=HEALTH_RECOVERY_HOURS)
            if datetime.now() >= recovery_time:
                logger.info(f"Attempting recovery for source {source_key}")
                return False

        return True

    def _fetch_with_retry(
        self,
        url: str,
        source_key: str,
        max_retries: int = MAX_RETRIES
    ) -> Optional[requests.Response]:
        """Fetch URL with retry logic and exponential backoff."""
        domain = NEWS_SOURCES[source_key]["base_url"]
        last_error = None

        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                self._rate_limit(domain)

                response = requests.get(
                    url,
                    headers=get_headers(),
                    timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                last_error = "Request timeout"
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{max_retries})")

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else None
                last_error = f"HTTP {status_code}"

                # Don't retry for certain status codes
                if status_code in [403, 404, 410]:
                    logger.warning(f"Permanent error {status_code} for {url}")
                    break

                logger.warning(f"HTTP error {status_code} for {url} (attempt {attempt + 1}/{max_retries})")

            except requests.exceptions.ConnectionError:
                last_error = "Connection error"
                logger.warning(f"Connection error for {url} (attempt {attempt + 1}/{max_retries})")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Error fetching {url}: {e} (attempt {attempt + 1}/{max_retries})")

            # Exponential backoff
            if attempt < max_retries - 1:
                delay = min(BASE_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                time.sleep(delay)

        return None

    def _scrape_html(self, source_key: str, max_articles: int = 10) -> List[NewsArticle]:
        """Scrape articles from HTML page."""
        source = NEWS_SOURCES[source_key]
        articles = []

        response = self._fetch_with_retry(source["politics_url"], source_key)
        if not response:
            return []

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            selectors = source["selectors"]

            article_elements = soup.select(selectors["articles"])[:max_articles]

            for element in article_elements:
                try:
                    # Extract title
                    title_elem = element.select_one(selectors["title"])
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue

                    # Extract link
                    link_elem = element.select_one(selectors["link"])
                    url = link_elem.get("href", "") if link_elem else ""
                    if not url:
                        continue
                    if not url.startswith("http"):
                        url = source["base_url"] + url

                    # Extract excerpt
                    excerpt_elem = element.select_one(selectors["excerpt"])
                    excerpt = excerpt_elem.get_text(strip=True)[:500] if excerpt_elem else ""

                    # Extract date
                    date_elem = element.select_one(selectors["date"])
                    pub_date = date_elem.get("datetime", date_elem.get_text(strip=True)) if date_elem else None

                    # Extract entities
                    combined_text = f"{title} {excerpt}"
                    politicians = extract_politicians(combined_text)
                    topics = extract_topics(combined_text)

                    article = NewsArticle(
                        id=generate_article_id(url),
                        title=title,
                        url=url,
                        source=source_key,
                        source_name=source["name"],
                        excerpt=excerpt,
                        published_date=pub_date,
                        scraped_at=datetime.now().isoformat(),
                        politicians_mentioned=politicians,
                        topics=topics,
                    )
                    articles.append(article)

                except Exception as e:
                    logger.debug(f"Error parsing article from {source_key}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing HTML from {source_key}: {e}")

        return articles

    def _scrape_rss_fallback(self, source_key: str, max_articles: int = 10) -> List[NewsArticle]:
        """Fallback to RSS feed when HTML scraping fails."""
        source = NEWS_SOURCES[source_key]
        rss_url = source.get("rss_url")

        if not rss_url:
            return []

        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed, RSS fallback unavailable")
            return []

        articles = []

        try:
            # Apply rate limiting
            self._rate_limit(source["base_url"])

            feed = feedparser.parse(rss_url)

            for entry in feed.entries[:max_articles]:
                try:
                    title = entry.get("title", "")
                    url = entry.get("link", "")

                    if not title or not url:
                        continue

                    excerpt = entry.get("summary", entry.get("description", ""))[:500]
                    pub_date = entry.get("published", entry.get("updated", ""))

                    # Extract entities
                    combined_text = f"{title} {excerpt}"
                    politicians = extract_politicians(combined_text)
                    topics = extract_topics(combined_text)

                    article = NewsArticle(
                        id=generate_article_id(url),
                        title=title,
                        url=url,
                        source=source_key,
                        source_name=source["name"],
                        excerpt=excerpt,
                        published_date=pub_date,
                        scraped_at=datetime.now().isoformat(),
                        politicians_mentioned=politicians,
                        topics=topics,
                    )
                    articles.append(article)

                except Exception as e:
                    logger.debug(f"Error parsing RSS entry from {source_key}: {e}")
                    continue

            logger.info(f"RSS fallback: Got {len(articles)} articles from {source['name']}")

        except Exception as e:
            logger.error(f"RSS fallback failed for {source_key}: {e}")

        return articles

    def scrape_source(self, source_key: str, max_articles: int = 10) -> ScrapeResult:
        """
        Scrape a single source with fallback logic.

        Returns:
            ScrapeResult with articles and metadata
        """
        start_time = time.time()
        result = ScrapeResult(source_key=source_key)

        # Check if source should be skipped
        if self._should_skip_source(source_key):
            result.error = "Source marked unhealthy, skipping"
            logger.info(f"Skipping unhealthy source: {source_key}")
            return result

        # Try HTML scraping first
        try:
            articles = self._scrape_html(source_key, max_articles)

            if articles:
                result.articles = articles
                result.success = True
                self._update_source_health(source_key, success=True)
                logger.info(f"✓ Scraped {len(articles)} articles from {source_key}")
            else:
                # Try RSS fallback
                logger.info(f"HTML scraping returned no articles, trying RSS fallback for {source_key}")
                articles = self._scrape_rss_fallback(source_key, max_articles)

                if articles:
                    result.articles = articles
                    result.success = True
                    result.used_fallback = True
                    self.source_health[source_key].using_fallback = True
                    self._update_source_health(source_key, success=True)
                    logger.info(f"✓ RSS fallback: {len(articles)} articles from {source_key}")
                else:
                    result.error = "No articles found from HTML or RSS"
                    self._update_source_health(source_key, success=False, error=result.error)
                    logger.warning(f"✗ No articles from {source_key}")

        except Exception as e:
            result.error = str(e)
            self._update_source_health(source_key, success=False, error=str(e))
            logger.error(f"✗ Failed to scrape {source_key}: {e}")

            # Try RSS as last resort
            try:
                articles = self._scrape_rss_fallback(source_key, max_articles)
                if articles:
                    result.articles = articles
                    result.success = True
                    result.used_fallback = True
                    logger.info(f"✓ Emergency RSS fallback: {len(articles)} articles from {source_key}")
            except Exception:
                pass

        result.duration_seconds = time.time() - start_time
        return result

    def scrape_all_sources(self, max_per_source: int = 10) -> List[NewsArticle]:
        """
        Scrape all configured sources.

        Returns:
            Combined list of articles from all sources
        """
        all_articles = []
        results = []

        for source_key in NEWS_SOURCES:
            result = self.scrape_source(source_key, max_per_source)
            results.append(result)
            all_articles.extend(result.articles)

        # Log summary
        successful = sum(1 for r in results if r.success)
        fallback_used = sum(1 for r in results if r.used_fallback)
        total_sources = len(NEWS_SOURCES)

        logger.info(
            f"Scraping complete: {successful}/{total_sources} sources successful, "
            f"{fallback_used} used fallback, {len(all_articles)} total articles"
        )

        return all_articles

    def get_source_health_report(self) -> Dict[str, Dict]:
        """Get health report for all sources."""
        return {
            source_key: {
                "is_healthy": health.is_healthy,
                "consecutive_failures": health.consecutive_failures,
                "total_successes": health.total_successes,
                "total_failures": health.total_failures,
                "using_fallback": health.using_fallback,
                "last_success": health.last_success.isoformat() if health.last_success else None,
                "last_failure": health.last_failure.isoformat() if health.last_failure else None,
                "last_error": health.last_error,
            }
            for source_key, health in self.source_health.items()
        }


# =============================================================================
# Module-level functions for backwards compatibility
# =============================================================================

_default_scraper: Optional[ResilientNewsScraper] = None


def get_scraper() -> ResilientNewsScraper:
    """Get or create default scraper instance."""
    global _default_scraper
    if _default_scraper is None:
        _default_scraper = ResilientNewsScraper()
    return _default_scraper


def scrape_all_sources(max_per_source: int = 10) -> List[NewsArticle]:
    """Scrape all sources using resilient scraper."""
    return get_scraper().scrape_all_sources(max_per_source)


def scrape_source(source_key: str, max_articles: int = 10) -> List[NewsArticle]:
    """Scrape a single source."""
    result = get_scraper().scrape_source(source_key, max_articles)
    return result.articles


def get_source_health() -> Dict[str, Dict]:
    """Get health report for all sources."""
    return get_scraper().get_source_health_report()


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Resilient Nigerian News Scraper")
    parser.add_argument("--max", type=int, default=5, help="Max articles per source")
    parser.add_argument("--source", type=str, help="Specific source to scrape")
    parser.add_argument("--health", action="store_true", help="Show source health report")

    args = parser.parse_args()

    scraper = ResilientNewsScraper()

    if args.health:
        report = scraper.get_source_health_report()
        print(json.dumps(report, indent=2))
    elif args.source:
        result = scraper.scrape_source(args.source, args.max)
        print(f"\nSource: {args.source}")
        print(f"Success: {result.success}")
        print(f"Used fallback: {result.used_fallback}")
        print(f"Articles: {len(result.articles)}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"Error: {result.error}")
        for article in result.articles:
            print(f"\n📰 {article.title}")
            print(f"   URL: {article.url}")
    else:
        articles = scraper.scrape_all_sources(args.max)
        print(f"\nTotal articles scraped: {len(articles)}")
        print("\nSource health:")
        print(json.dumps(scraper.get_source_health_report(), indent=2))
