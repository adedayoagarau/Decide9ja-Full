"""
Archivi.ng Nigerian Newspaper Scraper
=====================================
Scrapes historical Nigerian newspapers from archivi.ng.

Currently available:
- PM News (1960-2010) - ~50,000 pages

Planned for future:
- Punch, Guardian, Vanguard, Tribune, ThisDay (when uploaded)

Legal: Archivi.ng prohibits commercial scraping. Decide9ja is a public
civic education chatbot (non-commercial), so scraping is permitted.

Usage:
    python -m app.services.archiving_scraper --source pm-news --year 1999
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Base configuration
BASE_URL = "https://archivi.ng"
SEARCH_URL = f"{BASE_URL}/search"
EDITIONS_URL = f"{BASE_URL}/editions"

# Available sources (as of 2024)
SOURCES = {
    "pm-news": {
        "name": "PM News",
        "slug": "pm-news",
        "start_year": 1960,
        "end_year": 2010,
        "description": "Nigerian evening newspaper, part of ICNL",
    },
    "nigeria-magazine": {
        "name": "Nigeria Magazine",
        "slug": "nigeria-magazine",
        "start_year": 1960,
        "end_year": 1990,
        "description": "Quarterly magazine of general interest",
    },
}

# Known politicians for extraction (expanded list for historical coverage)
HISTORICAL_POLITICIANS = [
    # First Republic (1960-1966)
    "nnamdi azikiwe", "azikiwe", "zik", "abubakar tafawa balewa", "balewa",
    "obafemi awolowo", "awolowo", "ahmadu bello", "sardauna",

    # Military Era (1966-1979)
    "johnson aguiyi-ironsi", "ironsi", "yakubu gowon", "gowon",
    "murtala mohammed", "murtala", "olusegun obasanjo", "obasanjo",

    # Second Republic (1979-1983)
    "shehu shagari", "shagari", "alex ekwueme", "ekwueme",

    # Military Era (1983-1999)
    "muhammadu buhari", "buhari", "ibrahim babangida", "babangida", "ibb",
    "ernest shonekan", "shonekan", "sani abacha", "abacha",
    "abdulsalami abubakar", "abdulsalami",

    # Fourth Republic (1999-present)
    "olusegun obasanjo", "atiku abubakar", "atiku", "umaru yar'adua", "yar'adua",
    "goodluck jonathan", "jonathan", "bola tinubu", "tinubu",

    # Other notable figures
    "moshood abiola", "abiola", "mko", "ken saro-wiwa", "saro-wiwa",
    "wole soyinka", "soyinka", "fela kuti", "fela", "gani fawehinmi", "fawehinmi",
    "tai solarin", "balarabe musa", "aminu kano", "jim nwobodo",
    "samuel ogbemudia", "lateef jakande", "bisi onabanjo", "ambrose alli",
]


@dataclass
class NewspaperPage:
    """Represents a single newspaper page from archivi.ng."""
    page_id: str
    source: str
    source_name: str
    date: str
    page_number: int
    title: str
    image_url: Optional[str]
    text_content: Optional[str]
    politicians_mentioned: List[str]
    url: str
    scraped_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NewspaperEdition:
    """Represents a complete newspaper edition (all pages for a date)."""
    edition_id: str
    source: str
    source_name: str
    date: str
    pages: List[NewspaperPage]
    total_pages: int
    url: str

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "pages": [p.to_dict() for p in self.pages],
        }


class ArchiviNgScraper:
    """
    Scraper for archivi.ng Nigerian newspaper archives.

    Features:
    - Search by date range
    - Extract text from pages (if available) or prepare for OCR
    - Extract politician mentions
    - Rate limiting to respect the site
    """

    def __init__(self, timeout: int = 30, rate_limit: float = 1.0):
        self.timeout = timeout
        self.rate_limit = rate_limit  # seconds between requests
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request_time = 0

        self.stats = {
            "pages_scraped": 0,
            "editions_found": 0,
            "politicians_extracted": 0,
            "errors": 0,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with browser-like headers."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                }
            )
        return self._client

    async def _rate_limit_wait(self):
        """Wait to respect rate limiting."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def ocr_with_claude_vision(self, image_url: str) -> Optional[str]:
        """
        Extract text from a newspaper page image using Claude Vision API.

        Args:
            image_url: URL of the scanned newspaper page image

        Returns:
            Extracted text or None if OCR failed
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, skipping OCR")
            return None

        try:
            # Download image
            client = await self._get_client()
            response = await client.get(image_url)

            if response.status_code != 200:
                logger.warning(f"Failed to download image: {response.status_code}")
                return None

            # Get image content type
            content_type = response.headers.get("content-type", "image/jpeg")
            if "png" in content_type.lower():
                media_type = "image/png"
            elif "gif" in content_type.lower():
                media_type = "image/gif"
            elif "webp" in content_type.lower():
                media_type = "image/webp"
            else:
                media_type = "image/jpeg"

            # Base64 encode image
            image_data = base64.standard_b64encode(response.content).decode("utf-8")

            # Call Claude Vision API
            import anthropic

            anthropic_client = anthropic.Anthropic(api_key=api_key)

            message = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": """Extract ALL readable text from this Nigerian newspaper page image.

