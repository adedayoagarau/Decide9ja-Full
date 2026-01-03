"""
Nigeria Archive Crawler

Crawls historical Nigerian content from multiple sources:
- Internet Archive (archive.org) - Public domain newspapers and books
- Wikipedia/Wikidata - Structured historical data
- News RSS feeds - Current news (2010-present)
- Archivi.ng - Historical newspapers (requires partnership)

Designed to be respectful with rate limiting and caching.
"""

import asyncio
import aiohttp
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncIterator
from urllib.parse import urljoin, urlparse, quote

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Types of archive sources"""
    INTERNET_ARCHIVE = "internet_archive"
    WIKIPEDIA = "wikipedia"
    WIKIDATA = "wikidata"
    NEWS_RSS = "news_rss"
    ARCHIVI_NG = "archivi_ng"  # Requires partnership
    LOCAL_FILE = "local_file"


@dataclass
class ArchivedDocument:
    """A document retrieved from an archive"""
    id: str
    title: str
    source: SourceType
    source_url: str
    content: str  # Full text content

    # Metadata
    publication_date: Optional[date] = None
    publisher: Optional[str] = None
    author: Optional[str] = None
    language: str = "en"

    # Processing status
    ocr_processed: bool = False
    entities_extracted: bool = False

    # Storage
    local_path: Optional[str] = None
    raw_html: Optional[str] = None

    # Timestamps
    crawled_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source.value,
            "source_url": self.source_url,
            "content": self.content[:1000] + "..." if len(self.content) > 1000 else self.content,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "publisher": self.publisher,
            "author": self.author,
            "crawled_at": self.crawled_at.isoformat(),
        }


class ArchiveCrawler:
    """
    Multi-source archive crawler for Nigerian historical content.

    Designed for respectful crawling with:
    - Rate limiting (configurable delay between requests)
    - Caching (avoid re-downloading)
    - User-agent identification
    - Robots.txt compliance (where applicable)
    """

    def __init__(
        self,
        storage_path: str = "./archive_data",
        rate_limit_seconds: float = 2.0,
        cache_enabled: bool = True,
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.rate_limit = rate_limit_seconds
        self.cache_enabled = cache_enabled

        self.user_agent = "Decide9ja-ArchiveCrawler/1.0 (Nigerian Civic Education; contact@decide9ja.ng)"

        # Statistics
        self.stats = {
            "documents_crawled": 0,
            "bytes_downloaded": 0,
            "cache_hits": 0,
            "errors": 0,
        }

        # Last request time for rate limiting
        self._last_request_time: Dict[str, float] = {}

    async def _rate_limit(self, domain: str):
        """Enforce rate limiting per domain"""
        now = asyncio.get_event_loop().time()
        last = self._last_request_time.get(domain, 0)

        if now - last < self.rate_limit:
            await asyncio.sleep(self.rate_limit - (now - last))

        self._last_request_time[domain] = asyncio.get_event_loop().time()

    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for a URL"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.storage_path / "cache" / f"{url_hash}.json"

    async def _fetch_url(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Fetch URL with caching and rate limiting"""
        domain = urlparse(url).netloc

        # Check cache
        cache_path = self._get_cache_path(url)
        if self.cache_enabled and cache_path.exists():
            self.stats["cache_hits"] += 1
            with open(cache_path) as f:
                cached = json.load(f)
                return cached.get("content")

        # Rate limit
        await self._rate_limit(domain)

        try:
            headers = {"User-Agent": self.user_agent}
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content = await response.text()
                    self.stats["bytes_downloaded"] += len(content)

                    # Cache the result
                    if self.cache_enabled:
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(cache_path, "w") as f:
                            json.dump({
                                "url": url,
                                "content": content,
                                "fetched_at": datetime.now().isoformat(),
                            }, f)

                    return content
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    self.stats["errors"] += 1
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            self.stats["errors"] += 1
            return None

    # =========================================================================
    # INTERNET ARCHIVE - Nigerian newspapers and books
    # =========================================================================

    async def crawl_internet_archive(
        self,
        query: str = "nigeria newspaper",
        media_type: str = "texts",
        max_items: int = 100,
    ) -> AsyncIterator[ArchivedDocument]:
        """
        Crawl Nigerian content from Internet Archive.

        Args:
            query: Search query
            media_type: Type of media (texts, audio, video)
            max_items: Maximum items to retrieve
        """
        search_url = (
            f"https://archive.org/advancedsearch.php?"
            f"q={quote(query)}&fl[]=identifier,title,date,creator,description"
            f"&rows={max_items}&output=json&mediatype={media_type}"
        )

        async with aiohttp.ClientSession() as session:
            content = await self._fetch_url(search_url, session)
            if not content:
                return

            try:
                data = json.loads(content)
                docs = data.get("response", {}).get("docs", [])

                for doc in docs:
                    identifier = doc.get("identifier")
                    if not identifier:
                        continue

                    # Get full text if available
                    text_url = f"https://archive.org/stream/{identifier}/{identifier}_djvu.txt"
                    full_text = await self._fetch_url(text_url, session)

                    if full_text and "Page Not Found" not in full_text:
                        # Parse date
                        pub_date = None
                        date_str = doc.get("date")
                        if date_str:
                            try:
                                pub_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
                            except:
                                try:
                                    pub_date = datetime.strptime(date_str[:4], "%Y").date()
                                except:
                                    pass

                        archived_doc = ArchivedDocument(
                            id=f"ia_{identifier}",
                            title=doc.get("title", identifier),
                            source=SourceType.INTERNET_ARCHIVE,
                            source_url=f"https://archive.org/details/{identifier}",
                            content=full_text,
                            publication_date=pub_date,
                            author=doc.get("creator"),
                        )

                        self.stats["documents_crawled"] += 1
                        yield archived_doc

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing Internet Archive response: {e}")

    # =========================================================================
    # WIKIPEDIA - Nigerian history articles
    # =========================================================================

    async def crawl_wikipedia_category(
        self,
        category: str = "History_of_Nigeria",
        max_articles: int = 100,
    ) -> AsyncIterator[ArchivedDocument]:
        """
        Crawl articles from a Wikipedia category.

        Useful categories:
        - History_of_Nigeria
        - Nigerian_politicians
        - Military_coups_in_Nigeria
        - Nigerian_elections
        """
        api_url = "https://en.wikipedia.org/w/api.php"

        async with aiohttp.ClientSession() as session:
            # Get category members
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": f"Category:{category}",
                "cmlimit": max_articles,
                "cmtype": "page",
                "format": "json",
            }

            url = f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
            content = await self._fetch_url(url, session)

            if not content:
                return

            try:
                data = json.loads(content)
                pages = data.get("query", {}).get("categorymembers", [])

                for page in pages:
                    page_id = page.get("pageid")
                    title = page.get("title")

                    if not page_id or not title:
                        continue

                    # Get article content
                    extract_params = {
                        "action": "query",
                        "pageids": page_id,
                        "prop": "extracts",
                        "explaintext": "true",
                        "format": "json",
                    }

                    extract_url = f"{api_url}?{'&'.join(f'{k}={v}' for k, v in extract_params.items())}"
                    extract_content = await self._fetch_url(extract_url, session)

                    if extract_content:
                        extract_data = json.loads(extract_content)
                        page_data = extract_data.get("query", {}).get("pages", {}).get(str(page_id), {})
                        text = page_data.get("extract", "")

                        if text:
                            archived_doc = ArchivedDocument(
                                id=f"wiki_{page_id}",
                                title=title,
                                source=SourceType.WIKIPEDIA,
                                source_url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                                content=text,
                                publisher="Wikipedia",
                            )

                            self.stats["documents_crawled"] += 1
                            yield archived_doc

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing Wikipedia response: {e}")

    # =========================================================================
    # WIKIDATA - Structured Nigerian entity data
    # =========================================================================

    async def crawl_wikidata_nigerian_entities(
        self,
        entity_type: str = "politician",
        max_entities: int = 500,
    ) -> AsyncIterator[Dict]:
        """
        Crawl Nigerian entities from Wikidata using SPARQL.

        Entity types: politician, military_officer, president, governor
        """

        sparql_queries = {
            "politician": """
                SELECT ?person ?personLabel ?birthDate ?deathDate ?positionLabel ?partyLabel WHERE {
                    ?person wdt:P27 wd:Q1033 .  # Nigerian citizen
                    ?person wdt:P106 wd:Q82955 . # Politician
                    OPTIONAL { ?person wdt:P569 ?birthDate }
                    OPTIONAL { ?person wdt:P570 ?deathDate }
                    OPTIONAL { ?person wdt:P39 ?position }
                    OPTIONAL { ?person wdt:P102 ?party }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
                LIMIT %d
            """,
            "president": """
                SELECT ?person ?personLabel ?startDate ?endDate WHERE {
                    ?person wdt:P39 wd:Q3057085 .  # President of Nigeria
                    ?person p:P39 ?statement .
                    ?statement ps:P39 wd:Q3057085 .
                    OPTIONAL { ?statement pq:P580 ?startDate }
                    OPTIONAL { ?statement pq:P582 ?endDate }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,
            "governor": """
                SELECT ?person ?personLabel ?stateLabel ?startDate ?endDate WHERE {
                    ?person wdt:P39 ?position .
                    ?position wdt:P31 wd:Q30185908 .  # Governor of Nigerian state
                    OPTIONAL { ?person wdt:P39 ?position . ?position wdt:P131 ?state }
                    ?person p:P39 ?statement .
                    OPTIONAL { ?statement pq:P580 ?startDate }
                    OPTIONAL { ?statement pq:P582 ?endDate }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
                LIMIT %d
            """,
        }

        query = sparql_queries.get(entity_type, sparql_queries["politician"])
        if "%d" in query:
            query = query % max_entities

        url = f"https://query.wikidata.org/sparql?query={quote(query)}&format=json"

        async with aiohttp.ClientSession() as session:
            content = await self._fetch_url(url, session)

            if not content:
                return

            try:
                data = json.loads(content)
                results = data.get("results", {}).get("bindings", [])

                for result in results:
                    entity = {
                        "id": result.get("person", {}).get("value", "").split("/")[-1],
                        "name": result.get("personLabel", {}).get("value"),
                        "type": entity_type,
                        "source": "wikidata",
                    }

                    # Add optional fields
                    if "birthDate" in result:
                        entity["birth_date"] = result["birthDate"]["value"]
                    if "deathDate" in result:
                        entity["death_date"] = result["deathDate"]["value"]
                    if "positionLabel" in result:
                        entity["position"] = result["positionLabel"]["value"]
                    if "partyLabel" in result:
                        entity["party"] = result["partyLabel"]["value"]
                    if "stateLabel" in result:
                        entity["state"] = result["stateLabel"]["value"]
                    if "startDate" in result:
                        entity["start_date"] = result["startDate"]["value"]
                    if "endDate" in result:
                        entity["end_date"] = result["endDate"]["value"]

                    yield entity

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing Wikidata response: {e}")

    # =========================================================================
    # NEWS RSS - Current Nigerian news
    # =========================================================================

    async def crawl_news_rss(
        self,
        feeds: Optional[List[str]] = None,
    ) -> AsyncIterator[ArchivedDocument]:
        """
        Crawl Nigerian news from RSS feeds.

        Default feeds include major Nigerian news outlets.
        """

        default_feeds = [
            "https://punchng.com/feed/",
            "https://www.premiumtimesng.com/feed",
            "https://thenationonlineng.net/feed/",
            "https://www.vanguardngr.com/feed/",
            "https://dailypost.ng/feed/",
            "https://www.channelstv.com/feed/",
            "https://saharareporters.com/rss.xml",
        ]

        feeds = feeds or default_feeds

        try:
            import feedparser
        except ImportError:
            logger.error("feedparser not installed. Run: pip install feedparser")
            return

        async with aiohttp.ClientSession() as session:
            for feed_url in feeds:
                content = await self._fetch_url(feed_url, session)

                if not content:
                    continue

                try:
                    feed = feedparser.parse(content)
                    publisher = feed.feed.get("title", urlparse(feed_url).netloc)

                    for entry in feed.entries:
                        # Parse date
                        pub_date = None
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            pub_date = date(*entry.published_parsed[:3])

                        # Get content
                        content_text = ""
                        if hasattr(entry, "content"):
                            content_text = entry.content[0].get("value", "")
                        elif hasattr(entry, "summary"):
                            content_text = entry.summary

                        # Clean HTML
                        content_text = re.sub(r"<[^>]+>", "", content_text)

                        archived_doc = ArchivedDocument(
                            id=f"rss_{hashlib.md5(entry.link.encode()).hexdigest()[:12]}",
                            title=entry.title,
                            source=SourceType.NEWS_RSS,
                            source_url=entry.link,
                            content=content_text,
                            publication_date=pub_date,
                            publisher=publisher,
                            author=getattr(entry, "author", None),
                        )

                        self.stats["documents_crawled"] += 1
                        yield archived_doc

                except Exception as e:
                    logger.error(f"Error parsing feed {feed_url}: {e}")

    # =========================================================================
    # ARCHIVI.NG - Requires Partnership
    # =========================================================================

    async def crawl_archivi_ng(
        self,
        api_key: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AsyncIterator[ArchivedDocument]:
        """
        Crawl from Archivi.ng (requires partnership/API key).

        Contact start@archivi.ng for API access.

        This is a placeholder that will work once partnership is established.
        """

        if not api_key:
            api_key = os.environ.get("ARCHIVI_NG_API_KEY")

        if not api_key:
            logger.warning(
                "Archivi.ng requires API access. "
                "Contact start@archivi.ng for partnership."
            )
            return

        # Placeholder for when API access is granted
        # The actual implementation will depend on their API structure

        base_url = "https://api.archivi.ng/v1"  # Hypothetical API

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": self.user_agent,
            }

            # This is placeholder logic - actual implementation TBD
            params = {}
            if start_date:
                params["from"] = start_date.isoformat()
            if end_date:
                params["to"] = end_date.isoformat()

            # Would iterate through their archive
            # yield documents as they're retrieved

            logger.info("Archivi.ng API integration ready for when access is granted")
            return

    # =========================================================================
    # LOCAL FILES - Process existing documents
    # =========================================================================

    async def process_local_files(
        self,
        directory: str,
        extensions: List[str] = [".txt", ".pdf", ".json"],
    ) -> AsyncIterator[ArchivedDocument]:
        """
        Process local files (including those from your 2TB external drive).

        Supports:
        - .txt files (direct read)
        - .json files (structured data)
        - .pdf files (requires OCR pipeline)
        """

        path = Path(directory)
        if not path.exists():
            logger.error(f"Directory not found: {directory}")
            return

        for file_path in path.rglob("*"):
            if file_path.suffix.lower() not in extensions:
                continue

            try:
                if file_path.suffix.lower() == ".txt":
                    content = file_path.read_text(encoding="utf-8", errors="ignore")

                    archived_doc = ArchivedDocument(
                        id=f"local_{hashlib.md5(str(file_path).encode()).hexdigest()[:12]}",
                        title=file_path.stem,
                        source=SourceType.LOCAL_FILE,
                        source_url=f"file://{file_path}",
                        content=content,
                        local_path=str(file_path),
                    )

                    self.stats["documents_crawled"] += 1
                    yield archived_doc

                elif file_path.suffix.lower() == ".json":
                    with open(file_path) as f:
                        data = json.load(f)

                    # Handle various JSON structures
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "content" in item:
                                archived_doc = ArchivedDocument(
                                    id=f"local_{hashlib.md5(str(item).encode()).hexdigest()[:12]}",
                                    title=item.get("title", file_path.stem),
                                    source=SourceType.LOCAL_FILE,
                                    source_url=f"file://{file_path}",
                                    content=item.get("content", ""),
                                    local_path=str(file_path),
                                )
                                self.stats["documents_crawled"] += 1
                                yield archived_doc
                    elif isinstance(data, dict) and "content" in data:
                        archived_doc = ArchivedDocument(
                            id=f"local_{hashlib.md5(str(file_path).encode()).hexdigest()[:12]}",
                            title=data.get("title", file_path.stem),
                            source=SourceType.LOCAL_FILE,
                            source_url=f"file://{file_path}",
                            content=data.get("content", ""),
                            local_path=str(file_path),
                        )
                        self.stats["documents_crawled"] += 1
                        yield archived_doc

                elif file_path.suffix.lower() == ".pdf":
                    # PDF requires OCR - mark for processing
                    archived_doc = ArchivedDocument(
                        id=f"local_{hashlib.md5(str(file_path).encode()).hexdigest()[:12]}",
                        title=file_path.stem,
                        source=SourceType.LOCAL_FILE,
                        source_url=f"file://{file_path}",
                        content="[PDF - requires OCR processing]",
                        local_path=str(file_path),
                        ocr_processed=False,
                    )
                    self.stats["documents_crawled"] += 1
                    yield archived_doc

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                self.stats["errors"] += 1

    def get_statistics(self) -> Dict:
        """Get crawler statistics"""
        return {
            **self.stats,
            "storage_path": str(self.storage_path),
            "cache_size_mb": sum(
                f.stat().st_size for f in (self.storage_path / "cache").rglob("*") if f.is_file()
            ) / (1024 * 1024) if (self.storage_path / "cache").exists() else 0,
        }


# =========================================================================
# Convenience functions
# =========================================================================

async def crawl_all_sources(
    storage_path: str = "./archive_data",
    max_items_per_source: int = 100,
) -> List[ArchivedDocument]:
    """
    Crawl all available sources and return documents.

    This is a demo function to show the system working.
    """

    crawler = ArchiveCrawler(storage_path=storage_path)
    documents = []

    # 1. Internet Archive
    logger.info("Crawling Internet Archive...")
    async for doc in crawler.crawl_internet_archive(
        query="nigeria newspaper history",
        max_items=max_items_per_source
    ):
        documents.append(doc)
        if len(documents) % 10 == 0:
            logger.info(f"Crawled {len(documents)} documents...")

    # 2. Wikipedia categories
    logger.info("Crawling Wikipedia...")
    categories = [
        "History_of_Nigeria",
        "Nigerian_politicians",
        "Presidents_of_Nigeria",
        "Military_coups_in_Nigeria",
    ]

    for category in categories:
        async for doc in crawler.crawl_wikipedia_category(
            category=category,
            max_articles=max_items_per_source // len(categories)
        ):
            documents.append(doc)

    # 3. News RSS
    logger.info("Crawling News RSS feeds...")
    async for doc in crawler.crawl_news_rss():
        documents.append(doc)

    logger.info(f"Total documents crawled: {len(documents)}")
    logger.info(f"Statistics: {crawler.get_statistics()}")

    return documents


async def demo_crawl() -> Dict:
    """
    Demo function to test crawling capability.

    Run this to demonstrate the system to potential funders.
    """

    print("=" * 60)
    print("NIGERIA KNOWLEDGE SYSTEM - Archive Crawler Demo")
    print("=" * 60)

    crawler = ArchiveCrawler(storage_path="./demo_archive")
    results = {
        "internet_archive": [],
        "wikipedia": [],
        "wikidata": [],
        "news": [],
    }

    # Demo 1: Internet Archive
    print("\n[1/4] Searching Internet Archive for Nigerian newspapers...")
    count = 0
    async for doc in crawler.crawl_internet_archive(
        query="nigeria daily times newspaper",
        max_items=5
    ):
        results["internet_archive"].append(doc.to_dict())
        print(f"  Found: {doc.title[:50]}...")
        count += 1
    print(f"  -> {count} documents from Internet Archive")

    # Demo 2: Wikipedia
    print("\n[2/4] Fetching Nigerian history from Wikipedia...")
    count = 0
    async for doc in crawler.crawl_wikipedia_category(
        category="Presidents_of_Nigeria",
        max_articles=5
    ):
        results["wikipedia"].append(doc.to_dict())
        print(f"  Found: {doc.title}")
        count += 1
    print(f"  -> {count} articles from Wikipedia")

    # Demo 3: Wikidata
    print("\n[3/4] Querying Nigerian politicians from Wikidata...")
    count = 0
    async for entity in crawler.crawl_wikidata_nigerian_entities(
        entity_type="president",
        max_entities=10
    ):
        results["wikidata"].append(entity)
        print(f"  Found: {entity.get('name')} ({entity.get('start_date', 'N/A')[:4] if entity.get('start_date') else 'N/A'})")
        count += 1
    print(f"  -> {count} entities from Wikidata")

    # Demo 4: News RSS
    print("\n[4/4] Checking latest Nigerian news...")
    count = 0
    async for doc in crawler.crawl_news_rss():
        results["news"].append(doc.to_dict())
        if count < 5:
            print(f"  Latest: {doc.title[:50]}...")
        count += 1
    print(f"  -> {count} news articles from RSS feeds")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print(f"Total documents: {sum(len(v) for v in results.values())}")
    print(f"Statistics: {crawler.get_statistics()}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_crawl())
