"""
Enhanced News Scraper with AI Fallback.
Uses traditional CSS selectors first, falls back to AI extraction when needed.
ADDITIVE - original news_scraper.py unchanged.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ExtractedArticle:
    """Extracted article data."""
    title: str
    content: str
    excerpt: str
    url: str
    source_name: str
    published_date: Optional[str] = None
    author: Optional[str] = None
    politicians_mentioned: List[str] = None
    topics: List[str] = None
    extraction_method: str = "css"  # css or ai
    extracted_at: str = None
    
    def __post_init__(self):
        if self.politicians_mentioned is None:
            self.politicians_mentioned = []
        if self.topics is None:
            self.topics = []
        if self.extracted_at is None:
            self.extracted_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


async def extract_article_with_ai(url: str, source_name: str = "Unknown") -> Optional[ExtractedArticle]:
    """
    Extract article using AI crawler and schema extraction.
    
    Args:
        url: Article URL
        source_name: Name of the source
        
    Returns:
        ExtractedArticle or None
    """
    from app.services.ai_crawler import crawl_url
    from app.services.schema_generator import extract_with_schema, NewsArticleSchema
    
    try:
        # Crawl the page
        crawl_result = await crawl_url(url)
        
        if not crawl_result.success:
            logger.warning(f"Crawl failed for {url}: {crawl_result.error}")
            return None
        
        # Extract with schema
        extracted = await extract_with_schema(
            content=crawl_result.content_markdown,
            schema=NewsArticleSchema,
            source_url=url
        )
        
        if not extracted or not extracted.get("title"):
            logger.warning(f"Extraction returned empty for {url}")
            return None
        
        return ExtractedArticle(
            title=extracted.get("title", crawl_result.title),
            content=extracted.get("content", crawl_result.content_markdown[:5000]),
            excerpt=extracted.get("excerpt", extracted.get("content", "")[:300]),
            url=url,
            source_name=source_name,
            published_date=extracted.get("published_date"),
            author=extracted.get("author"),
            politicians_mentioned=extracted.get("politicians_mentioned", []),
            topics=extracted.get("topics", []),
            extraction_method="ai"
        )
        
    except Exception as e:
        logger.error(f"AI extraction failed for {url}: {e}")
        return None


async def extract_article_with_css(url: str, source_config: Dict) -> Optional[ExtractedArticle]:
    """
    Extract article using CSS selectors (traditional method).
    
    Args:
        url: Article URL
        source_config: Source configuration with selectors
        
    Returns:
        ExtractedArticle or None
    """
    import requests
    from bs4 import BeautifulSoup
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Get title
        title_selector = source_config.get("title_selector", "h1")
        title_el = soup.select_one(title_selector)
        title = title_el.get_text(strip=True) if title_el else ""
        
        # Get content
        content_selector = source_config.get("content_selector", "article p")
        content_els = soup.select(content_selector)
        content = "\n\n".join([p.get_text(strip=True) for p in content_els])
        
        # Get author
        author_selector = source_config.get("author_selector")
        author = None
        if author_selector:
            author_el = soup.select_one(author_selector)
            author = author_el.get_text(strip=True) if author_el else None
        
        # Get date
        date_selector = source_config.get("date_selector")
        pub_date = None
        if date_selector:
            date_el = soup.select_one(date_selector)
            pub_date = date_el.get_text(strip=True) if date_el else None
        
        if not title or not content or len(content) < 100:
            return None  # Trigger AI fallback
        
        return ExtractedArticle(
            title=title,
            content=content,
            excerpt=content[:300],
            url=url,
            source_name=source_config.get("name", "Unknown"),
            published_date=pub_date,
            author=author,
            extraction_method="css"
        )
        
    except Exception as e:
        logger.warning(f"CSS extraction failed for {url}: {e}")
        return None


async def extract_article(
    url: str,
    source_config: Dict,
    use_ai_fallback: bool = True
) -> Optional[ExtractedArticle]:
    """
    Extract article with CSS first, AI fallback if needed.
    
    Args:
        url: Article URL
        source_config: Source configuration
        use_ai_fallback: Whether to use AI if CSS fails
        
    Returns:
        ExtractedArticle or None
    """
    # Try CSS first (fast and free)
    article = await extract_article_with_css(url, source_config)
    
    if article and len(article.content) >= 100:
        return article
    
    # CSS failed or returned empty - try AI
    if use_ai_fallback:
        logger.info(f"Using AI fallback for {url}")
        article = await extract_article_with_ai(url, source_config.get("name", "Unknown"))
        return article
    
    return None


# ===========================================
# SOURCE CONFIGURATIONS
# ===========================================

SOURCE_CONFIGS = {
    "punch": {
        "name": "Punch NG",
        "base_url": "https://punchng.com",
        "listing_url": "https://punchng.com/topics/politics/",
        "title_selector": "h1.post-title, h1.entry-title",
        "content_selector": "div.post-content p, article.post-content p",
        "author_selector": "a.author-name, span.author",
        "date_selector": "time.entry-date, span.post-date",
        "link_selector": "h2.post-title a, h3.post-title a",
    },
    "premium_times": {
        "name": "Premium Times",
        "base_url": "https://www.premiumtimesng.com",
        "listing_url": "https://www.premiumtimesng.com/category/news/political-news",
        "title_selector": "h1.entry-title",
        "content_selector": "div.entry-content p",
        "author_selector": "a.author-name",
        "date_selector": "time.entry-date",
        "link_selector": "h2.entry-title a",
    },
    "channels": {
        "name": "Channels TV",
        "base_url": "https://www.channelstv.com",
        "listing_url": "https://www.channelstv.com/category/politics/",
        "title_selector": "h1.entry-title",
        "content_selector": "div.entry-content p",
        "author_selector": ".author-name",
        "date_selector": ".entry-date",
        "link_selector": "h2.entry-title a",
    },
    "inec": {
        "name": "INEC",
        "base_url": "https://www.inecnigeria.org",
        "listing_url": "https://www.inecnigeria.org/news/",
        "title_selector": "h1",
        "content_selector": "article p, .content p",
        "author_selector": None,
        "date_selector": ".date",
        "link_selector": "article a, .news-item a",
    },
    "budgit": {
        "name": "BudgIT",
        "base_url": "https://yourbudgit.com",
        "listing_url": "https://yourbudgit.com/blog/",
        "title_selector": "h1",
        "content_selector": "article p, .post-content p",
        "author_selector": ".author",
        "date_selector": ".date",
        "link_selector": "article a, .post-title a",
    },
}


async def scrape_source_enhanced(
    source_key: str,
    max_articles: int = 10,
    use_ai: bool = True
) -> List[ExtractedArticle]:
    """
    Scrape a news source with AI-enhanced extraction.
    
    Args:
        source_key: Key from SOURCE_CONFIGS
        max_articles: Maximum articles to scrape
        use_ai: Whether to use AI fallback
        
    Returns:
        List of ExtractedArticle
    """
    config = SOURCE_CONFIGS.get(source_key)
    if not config:
        logger.error(f"Unknown source: {source_key}")
        return []
    
    logger.info(f"Scraping {config['name']} (max {max_articles})")
    
    # Get article links from listing page
    from app.services.ai_crawler import crawl_url
    
    listing_result = await crawl_url(config["listing_url"])
    
    if not listing_result.success:
        logger.error(f"Failed to get listing for {source_key}")
        return []
    
    # Extract links
    article_urls = []
    for link in listing_result.links[:max_articles * 2]:
        if link and link.startswith("http") and "/author/" not in link and "/tag/" not in link:
            if config["base_url"] in link or link.startswith("/"):
                if link.startswith("/"):
                    link = config["base_url"] + link
                article_urls.append(link)
    
    article_urls = list(set(article_urls))[:max_articles]
    
    logger.info(f"Found {len(article_urls)} article URLs from {config['name']}")
    
    # Extract each article
    articles = []
    for url in article_urls:
        article = await extract_article(url, config, use_ai_fallback=use_ai)
        if article:
            articles.append(article)
        await asyncio.sleep(0.5)  # Polite delay
    
    logger.info(f"Extracted {len(articles)} articles from {config['name']}")
    
    # Log extraction methods
    css_count = len([a for a in articles if a.extraction_method == "css"])
    ai_count = len([a for a in articles if a.extraction_method == "ai"])
    logger.info(f"  CSS: {css_count}, AI: {ai_count}")
    
    return articles


async def scrape_all_sources_enhanced(
    max_per_source: int = 10,
    sources: List[str] = None
) -> List[ExtractedArticle]:
    """
    Scrape all configured sources.
    
    Args:
        max_per_source: Max articles per source
        sources: Optional list of source keys to scrape
        
    Returns:
        Combined list of articles
    """
    if sources is None:
        sources = list(SOURCE_CONFIGS.keys())
    
    all_articles = []
    
    for source_key in sources:
        articles = await scrape_source_enhanced(source_key, max_per_source)
        all_articles.extend(articles)
    
    logger.info(f"Total: {len(all_articles)} articles from {len(sources)} sources")
    return all_articles


def scrape_source_sync(source_key: str, max_articles: int = 10) -> List[ExtractedArticle]:
    """Synchronous wrapper."""
    return asyncio.run(scrape_source_enhanced(source_key, max_articles))


# Test
if __name__ == "__main__":
    async def test():
        # Test single source
        articles = await scrape_source_enhanced("punch", max_articles=3)
        
        for article in articles:
            print(f"\n{'='*50}")
            print(f"Title: {article.title}")
            print(f"Method: {article.extraction_method}")
            print(f"Content: {article.content[:200]}...")
            print(f"Politicians: {article.politicians_mentioned}")
    
    asyncio.run(test())
