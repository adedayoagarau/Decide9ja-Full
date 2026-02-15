"""
Catalog Search Service

Connects the Decide9ja backend to the newspaper archive catalog (catalog.db).
This database contains 80,345+ newspaper documents spanning 1941-2026 with
full-text search (FTS5) capabilities.

Usage:
    from app.services.catalog_search import CatalogSearchService
    
    service = CatalogSearchService()
    results = service.search("Tinubu corruption scandal")
    context = service.get_context_for_rag("Who is Bola Tinubu?", limit=5)
"""

import os
import sqlite3
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Catalog database paths (in priority order)
_env_catalog = os.getenv("CATALOG_DB_PATH", "")
CATALOG_DB_PATHS = [
    *([] if not _env_catalog else [Path(_env_catalog)]),
    Path("/Volumes/Crucial X10/Decide9ja/data/catalog.db"),
    Path("/app/data/catalog.db"),  # Railway deployment
    Path(os.path.expanduser("~/Decide9ja/data/catalog.db")),
]


@dataclass
class CatalogArticle:
    """A single article from the newspaper catalog."""
    id: str
    title: str
    content: str
    content_summary: Optional[str] = None
    published_date: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    topics: Optional[str] = None
    entities: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[float] = None
    relevance_rank: int = 0
    snippet: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "snippet": self.snippet,
            "published_date": self.published_date,
            "source_type": self.source_type,
            "source_id": self.source_id,
        }


@dataclass
class CatalogSearchResult:
    """Results from a catalog search."""
    query: str
    articles: List[CatalogArticle] = field(default_factory=list)
    total_matches: int = 0
    search_time_ms: float = 0
    source: str = "catalog_fts5"

    @property
    def has_results(self) -> bool:
        return len(self.articles) > 0

    def to_context_string(self, max_articles: int = 5) -> str:
        """Format results as context string for LLM."""
        if not self.articles:
            return ""

        parts = [f"=== NEWSPAPER ARCHIVE ({self.total_matches} matches) ==="]
        for i, article in enumerate(self.articles[:max_articles]):
            date_str = article.published_date or "Unknown date"
            source_str = (article.source_id or "newspaper").replace("-", "/")
            parts.append(f"\n--- [{i+1}] {article.title} ({date_str}, {source_str}) ---")
            # Use snippet (truncated content) for context
            parts.append(article.snippet)
        return "\n".join(parts)


