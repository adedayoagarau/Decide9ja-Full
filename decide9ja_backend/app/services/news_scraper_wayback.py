"""
Wayback Machine News Scraper
============================
Fetches Nigerian political news from Archive.org Wayback Machine.

Use cases:
1. Historical articles for knowledge base enrichment
2. Fallback when direct scraping fails (Cloudflare, rate limits)
3. Archived versions of articles that have been removed

Archive.org APIs:
- Availability API: https://archive.org/wayback/available?url=example.com
- CDX API: https://web.archive.org/cdx/search/cdx?url=example.com&output=json
"""

import asyncio
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Wayback Machine endpoints
WAYBACK_AVAILABILITY_API = "https://archive.org/wayback/available"
WAYBACK_CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK_WEB_PREFIX = "https://web.archive.org/web"

# Nigerian news sources with their politics sections
NIGERIAN_NEWS_SOURCES = {
    "premium_times": {
        "domain": "premiumtimesng.com",
        "politics_path": "/category/news/political-news/",
        "name": "Premium Times"
    },
    "punch": {
        "domain": "punchng.com",
        "politics_path": "/topics/politics/",
        "name": "Punch NG"
    },
    "vanguard": {
        "domain": "vanguardngr.com",
        "politics_path": "/category/politics/",
        "name": "Vanguard"
    },
    "sahara_reporters": {
        "domain": "saharareporters.com",
        "politics_path": "/politics",
        "name": "Sahara Reporters"
    },
    "channels": {
        "domain": "channelstv.com",
        "politics_path": "/category/politics/",
        "name": "Channels TV"
    },
    "thecable": {
        "domain": "thecable.ng",
        "politics_path": "/category/politics/",
        "name": "The Cable"
    },
    "dailytrust": {
        "domain": "dailytrust.com",
        "politics_path": "/category/politics/",
        "name": "Daily Trust"
    },
    "guardian": {
        "domain": "guardian.ng",
        "politics_path": "/category/politics/",
        "name": "Guardian Nigeria"
    }
}

# Known politicians for entity extraction
POLITICIANS = [
    "tinubu", "atiku", "obi", "peter obi", "shettima", "kwankwaso",
    "wike", "sanwo-olu", "el-rufai", "fubara", "akpabio", "lawan",
    "gbajabiamila", "abbas", "obasanjo", "buhari", "jonathan",
    "saraki", "tambuwal", "okowa", "osinbajo", "ayu", "datti"
]


@dataclass
class ArchivedArticle:
    """Represents an article from Wayback Machine."""
    article_id: str
    title: str
    url: str  # Original URL
    archive_url: str  # Wayback URL
    source: str
    source_name: str
    excerpt: str
    full_text: str
    published_date: str
    archived_date: str
    politicians_mentioned: List[str]


