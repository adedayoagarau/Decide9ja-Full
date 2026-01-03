"""
Real-Time Data Service
Fetches live data from RSS feeds and Web Search (DuckDuckGo).
Includes source quality scoring and recency filtering.
"""
import logging
import feedparser
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from ddgs import DDGS  # ddgs package (in requirements.txt)

logger = logging.getLogger(__name__)

# Nigerian News RSS Feeds with quality scores (1-5, higher = more reliable)
RSS_FEEDS = {
    "punch": {
        "url": "https://punchng.com/feed/",
        "quality": 4,
        "name": "Punch NG"
    },
    "premium_times": {
        "url": "https://www.premiumtimesng.com/feed",
        "quality": 5,
        "name": "Premium Times"
    },
    "vanguard": {
        "url": "https://www.vanguardngr.com/feed/",
        "quality": 4,
        "name": "Vanguard"
    },
    "dailypost": {
        "url": "https://dailypost.ng/feed/",
        "quality": 3,
        "name": "Daily Post"
    },
    "channels": {
        "url": "https://www.channelstv.com/feed/",
        "quality": 4,
        "name": "Channels TV"
    }
}

# Maximum age for news to be considered "recent" (in hours)
MAX_NEWS_AGE_HOURS = 72


def parse_published_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats from RSS feeds."""
    if not date_str:
        return None

    formats = [
        "%a, %d %b %Y %H:%M:%S %z",  # RFC 822
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def is_recent(pub_date: Optional[datetime], max_age_hours: int = MAX_NEWS_AGE_HOURS) -> bool:
    """Check if article is recent enough."""
    if not pub_date:
        return True  # Assume recent if date unknown

    # Make timezone-naive for comparison
    if pub_date.tzinfo:
        pub_date = pub_date.replace(tzinfo=None)

    age = datetime.now() - pub_date
    return age <= timedelta(hours=max_age_hours)


def calculate_relevance_score(
    article: Dict,
    topic: str,
    source_quality: int = 3
) -> float:
    """
    Calculate relevance score for an article.
    Factors: source quality, recency, topic match
    """
    score = source_quality * 10  # Base score from source quality (10-50)

    # Recency bonus (up to 30 points)
    if article.get("published"):
        pub_date = parse_published_date(article["published"])
        if pub_date:
            if pub_date.tzinfo:
                pub_date = pub_date.replace(tzinfo=None)
            hours_old = (datetime.now() - pub_date).total_seconds() / 3600
            recency_score = max(0, 30 - hours_old)  # Lose 1 point per hour
            score += recency_score

    # Topic match bonus (up to 20 points)
    if topic:
        topic_lower = topic.lower()
        title_lower = article.get("title", "").lower()
        summary_lower = article.get("summary", "").lower()

        if topic_lower in title_lower:
            score += 20
        elif topic_lower in summary_lower:
            score += 10

    return score


def fetch_rss_news(topic: str = None, limit: int = 3, max_age_hours: int = MAX_NEWS_AGE_HOURS) -> List[Dict]:
    """
    Fetch latest news from RSS feeds with quality and recency filtering.

    Args:
        topic: Optional topic to filter by
        limit: Maximum number of articles to return
        max_age_hours: Maximum age of articles in hours
    """
    articles = []

    for source_key, source_info in RSS_FEEDS.items():
        try:
            url = source_info["url"]
            quality = source_info.get("quality", 3)
            source_name = source_info.get("name", source_key)

            feed = feedparser.parse(url)

            for entry in feed.entries[:5]:  # Check more entries, filter later
                # Parse date and check recency
                pub_date_str = entry.get('published', '')
                pub_date = parse_published_date(pub_date_str)

                if not is_recent(pub_date, max_age_hours):
                    continue

                # Simple keyword filter if topic provided
                title = entry.get('title', '')
                summary = entry.get('summary', '')[:300] if entry.get('summary') else ''

                if topic:
                    topic_lower = topic.lower()
                    if topic_lower not in title.lower() and topic_lower not in summary.lower():
                        continue

                article = {
                    "title": title,
                    "link": entry.get('link', ''),
                    "source": source_name,
                    "source_key": source_key,
                    "quality": quality,
                    "published": pub_date_str or str(datetime.now()),
                    "published_date": pub_date,
                    "summary": summary + "..." if len(summary) >= 300 else summary
                }

                # Calculate relevance score
                article["relevance_score"] = calculate_relevance_score(
                    article, topic or "", quality
                )

                articles.append(article)

        except Exception as e:
            logger.error(f"RSS error {source_key}: {e}")

    # Sort by relevance score (highest first)
    articles.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    return articles[:limit]


def fetch_web_search(query: str, limit: int = 3) -> List[Dict]:
    """Perform a web search using DuckDuckGo."""
    results = []
    logger.info(f"fetch_web_search called with query: {query}")

    try:
        with DDGS(timeout=10) as ddgs:
            # Use news region='ng-en' for Nigeria
            search_query = f"{query} Nigeria" if "nigeria" not in query.lower() else query
            logger.info(f"DDGS searching for: {search_query}")

            # Execute search
            search_results = list(ddgs.text(search_query, region="ng-en", max_results=limit))
            logger.info(f"DDGS returned {len(search_results)} results")

            for res in search_results:
                results.append({
                    "title": res.get('title', 'No title'),
                    "link": res.get('href', ''),
                    "source": "Web Search",
                    "quality": 2,  # Web search results get lower quality score
                    "summary": res.get('body', '')
                })

        logger.info(f"fetch_web_search returning {len(results)} results")

    except Exception as e:
        logger.error(f"Web search error: {e}", exc_info=True)

    return results


def get_realtime_data(query: str) -> Dict:
    """Get real-time data for a query with quality scoring."""
    news = fetch_rss_news(topic=query, limit=3)
    web = fetch_web_search(query, limit=2)

    # Combine and sort by quality/relevance
    combined = news + web
    combined.sort(key=lambda x: x.get("relevance_score", x.get("quality", 0) * 10), reverse=True)

    return {
        "news": news,
        "web": web,
        "combined": combined[:5],
        "combined_text": _format_results(combined[:5])
    }


def _format_results(results: List[Dict]) -> str:
    """Format results into a string for context."""
    if not results:
        return "No real-time data found."

    text = "REAL-TIME DATA:\n"
    for r in results:
        source = r.get('source', 'Unknown')
        quality = r.get('quality', 3)
        quality_indicator = "⭐" * min(quality, 5)

        text += f"- [{source}] {quality_indicator}\n"
        text += f"  {r.get('title', 'No title')}\n"
        text += f"  {r.get('summary', '')[:200]}\n"

        if r.get('published'):
            text += f"  Published: {r.get('published')}\n"

        text += "\n"

    return text
