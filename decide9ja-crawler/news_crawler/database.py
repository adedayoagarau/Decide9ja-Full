"""
Database module for Decide9ja News Crawler
Uses Azure PostgreSQL (already set up) instead of Cosmos DB to avoid costs.
"""
import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import psycopg
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# PostgreSQL configuration (uses existing Azure PostgreSQL)
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Connection pool
_connection = None


def get_connection():
    """Get PostgreSQL connection."""
    global _connection
    
    if _connection is None or _connection.closed:
        if not DATABASE_URL:
            raise ValueError(
                "Missing DATABASE_URL. "
                "Set DATABASE_URL environment variable with PostgreSQL connection string."
            )
        
        # Handle SQLAlchemy-style URL (postgresql+psycopg://)
        conn_str = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        
        try:
            _connection = psycopg.connect(conn_str)
            logger.info("Connected to Azure PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    return _connection


def ensure_table_exists():
    """Create news_articles table if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'news_articles'
        )
    """)
    
    if not cur.fetchone()[0]:
        logger.info("Creating news_articles table...")
        cur.execute("""
            CREATE TABLE news_articles (
                id SERIAL PRIMARY KEY,
                article_id VARCHAR(20) UNIQUE NOT NULL,
                title VARCHAR(500) NOT NULL,
                url VARCHAR(1000) NOT NULL,
                source VARCHAR(50) NOT NULL,
                source_name VARCHAR(100),
                excerpt TEXT,
                full_text TEXT,
                politicians_json TEXT,
                topics_json TEXT,
                sentiment VARCHAR(20),
                sentiment_score FLOAT,
                published_date VARCHAR(50),
                scraped_at TIMESTAMP DEFAULT NOW(),
                is_processed BOOLEAN DEFAULT FALSE,
                is_indexed BOOLEAN DEFAULT FALSE
            )
        """)
        conn.commit()
        logger.info("Table created successfully")


def save_articles(articles: List[Dict]) -> int:
    """
    Save articles to PostgreSQL.
    
    Returns: Number of new articles saved
    """
    if not articles:
        return 0
    
    ensure_table_exists()
    conn = get_connection()
    cur = conn.cursor()
    saved_count = 0
    
    for article in articles:
        try:
            # Check if article already exists
            cur.execute(
                "SELECT 1 FROM news_articles WHERE article_id = %s",
                (article.get('id', article.get('article_id')),)
            )
            
            if cur.fetchone():
                continue  # Skip duplicate
            
            # Insert new article
            cur.execute("""
                INSERT INTO news_articles 
                (article_id, title, url, source, source_name, excerpt, full_text,
                 politicians_json, topics_json, sentiment, sentiment_score, published_date, scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                article.get('id', article.get('article_id')),
                article.get('headline', article.get('title', ''))[:500],
                article.get('url', ''),
                article.get('source', ''),
                article.get('source_name', ''),
                article.get('excerpt', '')[:2000] if article.get('excerpt') else None,
                article.get('full_text'),
                json.dumps(article.get('politicians_mentioned', [])),
                json.dumps(article.get('topics', [])),
                article.get('sentiment'),
                article.get('sentiment_score'),
                article.get('date', article.get('published_date')),
                article.get('crawled_at', datetime.now().isoformat())
            ))
            saved_count += 1
            
        except Exception as e:
            logger.error(f"Failed to save article: {e}")
            conn.rollback()
            continue
    
    conn.commit()
    return saved_count


def get_articles_by_date(date: str) -> List[Dict]:
    """Get all articles for a specific date."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM news_articles 
        WHERE DATE(scraped_at) = %s
        ORDER BY scraped_at DESC
    """, (date,))
    
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_articles_by_politician(politician: str, limit: int = 20) -> List[Dict]:
    """Get articles mentioning a specific politician."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Search in politicians_json
    cur.execute("""
        SELECT * FROM news_articles 
        WHERE politicians_json ILIKE %s
        ORDER BY scraped_at DESC
        LIMIT %s
    """, (f'%{politician}%', limit))
    
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_sentiment_summary(politician: str = None, days: int = 7) -> Dict:
    """Get sentiment summary for a politician or overall."""
    conn = get_connection()
    cur = conn.cursor()
    
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    if politician:
        cur.execute("""
            SELECT sentiment, COUNT(*) as count
            FROM news_articles 
            WHERE scraped_at >= %s 
              AND politicians_json ILIKE %s
              AND sentiment IS NOT NULL
            GROUP BY sentiment
        """, (cutoff_date, f'%{politician}%'))
    else:
        cur.execute("""
            SELECT sentiment, COUNT(*) as count
            FROM news_articles 
            WHERE scraped_at >= %s
              AND sentiment IS NOT NULL
            GROUP BY sentiment
        """, (cutoff_date,))
    
    results = cur.fetchall()
    
    summary = {
        'total_articles': 0,
        'positive': 0,
        'negative': 0,
        'neutral': 0,
        'mixed': 0
    }
    
    for sentiment, count in results:
        summary['total_articles'] += count
        if sentiment in summary:
            summary[sentiment] = count
    
    if summary['total_articles'] > 0:
        summary['positive_percentage'] = round(
            (summary['positive'] / summary['total_articles']) * 100, 1
        )
    else:
        summary['positive_percentage'] = 0.0
    
    return summary


def get_recent_articles(limit: int = 50) -> List[Dict]:
    """Get most recent articles."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM news_articles 
        ORDER BY scraped_at DESC
        LIMIT %s
    """, (limit,))
    
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_article_count() -> int:
    """Get total number of articles in database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM news_articles")
    return cur.fetchone()[0]
