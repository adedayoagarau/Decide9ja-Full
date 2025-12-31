"""
Azure Function: News Crawler Timer Trigger
Runs every 2 hours to scrape Nigerian political news.
"""
import os
import json
import logging
import hashlib
import requests
import azure.functions as func
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup

# Database connection
import psycopg
from urllib.parse import quote_plus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ============================================
# NEWS SOURCES CONFIG
# ============================================

NEWS_SOURCES = {
    "premium_times": {
        "name": "Premium Times",
        "base_url": "https://www.premiumtimesng.com",
        "politics_url": "https://www.premiumtimesng.com/category/news/political-news",
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
        "selectors": {
            "articles": "article, .post",
            "title": "h3 a, h2 a, .entry-title a, .post-title a",
            "link": "h3 a, h2 a, .entry-title a, .post-title a",
            "excerpt": "p, .excerpt, .entry-summary",
            "date": "time, .date"
        }
    },
    "channels": {
        "name": "Channels TV",
        "base_url": "https://www.channelstv.com",
        "politics_url": "https://www.channelstv.com/category/politics/",
        "selectors": {
            "articles": "article, .post",
            "title": "h2 a, h3 a, .entry-title a",
            "link": "h2 a, h3 a, .entry-title a",
            "excerpt": "p, .entry-content p",
            "date": "time"
        }
    },
    "thisday": {
        "name": "ThisDay",
        "base_url": "https://www.thisdaylive.com",
        "politics_url": "https://www.thisdaylive.com/index.php/category/politics/",
        "selectors": {
            "articles": "article, .post",
            "title": "h2 a, h3 a, .entry-title a",
            "link": "h2 a, h3 a, .entry-title a",
            "excerpt": "p, .excerpt",
            "date": "time"
        }
    }
}

# Politicians to track
TRACKED_POLITICIANS = [
    "Tinubu", "Bola Tinubu", "Atiku", "Peter Obi", "Kwankwaso",
    "Akpabio", "Shettima", "Fubara", "Wike", "Sanwo-Olu",
    "El-Rufai", "Fashola", "Osinbajo", "Buhari", "Makinde"
]

# Political topics
POLITICAL_TOPICS = [
    "naira", "fuel", "subsidy", "budget", "election", "INEC",
    "senate", "governor", "minister", "security", "economy",
    "power", "grid collapse", "electricity", "infrastructure"
]


# ============================================
# HELPER FUNCTIONS
# ============================================

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


def scrape_source(source_key: str, max_articles: int = 8) -> List[dict]:
    """Scrape articles from a single source."""
    source = NEWS_SOURCES.get(source_key)
    if not source:
        return []
    
    articles = []
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        
        response = requests.get(source["politics_url"], headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        selectors = source["selectors"]
        
        article_elements = soup.select(selectors["articles"])[:max_articles]
        
        for element in article_elements:
            try:
                title_elem = element.select_one(selectors["title"])
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                if not title or len(title) < 10:
                    continue
                
                link_elem = element.select_one(selectors["link"])
                url = link_elem.get("href", "") if link_elem else ""
                if not url:
                    continue
                if not url.startswith("http"):
                    url = source["base_url"] + url
                
                excerpt_elem = element.select_one(selectors["excerpt"])
                excerpt = excerpt_elem.get_text(strip=True)[:500] if excerpt_elem else ""
                
                date_elem = element.select_one(selectors["date"])
                pub_date = date_elem.get("datetime", date_elem.get_text(strip=True)) if date_elem else None
                
                combined_text = f"{title} {excerpt}"
                politicians = extract_politicians(combined_text)
                topics = extract_topics(combined_text)
                
                articles.append({
                    "article_id": generate_article_id(url),
                    "title": title,
                    "url": url,
                    "source": source_key,
                    "source_name": source["name"],
                    "excerpt": excerpt,
                    "published_date": pub_date,
                    "scraped_at": datetime.now().isoformat(),
                    "politicians_json": json.dumps(politicians),
                    "topics_json": json.dumps(topics)
                })
                
            except Exception as e:
                logger.warning(f"Error parsing article: {e}")
                continue
        
        logger.info(f"Scraped {len(articles)} from {source['name']}")
        
    except Exception as e:
        logger.error(f"Error scraping {source_key}: {e}")
    
    return articles


def store_articles(articles: List[dict]) -> int:
    """Store articles in Azure PostgreSQL."""
    if not DATABASE_URL:
        logger.error("DATABASE_URL not configured")
        return 0
    
    # Parse and fix connection string for psycopg (remove +psycopg)
    conn_str = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    
    stored = 0
    try:
        conn = psycopg.connect(conn_str)
        cur = conn.cursor()
        
        for article in articles:
            try:
                # Check if exists
                cur.execute(
                    "SELECT 1 FROM news_articles WHERE article_id = %s",
                    (article["article_id"],)
                )
                if cur.fetchone():
                    continue
                
                # Insert new article
                cur.execute("""
                    INSERT INTO news_articles 
                    (article_id, title, url, source, source_name, excerpt, 
                     politicians_json, topics_json, published_date, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    article["article_id"],
                    article["title"],
                    article["url"],
                    article["source"],
                    article["source_name"],
                    article["excerpt"],
                    article["politicians_json"],
                    article["topics_json"],
                    article["published_date"],
                    article["scraped_at"]
                ))
                stored += 1
                
            except Exception as e:
                logger.warning(f"Error storing article: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Database error: {e}")
    
    return stored


# ============================================
# AZURE FUNCTION ENTRY POINT
# ============================================

def main(mytimer: func.TimerRequest) -> None:
    """
    Timer-triggered function that runs every 2 hours.
    Scrapes Nigerian political news and stores in Azure PostgreSQL.
    """
    utc_timestamp = datetime.utcnow().isoformat()
    
    if mytimer.past_due:
        logger.info('Timer trigger is running late!')

    logger.info(f'🗞️ Starting news crawl at {utc_timestamp}')
    
    # Scrape all sources
    all_articles = []
    for source_key in NEWS_SOURCES:
        articles = scrape_source(source_key, max_articles=8)
        all_articles.extend(articles)
    
    logger.info(f"Total scraped: {len(all_articles)} articles")
    
    # Store in database
    stored = store_articles(all_articles)
    
    logger.info(f'✅ News crawl complete: {stored} new articles stored')