Instructions:
1. Read every article, headline, caption, and text visible on the page
2. Preserve the structure: headlines in CAPS, article text as paragraphs
3. Include dates, bylines, and source credits if visible
4. Pay special attention to names of politicians, government officials, and public figures
5. Note any mentioned political parties, government agencies, or institutions
6. If text is unclear, indicate with [unclear] but try your best to read it

Format output as:
HEADLINE
Article text...

NEXT HEADLINE
Next article text...

Extract the text now:"""
                            }
                        ],
                    }
                ],
            )

            extracted_text = message.content[0].text
            logger.info(f"OCR extracted {len(extracted_text)} chars from {image_url}")

            return extracted_text

        except Exception as e:
            logger.error(f"Claude Vision OCR failed: {e}")
            return None

    async def _fetch(self, url: str) -> Optional[str]:
        """Fetch a URL with rate limiting and error handling."""
        await self._rate_limit_wait()

        try:
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code == 200:
                return response.text
            elif response.status_code == 403:
                logger.warning(f"Access forbidden (403): {url}")
                return None
            elif response.status_code == 429:
                logger.warning(f"Rate limited (429): {url}, waiting 30s")
                await asyncio.sleep(30)
                return await self._fetch(url)  # Retry
            else:
                logger.warning(f"HTTP {response.status_code}: {url}")
                return None

        except Exception as e:
            logger.error(f"Fetch error {url}: {e}")
            self.stats["errors"] += 1
            return None

    async def search_by_date(
        self,
        source: str,
        year: int,
        month: Optional[int] = None,
        day: Optional[int] = None,
        keyword: Optional[str] = None
    ) -> List[Dict]:
        """
        Search archivi.ng for newspaper pages by date.

        Args:
            source: Source slug (e.g., "pm-news")
            year: Year to search
            month: Optional month (1-12)
            day: Optional day (1-31)
            keyword: Optional keyword to search for

        Returns:
            List of search result dicts
        """
        # Build search query
        # archivi.ng uses Elasticsearch-style search
        query_parts = [f"source:{source}"]

        if year:
            if month and day:
                date_str = f"{year}-{month:02d}-{day:02d}"
                query_parts.append(f"date:{date_str}")
            elif month:
                query_parts.append(f"date:{year}-{month:02d}")
            else:
                query_parts.append(f"date:{year}")

        if keyword:
            query_parts.append(keyword)

        query = " ".join(query_parts)
        search_url = f"{SEARCH_URL}?q={quote(query)}"

        logger.info(f"Searching archivi.ng: {query}")

        html = await self._fetch(search_url)
        if not html:
            return []

        return self._parse_search_results(html)

    async def browse_editions(
        self,
        source: str,
        year: int,
        limit: int = 100
    ) -> List[Dict]:
        """
        Browse the editions page directly to find newspaper pages.
        Fallback when search doesn't return results.

        Tries multiple URL patterns that archivi.ng might use.
        """
        results = []

        # Try different URL patterns
        patterns = [
            f"{EDITIONS_URL}/{source}",              # /editions/pm-news (main listing)
            f"{EDITIONS_URL}/{source}/{year}",       # /editions/pm-news/1999
            f"{EDITIONS_URL}/{source}?year={year}",  # /editions/pm-news?year=1999
            f"{BASE_URL}/{source}/{year}",           # /pm-news/1999
            f"{BASE_URL}/newspaper/{source}/{year}", # /newspaper/pm-news/1999
            f"{EDITIONS_URL}?source={source}&year={year}",  # /editions?source=pm-news&year=1999
        ]

        for url_pattern in patterns:
            logger.info(f"Trying editions URL: {url_pattern}")
            html = await self._fetch(url_pattern)

            if html:
                # Look for any links that might be newspaper editions/pages
                soup = BeautifulSoup(html, 'html.parser')

                # Find all links
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)

                    # Skip navigation and query links
                    if '?' in href or href.startswith('#'):
                        continue

                    # archivi.ng uses /search/{id} format for pages (e.g., /search/oyhy24oBCApQwdEHPVjl)
                    # Also look for date-like patterns or edition/page links
                    is_search_page = '/search/' in href and not href.endswith('/search')
                    is_edition_link = any(pattern in href.lower() for pattern in [
                        f'/{year}/', str(year), '/page/', '/edition/',
                        '/view/', '/read/', '/issue/'
                    ])

                    if is_search_page or is_edition_link:
                        url = urljoin(BASE_URL, href)
                        title = text[:200] if text else f"Edition: {href}"

                        if title and len(title) > 2:
                            results.append({
                                "page_id": hashlib.md5(url.encode()).hexdigest()[:16],
                                "url": url,
                                "title": title,
                                "date": None,
                                "image_url": None,
                            })

                if results:
                    logger.info(f"Found {len(results)} results from editions browser: {url_pattern}")
                    break
                else:
                    # Log HTML preview for debugging
                    logger.debug(f"No results from {url_pattern}. HTML preview: {html[:1000]}")

        # Deduplicate
        seen_urls = set()
        unique_results = []
        for r in results:
            if r['url'] not in seen_urls:
                seen_urls.add(r['url'])
                unique_results.append(r)

        return unique_results[:limit]

    def _parse_search_results(self, html: str) -> List[Dict]:
        """Parse search results page."""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # Debug: log HTML snippet if no results found with primary selectors
        # Try multiple selector strategies

        # Strategy 1: Common result container classes
        for item in soup.select('.search-result, .result-item, article, .card, .item, .result'):
            try:
                result = self._parse_result_item(item)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Error parsing result item: {e}")

        # Strategy 2: If no results, try finding links with newspaper/page patterns
        # archivi.ng uses /search/{id} format for individual pages
        if not results:
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                # Skip query params and anchor links
                if '?' in href or href.startswith('#'):
                    continue

                # archivi.ng uses /search/ID format (e.g., /search/oyhy24oBCApQwdEHPVjl)
                is_search_page = '/search/' in href and not href.endswith('/search')
                is_page_link = any(pattern in href.lower() for pattern in ['/page/', '/edition/', '/issue/', '/newspaper/', '/view/', '/item/', '/read/'])

                if is_search_page or is_page_link:
                    url = urljoin(BASE_URL, href)
                    title = link.get_text(strip=True)[:200] or f"Page: {href}"
                    if title and len(title) > 3:
                        results.append({
                            "page_id": hashlib.md5(url.encode()).hexdigest()[:16],
                            "url": url,
                            "title": title,
                            "date": None,
                            "image_url": None,
                        })

        # Strategy 3: If still no results, try finding any div/li with links inside
        if not results:
            for container in soup.select('div, li, tr'):
                link = container.find('a', href=True)
                if link:
                    href = link.get('href', '')
                    if href and not href.startswith('#') and not href.startswith('javascript'):
                        # Skip navigation/header links
                        if any(skip in href.lower() for skip in ['login', 'signup', 'about', 'contact', 'help', 'faq']):
                            continue
                        url = urljoin(BASE_URL, href)
                        title = link.get_text(strip=True)[:200]
                        if title and len(title) > 5:
                            results.append({
                                "page_id": hashlib.md5(url.encode()).hexdigest()[:16],
                                "url": url,
                                "title": title,
                                "date": None,
                                "image_url": None,
                            })

        # Debug logging if still no results
        if not results:
            # Log first 2000 chars of HTML for debugging
            logger.warning(f"No results found. HTML preview: {html[:2000]}")

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in results:
            if r['url'] not in seen_urls:
                seen_urls.add(r['url'])
                unique_results.append(r)

        return unique_results[:100]  # Limit to 100 results

    def _parse_result_item(self, item) -> Optional[Dict]:
        """Parse a single search result item."""
        # Extract link
        link = item.select_one('a[href]')
        if not link:
            return None

        href = link.get('href', '')
        if not href:
            return None

        # Make absolute URL
        url = urljoin(BASE_URL, href)

        # Extract ID from URL (pattern: /search/[ID])
        id_match = re.search(r'/search/([a-zA-Z0-9_-]+)', url)
        page_id = id_match.group(1) if id_match else hashlib.md5(url.encode()).hexdigest()[:16]

        # Extract title/text
        title = item.get_text(strip=True)[:200]

        # Look for date
        date_elem = item.select_one('.date, time, [datetime]')
        date_str = date_elem.get('datetime') if date_elem else None

        # Look for image
        img = item.select_one('img')
        image_url = img.get('src') if img else None
        if image_url:
            image_url = urljoin(BASE_URL, image_url)

        return {
            "page_id": page_id,
            "url": url,
            "title": title,
            "date": date_str,
            "image_url": image_url,
        }

    async def get_page_content(
        self,
        page_url: str,
        use_ocr: bool = False
    ) -> Optional[NewspaperPage]:
        """
        Fetch and parse a single newspaper page.

        Args:
            page_url: Full URL to the page
            use_ocr: Whether to use Claude Vision OCR for text extraction

        Returns:
            NewspaperPage object or None
        """
        html = await self._fetch(page_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Extract page ID from URL
        id_match = re.search(r'/search/([a-zA-Z0-9_-]+)', page_url)
        page_id = id_match.group(1) if id_match else hashlib.md5(page_url.encode()).hexdigest()[:16]

        # Extract title
        title_elem = soup.select_one('h1, .title, .headline')
        title = title_elem.get_text(strip=True) if title_elem else f"Page {page_id}"

        # Try to extract date from title or page content
        date_str = self._extract_date_from_text(title)

        # Extract source
        source = "pm-news"  # Default for now
        source_name = "PM News"

        # Look for page number
        page_number = 1
        page_match = re.search(r'[Pp]age\s*(\d+)', title)
        if page_match:
            page_number = int(page_match.group(1))

        # Get image URL (the scanned newspaper page)
        image_url = None
        for img in soup.select('img'):
            src = img.get('src', '')
            if 'page' in src.lower() or 'newspaper' in src.lower() or 'scan' in src.lower():
                image_url = urljoin(BASE_URL, src)
                break

        if not image_url:
            # Try any large image
            for img in soup.select('img'):
                src = img.get('src', '')
                if src and not any(x in src.lower() for x in ['logo', 'icon', 'avatar']):
                    image_url = urljoin(BASE_URL, src)
                    break

        # Extract any text content (OCR may have been done by archivi.ng)
        text_content = None
        content_elem = soup.select_one('.content, .text, .ocr-text, article, .page-content')
        if content_elem:
            text_content = content_elem.get_text(separator='\n', strip=True)

        # If no text, try the whole body (minus scripts/styles)
        if not text_content:
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            body_text = soup.get_text(separator='\n', strip=True)[:5000]
            # Only use body text if it has substantial content
            if len(body_text) > 200:
                text_content = body_text

        # If still no meaningful text and OCR is enabled, use Claude Vision
        if use_ocr and (not text_content or len(text_content) < 200) and image_url:
            logger.info(f"Using Claude Vision OCR for {page_url}")
            ocr_text = await self.ocr_with_claude_vision(image_url)
            if ocr_text:
                text_content = ocr_text
                self.stats["ocr_pages"] = self.stats.get("ocr_pages", 0) + 1

        # Extract politicians mentioned
        politicians = self._extract_politicians(text_content or title)

        self.stats["pages_scraped"] += 1
        self.stats["politicians_extracted"] += len(politicians)

        return NewspaperPage(
            page_id=page_id,
            source=source,
            source_name=source_name,
            date=date_str or "",
            page_number=page_number,
            title=title,
            image_url=image_url,
            text_content=text_content,
            politicians_mentioned=politicians,
            url=page_url,
            scraped_at=datetime.now().isoformat(),
        )

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """Extract date from text like 'Monday, July 3, 2000'."""
        # Pattern for dates like "July 3, 2000" or "3 July 2000"
        patterns = [
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # July 3, 2000
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',     # 3 July 2000
            r'(\d{4})-(\d{2})-(\d{2})',          # 2000-07-03
        ]

        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    if groups[0].isdigit():
                        # Already ISO format or day first
                        if len(groups[0]) == 4:
                            return f"{groups[0]}-{groups[1]}-{groups[2]}"
                        else:
                            month = months.get(groups[1].lower(), 1)
                            return f"{groups[2]}-{month:02d}-{int(groups[0]):02d}"
                    else:
                        # Month name first
                        month = months.get(groups[0].lower(), 1)
                        return f"{groups[2]}-{month:02d}-{int(groups[1]):02d}"
                except:
                    pass

        return None

    def _extract_politicians(self, text: str) -> List[str]:
        """Extract politician names from text."""
        if not text:
            return []

        text_lower = text.lower()
        found = []

        for name in HISTORICAL_POLITICIANS:
            if name in text_lower:
                # Normalize the name
                normalized = name.title()
                if normalized not in found:
                    found.append(normalized)

        return found

    async def scrape_year(
        self,
        source: str,
        year: int,
        limit: int = 100,
        use_ocr: bool = False
    ) -> Dict[str, Any]:
        """
        Scrape all available pages for a source in a given year.

        Args:
            source: Source slug (e.g., "pm-news")
            year: Year to scrape
            limit: Maximum pages to scrape
            use_ocr: Use Claude Vision OCR for text extraction (slower, costs API calls)

        Returns:
            Statistics dict
        """
        logger.info(f"Starting archivi.ng scrape: {source} for {year}")

        source_info = SOURCES.get(source)
        if not source_info:
            return {"error": f"Unknown source: {source}"}

        if year < source_info["start_year"] or year > source_info["end_year"]:
            return {
                "error": f"{source} not available for {year}. "
                         f"Available: {source_info['start_year']}-{source_info['end_year']}"
            }

        all_pages = []

        # First try: search month by month
        for month in range(1, 13):
            if len(all_pages) >= limit:
                break

            logger.info(f"Searching {source} for {year}-{month:02d}")

            results = await self.search_by_date(source, year, month)

            for result in results:
                if len(all_pages) >= limit:
                    break

                page = await self.get_page_content(result["url"], use_ocr=use_ocr)
                if page:
                    all_pages.append(page)

        # Fallback: If search returned nothing, try browsing editions directly
        if not all_pages:
            logger.info(f"Search returned 0 results, trying editions browser for {source}/{year}")
            results = await self.browse_editions(source, year, limit)
            for result in results:
                if len(all_pages) >= limit:
                    break
                page = await self.get_page_content(result["url"], use_ocr=use_ocr)
                if page:
                    all_pages.append(page)

        self.stats["editions_found"] = len(set(p.date for p in all_pages if p.date))

        return {
            "source": source,
            "year": year,
            "pages_scraped": len(all_pages),
            "unique_dates": len(set(p.date for p in all_pages if p.date)),
            "politicians_found": list(set(
                p for page in all_pages for p in page.politicians_mentioned
            )),
            "pages": [p.to_dict() for p in all_pages],
            "stats": self.stats,
        }

    async def scrape_date(
        self,
        source: str,
        year: int,
        month: int,
        day: int,
        use_ocr: bool = False
    ) -> Optional[NewspaperEdition]:
        """
        Scrape all pages for a specific date.

        Args:
            source: Source slug
            year, month, day: Date to scrape
            use_ocr: Use Claude Vision OCR for text extraction

        Returns:
            NewspaperEdition or None
        """
        date_str = f"{year}-{month:02d}-{day:02d}"
        logger.info(f"Scraping {source} for {date_str}")

        results = await self.search_by_date(source, year, month, day)

        if not results:
            return None

        pages = []
        for result in results:
            page = await self.get_page_content(result["url"], use_ocr=use_ocr)
            if page:
                pages.append(page)

        if not pages:
            return None

        source_info = SOURCES.get(source, {"name": source})

        return NewspaperEdition(
            edition_id=hashlib.md5(f"{source}_{date_str}".encode()).hexdigest()[:16],
            source=source,
            source_name=source_info.get("name", source),
            date=date_str,
            pages=pages,
            total_pages=len(pages),
            url=f"{EDITIONS_URL}/{source}",
        )


async def store_scraped_pages(pages: List[NewspaperPage], db=None):
    """
    Store scraped newspaper pages in the database.

    Args:
        pages: List of NewspaperPage objects
        db: Database session (optional, will create if not provided)
    """
    from app.database import SessionLocal, NewsArticle
    from app.services.politician_mention_service import extract_and_link_politicians

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    stored = 0
    try:
        for page in pages:
            # Create article ID from page ID
            article_id = f"archiving_{page.page_id}"

            # Check if exists
            existing = db.query(NewsArticle).filter(
                NewsArticle.article_id == article_id
            ).first()

            if existing:
                continue

            # Create NewsArticle
            article = NewsArticle(
                article_id=article_id,
                title=page.title,
                url=page.url,
                source="archiving",
                source_name=f"archivi.ng - {page.source_name}",
                excerpt=page.text_content[:500] if page.text_content else None,
                full_text=page.text_content,
                politicians_json=json.dumps(page.politicians_mentioned),
                scraped_at=datetime.fromisoformat(page.scraped_at) if page.scraped_at else datetime.now(),
            )

            db.add(article)
            db.flush()

            # Link politicians
            try:
                extract_and_link_politicians(article, db)
            except Exception as e:
                logger.warning(f"Error linking politicians: {e}")

            stored += 1

        db.commit()
        logger.info(f"Stored {stored} pages from archivi.ng")

    finally:
        if close_db:
            db.close()

    return stored


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Archivi.ng Scraper")
    parser.add_argument("--source", type=str, default="pm-news", help="Source slug")
    parser.add_argument("--year", type=int, required=True, help="Year to scrape")
    parser.add_argument("--month", type=int, help="Month (1-12)")
    parser.add_argument("--day", type=int, help="Day (1-31)")
    parser.add_argument("--limit", type=int, default=50, help="Max pages")
    parser.add_argument("--ocr", action="store_true", help="Use Claude Vision OCR for text extraction")
    parser.add_argument("--store", action="store_true", help="Store in database")

    args = parser.parse_args()

    async def main():
        scraper = ArchiviNgScraper()

        try:
            if args.day and args.month:
                # Scrape specific date
                edition = await scraper.scrape_date(
                    args.source, args.year, args.month, args.day, use_ocr=args.ocr
                )
                if edition:
                    print(f"\nEdition: {edition.source_name} - {edition.date}")
                    print(f"Pages: {edition.total_pages}")
                    for page in edition.pages[:3]:
                        print(f"  - {page.title[:60]}...")
                        if page.politicians_mentioned:
                            print(f"    Politicians: {', '.join(page.politicians_mentioned[:5])}")
                else:
                    print("No edition found for that date")
            else:
                # Scrape whole year
                result = await scraper.scrape_year(
                    args.source, args.year, args.limit, use_ocr=args.ocr
                )
                print(f"\nScrape complete for {args.source} {args.year}:")
                print(f"  Pages: {result.get('pages_scraped', 0)}")
                print(f"  Unique dates: {result.get('unique_dates', 0)}")
                print(f"  Politicians: {result.get('politicians_found', [])[:10]}")

                if args.store and result.get('pages'):
                    pages = [NewspaperPage(**p) for p in result['pages']]
                    stored = await store_scraped_pages(pages)
                    print(f"  Stored: {stored}")

        finally:
            await scraper.close()

    asyncio.run(main())