class WaybackNewsScraper:
    """
    Scraper for Nigerian political news via Archive.org Wayback Machine.

    Features:
    - Search archived URLs matching patterns
    - Fetch historical snapshots of articles
    - Extract article content from archived pages
    - Handle rate limiting gracefully
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": "Decide9ja-Bot/1.0 (Nigerian Political Intelligence; contact@decide9ja.com)"
                }
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def check_availability(self, url: str) -> Optional[Dict]:
        """
        Check if a URL has been archived.

        Args:
            url: The URL to check

        Returns:
            Dict with archive info or None if not archived
        """
        try:
            client = await self._get_client()
            response = await client.get(
                WAYBACK_AVAILABILITY_API,
                params={"url": url}
            )
            response.raise_for_status()

            data = response.json()
            if data.get("archived_snapshots", {}).get("closest"):
                snapshot = data["archived_snapshots"]["closest"]
                return {
                    "available": snapshot.get("available", False),
                    "url": snapshot.get("url"),
                    "timestamp": snapshot.get("timestamp"),
                    "status": snapshot.get("status")
                }
            return None

        except Exception as e:
            logger.warning(f"Availability check failed for {url}: {e}")
            return None

    async def search_cdx(
        self,
        url_pattern: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Search the CDX index for archived URLs.

        Args:
            url_pattern: URL pattern to search (can include wildcards)
            from_date: Start date in YYYYMMDD format
            to_date: End date in YYYYMMDD format
            limit: Maximum results to return

        Returns:
            List of archive records with timestamp, url, status, etc.
        """
        try:
            client = await self._get_client()

            params = {
                "url": url_pattern,
                "output": "json",
                "limit": limit,
                "filter": "statuscode:200",  # Only successful captures
                "collapse": "urlkey",  # Deduplicate by URL
            }

            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date

            response = await client.get(WAYBACK_CDX_API, params=params)
            response.raise_for_status()

            # Parse CDX response (first row is headers)
            lines = response.text.strip().split("\n")
            if len(lines) < 2:
                return []

            # CDX columns: urlkey, timestamp, original, mimetype, statuscode, digest, length
            records = []
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 3:
                    records.append({
                        "timestamp": parts[1],
                        "original_url": parts[2],
                        "archive_url": f"{WAYBACK_WEB_PREFIX}/{parts[1]}/{parts[2]}"
                    })

            return records

        except Exception as e:
            logger.warning(f"CDX search failed for {url_pattern}: {e}")
            return []

    async def fetch_archived_page(self, archive_url: str) -> Optional[str]:
        """
        Fetch the HTML content of an archived page.

        Args:
            archive_url: Full Wayback Machine URL

        Returns:
            HTML content or None if failed
        """
        try:
            client = await self._get_client()
            response = await client.get(archive_url)
            response.raise_for_status()
            return response.text

        except Exception as e:
            logger.warning(f"Failed to fetch archived page {archive_url}: {e}")
            return None

    def _extract_article_content(
        self,
        html: str,
        source_key: str,
        original_url: str,
        archive_url: str,
        archived_timestamp: str
    ) -> Optional[ArchivedArticle]:
        """
        Extract article content from archived HTML.

        Args:
            html: Raw HTML content
            source_key: Key identifying the news source
            original_url: Original article URL
            archive_url: Wayback Machine URL
            archived_timestamp: When the page was archived (YYYYMMDDHHMMSS)

        Returns:
            ArchivedArticle or None if extraction failed
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove Wayback Machine toolbar
            for toolbar in soup.select('#wm-ipp-base, #wm-ipp'):
                toolbar.decompose()

            # Extract title
            title = None
            for selector in ['h1.entry-title', 'h1.post-title', 'h1.article-title', 'h1', 'title']:
                elem = soup.select_one(selector)
                if elem:
                    title = elem.get_text(strip=True)
                    break

            if not title:
                return None

            # Clean title (remove site name suffixes)
            title = re.sub(r'\s*[-|]\s*(Premium Times|Punch|Vanguard|Sahara Reporters|Channels TV|The Cable|Daily Trust|Guardian).*$', '', title, flags=re.IGNORECASE)

            # Extract article body
            content = ""
            for selector in [
                'article .entry-content',
                'article .post-content',
                '.article-content',
                '.post-body',
                'article p',
                '.entry-content p'
            ]:
                elems = soup.select(selector)
                if elems:
                    content = " ".join(p.get_text(strip=True) for p in elems)
                    break

            if not content:
                # Fallback: get all paragraphs
                paragraphs = soup.find_all('p')
                content = " ".join(p.get_text(strip=True) for p in paragraphs[:10])

            # Create excerpt
            excerpt = content[:500] + "..." if len(content) > 500 else content

            # Extract politicians mentioned
            content_lower = content.lower()
            politicians = [p for p in POLITICIANS if p in content_lower]

            # Parse archived timestamp
            archived_date = datetime.strptime(archived_timestamp[:8], "%Y%m%d").strftime("%Y-%m-%d")

            # Generate article ID
            article_id = hashlib.md5(original_url.encode()).hexdigest()[:16]

            source_info = NIGERIAN_NEWS_SOURCES.get(source_key, {})

            return ArchivedArticle(
                article_id=article_id,
                title=title,
                url=original_url,
                archive_url=archive_url,
                source=source_key,
                source_name=source_info.get("name", source_key),
                excerpt=excerpt,
                full_text=content[:5000],  # Limit to 5000 chars
                published_date=archived_date,  # Use archive date as proxy
                archived_date=archived_date,
                politicians_mentioned=politicians
            )

        except Exception as e:
            logger.warning(f"Failed to extract content from {archive_url}: {e}")
            return None

    async def search_archived_news(
        self,
        source_key: str,
        days_back: int = 30,
        limit: int = 50
    ) -> List[ArchivedArticle]:
        """
        Search for archived news articles from a specific source.

        Args:
            source_key: Key from NIGERIAN_NEWS_SOURCES
            days_back: How far back to search
            limit: Maximum articles to return

        Returns:
            List of ArchivedArticle objects
        """
        source_info = NIGERIAN_NEWS_SOURCES.get(source_key)
        if not source_info:
            logger.warning(f"Unknown source: {source_key}")
            return []

        domain = source_info["domain"]
        politics_path = source_info["politics_path"]

        # Calculate date range
        to_date = datetime.now().strftime("%Y%m%d")
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

        # Search CDX for politics articles
        url_pattern = f"https://{domain}{politics_path}*"
        logger.info(f"Searching Wayback for: {url_pattern} ({from_date} to {to_date})")

        records = await self.search_cdx(
            url_pattern=url_pattern,
            from_date=from_date,
            to_date=to_date,
            limit=limit * 2  # Get more to account for extraction failures
        )

        logger.info(f"Found {len(records)} archived URLs for {source_key}")

        # Fetch and extract articles
        articles = []
        for record in records[:limit]:
            # Rate limit
            await asyncio.sleep(0.5)

            html = await self.fetch_archived_page(record["archive_url"])
            if not html:
                continue

            article = self._extract_article_content(
                html=html,
                source_key=source_key,
                original_url=record["original_url"],
                archive_url=record["archive_url"],
                archived_timestamp=record["timestamp"]
            )

            if article:
                articles.append(article)
                logger.debug(f"Extracted: {article.title[:50]}...")

            if len(articles) >= limit:
                break

        logger.info(f"Extracted {len(articles)} articles from {source_key} via Wayback")
        return articles

    async def fetch_historical_articles(
        self,
        politician_name: str,
        year: int,
        limit: int = 20
    ) -> List[ArchivedArticle]:
        """
        Fetch historical articles about a specific politician from a given year.

        Args:
            politician_name: Name of the politician (e.g., "Tinubu")
            year: Year to search (e.g., 2015)
            limit: Maximum articles per source

        Returns:
            List of ArchivedArticle objects mentioning the politician
        """
        from_date = f"{year}0101"
        to_date = f"{year}1231"

        all_articles = []

        for source_key, source_info in NIGERIAN_NEWS_SOURCES.items():
            domain = source_info["domain"]

            # Search for articles
            url_pattern = f"https://{domain}/*{politician_name.lower()}*"

            records = await self.search_cdx(
                url_pattern=url_pattern,
                from_date=from_date,
                to_date=to_date,
                limit=limit
            )

            for record in records:
                await asyncio.sleep(0.5)

                html = await self.fetch_archived_page(record["archive_url"])
                if not html:
                    continue

                article = self._extract_article_content(
                    html=html,
                    source_key=source_key,
                    original_url=record["original_url"],
                    archive_url=record["archive_url"],
                    archived_timestamp=record["timestamp"]
                )

                if article and politician_name.lower() in article.full_text.lower():
                    all_articles.append(article)

        logger.info(f"Found {len(all_articles)} historical articles about {politician_name} in {year}")
        return all_articles

    async def get_article_from_archive(self, original_url: str) -> Optional[ArchivedArticle]:
        """
        Get an article from Wayback Machine by its original URL.

        Useful as fallback when direct scraping fails.

        Args:
            original_url: The original article URL

        Returns:
            ArchivedArticle or None if not available
        """
        # Check availability
        availability = await self.check_availability(original_url)
        if not availability or not availability.get("available"):
            return None

        archive_url = availability["url"]
        timestamp = availability["timestamp"]

        # Determine source
        source_key = None
        for key, info in NIGERIAN_NEWS_SOURCES.items():
            if info["domain"] in original_url:
                source_key = key
                break

        if not source_key:
            source_key = "unknown"

        # Fetch and extract
        html = await self.fetch_archived_page(archive_url)
        if not html:
            return None

        return self._extract_article_content(
            html=html,
            source_key=source_key,
            original_url=original_url,
            archive_url=archive_url,
            archived_timestamp=timestamp
        )


async def scrape_all_sources_from_wayback(
    days_back: int = 7,
    limit_per_source: int = 10
) -> List[ArchivedArticle]:
    """
    Scrape recent politics news from all sources via Wayback Machine.

    Args:
        days_back: How far back to search
        limit_per_source: Max articles per source

    Returns:
        List of all scraped articles
    """
    scraper = WaybackNewsScraper()
    all_articles = []

    try:
        for source_key in NIGERIAN_NEWS_SOURCES.keys():
            articles = await scraper.search_archived_news(
                source_key=source_key,
                days_back=days_back,
                limit=limit_per_source
            )
            all_articles.extend(articles)

            # Rate limit between sources
            await asyncio.sleep(1)

        logger.info(f"Total articles from Wayback: {len(all_articles)}")
        return all_articles

    finally:
        await scraper.close()


# CLI for testing
if __name__ == "__main__":
    import sys

    async def main():
        scraper = WaybackNewsScraper()

        try:
            if len(sys.argv) > 1:
                source = sys.argv[1]
                days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
                articles = await scraper.search_archived_news(source, days_back=days, limit=5)
            else:
                articles = await scrape_all_sources_from_wayback(days_back=7, limit_per_source=3)

            print(f"\nFound {len(articles)} articles:\n")
            for article in articles:
                print(f"  [{article.source_name}] {article.title[:60]}...")
                print(f"    Date: {article.published_date}")
                print(f"    Politicians: {', '.join(article.politicians_mentioned) or 'None detected'}")
                print(f"    Archive: {article.archive_url[:80]}...")
                print()

        finally:
            await scraper.close()

    asyncio.run(main())
