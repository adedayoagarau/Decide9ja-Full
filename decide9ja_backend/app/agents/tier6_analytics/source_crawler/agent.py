"""
SourceCrawlerAgent
==================
Crawls Nigerian news sources for political information.

Sources:
- Premium Times (high credibility)
- Punch (high credibility)
- Channels TV (high credibility)
- ThisDay (high credibility)
- Vanguard (medium credibility)
- INEC (official)
- NASS (official)

Cost: FREE (just HTTP requests, no LLM)
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote_plus
import logging
import re

try:
    import httpx
except ImportError:
    httpx = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class SourceCrawlerAgent(BaseAgent):
    """Crawls Nigerian political news sources"""

    name = "source_crawler"
    description = "Scrapes Nigerian news websites for political information"
    tier = AgentTier.ANALYTICS
    cost_level = CostLevel.FREE  # Just HTTP requests
    handled_intents = []  # Background agent

    # Trusted Nigerian news sources
    SOURCES = {
        "premium_times": {
            "name": "Premium Times",
            "base_url": "https://www.premiumtimesng.com",
            "search_url": "https://www.premiumtimesng.com/?s={query}",
            "category": "news",
            "credibility": "high",
            "selectors": {
                "articles": "article, .post",
                "title": "h2 a, h3 a, .entry-title a",
                "link": "h2 a, h3 a, .entry-title a",
                "date": "time, .date, .published",
                "content": ".entry-content, .post-content, article"
            }
        },
        "punch": {
            "name": "Punch",
            "base_url": "https://punchng.com",
            "search_url": "https://punchng.com/?s={query}",
            "category": "news",
            "credibility": "high",
            "selectors": {
                "articles": "article, .post, .news-item",
                "title": "h2 a, h3 a, .entry-title a",
                "link": "h2 a, h3 a, .entry-title a",
                "date": "time, .date, .meta-date",
                "content": ".post-content, .entry-content, article"
            }
        },
        "channels_tv": {
            "name": "Channels TV",
            "base_url": "https://www.channelstv.com",
            "search_url": "https://www.channelstv.com/?s={query}",
            "category": "news",
            "credibility": "high",
            "selectors": {
                "articles": "article, .post",
                "title": "h2 a, h3 a, .title a",
                "link": "h2 a, h3 a, .title a",
                "date": "time, .date",
                "content": ".entry-content, .post-body"
            }
        },
        "thisday": {
            "name": "ThisDay",
            "base_url": "https://www.thisdaylive.com",
            "search_url": "https://www.thisdaylive.com/?s={query}",
            "category": "news",
            "credibility": "high",
            "selectors": {
                "articles": "article, .td-module-container",
                "title": "h3 a, .entry-title a",
                "link": "h3 a, .entry-title a",
                "date": "time, .td-post-date",
                "content": ".td-post-content, .entry-content"
            }
        },
        "vanguard": {
            "name": "Vanguard",
            "base_url": "https://www.vanguardngr.com",
            "search_url": "https://www.vanguardngr.com/?s={query}",
            "category": "news",
            "credibility": "medium",
            "selectors": {
                "articles": "article, .post",
                "title": "h2 a, .entry-title a",
                "link": "h2 a, .entry-title a",
                "date": "time, .post-date",
                "content": ".entry-content"
            }
        },
        "guardian": {
            "name": "The Guardian Nigeria",
            "base_url": "https://guardian.ng",
            "search_url": "https://guardian.ng/?s={query}",
            "category": "news",
            "credibility": "high",
            "selectors": {
                "articles": "article, .post",
                "title": "h2 a, h3 a",
                "link": "h2 a, h3 a",
                "date": "time, .date",
                "content": ".entry-content, .single-content"
            }
        },
    }

    # Official sources (different crawl strategy)
    OFFICIAL_SOURCES = {
        "inec": {
            "name": "INEC",
            "base_url": "https://www.inecnigeria.org",
            "category": "official",
            "credibility": "official"
        },
        "nass": {
            "name": "National Assembly",
            "base_url": "https://nass.gov.ng",
            "category": "official",
            "credibility": "official"
        }
    }

    # Request settings
    REQUEST_TIMEOUT = 30
    MAX_ARTICLES_PER_SOURCE = 10
    RATE_LIMIT_DELAY = 2  # seconds between requests

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._http_client = None

    async def can_handle(self, input: AgentInput) -> bool:
        return False  # Background agent

    async def handle(self, input: AgentInput) -> AgentOutput:
        """Not used directly - call crawl methods instead"""
        return self.fail("SourceCrawler is a background agent", "NOT_USER_FACING")

    async def crawl_for_entity(self, entity_name: str, max_per_source: int = 5) -> List[Dict]:
        """
        Crawl all sources for information about an entity.

        Args:
            entity_name: Name to search for (e.g., "Bola Tinubu")
            max_per_source: Maximum articles to fetch per source

        Returns:
            List of article metadata dicts
        """
        if not httpx or not BeautifulSoup:
            logger.error("httpx and beautifulsoup4 required for crawling")
            return []

        results = []
        query = quote_plus(entity_name)

        for source_name, source_config in self.SOURCES.items():
            try:
                if "search_url" in source_config:
                    articles = await self._search_source(
                        source_config["search_url"].format(query=query),
                        source_name,
                        source_config,
                        max_per_source
                    )
                    results.extend(articles)

                    # Rate limiting
                    await asyncio.sleep(self.RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"Failed to crawl {source_name}: {e}")
                continue

        logger.info(f"Crawled {len(results)} articles for '{entity_name}'")
        return results

    async def _search_source(
        self,
        url: str,
        source_name: str,
        source_config: Dict,
        max_articles: int
    ) -> List[Dict]:
        """Search a single source and extract article links"""
        try:
            async with httpx.AsyncClient(
                timeout=self.REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Decide9jaBot/1.0; +https://decide9ja.ng)"
                }
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text

        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error for {source_name}: {e.response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"Request failed for {source_name}: {e}")
            return []

        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        selectors = source_config["selectors"]
        articles = []

        # Find article containers
        for article in soup.select(selectors["articles"])[:max_articles]:
            try:
                # Extract link
                link_elem = article.select_one(selectors["link"])
                if not link_elem or not link_elem.get("href"):
                    continue

                link = link_elem["href"]
                if not link.startswith("http"):
                    link = urljoin(source_config["base_url"], link)

                # Extract title
                title_elem = article.select_one(selectors["title"])
                title = title_elem.get_text(strip=True) if title_elem else "No title"

                # Extract date
                date_elem = article.select_one(selectors["date"])
                date_str = date_elem.get_text(strip=True) if date_elem else None
                parsed_date = self._parse_date(date_str) if date_str else None

                articles.append({
                    "url": link,
                    "title": title,
                    "date": parsed_date,
                    "date_raw": date_str,
                    "source": source_name,
                    "source_name": source_config["name"],
                    "credibility": source_config["credibility"],
                    "crawled_at": datetime.utcnow().isoformat()
                })

            except Exception as e:
                logger.debug(f"Failed to parse article from {source_name}: {e}")
                continue

        return articles

    async def fetch_article_content(self, url: str, source_name: str = None) -> Dict:
        """
        Fetch full article content from URL.

        Args:
            url: Article URL
            source_name: Optional source name for selector lookup

        Returns:
            Dict with url, content (plain text), html
        """
        if not httpx or not BeautifulSoup:
            return {"url": url, "content": "", "html": "", "error": "dependencies_missing"}

        try:
            async with httpx.AsyncClient(
                timeout=self.REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Decide9jaBot/1.0; +https://decide9ja.ng)"
                }
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text

        except Exception as e:
            logger.warning(f"Failed to fetch article {url}: {e}")
            return {"url": url, "content": "", "html": "", "error": str(e)}

        soup = BeautifulSoup(html, 'html.parser')

        # Remove scripts, styles, ads, navigation
        for tag in soup.select('script, style, .ads, .advertisement, nav, footer, aside, .sidebar, .comments'):
            tag.decompose()

        # Try to find main content
        content_selectors = [
            'article .entry-content',
            '.post-content',
            '.entry-content',
            '.single-content',
            '.article-body',
            '.td-post-content',
            'article',
            'main',
            '.content'
        ]

        content = None
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 100:
                break

        if content:
            # Clean up the text
            text = content.get_text(strip=True, separator='\n')
            # Remove excessive whitespace
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)

            return {
                "url": url,
                "content": text[:10000],  # Limit content size
                "html": str(content)[:20000],
                "word_count": len(text.split()),
                "fetched_at": datetime.utcnow().isoformat()
            }

        return {
            "url": url,
            "content": soup.get_text(strip=True, separator='\n')[:5000],
            "html": "",
            "word_count": 0,
            "error": "content_extraction_failed"
        }

    async def crawl_recent_news(self, hours: int = 24, max_articles: int = 50) -> List[Dict]:
        """
        Crawl recent news from all sources (not entity-specific).

        Args:
            hours: How recent the news should be
            max_articles: Maximum total articles

        Returns:
            List of recent article metadata
        """
        results = []

        for source_name, source_config in self.SOURCES.items():
            try:
                # Fetch homepage or news section
                url = source_config["base_url"]
                articles = await self._crawl_homepage(url, source_name, source_config)
                results.extend(articles)

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"Failed to crawl recent from {source_name}: {e}")
                continue

        # Sort by date (most recent first)
        results.sort(key=lambda x: x.get("date") or "", reverse=True)

        return results[:max_articles]

    async def _crawl_homepage(
        self,
        url: str,
        source_name: str,
        source_config: Dict
    ) -> List[Dict]:
        """Crawl homepage for recent articles"""
        try:
            async with httpx.AsyncClient(
                timeout=self.REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Decide9jaBot/1.0)"
                }
            ) as client:
                response = await client.get(url)
                html = response.text

        except Exception as e:
            logger.warning(f"Failed to fetch homepage {url}: {e}")
            return []

        soup = BeautifulSoup(html, 'html.parser')
        selectors = source_config["selectors"]
        articles = []

        for article in soup.select(selectors["articles"])[:self.MAX_ARTICLES_PER_SOURCE]:
            try:
                link_elem = article.select_one(selectors["link"])
                if not link_elem or not link_elem.get("href"):
                    continue

                link = link_elem["href"]
                if not link.startswith("http"):
                    link = urljoin(source_config["base_url"], link)

                title_elem = article.select_one(selectors["title"])
                title = title_elem.get_text(strip=True) if title_elem else "No title"

                # Filter for political content
                if self._is_political_content(title):
                    articles.append({
                        "url": link,
                        "title": title,
                        "source": source_name,
                        "source_name": source_config["name"],
                        "credibility": source_config["credibility"],
                        "crawled_at": datetime.utcnow().isoformat()
                    })

            except Exception as e:
                continue

        return articles

    def _is_political_content(self, title: str) -> bool:
        """Check if content is likely political"""
        political_keywords = [
            "tinubu", "atiku", "obi", "apc", "pdp", "labour party",
            "senate", "house of rep", "governor", "minister", "president",
            "election", "inec", "efcc", "court", "tribunal",
            "budget", "naira", "subsidy", "fuel", "economy",
            "security", "insecurity", "bandit", "terrorist",
            "assembly", "bill", "law", "policy", "government"
        ]
        title_lower = title.lower()
        return any(kw in title_lower for kw in political_keywords)

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to ISO format"""
        if not date_str:
            return None

        # Common date patterns
        patterns = [
            r"(\d{4}-\d{2}-\d{2})",  # 2024-01-15
            r"(\d{1,2}/\d{1,2}/\d{4})",  # 15/01/2024
            r"(\w+ \d{1,2}, \d{4})",  # January 15, 2024
            r"(\d{1,2} \w+ \d{4})",  # 15 January 2024
        ]

        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    # Try to parse and return ISO format
                    from dateutil import parser
                    parsed = parser.parse(match.group(1))
                    return parsed.strftime("%Y-%m-%d")
                except:
                    pass

        return None

    def stats(self) -> Dict:
        """Return crawler statistics"""
        base_stats = super().stats()
        base_stats.update({
            "sources_count": len(self.SOURCES),
            "sources": list(self.SOURCES.keys())
        })
        return base_stats
