"""
Nigerian News Scraper for Decide9ja.
Scrapes political news from trusted Nigerian sources.
"""
import os
import re
import json
import logging
import hashlib
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
    }

# Nigerian news sources - Comprehensive list
NEWS_SOURCES = {
    # === WORKING SOURCES (Original) ===
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
    "sahara_reporters": {
        "name": "Sahara Reporters",
        "base_url": "https://saharareporters.com",
        "politics_url": "https://saharareporters.com/politics",
        "selectors": {
            "articles": "article, .node--type-article, .views-row, .card",
            "title": "h2 a, h3 a, .field--name-title a, .card-title a",
            "link": "h2 a, h3 a, .field--name-title a, .card-title a",
            "excerpt": ".field--name-body p, .teaser-text, .card-text",
            "date": "time, .field--name-created"
        }
    },
    "vanguard": {
        "name": "Vanguard",
        "base_url": "https://www.vanguardngr.com",
        "politics_url": "https://www.vanguardngr.com/category/politics/",
        "selectors": {
            "articles": "article, .entry",
            "title": "h3 a, h2 a, .entry-title a",
            "link": "h3 a, h2 a, .entry-title a",
            "excerpt": "p, .entry-summary",
            "date": "time"
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
    "leadership": {
        "name": "Leadership",
        "base_url": "https://leadership.ng",
        "politics_url": "https://leadership.ng/category/politics/",
        "selectors": {
            "articles": "article, .post, .jeg_post",
            "title": "h2 a, h3 a, .jeg_post_title a",
            "link": "h2 a, h3 a, .jeg_post_title a",
            "excerpt": "p, .jeg_post_excerpt",
            "date": "time, .jeg_meta_date"
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
    },
    # === NEW SOURCES (User requested) ===
    "thecable": {
        "name": "The Cable",
        "base_url": "https://www.thecable.ng",
        "politics_url": "https://www.thecable.ng/category/politics",
        "selectors": {
            "articles": ".td-block-span6, .td-module-container, article, .post-item",
            "title": "h3 a, .td-module-title a, .entry-title a",
            "link": "h3 a, .td-module-title a, .entry-title a",
            "excerpt": ".td-excerpt, .entry-summary, p",
            "date": "time, .td-post-date, .date"
        }
    },
    "dailytrust": {
        "name": "Daily Trust",
        "base_url": "https://dailytrust.com",
        "politics_url": "https://dailytrust.com/category/politics/",
        "selectors": {
            "articles": ".jeg_post, article, .post, .article-item",
            "title": ".jeg_post_title a, h2 a, h3 a, .title a",
            "link": ".jeg_post_title a, h2 a, h3 a, .title a",
            "excerpt": ".jeg_post_excerpt, p, .excerpt",
            "date": ".jeg_meta_date, time"
        }
    },
    "dailypost": {
        "name": "Daily Post",
        "base_url": "https://dailypost.ng",
        "politics_url": "https://dailypost.ng/politics/",
        "selectors": {
            "articles": ".mvp-blog-story-out, .mvp-blog-story-wrap, article, .post",
            "title": "h2 a, h3 a, .mvp-blog-story-title a",
            "link": "h2 a, h3 a, .mvp-blog-story-title a",
            "excerpt": ".mvp-blog-story-excerpt, p",
            "date": "time, .mvp-post-date"
        }
    },
    "guardian": {
        "name": "The Guardian Nigeria",
        "base_url": "https://guardian.ng",
        "politics_url": "https://guardian.ng/category/politics/",
        "selectors": {
            "articles": ".single-post, article, .post, .item",
            "title": "h2 a, h3 a, .post-title a, .title a",
            "link": "h2 a, h3 a, .post-title a, .title a",
            "excerpt": ".post-excerpt, p",
            "date": "time, .post-date"
        }
    }
}



# Politicians to track (can be expanded from database)
TRACKED_POLITICIANS = [
    "Tinubu", "Bola Tinubu", "Atiku", "Peter Obi", "Kwankwaso",
    "Akpabio", "Godswill Akpabio", "Abbas", "Tajudeen Abbas",
    "Shettima", "Kashim Shettima", "Fubara", "Wike", "Sanwo-Olu",
    "El-Rufai", "Adelabu", "Fashola", "Osinbajo", "Buhari",
    "Makinde", "Adeleke", "Ganduje", "Umahi", "Soludo"
]

# Political topics
POLITICAL_TOPICS = [
    "naira", "fuel", "subsidy", "budget", "election", "INEC",
    "NASS", "senate", "house of reps", "governor", "minister",
    "security", "economy", "corruption", "EFCC", "police",
    "power", "grid collapse", "nerc", "disco", "electricity",
    "road", "highway", "infrastructure", "flooding", "healthcare"
]


@dataclass
class NewsArticle:
    """Scraped news article."""
    id: str
    title: str
    url: str
    source: str
    source_name: str
    excerpt: str
    published_date: Optional[str]
    scraped_at: str
    politicians_mentioned: List[str]
    topics: List[str]
    full_text: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


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


def scrape_source(source_key: str, max_articles: int = 10, fetch_full: bool = True) -> List[NewsArticle]:
    """Scrape articles from a single source.
    
    Args:
        source_key: Key from NEWS_SOURCES dict
        max_articles: Max articles to scrape
        fetch_full: Whether to fetch full article text (slower but needed for extraction)
    """
    source = NEWS_SOURCES.get(source_key)
    if not source:
        logger.error(f"Unknown source: {source_key}")
        return []
    
    articles = []
    
    try:
        headers = get_headers()
        
        response = requests.get(source["politics_url"], headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        selectors = source["selectors"]
        
        # Find article containers
        article_elements = soup.select(selectors["articles"])[:max_articles]
        
        for element in article_elements:
            try:
                # Extract title
                title_elem = element.select_one(selectors["title"])
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                if not title or len(title) < 10:
                    continue
                
                # Extract link
                link_elem = element.select_one(selectors["link"])
                url = link_elem.get("href", "") if link_elem else ""
                if not url:
                    continue
                if not url.startswith("http"):
                    url = source["base_url"] + url
                
                # Extract excerpt from list page
                excerpt_elem = element.select_one(selectors["excerpt"])
                excerpt = excerpt_elem.get_text(strip=True)[:500] if excerpt_elem else ""
                
                # Extract date
                date_elem = element.select_one(selectors["date"])
                pub_date = date_elem.get("datetime", date_elem.get_text(strip=True)) if date_elem else None
                
                # Fetch full article text if enabled
                full_text = None
                if fetch_full:
                    full_text = fetch_full_article(url)
                    # Use full text as excerpt if no excerpt was found
                    if not excerpt and full_text:
                        excerpt = full_text[:500]
                
                # Extract entities from title + text
                combined_text = f"{title} {full_text or excerpt or ''}"
                politicians = extract_politicians(combined_text)
                topics = extract_topics(combined_text)
                
                article = NewsArticle(
                    id=generate_article_id(url),
                    title=title,
                    url=url,
                    source=source_key,
                    source_name=source["name"],
                    excerpt=excerpt,
                    published_date=pub_date,
                    scraped_at=datetime.now().isoformat(),
                    politicians_mentioned=politicians,
                    topics=topics,
                    full_text=full_text
                )
                
                articles.append(article)
                
            except Exception as e:
                logger.warning(f"Error parsing article from {source_key}: {e}")
                continue
        
        logger.info(f"Scraped {len(articles)} articles from {source['name']}")
        
    except Exception as e:
        logger.error(f"Error scraping {source_key}: {e}")
    
    return articles


def scrape_all_sources(max_per_source: int = 10) -> List[NewsArticle]:
    """Scrape all configured news sources."""
    all_articles = []
    
    for source_key in NEWS_SOURCES:
        articles = scrape_source(source_key, max_per_source)
        all_articles.extend(articles)
    
    logger.info(f"Total scraped: {len(all_articles)} articles from {len(NEWS_SOURCES)} sources")
    return all_articles


def fetch_full_article(url: str) -> Optional[str]:
    """Fetch full article text from URL."""
    try:
        headers = {
            "User-Agent": "Decide9ja/1.0 (Political News Aggregator)"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove scripts, styles, etc.
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        
        # Find main content
        content = soup.find("article") or soup.find("div", class_=re.compile("content|post|article"))
        
        if content:
            # Get paragraphs
            paragraphs = content.find_all("p")
            text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50)
            return text[:5000]  # Limit to 5000 chars
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching full article: {e}")
        return None


def save_articles_to_json(articles: List[NewsArticle], filepath: str):
    """Save articles to JSON file."""
    data = [article.to_dict() for article in articles]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(articles)} articles to {filepath}")


def run_scraper(max_per_source: int = 10, output_dir: str = None):
    """Run the news scraper and save results."""
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Scrape all sources
    articles = scrape_all_sources(max_per_source)
    
    # Save to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"news_{timestamp}.json")
    save_articles_to_json(articles, output_file)
    
    # Also save latest
    latest_file = os.path.join(output_dir, "news_latest.json")
    save_articles_to_json(articles, latest_file)
    
    return articles


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape Nigerian political news")
    parser.add_argument("--max", type=int, default=10, help="Max articles per source")
    parser.add_argument("--source", type=str, help="Specific source to scrape")
    parser.add_argument("--output", type=str, help="Output directory")
    
    args = parser.parse_args()
    
    if args.source:
        articles = scrape_source(args.source, args.max)
        for article in articles:
            print(f"\n📰 {article.title}")
            print(f"   Source: {article.source_name}")
            print(f"   Politicians: {', '.join(article.politicians_mentioned) or 'None'}")
            print(f"   Topics: {', '.join(article.topics) or 'None'}")
    else:
        run_scraper(max_per_source=args.max, output_dir=args.output)
