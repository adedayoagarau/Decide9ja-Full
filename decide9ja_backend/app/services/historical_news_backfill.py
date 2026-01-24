"""
Historical News Backfill via Wayback Machine
=============================================
Backdates RSS feed crawling from 2010 to present using Archive.org.

Strategy:
1. Find Wayback snapshots of RSS feeds for each year
2. Parse archived feeds to get article URLs
3. Fetch archived versions of articles
4. Store with proper politician linking

Usage:
    python -m app.services.historical_news_backfill --year 2023 --limit 50
"""

import asyncio
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass, asdict

import httpx
from bs4 import BeautifulSoup

from app.database import SessionLocal, NewsArticle

logger = logging.getLogger(__name__)

# Wayback Machine endpoints
WAYBACK_CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK_WEB_PREFIX = "https://web.archive.org/web"

# Nigerian news RSS feeds with their archive history
RSS_FEEDS = {
    "punch": {
        "name": "Punch NG",
        "urls": [
            "https://punchng.com/feed/",
            "https://www.punchng.com/feed/",
        ],
        "archive_start": 2010,
    },
    "premium_times": {
        "name": "Premium Times",
        "urls": [
            "https://www.premiumtimesng.com/feed",
            "https://premiumtimesng.com/feed",
        ],
        "archive_start": 2011,
    },
    "vanguard": {
        "name": "Vanguard",
        "urls": [
            "https://www.vanguardngr.com/feed/",
            "https://vanguardngr.com/feed/",
        ],
        "archive_start": 2010,
    },
    "sahara_reporters": {
        "name": "Sahara Reporters",
        "urls": [
            "https://saharareporters.com/rss.xml",
            "https://www.saharareporters.com/rss.xml",
        ],
        "archive_start": 2008,
    },
    "channels": {
        "name": "Channels TV",
        "urls": [
            "https://www.channelstv.com/feed/",
            "https://channelstv.com/feed/",
        ],
        "archive_start": 2012,
    },
    "guardian": {
        "name": "Guardian Nigeria",
        "urls": [
            "https://guardian.ng/feed/",
            "https://www.guardian.ng/feed/",
        ],
        "archive_start": 2014,
    },
    "dailytrust": {
        "name": "Daily Trust",
        "urls": [
            "https://dailytrust.com/feed/",
            "https://www.dailytrust.com/feed/",
        ],
        "archive_start": 2012,
    },
    "thecable": {
        "name": "The Cable",
        "urls": [
            "https://www.thecable.ng/feed/",
            "https://thecable.ng/feed/",
        ],
        "archive_start": 2014,
    },
    "thisday": {
        "name": "ThisDay",
        "urls": [
            "https://www.thisdaylive.com/feed/",
            "https://thisdaylive.com/feed/",
        ],
        "archive_start": 2010,
    },
    "leadership": {
        "name": "Leadership",
        "urls": [
            "https://leadership.ng/feed/",
            "https://www.leadership.ng/feed/",
        ],
        "archive_start": 2012,
    },
}

# Known politicians for entity extraction
POLITICIANS = [
    "tinubu", "atiku", "obi", "peter obi", "shettima", "kwankwaso",
    "wike", "sanwo-olu", "el-rufai", "fubara", "akpabio", "lawan",
    "gbajabiamila", "abbas", "obasanjo", "buhari", "jonathan",
    "saraki", "tambuwal", "okowa", "osinbajo", "ayu", "datti",
    "makinde", "ganduje", "soludo", "umahi", "fashola", "adelabu",
    "adeleke", "uba sani", "abiodun", "oyetola", "fayemi",
]


@dataclass
class HistoricalArticle:
    """Represents a historical article from Wayback Machine."""
    article_id: str
    title: str
    url: str
    archive_url: str
    source: str
    source_name: str
    excerpt: str
    full_text: str
    published_date: str
    archived_date: str
    politicians_mentioned: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


