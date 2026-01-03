#!/usr/bin/env python3
"""
Massive Nigerian Data Collection Script

Collects comprehensive data from public domain sources:
- Internet Archive: Nigerian newspapers, books, documents
- Wikipedia: All Nigerian history, politics, culture articles
- Wikidata: Structured data on Nigerian entities
- News RSS: Current Nigerian news

Run: python scripts/collect_nigeria_data.py
"""

import asyncio
import aiohttp
import json
import hashlib
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import quote, urljoin
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data_collection.log')
    ]
)
logger = logging.getLogger(__name__)

# Data storage path
DATA_DIR = Path("./nigeria_knowledge_data")
DATA_DIR.mkdir(exist_ok=True)

# Rate limiting
RATE_LIMIT_SECONDS = 1.0


class DataCollector:
    """Collects data from multiple sources"""

    def __init__(self):
        self.stats = {
            "internet_archive": 0,
            "wikipedia": 0,
            "wikidata": 0,
            "news": 0,
            "total_bytes": 0,
            "errors": 0,
            "start_time": datetime.now().isoformat(),
        }
        self.user_agent = "Decide9ja-DataCollector/1.0 (Nigerian Civic Education Project)"
        self._last_request = {}

    async def _rate_limit(self, domain: str):
        """Rate limit requests per domain"""
        import time
        now = time.time()
        last = self._last_request.get(domain, 0)
        if now - last < RATE_LIMIT_SECONDS:
            await asyncio.sleep(RATE_LIMIT_SECONDS - (now - last))
        self._last_request[domain] = time.time()

    async def _fetch(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """Fetch URL with rate limiting"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        await self._rate_limit(domain)

        try:
            headers = {"User-Agent": self.user_agent}
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content = await response.text()
                    self.stats["total_bytes"] += len(content)
                    return content
                else:
                    logger.warning(f"HTTP {response.status}: {url}")
                    return None
        except Exception as e:
            logger.error(f"Fetch error {url}: {e}")
            self.stats["errors"] += 1
            return None

    # =========================================================================
    # INTERNET ARCHIVE
    # =========================================================================

    async def collect_internet_archive(self, session: aiohttp.ClientSession):
        """Collect Nigerian content from Internet Archive"""

        output_dir = DATA_DIR / "internet_archive"
        output_dir.mkdir(exist_ok=True)

        # Search queries for Nigerian content
        queries = [
            "nigeria newspaper",
            "nigerian history",
            "nigeria independence",
            "nigeria civil war biafra",
            "nigeria politics government",
            "nigerian constitution",
            "lagos nigeria",
            "northern nigeria",
            "eastern nigeria",
            "western nigeria",
            "nigeria military",
            "nigeria election",
            "ahmadu bello",
            "nnamdi azikiwe",
            "obafemi awolowo",
            "tafawa balewa",
            "nigerian daily times",
            "west african pilot",
            "daily trust nigeria",
            "nigerian tribune",
            "africa nigeria colonial",
            "british nigeria",
            "royal niger company",
            "nigeria oil petroleum",
            "nigerian economy",
            "nigeria education",
            "nigerian literature",
            "chinua achebe nigeria",
            "wole soyinka nigeria",
        ]

        all_items = []

        for query in queries:
            logger.info(f"[Internet Archive] Searching: {query}")

            # Search API
            search_url = (
                f"https://archive.org/advancedsearch.php?"
                f"q={quote(query)}&fl[]=identifier,title,date,creator,description,mediatype,collection"
                f"&rows=500&output=json&mediatype=texts"
            )

            content = await self._fetch(session, search_url)
            if not content:
                continue

            try:
                data = json.loads(content)
                docs = data.get("response", {}).get("docs", [])
                logger.info(f"  Found {len(docs)} items")

                for doc in docs:
                    identifier = doc.get("identifier")
                    if not identifier:
                        continue

                    # Check if already downloaded
                    item_file = output_dir / f"{identifier}.json"
                    if item_file.exists():
                        continue

                    # Get metadata
                    meta_url = f"https://archive.org/metadata/{identifier}"
                    meta_content = await self._fetch(session, meta_url)

                    if meta_content:
                        try:
                            metadata = json.loads(meta_content)
                        except:
                            metadata = {}
                    else:
                        metadata = {}

                    # Try to get full text
                    text_url = f"https://archive.org/stream/{identifier}/{identifier}_djvu.txt"
                    full_text = await self._fetch(session, text_url)

                    # Store item
                    item_data = {
                        "id": identifier,
                        "title": doc.get("title", ""),
                        "date": doc.get("date", ""),
                        "creator": doc.get("creator", ""),
                        "description": doc.get("description", ""),
                        "mediatype": doc.get("mediatype", ""),
                        "collection": doc.get("collection", []),
                        "metadata": metadata.get("metadata", {}),
                        "full_text": full_text if full_text and "Page Not Found" not in full_text else None,
                        "url": f"https://archive.org/details/{identifier}",
                        "query": query,
                        "collected_at": datetime.now().isoformat(),
                    }

                    # Save
                    with open(item_file, "w", encoding="utf-8") as f:
                        json.dump(item_data, f, indent=2, ensure_ascii=False)

                    self.stats["internet_archive"] += 1
                    all_items.append(item_data)

                    if self.stats["internet_archive"] % 50 == 0:
                        logger.info(f"  Collected {self.stats['internet_archive']} items from Internet Archive")

            except Exception as e:
                logger.error(f"Error processing Internet Archive results: {e}")

        # Save index
        index_file = output_dir / "_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_items": len(all_items),
                "queries": queries,
                "collected_at": datetime.now().isoformat(),
            }, f, indent=2)

        logger.info(f"[Internet Archive] Complete: {self.stats['internet_archive']} items")

    # =========================================================================
    # WIKIPEDIA
    # =========================================================================

    async def collect_wikipedia(self, session: aiohttp.ClientSession):
        """Collect Nigerian articles from Wikipedia"""

        output_dir = DATA_DIR / "wikipedia"
        output_dir.mkdir(exist_ok=True)

        # Categories to crawl
        categories = [
            # History
            "History_of_Nigeria",
            "Nigerian_Civil_War",
            "Military_coups_in_Nigeria",
            "Colonial_Nigeria",
            "Pre-colonial_Nigeria",
            "Nigerian_independence_movement",

            # Politics
            "Nigerian_politicians",
            "Presidents_of_Nigeria",
            "Vice_Presidents_of_Nigeria",
            "Governors_of_Nigerian_states",
            "Nigerian_senators",
            "Members_of_the_House_of_Representatives_of_Nigeria",
            "Nigerian_political_parties",
            "Nigerian_elections",
            "First_Nigerian_Republic",
            "Second_Nigerian_Republic",
            "Third_Nigerian_Republic",
            "Fourth_Nigerian_Republic",

            # Military
            "Nigerian_military_personnel",
            "Nigerian_Army_officers",
            "Chiefs_of_Army_Staff_(Nigeria)",
            "Nigerian_generals",

            # Government
            "Government_of_Nigeria",
            "Nigerian_federal_ministries",
            "Nigerian_law",
            "Nigerian_constitutions",

            # States and Geography
            "States_of_Nigeria",
            "Local_government_areas_of_Nigeria",
            "Cities_in_Nigeria",
            "Regions_of_Nigeria",

            # Economy
            "Economy_of_Nigeria",
            "Nigerian_businesspeople",
            "Oil_and_gas_companies_of_Nigeria",
            "Nigerian_banks",

            # Society
            "Ethnic_groups_in_Nigeria",
            "Nigerian_culture",
            "Education_in_Nigeria",
            "Universities_in_Nigeria",
            "Nigerian_media",
            "Newspapers_published_in_Nigeria",

            # People
            "Nigerian_activists",
            "Nigerian_journalists",
            "Nigerian_lawyers",
            "Nigerian_judges",
            "Nigerian_traditional_rulers",
            "Obas_of_Lagos",
            "Obas_of_Benin",
            "Sultans_of_Sokoto",
            "Emirs_in_Nigeria",
        ]

        all_articles = []
        seen_titles = set()

        api_url = "https://en.wikipedia.org/w/api.php"

        for category in categories:
            logger.info(f"[Wikipedia] Crawling category: {category}")

            # Get category members (with continuation for large categories)
            cmcontinue = None
            category_count = 0

            while True:
                params = {
                    "action": "query",
                    "list": "categorymembers",
                    "cmtitle": f"Category:{category}",
                    "cmlimit": "500",
                    "cmtype": "page",
                    "format": "json",
                }

                if cmcontinue:
                    params["cmcontinue"] = cmcontinue

                url = f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
                content = await self._fetch(session, url)

                if not content:
                    break

                try:
                    data = json.loads(content)
                    pages = data.get("query", {}).get("categorymembers", [])

                    for page in pages:
                        title = page.get("title", "")
                        page_id = page.get("pageid")

                        if not title or not page_id or title in seen_titles:
                            continue

                        if title.startswith("Category:") or title.startswith("Template:"):
                            continue

                        seen_titles.add(title)

                        # Check if already downloaded
                        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:100]
                        article_file = output_dir / f"{safe_title}_{page_id}.json"

                        if article_file.exists():
                            category_count += 1
                            continue

                        # Get article content
                        extract_params = {
                            "action": "query",
                            "pageids": page_id,
                            "prop": "extracts|info|categories|links",
                            "explaintext": "true",
                            "inprop": "url",
                            "pllimit": "100",
                            "cllimit": "50",
                            "format": "json",
                        }

                        extract_url = f"{api_url}?{'&'.join(f'{k}={v}' for k, v in extract_params.items())}"
                        extract_content = await self._fetch(session, extract_url)

                        if extract_content:
                            try:
                                extract_data = json.loads(extract_content)
                                page_data = extract_data.get("query", {}).get("pages", {}).get(str(page_id), {})

                                article = {
                                    "id": page_id,
                                    "title": title,
                                    "content": page_data.get("extract", ""),
                                    "url": page_data.get("fullurl", f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"),
                                    "categories": [c.get("title", "").replace("Category:", "") for c in page_data.get("categories", [])],
                                    "links": [l.get("title", "") for l in page_data.get("links", [])],
                                    "source_category": category,
                                    "collected_at": datetime.now().isoformat(),
                                }

                                # Save
                                with open(article_file, "w", encoding="utf-8") as f:
                                    json.dump(article, f, indent=2, ensure_ascii=False)

                                self.stats["wikipedia"] += 1
                                all_articles.append({"title": title, "id": page_id})
                                category_count += 1

                                if self.stats["wikipedia"] % 100 == 0:
                                    logger.info(f"  Collected {self.stats['wikipedia']} Wikipedia articles")

                            except Exception as e:
                                logger.error(f"Error processing article {title}: {e}")

                    # Check for more pages
                    cmcontinue = data.get("continue", {}).get("cmcontinue")
                    if not cmcontinue:
                        break

                except Exception as e:
                    logger.error(f"Error processing category {category}: {e}")
                    break

            logger.info(f"  Category {category}: {category_count} articles")

        # Save index
        index_file = output_dir / "_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_articles": len(all_articles),
                "categories": categories,
                "articles": all_articles,
                "collected_at": datetime.now().isoformat(),
            }, f, indent=2)

        logger.info(f"[Wikipedia] Complete: {self.stats['wikipedia']} articles")

    # =========================================================================
    # WIKIDATA
    # =========================================================================

    async def collect_wikidata(self, session: aiohttp.ClientSession):
        """Collect structured Nigerian entity data from Wikidata"""

        output_dir = DATA_DIR / "wikidata"
        output_dir.mkdir(exist_ok=True)

        # SPARQL queries for different entity types
        queries = {
            "nigerian_politicians": """
                SELECT ?person ?personLabel ?personDescription ?birthDate ?deathDate ?positionLabel ?partyLabel ?genderLabel ?image WHERE {
                    ?person wdt:P27 wd:Q1033 .
                    ?person wdt:P106 wd:Q82955 .
                    OPTIONAL { ?person wdt:P569 ?birthDate }
                    OPTIONAL { ?person wdt:P570 ?deathDate }
                    OPTIONAL { ?person wdt:P39 ?position }
                    OPTIONAL { ?person wdt:P102 ?party }
                    OPTIONAL { ?person wdt:P21 ?gender }
                    OPTIONAL { ?person wdt:P18 ?image }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
                LIMIT 5000
            """,

            "presidents_of_nigeria": """
                SELECT ?person ?personLabel ?personDescription ?startDate ?endDate ?predecessorLabel ?successorLabel WHERE {
                    ?person wdt:P39 wd:Q3057085 .
                    ?person p:P39 ?statement .
                    ?statement ps:P39 wd:Q3057085 .
                    OPTIONAL { ?statement pq:P580 ?startDate }
                    OPTIONAL { ?statement pq:P582 ?endDate }
                    OPTIONAL { ?statement pq:P1365 ?predecessor }
                    OPTIONAL { ?statement pq:P1366 ?successor }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,

            "heads_of_state_nigeria": """
                SELECT ?person ?personLabel ?personDescription ?positionLabel ?startDate ?endDate WHERE {
                    ?person wdt:P39 ?position .
                    ?position wdt:P17 wd:Q1033 .
                    VALUES ?positionType { wd:Q48352 wd:Q3057085 wd:Q1006669 }
                    ?position wdt:P31 ?positionType .
                    ?person p:P39 ?statement .
                    ?statement ps:P39 ?position .
                    OPTIONAL { ?statement pq:P580 ?startDate }
                    OPTIONAL { ?statement pq:P582 ?endDate }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,

            "nigerian_military_officers": """
                SELECT ?person ?personLabel ?personDescription ?rankLabel ?branchLabel ?birthDate ?deathDate WHERE {
                    ?person wdt:P27 wd:Q1033 .
                    ?person wdt:P410 ?rank .
                    OPTIONAL { ?person wdt:P241 ?branch }
                    OPTIONAL { ?person wdt:P569 ?birthDate }
                    OPTIONAL { ?person wdt:P570 ?deathDate }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
                LIMIT 2000
            """,

            "nigerian_states": """
                SELECT ?state ?stateLabel ?stateDescription ?capital ?capitalLabel ?population ?area ?established WHERE {
                    ?state wdt:P31 wd:Q465842 .
                    OPTIONAL { ?state wdt:P36 ?capital }
                    OPTIONAL { ?state wdt:P1082 ?population }
                    OPTIONAL { ?state wdt:P2046 ?area }
                    OPTIONAL { ?state wdt:P571 ?established }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,

            "nigerian_cities": """
                SELECT ?city ?cityLabel ?cityDescription ?stateLabel ?population ?coordinates WHERE {
                    ?city wdt:P17 wd:Q1033 .
                    ?city wdt:P31/wdt:P279* wd:Q515 .
                    OPTIONAL { ?city wdt:P131 ?state }
                    OPTIONAL { ?city wdt:P1082 ?population }
                    OPTIONAL { ?city wdt:P625 ?coordinates }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
                LIMIT 1000
            """,

            "nigerian_political_parties": """
                SELECT ?party ?partyLabel ?partyDescription ?founded ?dissolved ?ideology ?ideologyLabel WHERE {
                    ?party wdt:P17 wd:Q1033 .
                    ?party wdt:P31 wd:Q7278 .
                    OPTIONAL { ?party wdt:P571 ?founded }
                    OPTIONAL { ?party wdt:P576 ?dissolved }
                    OPTIONAL { ?party wdt:P1142 ?ideology }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,

            "nigerian_ethnic_groups": """
                SELECT ?group ?groupLabel ?groupDescription ?population ?region ?regionLabel WHERE {
                    ?group wdt:P17 wd:Q1033 .
                    ?group wdt:P31 wd:Q41710 .
                    OPTIONAL { ?group wdt:P1082 ?population }
                    OPTIONAL { ?group wdt:P276 ?region }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,

            "nigerian_universities": """
                SELECT ?uni ?uniLabel ?uniDescription ?founded ?location ?locationLabel ?students WHERE {
                    ?uni wdt:P17 wd:Q1033 .
                    ?uni wdt:P31/wdt:P279* wd:Q3918 .
                    OPTIONAL { ?uni wdt:P571 ?founded }
                    OPTIONAL { ?uni wdt:P131 ?location }
                    OPTIONAL { ?uni wdt:P2196 ?students }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,

            "nigerian_companies": """
                SELECT ?company ?companyLabel ?companyDescription ?founded ?industry ?industryLabel ?headquarters ?headquartersLabel WHERE {
                    ?company wdt:P17 wd:Q1033 .
                    ?company wdt:P31/wdt:P279* wd:Q4830453 .
                    OPTIONAL { ?company wdt:P571 ?founded }
                    OPTIONAL { ?company wdt:P452 ?industry }
                    OPTIONAL { ?company wdt:P159 ?headquarters }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
                LIMIT 1000
            """,

            "nigerian_newspapers": """
                SELECT ?paper ?paperLabel ?paperDescription ?founded ?headquarters ?headquartersLabel WHERE {
                    ?paper wdt:P17 wd:Q1033 .
                    ?paper wdt:P31 wd:Q11032 .
                    OPTIONAL { ?paper wdt:P571 ?founded }
                    OPTIONAL { ?paper wdt:P159 ?headquarters }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,

            "nigerian_events": """
                SELECT ?event ?eventLabel ?eventDescription ?date ?location ?locationLabel WHERE {
                    ?event wdt:P17 wd:Q1033 .
                    ?event wdt:P31/wdt:P279* wd:Q1190554 .
                    OPTIONAL { ?event wdt:P585 ?date }
                    OPTIONAL { ?event wdt:P276 ?location }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
                LIMIT 1000
            """,

            "nigerian_elections": """
                SELECT ?election ?electionLabel ?electionDescription ?date ?winner ?winnerLabel ?office ?officeLabel WHERE {
                    ?election wdt:P17 wd:Q1033 .
                    ?election wdt:P31/wdt:P279* wd:Q40231 .
                    OPTIONAL { ?election wdt:P585 ?date }
                    OPTIONAL { ?election wdt:P991 ?winner }
                    OPTIONAL { ?election wdt:P541 ?office }
                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
                }
            """,
        }

        endpoint = "https://query.wikidata.org/sparql"

        all_entities = []

        for query_name, sparql in queries.items():
            logger.info(f"[Wikidata] Running query: {query_name}")

            query_file = output_dir / f"{query_name}.json"

            # Check if already collected
            if query_file.exists():
                logger.info(f"  Already collected, skipping")
                with open(query_file) as f:
                    data = json.load(f)
                    self.stats["wikidata"] += len(data.get("results", []))
                continue

            url = f"{endpoint}?query={quote(sparql)}&format=json"
            content = await self._fetch(session, url)

            if not content:
                continue

            try:
                data = json.loads(content)
                results = data.get("results", {}).get("bindings", [])

                # Clean up results
                cleaned_results = []
                for result in results:
                    cleaned = {}
                    for key, value in result.items():
                        if isinstance(value, dict):
                            cleaned[key] = value.get("value", "")
                        else:
                            cleaned[key] = value
                    cleaned_results.append(cleaned)

                # Save
                with open(query_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "query_name": query_name,
                        "total_results": len(cleaned_results),
                        "results": cleaned_results,
                        "collected_at": datetime.now().isoformat(),
                    }, f, indent=2, ensure_ascii=False)

                self.stats["wikidata"] += len(cleaned_results)
                all_entities.extend(cleaned_results)

                logger.info(f"  Found {len(cleaned_results)} entities")

            except Exception as e:
                logger.error(f"Error processing Wikidata query {query_name}: {e}")

        # Save index
        index_file = output_dir / "_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_entities": self.stats["wikidata"],
                "queries": list(queries.keys()),
                "collected_at": datetime.now().isoformat(),
            }, f, indent=2)

        logger.info(f"[Wikidata] Complete: {self.stats['wikidata']} entities")

    # =========================================================================
    # NEWS RSS
    # =========================================================================

    async def collect_news(self, session: aiohttp.ClientSession):
        """Collect current Nigerian news from RSS feeds"""

        output_dir = DATA_DIR / "news"
        output_dir.mkdir(exist_ok=True)

        feeds = [
            ("Punch", "https://punchng.com/feed/"),
            ("Premium Times", "https://www.premiumtimesng.com/feed"),
            ("The Nation", "https://thenationonlineng.net/feed/"),
            ("Vanguard", "https://www.vanguardngr.com/feed/"),
            ("Daily Post", "https://dailypost.ng/feed/"),
            ("Channels TV", "https://www.channelstv.com/feed/"),
            ("Sahara Reporters", "https://saharareporters.com/rss.xml"),
            ("This Day", "https://www.thisdaylive.com/feed/"),
            ("Guardian Nigeria", "https://guardian.ng/feed/"),
            ("Tribune", "https://tribuneonlineng.com/feed/"),
            ("Leadership", "https://leadership.ng/feed/"),
            ("Daily Trust", "https://dailytrust.com/feed/"),
            ("BusinessDay", "https://businessday.ng/feed/"),
            ("Nairametrics", "https://nairametrics.com/feed/"),
        ]

        try:
            import feedparser
        except ImportError:
            logger.error("feedparser not installed. Run: pip install feedparser")
            return

        all_articles = []

        for name, feed_url in feeds:
            logger.info(f"[News] Fetching: {name}")

            content = await self._fetch(session, feed_url)
            if not content:
                continue

            try:
                feed = feedparser.parse(content)

                for entry in feed.entries:
                    article_id = hashlib.md5(entry.link.encode()).hexdigest()[:12]

                    # Parse date
                    pub_date = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6]).isoformat()

                    # Get content
                    content_text = ""
                    if hasattr(entry, "content"):
                        content_text = entry.content[0].get("value", "")
                    elif hasattr(entry, "summary"):
                        content_text = entry.summary

                    # Clean HTML
                    content_text = re.sub(r"<[^>]+>", "", content_text)

                    article = {
                        "id": article_id,
                        "title": entry.title,
                        "link": entry.link,
                        "published": pub_date,
                        "content": content_text,
                        "source": name,
                        "author": getattr(entry, "author", None),
                        "collected_at": datetime.now().isoformat(),
                    }

                    all_articles.append(article)
                    self.stats["news"] += 1

                logger.info(f"  Found {len(feed.entries)} articles")

            except Exception as e:
                logger.error(f"Error parsing feed {name}: {e}")

        # Save all news
        news_file = output_dir / f"news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(news_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_articles": len(all_articles),
                "sources": [name for name, _ in feeds],
                "articles": all_articles,
                "collected_at": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)

        logger.info(f"[News] Complete: {self.stats['news']} articles")

    async def run(self):
        """Run all collectors"""

        logger.info("=" * 60)
        logger.info("NIGERIA KNOWLEDGE DATA COLLECTION")
        logger.info(f"Started: {datetime.now().isoformat()}")
        logger.info(f"Output: {DATA_DIR.absolute()}")
        logger.info("=" * 60)

        async with aiohttp.ClientSession() as session:
            # Run collectors
            await self.collect_internet_archive(session)
            await self.collect_wikipedia(session)
            await self.collect_wikidata(session)
            await self.collect_news(session)

        # Final stats
        self.stats["end_time"] = datetime.now().isoformat()

        # Save stats
        stats_file = DATA_DIR / "_collection_stats.json"
        with open(stats_file, "w") as f:
            json.dump(self.stats, f, indent=2)

        logger.info("\n" + "=" * 60)
        logger.info("COLLECTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Internet Archive: {self.stats['internet_archive']} items")
        logger.info(f"Wikipedia: {self.stats['wikipedia']} articles")
        logger.info(f"Wikidata: {self.stats['wikidata']} entities")
        logger.info(f"News: {self.stats['news']} articles")
        logger.info(f"Total bytes: {self.stats['total_bytes'] / (1024*1024):.2f} MB")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Output: {DATA_DIR.absolute()}")
        logger.info("=" * 60)


if __name__ == "__main__":
    collector = DataCollector()
    asyncio.run(collector.run())
