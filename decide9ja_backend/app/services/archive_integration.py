"""
Archive Integration for Tade

Connects Tade to the archivi.ng historical newspaper database.
Enables queries like "What did Obasanjo say about corruption in 2007?"
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Database paths to check (in order of preference)
DB_PATHS = [
    Path("/Users/adedayoagarau/.openclaw/workspace/beast-crawler/data/decide9ja.db"),
    Path("/Users/adedayoagarau/.openclaw/workspace/beast-crawler/data/results/crawled_articles.db"),
    Path("/Volumes/Admin/Decide9ja/decide9ja_backend/data/archive.db"),
]


def get_archive_db() -> Optional[Path]:
    """Find the archive database if it exists."""
    for db_path in DB_PATHS:
        if db_path.exists():
            return db_path
    return None


def query_archive(
    query: str, 
    politician: str = None, 
    year: int = None, 
    topic: str = None,
    limit: int = 5
) -> Optional[str]:
    """
    Query historical news archives for relevant articles.
    
    Args:
        query: Search terms (e.g., "Obasanjo corruption agriculture")
        politician: Filter by politician name
        year: Filter by specific year
        topic: Filter by topic (corruption, election, etc.)
        limit: Max results to return
        
    Returns:
        Formatted string with results, or None if no database/matches
    """
    db_path = get_archive_db()
    if not db_path:
        logger.debug("No archive database found")
        return None
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Build dynamic query
        conditions = ["ocr_text IS NOT NULL"]
        params = []
        
        # Search query terms
        if query:
            # Split query into words for better matching
            words = query.split()
            word_conditions = []
            for word in words:
                if len(word) > 3:  # Skip short words
                    word_conditions.append("ocr_text LIKE ?")
                    params.append(f"%{word}%")
            if word_conditions:
                conditions.append(f"({' OR '.join(word_conditions)})")
        
        # Politician filter
        if politician:
            conditions.append("(ocr_text LIKE ? OR politicians LIKE ?)")
            params.append(f"%{politician}%")
            params.append(f"%{politician}%")
        
        # Year filter
        if year:
            conditions.append("year = ?")
            params.append(year)
        
        # Topic filter
        if topic:
            conditions.append("(topics LIKE ? OR ocr_text LIKE ?)")
            params.append(f"%{topic}%")
            params.append(f"%{topic}%")
        
        # Build SQL
        where_clause = " AND ".join(conditions)
        
        sql = f"""
            SELECT date, year, source, ocr_text, politicians, topics
            FROM articles 
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(sql, params)
        results = cursor.fetchall()
        
        if not results:
            return None
        
        return format_results(results)
        
    except Exception as e:
        logger.error(f"Archive query error: {e}")
        return None
    finally:
        if conn:
            conn.close()


def format_results(results: List[Tuple]) -> str:
    """Format database results into readable text."""
    formatted = []
    
    for row in results:
        date, year, source, text, politicians, topics = row
        
        # Clean and truncate text
        preview = text[:250].replace("\n", " ").strip() if text else "[No text available]"
        if len(text) > 250:
            preview += "..."
        
        # Build header
        header = f"📅 {date} ({source})"
        
        # Add politicians if available
        if politicians:
            pol_list = politicians.split(",")[:3]  # First 3
            header += f" | 👤 {', '.join(pol_list)}"
        
        formatted.append(f"{header}\n{preview}")
    
    return "\n\n".join(formatted)


def search_by_politician(politician: str, limit: int = 10) -> Optional[str]:
    """
    Quick search for articles about a specific politician.
    
    Example: search_by_politician("Obasanjo", 5)
    """
    return query_archive(query=politician, politician=politician, limit=limit)


def search_by_topic(topic: str, year: int = None, limit: int = 10) -> Optional[str]:
    """
    Search for articles on a specific topic.
    
    Example: search_by_topic("corruption", 2007, 5)
    """
    return query_archive(query=topic, topic=topic, year=year, limit=limit)


def get_stats() -> Dict:
    """Get archive database statistics."""
    db_path = get_archive_db()
    if not db_path:
        return {"error": "No database found"}
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Total articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        total = cursor.fetchone()[0]
        
        # Articles with OCR
        cursor.execute("SELECT COUNT(*) FROM articles WHERE ocr_text IS NOT NULL")
        with_ocr = cursor.fetchone()[0]
        
        # Year range
        cursor.execute("SELECT MIN(year), MAX(year) FROM articles WHERE year IS NOT NULL")
        year_range = cursor.fetchone()
        
        # Sources
        cursor.execute("SELECT source, COUNT(*) FROM articles GROUP BY source")
        sources = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            "total_articles": total,
            "with_ocr": with_ocr,
            "year_range": f"{year_range[0]}-{year_range[1]}" if year_range else "unknown",
            "sources": sources,
            "database_path": str(db_path)
        }
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


# Quick test if run directly
if __name__ == "__main__":
    print("📰 Archive Integration Test")
    print("=" * 50)
    
    # Check database
    db = get_archive_db()
    if db:
        print(f"✅ Database found: {db}")
        
        # Get stats
        stats = get_stats()
        print(f"\n📊 Stats:")
        print(f"  Total articles: {stats.get('total_articles', 0)}")
        print(f"  With OCR: {stats.get('with_ocr', 0)}")
        print(f"  Year range: {stats.get('year_range', 'unknown')}")
        
        # Test query
        print(f"\n🔍 Test query: 'Obasanjo Lagos'")
        result = query_archive("Obasanjo Lagos", limit=3)
        if result:
            print(f"\n{result}")
        else:
            print("No results found")
    else:
        print("❌ No archive database found")
        print("Expected locations:")
        for p in DB_PATHS:
            print(f"  - {p}")
