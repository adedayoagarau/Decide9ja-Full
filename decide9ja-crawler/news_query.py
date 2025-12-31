"""
Query Helper for Decide9ja Bot
------------------------------
Import this into your Flask app to query the news database.

Usage in your bot:
    from news_query import get_politician_news, get_sentiment_report
    
    # When user asks "What's the news about Tinubu?"
    news = get_politician_news("Tinubu")
    
    # When user asks "How is Obi being covered?"
    report = get_sentiment_report("Obi")
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from azure.cosmos import CosmosClient

# Cosmos DB configuration
COSMOS_ENDPOINT = os.environ.get('COSMOS_ENDPOINT')
COSMOS_KEY = os.environ.get('COSMOS_KEY')
DATABASE_NAME = 'decide9ja'
CONTAINER_NAME = 'news_articles'


def get_container():
    """Get Cosmos DB container"""
    client = CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)
    return container


def get_politician_news(politician: str, days: int = 3, limit: int = 5) -> List[Dict]:
    """
    Get recent news mentioning a politician
    
    Returns list of:
        {
            'headline': str,
            'source': str,
            'url': str,
            'sentiment': str,
            'date': str
        }
    """
    container = get_container()
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    query = """
        SELECT TOP @limit 
            c.headline, c.source, c.url, c.sentiment, c.date
        FROM c 
        WHERE c.date >= @cutoff_date 
          AND ARRAY_CONTAINS(c.politicians_mentioned, @politician)
        ORDER BY c.crawled_at DESC
    """
    
    results = list(container.query_items(
        query=query,
        parameters=[
            {"name": "@cutoff_date", "value": cutoff_date},
            {"name": "@politician", "value": politician},
            {"name": "@limit", "value": limit}
        ],
        enable_cross_partition_query=True
    ))
    
    return results


def get_sentiment_report(politician: str, days: int = 7) -> Dict:
    """
    Get sentiment analysis report for a politician
    
    Returns:
        {
            'politician': str,
            'period': str,
            'total_mentions': int,
            'positive': int,
            'negative': int,
            'neutral': int,
            'trend': str,  # 'improving', 'declining', 'stable'
            'summary': str  # Human-readable summary
        }
    """
    container = get_container()
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    query = """
        SELECT c.sentiment, c.date FROM c 
        WHERE c.date >= @cutoff_date 
          AND ARRAY_CONTAINS(c.politicians_mentioned, @politician)
    """
    
    results = list(container.query_items(
        query=query,
        parameters=[
            {"name": "@cutoff_date", "value": cutoff_date},
            {"name": "@politician", "value": politician}
        ],
        enable_cross_partition_query=True
    ))
    
    # Count sentiments
    counts = {'positive': 0, 'negative': 0, 'neutral': 0, 'mixed': 0}
    for r in results:
        sentiment = r.get('sentiment', 'neutral')
        counts[sentiment] = counts.get(sentiment, 0) + 1
    
    total = sum(counts.values())
    
    # Determine trend (simplified - compare first half to second half)
    if total >= 4:
        sorted_results = sorted(results, key=lambda x: x['date'])
        mid = len(sorted_results) // 2
        
        first_half_pos = sum(1 for r in sorted_results[:mid] if r['sentiment'] == 'positive')
        second_half_pos = sum(1 for r in sorted_results[mid:] if r['sentiment'] == 'positive')
        
        if second_half_pos > first_half_pos:
            trend = 'improving'
        elif second_half_pos < first_half_pos:
            trend = 'declining'
        else:
            trend = 'stable'
    else:
        trend = 'insufficient data'
    
    # Generate summary
    if total == 0:
        summary = f"No news found about {politician} in the last {days} days."
    else:
        pos_pct = round((counts['positive'] / total) * 100)
        neg_pct = round((counts['negative'] / total) * 100)
        
        if pos_pct > 50:
            tone = "mostly positive"
        elif neg_pct > 50:
            tone = "mostly negative"
        else:
            tone = "mixed"
        
        summary = f"{politician} was mentioned in {total} articles over the past {days} days. Coverage has been {tone} ({pos_pct}% positive, {neg_pct}% negative)."
        
        if trend == 'improving':
            summary += " Sentiment is trending upward."
        elif trend == 'declining':
            summary += " Sentiment is trending downward."
    
    return {
        'politician': politician,
        'period': f'Last {days} days',
        'total_mentions': total,
        'positive': counts['positive'],
        'negative': counts['negative'],
        'neutral': counts['neutral'],
        'trend': trend,
        'summary': summary
    }


def get_topic_news(topic: str, days: int = 3, limit: int = 5) -> List[Dict]:
    """
    Get recent news about a topic (economy, security, education, etc.)
    """
    container = get_container()
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    query = """
        SELECT TOP @limit 
            c.headline, c.source, c.url, c.sentiment, c.date, c.politicians_mentioned
        FROM c 
        WHERE c.date >= @cutoff_date 
          AND ARRAY_CONTAINS(c.topics, @topic)
        ORDER BY c.crawled_at DESC
    """
    
    results = list(container.query_items(
        query=query,
        parameters=[
            {"name": "@cutoff_date", "value": cutoff_date},
            {"name": "@topic", "value": topic.lower()},
            {"name": "@limit", "value": limit}
        ],
        enable_cross_partition_query=True
    ))
    
    return results


def get_latest_headlines(limit: int = 10) -> List[Dict]:
    """Get the most recent headlines across all sources"""
    container = get_container()
    
    query = """
        SELECT TOP @limit 
            c.headline, c.source, c.url, c.sentiment, c.date
        FROM c 
        ORDER BY c.crawled_at DESC
    """
    
    results = list(container.query_items(
        query=query,
        parameters=[{"name": "@limit", "value": limit}],
        enable_cross_partition_query=True
    ))
    
    return results


def format_news_for_whatsapp(articles: List[Dict]) -> str:
    """Format articles for WhatsApp response"""
    
    if not articles:
        return "No recent news found on this topic."
    
    response = ""
    for i, article in enumerate(articles, 1):
        sentiment_emoji = {
            'positive': '🟢',
            'negative': '🔴',
            'neutral': '⚪',
            'mixed': '🟡'
        }.get(article.get('sentiment', 'neutral'), '⚪')
        
        response += f"{i}. {sentiment_emoji} *{article['headline']}*\n"
        response += f"   📰 {article['source']}\n"
        if article.get('url'):
            response += f"   🔗 {article['url']}\n"
        response += "\n"
    
    return response.strip()


# Example integration with your Flask bot
"""
# In your main bot file:

from news_query import (
    get_politician_news, 
    get_sentiment_report,
    get_topic_news,
    format_news_for_whatsapp
)

# When user asks about a politician
if "news about" in user_message.lower():
    politician = extract_politician_name(user_message)
    articles = get_politician_news(politician)
    response = format_news_for_whatsapp(articles)

# When user asks about sentiment
if "how is" in user_message.lower() and "being covered" in user_message.lower():
    politician = extract_politician_name(user_message)
    report = get_sentiment_report(politician)
    response = report['summary']

# When user asks about a topic
if any(topic in user_message.lower() for topic in ['economy', 'security', 'education']):
    topic = detect_topic(user_message)
    articles = get_topic_news(topic)
    response = format_news_for_whatsapp(articles)
"""
