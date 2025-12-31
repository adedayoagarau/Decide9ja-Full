"""
Real-Time Data Service
Fetches live data from RSS feeds and Web Search (DuckDuckGo).
"""
import logging
import feedparser
from typing import List, Dict
from datetime import datetime
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# Nigerian News RSS Feeds
RSS_FEEDS = {
    "punch": "https://punchng.com/feed/",
    "premium_times": "https://www.premiumtimesng.com/feed",
    "vanguard": "https://www.vanguardngr.com/feed/",
    "dailypost": "https://dailypost.ng/feed/"
}

def fetch_rss_news(topic: str = None, limit: int = 3) -> List[Dict]:
    """Fetch latest news from RSS feeds."""
    articles = []
    
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                # Simple keyword filter if topic provided
                if topic and topic.lower() not in entry.title.lower() and topic.lower() not in entry.summary.lower():
                    continue
                    
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "source": source,
                    "published": entry.published if 'published' in entry else str(datetime.now()),
                    "summary": entry.summary[:200] + "..." if 'summary' in entry else ""
                })
                
                if len(articles) >= limit:
                    break
        except Exception as e:
            logger.error(f"RSS error {source}: {e}")
            
        if len(articles) >= limit:
            break
            
    return articles

def fetch_web_search(query: str, limit: int = 3) -> List[Dict]:
    """Perform a web search using DuckDuckGo."""
    results = []
    try:
        with DDGS() as ddgs:
            # "news" region='ng-en' for Nigeria
            search_results = ddgs.text(f"{query} Nigeria", region="ng-en", max_results=limit)
            
            for res in search_results:
                results.append({
                    "title": res['title'],
                    "link": res['href'],
                    "source": "Web Search",
                    "summary": res['body']
                })
    except Exception as e:
        logger.error(f"Web search error: {e}")
        
    return results

def get_realtime_data(query: str) -> Dict:
    """Get real-time data for a query."""
    news = fetch_rss_news(topic=query, limit=2)
    web = fetch_web_search(query, limit=2)
    
    return {
        "news": news,
        "web": web,
        "combined_text": _format_results(news + web)
    }

def _format_results(results: List[Dict]) -> str:
    """Format results into a string found in context."""
    if not results:
        return "No real-time data found."
        
    text = "REAL-TIME DATA:\n"
    for r in results:
        text += f"- [{r['source']}] {r['title']}: {r['summary']} ({r['published'] if 'published' in r else 'Now'})\n"
    return text
