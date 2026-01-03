"""
Ministry & OSGF Data Crawler for Decide9ja.

Crawls:
- https://www.osgf.gov.ng/ministries/ - Office of the Secretary to the Government
- Individual ministry websites
- Project/initiative data from ministry pages

Uses proper headers and retry logic to handle blocking.
"""
import asyncio
import logging
import random
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse
import time

logger = logging.getLogger(__name__)

# Realistic browser user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Known ministry websites
MINISTRY_URLS = {
    "finance": "https://finance.gov.ng",
    "education": "https://education.gov.ng",
    "health": "https://health.gov.ng",
    "works": "https://works.gov.ng",
    "agriculture": "https://fmard.gov.ng",
    "power": "https://power.gov.ng",
    "transport": "https://transport.gov.ng",
    "communications": "https://communications.gov.ng",
    "justice": "https://justice.gov.ng",
    "defence": "https://defence.gov.ng",
    "interior": "https://interior.gov.ng",
    "foreign_affairs": "https://foreignaffairs.gov.ng",
    "petroleum": "https://petroleum.gov.ng",
    "environment": "https://environment.gov.ng",
    "science": "https://scienceandtech.gov.ng",
    "water": "https://waterresources.gov.ng",
    "housing": "https://housingandurban.gov.ng",
    "aviation": "https://aviation.gov.ng",
    "trade": "https://trade.gov.ng",
    "industry": "https://industry.gov.ng",
    "labour": "https://labour.gov.ng",
    "women": "https://womenaffairs.gov.ng",
    "youth": "https://youth.gov.ng",
    "sports": "https://sports.gov.ng",
    "information": "https://fmic.gov.ng",
    "budget": "https://budgetoffice.gov.ng",
    "humanitarian": "https://humanitarian.gov.ng",
}

# Alternative data sources
ALTERNATIVE_SOURCES = {
    "osgf": "https://www.osgf.gov.ng",
    "open_treasury": "https://opentreasury.gov.ng",
    "budgit": "https://yourbudgit.com",
    "tracka": "https://tracka.ng",
    "follow_the_money": "https://followthemoney.ng",
}


@dataclass
class CrawlResult:
    """Result from a crawl attempt."""
    url: str
    success: bool
    status_code: Optional[int] = None
    content: Optional[str] = None
    error: Optional[str] = None
    crawled_at: datetime = field(default_factory=datetime.now)


@dataclass
class MinistryInfo:
    """Extracted ministry information."""
    name: str
    url: str
    minister: Optional[str] = None
    permanent_secretary: Optional[str] = None
    description: Optional[str] = None
    departments: List[str] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    contact: Optional[Dict[str, str]] = None


@dataclass
class ProjectInfo:
    """Extracted project information."""
    title: str
    ministry: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    budget: Optional[float] = None
    status: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None