class CatalogSearchService:
    """
    Service for searching the newspaper archive catalog.
    
    Uses SQLite FTS5 for fast full-text search across 80K+ documents
    spanning 85 years of Nigerian newspaper content.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = self._resolve_db_path(db_path)
        self._available = self._db_path is not None
        if self._available:
            logger.info(f"📰 Catalog search initialized: {self._db_path}")
        else:
            logger.warning("📰 Catalog database not found — archive search disabled")

    def _resolve_db_path(self, explicit_path: Optional[str] = None) -> Optional[Path]:
        """Find the catalog database."""
        if explicit_path:
            p = Path(explicit_path)
            if p.exists():
                return p
        for path in CATALOG_DB_PATHS:
            if path and path.exists():
                return path
        return None

    @property
    def is_available(self) -> bool:
        return self._available

    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Get a database connection."""
        if not self._available:
            return None
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=5)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Catalog DB connection error: {e}")
            return None

    def search(
        self,
        query: str,
        limit: int = 10,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        source_id: Optional[str] = None,
        topic: Optional[str] = None,
        entity: Optional[str] = None,
        snippet_length: int = 400,
    ) -> CatalogSearchResult:
        """
        Full-text search across the newspaper catalog.
        
        Args:
            query: Search terms (natural language or keywords)
            limit: Maximum results to return
            year_from: Filter by start year
            year_to: Filter by end year  
            source_id: Filter by newspaper source
            topic: Filter by topic (e.g. "economy")
            entity: Filter by entity name (e.g. "Bola Tinubu")
            snippet_length: Max characters for content snippets
            
        Returns:
            CatalogSearchResult with matching articles
        """
        start = datetime.now()
        result = CatalogSearchResult(query=query)

        if not self._available:
            return result

        conn = self._get_connection()
        if not conn:
            return result

        try:
            # Clean and prepare FTS5 query
            fts_query = self._prepare_fts_query(query)
            if not fts_query:
                return result

            # Build the SQL query
            # FTS5 match with ranking
            sql = """
                SELECT 
                    d.id,
                    d.title,
                    d.content,
                    d.content_summary,
                    d.published_date,
                    d.source_type,
                    d.source_id,
                    d.topics,
                    d.entities,
                    d.sentiment,
                    d.confidence,
                    rank
                FROM documents_fts 
                JOIN documents d ON documents_fts.rowid = d.rowid
                WHERE documents_fts MATCH ?
            """
            params: list = [fts_query]

            # Apply filters
            if year_from:
                sql += " AND d.published_date >= ?"
                params.append(f"{year_from}-01-01")
            if year_to:
                sql += " AND d.published_date <= ?"
                params.append(f"{year_to}-12-31")
            if source_id:
                # Handle fuzzy source matching
                if "_" in source_id:
                     # Exact match if likely an ID
                    sql += " AND d.source_id = ?"
                    params.append(source_id)
                else:
                    # Like match for names
                    sql += " AND d.source_id LIKE ?"
                    params.append(f"%{source_id}%")

            if topic:
                sql += " AND d.topics LIKE ?"
                params.append(f"%{topic}%")
            
            if entity:
                # Entities are stored as JSON or text list
                sql += " AND d.entities LIKE ?"
                params.append(f"%{entity}%")

            # Order by relevance (FTS5 rank) then recency
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)

            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            # Count total matches (for display)
            try:
                count_sql = """
                    SELECT COUNT(*) FROM documents_fts 
                    JOIN documents d ON documents_fts.rowid = d.rowid
                    WHERE documents_fts MATCH ?
                """
                count_params = [fts_query]
                if year_from:
                    count_sql += " AND d.published_date >= ?"
                    count_params.append(f"{year_from}-01-01")
                if year_to:
                    count_sql += " AND d.published_date <= ?"
                    count_params.append(f"{year_to}-12-31")
                if source_id:
                    if "_" in source_id:
                        count_sql += " AND d.source_id = ?"
                        count_params.append(source_id)
                    else:
                        count_sql += " AND d.source_id LIKE ?"
                        count_params.append(f"%{source_id}%")
                if topic:
                    count_sql += " AND d.topics LIKE ?"
                    count_params.append(f"%{topic}%")
                if entity:
                    count_sql += " AND d.entities LIKE ?"
                    count_params.append(f"%{entity}%")

                cursor.execute(count_sql, count_params)
                result.total_matches = cursor.fetchone()[0]
            except Exception:
                result.total_matches = len(rows)

            # Build article objects
            for i, row in enumerate(rows):
                content = row["content"] or ""
                snippet = self._make_snippet(content, query, snippet_length)
                
                article = CatalogArticle(
                    id=row["id"],
                    title=row["title"] or "Untitled",
                    content=content,
                    content_summary=row["content_summary"],
                    published_date=row["published_date"],
                    source_type=row["source_type"],
                    source_id=row["source_id"],
                    topics=row["topics"],
                    entities=row["entities"],
                    sentiment=row["sentiment"],
                    confidence=row["confidence"],
                    relevance_rank=i + 1,
                    snippet=snippet,
                )
                result.articles.append(article)

        except sqlite3.OperationalError as e:
            logger.error(f"Catalog search SQL error: {e}")
        except Exception as e:
            logger.error(f"Catalog search error: {e}")
        finally:
            conn.close()

        elapsed = (datetime.now() - start).total_seconds() * 1000
        result.search_time_ms = elapsed
        
        if result.has_results:
            logger.info(
                f"📰 Catalog: '{query}' → {result.total_matches} matches "
                f"(returned {len(result.articles)}) in {elapsed:.0f}ms"
            )
        
        return result

    def get_facets(self, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Get faceted counts for topics, sources, and years.
        If query is provided, facets are filtered by the query.
        """
        if not self._available:
             return {}

        conn = self._get_connection()
        if not conn:
            return {}

        try:
            cursor = conn.cursor()
            facets = {
                "topics": {},
                "sources": {},
                "years": {},
                "total_docs": 0
            }
            
            # Base WHERE clause
            where_clause = ""
            params = []
            
            if query:
                fts_query = self._prepare_fts_query(query)
                if fts_query:
                    # We need to join FTS table
                    table = "documents d JOIN documents_fts f ON d.rowid = f.rowid"
                    where_clause = "WHERE f.documents_fts MATCH ?"
                    params = [fts_query]
                else:
                    table = "documents d"
            else:
                 table = "documents d"


            # Total docs
            cursor.execute(f"SELECT COUNT(*) FROM {table} {where_clause}", params)
            facets["total_docs"] = cursor.fetchone()[0]

            # Sources (top 10)
            cursor.execute(
                f"SELECT d.source_id, COUNT(*) as c FROM {table} {where_clause} "
                f"GROUP BY d.source_id ORDER BY c DESC LIMIT 10", 
                params
            )
            facets["sources"] = {r[0]: r[1] for r in cursor.fetchall() if r[0]}

            # Years
            cursor.execute(
                f"SELECT substr(d.published_date, 1, 4) as year, COUNT(*) as c "
                f"FROM {table} {where_clause} "
                f"WHERE d.published_date IS NOT NULL "
                f"GROUP BY year ORDER BY year DESC", 
                params
            )
            facets["years"] = {r[0]: r[1] for r in cursor.fetchall() if r[0]}
            
            # Topics (JSON parsing is hard in SQLite, using simple LIKE approximation or generic counts)
            # Since topics are likely stored as comma-separated or JSON string, extracting them strictly in SQLite is tough without extensions.
            # We'll rely on the dedicated 'topics' table for global stats, but for query-filtered stats, we might skip complex topic breakdown 
            # or just do a simple check for known top categories.
            
            top_categories = ["politics", "economy", "security", "infrastructure", "health", "education"]
            for cat in top_categories:
                # Reuse params for each query
                cat_params = params + [f"%{cat}%"]
                cat_where = f"{where_clause} AND d.topics LIKE ?" if where_clause else "WHERE d.topics LIKE ?"
                
                cursor.execute(f"SELECT COUNT(*) FROM {table} {cat_where}", cat_params)
                count = cursor.fetchone()[0]
                if count > 0:
                    facets["topics"][cat] = count

            return facets
            
        except Exception as e:
            logger.error(f"Error getting facets: {e}")
            return {}
        finally:
            conn.close()

    def search_by_politician(
        self, name: str, limit: int = 10, year: Optional[int] = None
    ) -> CatalogSearchResult:
        """Search for articles mentioning a specific politician."""
        return self.search(
            query=f'"{name}"',  # Use entity filter instead? Or text search? Text search is broader.
            limit=limit,
            year_from=year,
            year_to=year,
            # We could also use entity=name if we trust the entity extraction
        )

    def search_by_topic(
        self, topic: str, limit: int = 10, year_from: Optional[int] = None
    ) -> CatalogSearchResult:
        """Search for articles on a specific topic."""
        return self.search(
            query=topic, # Use text search for topic keywords
            limit=limit,
            year_from=year_from,
            topic=topic # And strict filter
        )

    def get_context_for_rag(
        self, query: str, limit: int = 5, snippet_length: int = 500
    ) -> Optional[str]:
        """
        Get formatted context string suitable for RAG pipeline injection.
        
        Returns None if no relevant results found.
        """
        result = self.search(query, limit=limit, snippet_length=snippet_length)
        if not result.has_results:
            return None
        return result.to_context_string(max_articles=limit)

    def get_stats(self) -> Dict:
        """Get catalog database statistics."""
        if not self._available:
            return {"available": False, "error": "Database not found"}

        conn = self._get_connection()
        if not conn:
            return {"available": False, "error": "Connection failed"}

        try:
            cursor = conn.cursor()
            stats = {"available": True, "db_path": str(self._db_path)}

            cursor.execute("SELECT COUNT(*) FROM documents")
            stats["total_documents"] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT MIN(published_date), MAX(published_date) FROM documents"
            )
            row = cursor.fetchone()
            stats["date_range"] = {"from": row[0], "to": row[1]}

            cursor.execute(
                "SELECT processing_status, COUNT(*) FROM documents GROUP BY processing_status"
            )
            stats["by_status"] = {r[0]: r[1] for r in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM topics")
            stats["topics_count"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM entities")
            stats["entities_count"] = cursor.fetchone()[0]

            return stats
        except Exception as e:
            return {"available": True, "error": str(e)}
        finally:
            conn.close()

    def _prepare_fts_query(self, query: str) -> Optional[str]:
        """
        Prepare a natural language query for FTS5 MATCH syntax.
        
        Handles:
        - Quoted phrases (pass through) 
        - Individual keywords (OR them together)
        - Remove special FTS characters
        """
        if not query or not query.strip():
            return None

        # If user already quoted, pass through
        if '"' in query:
            # Clean dangerous characters but preserve quotes
            cleaned = re.sub(r'[^\w\s"*]', ' ', query)
            return cleaned.strip() or None

        # Remove FTS special characters
        cleaned = re.sub(r'[^\w\s]', ' ', query)
        
        # Split into words, filter short/stop words
        stop_words = {
            'the', 'is', 'at', 'on', 'in', 'a', 'an', 'of', 'to', 'for',
            'and', 'or', 'but', 'not', 'with', 'by', 'from', 'as', 'are',
            'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'what', 'who', 'when', 'where', 'how', 'which', 'that', 'this',
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'me', 'him',
            'about', 'tell', 'can', 'you', 'i', 'it', 'they', 'we', 'he', 'she',
        }
        
        words = [w for w in cleaned.split() if len(w) > 2 and w.lower() not in stop_words]
        
        if not words:
            # All words were too short or stop words, try raw
            words = [w for w in cleaned.split() if len(w) > 1]
        
        if not words:
            return None

        # Use OR for broader matching
        return " OR ".join(words)

    def _make_snippet(self, content: str, query: str, max_length: int = 400) -> str:
        """
        Create a relevant snippet from content, trying to center on query terms.
        """
        if not content:
            return "[No content]"
        
        content_clean = content.replace('\n', ' ').strip()
        
        if len(content_clean) <= max_length:
            return content_clean

        # Try to find a passage containing query terms
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        content_lower = content_clean.lower()
        
        best_pos = 0
        best_score = 0
        
        # Slide a window looking for maximum query term density
        window = max_length
        for i in range(0, min(len(content_clean) - window, 2000), 50):
            chunk = content_lower[i:i + window]
            score = sum(1 for w in query_words if w in chunk)
            if score > best_score:
                best_score = score
                best_pos = i
        
        # Extract snippet  
        start = max(0, best_pos)
        snippet = content_clean[start:start + max_length]
        
        # Clean up edges
        if start > 0:
            # Start at word boundary
            space_idx = snippet.find(' ')
            if space_idx > 0 and space_idx < 30:
                snippet = "..." + snippet[space_idx + 1:]
        
        if start + max_length < len(content_clean):
            # End at word boundary
            last_space = snippet.rfind(' ')
            if last_space > max_length - 50:
                snippet = snippet[:last_space] + "..."
        
        return snippet


# Module-level singleton
_catalog_service: Optional[CatalogSearchService] = None


def get_catalog_service() -> CatalogSearchService:
    """Get or create the catalog search service singleton."""
    global _catalog_service
    if _catalog_service is None:
        _catalog_service = CatalogSearchService()
    return _catalog_service


def catalog_search(query: str, limit: int = 5) -> Optional[str]:
    """
    Quick function to search the catalog and return formatted context.
    
    Usage:
        context = catalog_search("Tinubu anti-corruption policy")
        if context:
            print(context)
    """
    service = get_catalog_service()
    return service.get_context_for_rag(query, limit=limit)


# Test if run directly
if __name__ == "__main__":
    print("📰 Catalog Search Service Test")
    print("=" * 60)

    service = CatalogSearchService()

    if not service.is_available:
        print("❌ Catalog database not found")
        exit(1)

    # Stats
    stats = service.get_stats()
    print(f"\n📊 Database Stats:")
    print(f"   Total documents: {stats.get('total_documents', 'unknown'):,}")
    print(f"   Date range: {stats.get('date_range', {}).get('from', '?')} → {stats.get('date_range', {}).get('to', '?')}")
    print(f"   Topics: {stats.get('topics_count', 0)}")
    print(f"   Entities: {stats.get('entities_count', 0)}")

    # Test searches
    test_queries = [
        "Tinubu corruption",
        "election violence Nigeria",
        "Nigerian independence 1960",
        "fuel subsidy removal",
    ]

    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        result = service.search(query, limit=3)
        print(f"   Matches: {result.total_matches} ({result.search_time_ms:.0f}ms)")
        for article in result.articles:
            print(f"   [{article.relevance_rank}] {article.title} ({article.published_date})")
            print(f"       {article.snippet[:100]}...")