class HistoricalNewsBackfill:
    """
    Backfill historical news from 2010 to present via Wayback Machine.

    Features:
    - Find RSS feed snapshots by year/month
    - Parse archived RSS feeds for article links
    - Fetch archived articles
    - Extract politician mentions
    - Store in database with deduplication
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self.stats = {
            "snapshots_found": 0,
            "feeds_parsed": 0,
            "articles_fetched": 0,
            "articles_stored": 0,
            "duplicates_skipped": 0,
            "errors": 0,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": "Decide9ja-HistoricalBot/1.0 (Nigerian Political Intelligence; contact@decide9ja.com)"
                }
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_rss_snapshots(
        self,
        feed_url: str,
        year: int,
        month: Optional[int] = None
    ) -> List[Dict]:
        """
        Get all Wayback snapshots of an RSS feed for a given year/month.

        Args:
            feed_url: The RSS feed URL
            year: Year to search
            month: Optional specific month (1-12)

        Returns:
            List of snapshot records with timestamp and archive URL
        """
        try:
            client = await self._get_client()

            # Build date range
            if month:
                from_date = f"{year}{month:02d}01"
                # Get last day of month
                if month == 12:
                    to_date = f"{year}1231"
                else:
                    next_month = datetime(year, month + 1, 1) - timedelta(days=1)
                    to_date = next_month.strftime("%Y%m%d")
            else:
                from_date = f"{year}0101"
                to_date = f"{year}1231"

            params = {
                "url": feed_url,
                "output": "json",
                "from": from_date,
                "to": to_date,
                "filter": "statuscode:200",
                "collapse": "timestamp:8",  # One per day
                "limit": 100,
            }

            response = await client.get(WAYBACK_CDX_API, params=params)
            response.raise_for_status()

            # Parse CDX response (first row is headers if JSON)
            try:
                data = response.json()
                if not data or len(data) < 2:
                    return []

                # Skip header row
                records = []
                for row in data[1:]:
                    if len(row) >= 3:
                        timestamp = row[1]
                        original_url = row[2]
                        records.append({
                            "timestamp": timestamp,
                            "original_url": original_url,
                            "archive_url": f"{WAYBACK_WEB_PREFIX}/{timestamp}/{original_url}"
                        })
                        self.stats["snapshots_found"] += 1

                return records

            except json.JSONDecodeError:
                # Fallback to text parsing
                lines = response.text.strip().split("\n")
                records = []
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 3:
                        records.append({
                            "timestamp": parts[1],
                            "original_url": parts[2],
                            "archive_url": f"{WAYBACK_WEB_PREFIX}/{parts[1]}/{parts[2]}"
                        })
                        self.stats["snapshots_found"] += 1
                return records

        except Exception as e:
            logger.warning(f"Error fetching snapshots for {feed_url} ({year}): {e}")
            self.stats["errors"] += 1
            return []

    async def parse_archived_rss(self, archive_url: str) -> List[Dict]:
        """
        Parse an archived RSS feed and extract article URLs.

        Args:
            archive_url: Wayback Machine URL of the RSS feed

        Returns:
            List of article info dicts with url, title, date
        """
        try:
            client = await self._get_client()
            response = await client.get(archive_url)
            response.raise_for_status()

            content = response.text
            self.stats["feeds_parsed"] += 1

            # Parse as XML/RSS
            soup = BeautifulSoup(content, 'xml')

            articles = []
            items = soup.find_all('item')

            for item in items:
                # Extract link
                link_elem = item.find('link')
                if not link_elem:
                    continue

                link = link_elem.get_text(strip=True)
                if not link:
                    continue

                # Extract title
                title_elem = item.find('title')
                title = title_elem.get_text(strip=True) if title_elem else ""

                # Extract date
                date_elem = item.find('pubDate')
                pub_date = date_elem.get_text(strip=True) if date_elem else None

                # Extract description/content
                desc_elem = item.find('description') or item.find('content:encoded')
                description = desc_elem.get_text(strip=True) if desc_elem else ""

                articles.append({
                    "url": link,
                    "title": title,
                    "pub_date": pub_date,
                    "description": description[:500] if description else "",
                })

            logger.debug(f"Parsed {len(articles)} articles from {archive_url}")
            return articles

        except Exception as e:
            logger.warning(f"Error parsing RSS {archive_url}: {e}")
            self.stats["errors"] += 1
            return []

    async def fetch_archived_article(
        self,
        original_url: str,
        timestamp: str,
        source_key: str
    ) -> Optional[HistoricalArticle]:
        """
        Fetch an archived article from Wayback Machine.

        Args:
            original_url: Original article URL
            timestamp: Wayback timestamp
            source_key: Source identifier

        Returns:
            HistoricalArticle or None
        """
        try:
            # Build archive URL
            archive_url = f"{WAYBACK_WEB_PREFIX}/{timestamp}/{original_url}"

            client = await self._get_client()
            response = await client.get(archive_url)
            response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # Remove Wayback toolbar
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

            # Extract content
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
                paragraphs = soup.find_all('p')
                content = " ".join(p.get_text(strip=True) for p in paragraphs[:10])

            # Create excerpt
            excerpt = content[:500] + "..." if len(content) > 500 else content

            # Extract politicians mentioned
            content_lower = content.lower()
            politicians = [p for p in POLITICIANS if p in content_lower]

            # Parse timestamp
            archived_date = datetime.strptime(timestamp[:8], "%Y%m%d").strftime("%Y-%m-%d")

            # Generate article ID
            article_id = hashlib.md5(original_url.encode()).hexdigest()[:16]

            source_info = RSS_FEEDS.get(source_key, {})

            self.stats["articles_fetched"] += 1

            return HistoricalArticle(
                article_id=article_id,
                title=title,
                url=original_url,
                archive_url=archive_url,
                source=source_key,
                source_name=source_info.get("name", source_key),
                excerpt=excerpt,
                full_text=content[:5000],
                published_date=archived_date,
                archived_date=archived_date,
                politicians_mentioned=politicians
            )

        except Exception as e:
            logger.warning(f"Error fetching article {original_url}: {e}")
            self.stats["errors"] += 1
            return None

    async def backfill_source_year(
        self,
        source_key: str,
        year: int,
        limit: int = 100,
        store: bool = True
    ) -> List[HistoricalArticle]:
        """
        Backfill articles from a single source for a specific year.

        Args:
            source_key: Source identifier from RSS_FEEDS
            year: Year to backfill
            limit: Maximum articles to fetch
            store: Whether to store in database

        Returns:
            List of fetched articles
        """
        source_info = RSS_FEEDS.get(source_key)
        if not source_info:
            logger.warning(f"Unknown source: {source_key}")
            return []

        if year < source_info.get("archive_start", 2010):
            logger.info(f"{source_key} not archived before {source_info['archive_start']}")
            return []

        articles = []
        seen_urls = set()

        # Try each URL variation
        for feed_url in source_info["urls"]:
            logger.info(f"Searching {source_key} RSS snapshots for {year}: {feed_url}")

            # Get snapshots for the year
            snapshots = await self.get_rss_snapshots(feed_url, year)
            logger.info(f"Found {len(snapshots)} RSS snapshots for {source_key} in {year}")

            # Parse each snapshot
            for snapshot in snapshots[:10]:  # Limit snapshots to parse
                await asyncio.sleep(0.5)  # Rate limit

                rss_articles = await self.parse_archived_rss(snapshot["archive_url"])

                for article_info in rss_articles:
                    if len(articles) >= limit:
                        break

                    url = article_info["url"]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    await asyncio.sleep(0.5)  # Rate limit

                    article = await self.fetch_archived_article(
                        url,
                        snapshot["timestamp"],
                        source_key
                    )

                    if article:
                        articles.append(article)

                if len(articles) >= limit:
                    break

            if len(articles) >= limit:
                break

        # Store articles
        if store and articles:
            stored = await self.store_articles(articles)
            logger.info(f"Stored {stored} articles from {source_key} ({year})")

        logger.info(f"Backfilled {len(articles)} articles from {source_key} for {year}")
        return articles

    async def store_articles(self, articles: List[HistoricalArticle]) -> int:
        """
        Store articles in database with deduplication.

        Args:
            articles: List of articles to store

        Returns:
            Number of articles stored
        """
        db = SessionLocal()
        stored = 0

        try:
            for article in articles:
                # Check if already exists
                existing = db.query(NewsArticle).filter(
                    NewsArticle.article_id == article.article_id
                ).first()

                if existing:
                    self.stats["duplicates_skipped"] += 1
                    continue

                # Create new article
                db_article = NewsArticle(
                    article_id=article.article_id,
                    title=article.title,
                    url=article.url,
                    source=article.source,
                    source_name=article.source_name,
                    excerpt=article.excerpt,
                    full_text=article.full_text,
                    politicians_json=json.dumps(article.politicians_mentioned),
                    scraped_at=datetime.strptime(article.archived_date, "%Y-%m-%d"),
                )

                db.add(db_article)
                db.flush()

                # Link politicians
                try:
                    from app.services.politician_mention_service import extract_and_link_politicians
                    extract_and_link_politicians(db_article, db)
                except Exception as e:
                    logger.warning(f"Error linking politicians: {e}")

                stored += 1
                self.stats["articles_stored"] += 1

            db.commit()

        except Exception as e:
            logger.error(f"Error storing articles: {e}")
            db.rollback()

        finally:
            db.close()

        return stored

    async def backfill_year(
        self,
        year: int,
        source: str = "all",
        limit: int = 50
    ) -> Dict:
        """
        Backfill all sources for a specific year.

        Args:
            year: Year to backfill (e.g., 2023)
            source: Specific source key or "all"
            limit: Max articles per source

        Returns:
            Statistics dictionary
        """
        sources = [source] if source != "all" else list(RSS_FEEDS.keys())

        all_articles = []

        for source_key in sources:
            logger.info(f"Starting backfill for {source_key} ({year})")

            articles = await self.backfill_source_year(
                source_key=source_key,
                year=year,
                limit=limit,
                store=True
            )

            all_articles.extend(articles)

            # Rate limit between sources
            await asyncio.sleep(1)

        return {
            "year": year,
            "sources": sources,
            "total_articles": len(all_articles),
            "stats": self.stats,
        }

    async def backfill_range(
        self,
        start_year: int,
        end_year: int,
        limit_per_source: int = 50
    ) -> Dict:
        """
        Backfill a range of years.

        Args:
            start_year: First year (e.g., 2010)
            end_year: Last year (e.g., 2024)
            limit_per_source: Max articles per source per year

        Returns:
            Statistics dictionary
        """
        results = {}

        for year in range(end_year, start_year - 1, -1):  # Start with recent years
            logger.info(f"=== Backfilling year {year} ===")
            result = await self.backfill_year(
                year=year,
                source="all",
                limit=limit_per_source
            )
            results[year] = result

        return {
            "years": list(results.keys()),
            "total_articles": sum(r["total_articles"] for r in results.values()),
            "by_year": results,
        }


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Historical News Backfill")
    parser.add_argument("--year", type=int, required=True, help="Year to backfill")
    parser.add_argument("--source", type=str, default="all", help="Source key or 'all'")
    parser.add_argument("--limit", type=int, default=50, help="Max articles per source")
    parser.add_argument("--no-store", action="store_true", help="Don't store in database")

    args = parser.parse_args()

    async def main():
        backfill = HistoricalNewsBackfill()

        try:
            if args.no_store:
                # Just test fetching
                articles = await backfill.backfill_source_year(
                    args.source if args.source != "all" else "punch",
                    args.year,
                    limit=args.limit,
                    store=False
                )
                print(f"\nFetched {len(articles)} articles:")
                for a in articles[:5]:
                    print(f"  [{a.archived_date}] {a.title[:60]}...")
            else:
                result = await backfill.backfill_year(
                    year=args.year,
                    source=args.source,
                    limit=args.limit
                )
                print(f"\nBackfill complete:")
                print(f"  Year: {result['year']}")
                print(f"  Sources: {result['sources']}")
                print(f"  Total articles: {result['total_articles']}")
                print(f"  Stats: {result['stats']}")

        finally:
            await backfill.close()

    asyncio.run(main())