class MinistryCrawler:
    """Crawler for Nigerian ministry websites."""

    def __init__(self, max_retries: int = 3, delay_range: tuple = (2, 5)):
        self.max_retries = max_retries
        self.delay_range = delay_range
        self.session = None
        self._results: List[CrawlResult] = []

    def _get_headers(self) -> Dict[str, str]:
        """Get realistic browser headers."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self.session is None:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=5, force_close=True)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
        return self.session

    async def close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_url(self, url: str) -> CrawlResult:
        """Fetch a URL with retries and proper headers."""
        session = await self._get_session()

        for attempt in range(self.max_retries):
            try:
                # Random delay between requests
                if attempt > 0:
                    delay = random.uniform(*self.delay_range) * (attempt + 1)
                    await asyncio.sleep(delay)

                headers = self._get_headers()
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{self.max_retries})")

                async with session.get(url, headers=headers, allow_redirects=True) as response:
                    status = response.status

                    if status == 200:
                        content = await response.text()
                        result = CrawlResult(
                            url=url,
                            success=True,
                            status_code=status,
                            content=content
                        )
                        self._results.append(result)
                        return result

                    elif status == 403:
                        logger.warning(f"403 Forbidden for {url}, trying with different UA")
                        continue

                    elif status == 429:
                        # Rate limited - wait longer
                        wait_time = int(response.headers.get('Retry-After', 60))
                        logger.warning(f"Rate limited, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue

                    else:
                        logger.warning(f"HTTP {status} for {url}")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url}")
            except Exception as e:
                logger.warning(f"Error fetching {url}: {e}")

        # All retries failed
        result = CrawlResult(
            url=url,
            success=False,
            error=f"Failed after {self.max_retries} attempts"
        )
        self._results.append(result)
        return result

    def fetch_url_sync(self, url: str) -> CrawlResult:
        """Synchronous version using requests library."""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # Configure retries
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)

        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(*self.delay_range) * (attempt + 1))

                headers = self._get_headers()
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{self.max_retries})")

                response = session.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    return CrawlResult(
                        url=url,
                        success=True,
                        status_code=200,
                        content=response.text
                    )
                elif response.status_code == 403:
                    logger.warning(f"403 Forbidden for {url}")
                    continue
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")

            except requests.Timeout:
                logger.warning(f"Timeout fetching {url}")
            except requests.RequestException as e:
                logger.warning(f"Error fetching {url}: {e}")

        return CrawlResult(
            url=url,
            success=False,
            error=f"Failed after {self.max_retries} attempts"
        )

    def extract_ministry_info(self, html: str, url: str) -> Optional[MinistryInfo]:
        """Extract ministry information from HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Try to extract ministry name
            name = None
            title_tag = soup.find('title')
            if title_tag:
                name = title_tag.text.strip()

            # Look for minister name
            minister = None
            minister_patterns = [
                r'Minister[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                r'Hon\.?\s*Minister[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            ]
            for pattern in minister_patterns:
                match = re.search(pattern, html)
                if match:
                    minister = match.group(1)
                    break

            # Look for description/about
            description = None
            about_section = soup.find(['div', 'section'], class_=re.compile(r'about|mission|overview', re.I))
            if about_section:
                description = about_section.get_text(strip=True)[:500]

            # Extract departments
            departments = []
            dept_list = soup.find_all('a', href=re.compile(r'department|directorate', re.I))
            for dept in dept_list[:10]:
                dept_text = dept.get_text(strip=True)
                if dept_text and len(dept_text) > 3:
                    departments.append(dept_text)

            if name:
                return MinistryInfo(
                    name=name,
                    url=url,
                    minister=minister,
                    description=description,
                    departments=departments
                )

        except ImportError:
            logger.error("BeautifulSoup not installed. Run: pip install beautifulsoup4")
        except Exception as e:
            logger.error(f"Error extracting ministry info: {e}")

        return None

    def extract_projects(self, html: str, source_url: str) -> List[ProjectInfo]:
        """Extract project information from HTML."""
        projects = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Look for project-related content
            project_containers = soup.find_all(
                ['div', 'article', 'li', 'tr'],
                class_=re.compile(r'project|initiative|programme|program', re.I)
            )

            for container in project_containers[:50]:
                title_elem = container.find(['h2', 'h3', 'h4', 'strong', 'a'])
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                if len(title) < 5:
                    continue

                # Try to extract budget
                budget = None
                budget_match = re.search(r'[₦N]\s*([\d,]+(?:\.\d+)?)\s*(?:billion|million|bn|m)?', container.text, re.I)
                if budget_match:
                    amount = float(budget_match.group(1).replace(',', ''))
                    if 'billion' in container.text.lower() or 'bn' in container.text.lower():
                        amount *= 1_000_000_000
                    elif 'million' in container.text.lower() or 'm' in container.text.lower():
                        amount *= 1_000_000
                    budget = amount

                # Try to extract status
                status = None
                status_keywords = {
                    'completed': 'Completed',
                    'ongoing': 'Ongoing',
                    'abandoned': 'Abandoned',
                    'not started': 'Not Started',
                    'in progress': 'Ongoing',
                }
                text_lower = container.text.lower()
                for keyword, status_val in status_keywords.items():
                    if keyword in text_lower:
                        status = status_val
                        break

                # Try to extract state
                state = None
                from ..services.fuzzy_match import NIGERIAN_STATES
                for s in NIGERIAN_STATES:
                    if s.lower() in text_lower:
                        state = s
                        break

                projects.append(ProjectInfo(
                    title=title[:200],
                    budget=budget,
                    status=status,
                    state=state,
                    source_url=source_url,
                    description=container.get_text(strip=True)[:300]
                ))

        except ImportError:
            logger.error("BeautifulSoup not installed")
        except Exception as e:
            logger.error(f"Error extracting projects: {e}")

        return projects

    async def crawl_osgf(self) -> Dict[str, Any]:
        """Crawl OSGF website for ministry information."""
        results = {
            "ministries": [],
            "errors": [],
            "crawled_at": datetime.now().isoformat()
        }

        # Try main OSGF page
        osgf_result = await self.fetch_url("https://www.osgf.gov.ng/ministries/")

        if osgf_result.success:
            info = self.extract_ministry_info(osgf_result.content, osgf_result.url)
            if info:
                results["ministries"].append(info)

            # Extract links to individual ministries
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(osgf_result.content, 'html.parser')
            ministry_links = soup.find_all('a', href=re.compile(r'/ministry', re.I))

            for link in ministry_links[:30]:
                href = link.get('href')
                if href:
                    full_url = urljoin(osgf_result.url, href)
                    ministry_result = await self.fetch_url(full_url)
                    if ministry_result.success:
                        info = self.extract_ministry_info(
                            ministry_result.content,
                            ministry_result.url
                        )
                        if info:
                            results["ministries"].append(info)
                    await asyncio.sleep(random.uniform(1, 3))
        else:
            results["errors"].append(f"Failed to fetch OSGF: {osgf_result.error}")
            logger.warning("OSGF blocked. Trying individual ministry websites.")

        return results

    async def crawl_ministry_websites(self) -> Dict[str, Any]:
        """Crawl individual ministry websites."""
        results = {
            "ministries": [],
            "projects": [],
            "errors": [],
            "crawled_at": datetime.now().isoformat()
        }

        for ministry_key, url in MINISTRY_URLS.items():
            logger.info(f"Crawling {ministry_key}: {url}")

            result = await self.fetch_url(url)
            if result.success:
                info = self.extract_ministry_info(result.content, url)
                if info:
                    results["ministries"].append({
                        "key": ministry_key,
                        "name": info.name,
                        "minister": info.minister,
                        "description": info.description,
                        "departments": info.departments
                    })

                # Try to find projects page
                projects_urls = [
                    urljoin(url, "/projects"),
                    urljoin(url, "/programmes"),
                    urljoin(url, "/initiatives"),
                ]

                for proj_url in projects_urls:
                    proj_result = await self.fetch_url(proj_url)
                    if proj_result.success:
                        projects = self.extract_projects(proj_result.content, proj_url)
                        for proj in projects:
                            proj.ministry = ministry_key
                            results["projects"].append({
                                "title": proj.title,
                                "ministry": proj.ministry,
                                "state": proj.state,
                                "budget": proj.budget,
                                "status": proj.status,
                                "source_url": proj.source_url
                            })
                        break

            else:
                results["errors"].append(f"Failed {ministry_key}: {result.error}")

            # Polite delay between ministries
            await asyncio.sleep(random.uniform(2, 5))

        return results

    async def crawl_alternative_sources(self) -> Dict[str, Any]:
        """Crawl alternative data sources like BudgIT, Tracka."""
        results = {
            "sources": [],
            "projects": [],
            "errors": [],
            "crawled_at": datetime.now().isoformat()
        }

        # Try Tracka - tracks constituency projects
        tracka_result = await self.fetch_url("https://tracka.ng/projects")
        if tracka_result.success:
            projects = self.extract_projects(tracka_result.content, "https://tracka.ng")
            results["projects"].extend([{
                "title": p.title,
                "state": p.state,
                "budget": p.budget,
                "status": p.status,
                "source": "Tracka"
            } for p in projects])
            results["sources"].append("Tracka")

        # Try Open Treasury
        treasury_result = await self.fetch_url("https://opentreasury.gov.ng/index.php/projects")
        if treasury_result.success:
            projects = self.extract_projects(treasury_result.content, "https://opentreasury.gov.ng")
            results["projects"].extend([{
                "title": p.title,
                "state": p.state,
                "budget": p.budget,
                "status": p.status,
                "source": "Open Treasury"
            } for p in projects])
            results["sources"].append("Open Treasury")

        return results


async def run_full_crawl() -> Dict[str, Any]:
    """Run a full crawl of all ministry sources."""
    crawler = MinistryCrawler()

    try:
        results = {
            "osgf": await crawler.crawl_osgf(),
            "ministries": await crawler.crawl_ministry_websites(),
            "alternatives": await crawler.crawl_alternative_sources(),
            "total_ministries": 0,
            "total_projects": 0,
            "completed_at": datetime.now().isoformat()
        }

        results["total_ministries"] = len(results["osgf"].get("ministries", [])) + \
                                      len(results["ministries"].get("ministries", []))
        results["total_projects"] = len(results["ministries"].get("projects", [])) + \
                                    len(results["alternatives"].get("projects", []))

        return results

    finally:
        await crawler.close()


def run_crawl_sync():
    """Synchronous wrapper for running the crawl."""
    return asyncio.run(run_full_crawl())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_crawl_sync()
    print(f"Crawled {results['total_ministries']} ministries and {results['total_projects']} projects")
