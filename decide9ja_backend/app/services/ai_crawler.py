"""
AI Web Crawler Service
Uses Crawl4AI for intelligent web scraping with Markdown output.
Fallback when CSS selectors fail.
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Result from AI crawler."""
    url: str
    title: str
    content_markdown: str
    raw_html: Optional[str] = None
    links: List[str] = None
    success: bool = True
    error: Optional[str] = None
    crawled_at: str = None
    
    def __post_init__(self):
        if self.links is None:
            self.links = []
        if self.crawled_at is None:
            self.crawled_at = datetime.now().isoformat()


async def crawl_url(url: str, timeout: int = 30) -> CrawlResult:
    """
    Crawl a URL using Crawl4AI and return Markdown content.
    
    Args:
        url: URL to crawl
        timeout: Timeout in seconds
        
    Returns:
        CrawlResult with markdown content
    """
    try:
        from crawl4ai import AsyncWebCrawler
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            
            # Crawl4AI 0.7.8 returns markdown as StringCompatibleMarkdown
            markdown_content = str(result.markdown) if result.markdown else ""
            
            # Get links - try different attributes
            links = []
            if hasattr(result, 'links') and result.links:
                try:
                    link_list = list(result.links)[:20]
                    links = [link.get("href", "") if isinstance(link, dict) else str(link) 
                            for link in link_list]
                except:
                    pass
            
            # Get HTML
            html_content = None
            if hasattr(result, 'html') and result.html:
                html_content = str(result.html)[:5000]
            
            # Extract title from markdown or HTML
            title = ""
            if markdown_content:
                lines = markdown_content.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith(('|', '-', '*', '[')):
                        title = line.strip()[:200]
                        break
            
            if markdown_content:
                return CrawlResult(
                    url=url,
                    title=title,
                    content_markdown=markdown_content,
                    raw_html=html_content,
                    links=links,
                    success=True
                )
            else:
                return CrawlResult(
                    url=url,
                    title="",
                    content_markdown="",
                    success=False,
                    error="No content returned"
                )
                
    except ImportError:
        # Fallback to requests if crawl4ai not available
        return await _fallback_crawl(url)
    except Exception as e:
        logger.error(f"Crawl error for {url}: {e}")
        return CrawlResult(
            url=url,
            title="",
            content_markdown="",
            success=False,
            error=str(e)
        )


async def _fallback_crawl(url: str) -> CrawlResult:
    """Fallback crawler using requests + BeautifulSoup + html2text."""
    import requests
    from bs4 import BeautifulSoup
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove scripts, styles, nav
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        
        # Get title
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""
        
        # Convert to markdown-like text
        # Find article body
        article = soup.find("article") or soup.find("main") or soup.find("body")
        
        if article:
            # Get all paragraphs
            paragraphs = article.find_all(["p", "h1", "h2", "h3", "li"])
            content = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        else:
            content = soup.get_text(separator="\n", strip=True)
        
        # Limit content
        content = content[:8000]
        
        # Get links
        links = [a.get("href", "") for a in soup.find_all("a", href=True)[:20]]
        
        return CrawlResult(
            url=url,
            title=title_text,
            content_markdown=content,
            links=links,
            success=True
        )
        
    except Exception as e:
        return CrawlResult(
            url=url,
            title="",
            content_markdown="",
            success=False,
            error=str(e)
        )


async def crawl_multiple(urls: List[str], max_concurrent: int = 5) -> List[CrawlResult]:
    """
    Crawl multiple URLs concurrently.
    
    Args:
        urls: List of URLs to crawl
        max_concurrent: Max concurrent requests
        
    Returns:
        List of CrawlResults
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_crawl(url: str) -> CrawlResult:
        async with semaphore:
            return await crawl_url(url)
    
    tasks = [limited_crawl(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions
    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed.append(CrawlResult(
                url=urls[i],
                title="",
                content_markdown="",
                success=False,
                error=str(result)
            ))
        else:
            processed.append(result)
    
    return processed


def crawl_url_sync(url: str) -> CrawlResult:
    """Synchronous wrapper for crawl_url."""
    return asyncio.run(crawl_url(url))


# ===========================================
# DATA SOURCES
# ===========================================

# Nigerian government and data sources
DATA_SOURCES = {
    "inec": {
        "name": "INEC",
        "base_url": "https://www.inecnigeria.org",
        "pages": [
            "/",
            "/news",
            "/voter-register",
        ],
        "type": "government",
        "schedule": "daily",
    },
    "budgit": {
        "name": "BudgIT",
        "base_url": "https://yourbudgit.com",
        "pages": [
            "/",
            "/blog",
        ],
        "type": "ngo",
        "schedule": "daily",
    },
    "premium_times": {
        "name": "Premium Times",
        "base_url": "https://www.premiumtimesng.com",
        "pages": [
            "/category/news/political-news",
        ],
        "type": "news",
        "schedule": "hourly",
    },
    "punch": {
        "name": "Punch NG",
        "base_url": "https://punchng.com",
        "pages": [
            "/topics/politics/",
        ],
        "type": "news",
        "schedule": "hourly",
    },
}


async def crawl_source(source_key: str, max_pages: int = 5) -> List[CrawlResult]:
    """
    Crawl a configured data source.
    
    Args:
        source_key: Key from DATA_SOURCES
        max_pages: Max pages to crawl
        
    Returns:
        List of CrawlResults
    """
    source = DATA_SOURCES.get(source_key)
    if not source:
        logger.error(f"Unknown source: {source_key}")
        return []
    
    urls = [source["base_url"] + page for page in source["pages"][:max_pages]]
    
    logger.info(f"Crawling {source['name']}: {len(urls)} pages")
    results = await crawl_multiple(urls)
    
    successful = [r for r in results if r.success]
    logger.info(f"Crawled {len(successful)}/{len(urls)} pages from {source['name']}")
    
    return results


# Test
if __name__ == "__main__":
    async def test():
        # Test single URL
        result = await crawl_url("https://punchng.com/topics/politics/")
        print(f"Title: {result.title}")
        print(f"Content length: {len(result.content_markdown)}")
        print(f"Content preview: {result.content_markdown[:500]}...")
    
    asyncio.run(test())
