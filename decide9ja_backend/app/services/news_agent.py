"""
News Agent for Decide9ja/Tade Chatbot.

A dedicated agent for handling all news-related queries with:
1. Local news database querying (recent articles)
2. Issue/trending topic extraction
3. Politician-specific news filtering
4. State-specific news filtering
5. Real-time news digests
6. Integration with agentic retrieval system

This agent runs as both:
- A callable tool in the agentic retrieval stack
- A background worker processing new articles continuously

Author: Decide9ja Team
Created: January 2025
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from sqlalchemy import or_, and_, desc, func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

class NewsQueryType(str, Enum):
    """Types of news queries the agent handles."""
    LATEST = "latest"           # Get latest news overall
    POLITICIAN = "politician"   # News about specific politician
    STATE = "state"             # News about specific state
    TOPIC = "topic"             # News about specific topic/domain
    TRENDING = "trending"       # Trending issues
    BREAKING = "breaking"       # High-priority recent news
    SEARCH = "search"           # Keyword search


@dataclass
class NewsQuery:
    """Structured news query."""
    query_type: NewsQueryType
    original_query: str
    politician_name: Optional[str] = None
    state: Optional[str] = None
    topic: Optional[str] = None
    domain: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    hours_back: int = 48
    limit: int = 5


@dataclass
class NewsResult:
    """Result from news query."""
    articles: List[Dict]
    issues: List[Dict]
    trending_topics: List[str]
    sources_used: List[str]
    query_type: NewsQueryType
    total_found: int
    formatted_response: str
    confidence: float = 0.8


# =============================================================================
# NEWS AGENT CLASS
# =============================================================================

class NewsAgent:
    """
    Dedicated agent for news retrieval and processing.

    Capabilities:
    - Query local news database by multiple criteria
    - Extract and track trending issues
    - Provide politician-specific news
    - Generate news digests
    - Process new articles for issue extraction
    """

    def __init__(self, db: Session = None):
        """Initialize news agent."""
        self._db = db
        self._db_owner = False

    def _get_db(self) -> Session:
        """Get database session, creating if needed."""
        if self._db is None:
            from app.database import SessionLocal
            self._db = SessionLocal()
            self._db_owner = True
        return self._db

    def _close_db(self):
        """Close database session if we own it."""
        if self._db_owner and self._db:
            self._db.close()
            self._db = None
            self._db_owner = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_db()

    # =========================================================================
    # QUERY PARSING
    # =========================================================================

    def parse_query(self, query: str, entities: Dict = None) -> NewsQuery:
        """
        Parse natural language query into structured NewsQuery.

        Args:
            query: Natural language query
            entities: Pre-extracted entities from understanding layer

        Returns:
            NewsQuery with parsed parameters
        """
        query_lower = query.lower()
        entities = entities or {}

        # Detect query type from keywords
        query_type = NewsQueryType.LATEST

        if any(kw in query_lower for kw in ["trending", "hot", "popular", "viral"]):
            query_type = NewsQueryType.TRENDING
        elif any(kw in query_lower for kw in ["breaking", "urgent", "just in", "happening now"]):
            query_type = NewsQueryType.BREAKING
        elif entities.get("politician_name"):
            query_type = NewsQueryType.POLITICIAN
        elif entities.get("state"):
            query_type = NewsQueryType.STATE
        elif entities.get("topic") or entities.get("domain"):
            query_type = NewsQueryType.TOPIC
        elif any(kw in query_lower for kw in ["latest", "recent", "today", "news"]):
            query_type = NewsQueryType.LATEST
        else:
            query_type = NewsQueryType.SEARCH

        # Extract keywords from query
        stop_words = {"what", "who", "when", "where", "how", "is", "the", "a", "an",
                      "in", "on", "at", "to", "for", "of", "and", "or", "news", "about",
                      "latest", "recent", "happening", "tell", "me", "give"}
        keywords = [w for w in query_lower.split() if w not in stop_words and len(w) > 2]

        # Determine time window
        hours_back = 48  # Default
        if "today" in query_lower:
            hours_back = 24
        elif "week" in query_lower:
            hours_back = 168
        elif "breaking" in query_lower or "just" in query_lower:
            hours_back = 6

        return NewsQuery(
            query_type=query_type,
            original_query=query,
            politician_name=entities.get("politician_name"),
            state=entities.get("state"),
            topic=entities.get("topic"),
            domain=entities.get("domain"),
            keywords=keywords,
            hours_back=hours_back,
            limit=entities.get("limit", 5)
        )

    # =========================================================================
    # CORE QUERY METHODS
    # =========================================================================

    async def query(self, query: str, entities: Dict = None) -> NewsResult:
        """
        Main query method - routes to appropriate handler.

        Args:
            query: Natural language query
            entities: Pre-extracted entities

        Returns:
            NewsResult with articles and formatted response
        """
        parsed = self.parse_query(query, entities)

        handlers = {
            NewsQueryType.LATEST: self._query_latest,
            NewsQueryType.POLITICIAN: self._query_by_politician,
            NewsQueryType.STATE: self._query_by_state,
            NewsQueryType.TOPIC: self._query_by_topic,
            NewsQueryType.TRENDING: self._query_trending,
            NewsQueryType.BREAKING: self._query_breaking,
            NewsQueryType.SEARCH: self._query_search,
        }

        handler = handlers.get(parsed.query_type, self._query_latest)
        return await handler(parsed)

    async def _query_latest(self, parsed: NewsQuery) -> NewsResult:
        """Get latest news articles."""
        from app.database import NewsArticle

        db = self._get_db()
        cutoff = datetime.now() - timedelta(hours=parsed.hours_back)

        articles = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff
        ).order_by(desc(NewsArticle.scraped_at)).limit(parsed.limit).all()

        return self._build_result(articles, parsed, "latest Nigerian political news")

    async def _query_by_politician(self, parsed: NewsQuery) -> NewsResult:
        """Get news mentioning a specific politician."""
        from app.database import NewsArticle

        db = self._get_db()
        cutoff = datetime.now() - timedelta(hours=parsed.hours_back)
        name = parsed.politician_name or ""

        # Search in politicians_json and title
        articles = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff,
            or_(
                NewsArticle.politicians_json.ilike(f'%{name}%'),
                NewsArticle.title.ilike(f'%{name}%'),
                NewsArticle.excerpt.ilike(f'%{name}%')
            )
        ).order_by(desc(NewsArticle.scraped_at)).limit(parsed.limit).all()

        return self._build_result(articles, parsed, f"news about {name}")

    async def _query_by_state(self, parsed: NewsQuery) -> NewsResult:
        """Get news about a specific state."""
        from app.database import NewsArticle

        db = self._get_db()
        cutoff = datetime.now() - timedelta(hours=parsed.hours_back)
        state = parsed.state or ""

        articles = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff,
            or_(
                NewsArticle.title.ilike(f'%{state}%'),
                NewsArticle.excerpt.ilike(f'%{state}%'),
                NewsArticle.full_text.ilike(f'%{state}%')
            )
        ).order_by(desc(NewsArticle.scraped_at)).limit(parsed.limit).all()

        return self._build_result(articles, parsed, f"news from {state}")

    async def _query_by_topic(self, parsed: NewsQuery) -> NewsResult:
        """Get news about a specific topic/domain."""
        from app.database import NewsArticle

        db = self._get_db()
        cutoff = datetime.now() - timedelta(hours=parsed.hours_back)
        topic = parsed.topic or parsed.domain or ""

        # Map common topics to domains
        topic_domains = {
            "power": ["power", "electricity", "grid", "nerc", "blackout"],
            "security": ["security", "kidnap", "bandit", "terrorist", "attack"],
            "economy": ["economy", "naira", "inflation", "cbn", "gdp", "budget"],
            "education": ["education", "university", "asuu", "school"],
            "health": ["health", "hospital", "disease", "medical"],
            "roads": ["road", "highway", "bridge", "transport"],
        }

        search_terms = topic_domains.get(topic.lower(), [topic])

        conditions = [NewsArticle.scraped_at >= cutoff]
        term_conditions = []
        for term in search_terms:
            term_conditions.append(NewsArticle.title.ilike(f'%{term}%'))
            term_conditions.append(NewsArticle.excerpt.ilike(f'%{term}%'))

        if term_conditions:
            conditions.append(or_(*term_conditions))

        articles = db.query(NewsArticle).filter(
            and_(*conditions)
        ).order_by(desc(NewsArticle.scraped_at)).limit(parsed.limit).all()

        return self._build_result(articles, parsed, f"news about {topic}")

    async def _query_trending(self, parsed: NewsQuery) -> NewsResult:
        """Get trending issues/topics."""
        from app.database import Issue, NewsArticle

        db = self._get_db()
        cutoff = datetime.now() - timedelta(hours=72)

        # Get trending issues (most events recently)
        trending_issues = db.query(Issue).filter(
            Issue.last_updated >= cutoff,
            Issue.status == "active"
        ).order_by(desc(Issue.event_count)).limit(5).all()

        # Also get recent news
        articles = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff
        ).order_by(desc(NewsArticle.scraped_at)).limit(parsed.limit).all()

        result = self._build_result(articles, parsed, "trending Nigerian political issues")

        # Add issues to result
        result.issues = [
            {
                "issue_id": i.issue_id,
                "title": i.title,
                "domain": i.domain,
                "severity": i.severity,
                "event_count": i.event_count
            }
            for i in trending_issues
        ]

        # Extract trending topics
        result.trending_topics = [i.title for i in trending_issues[:5]]

        return result

    async def _query_breaking(self, parsed: NewsQuery) -> NewsResult:
        """Get breaking/urgent news (last 6 hours)."""
        from app.database import NewsArticle

        db = self._get_db()
        cutoff = datetime.now() - timedelta(hours=6)

        articles = db.query(NewsArticle).filter(
            NewsArticle.scraped_at >= cutoff
        ).order_by(desc(NewsArticle.scraped_at)).limit(parsed.limit).all()

        return self._build_result(articles, parsed, "breaking news")

    async def _query_search(self, parsed: NewsQuery) -> NewsResult:
        """Search news by keywords."""
        from app.database import NewsArticle

        db = self._get_db()
        cutoff = datetime.now() - timedelta(hours=parsed.hours_back)

        conditions = [NewsArticle.scraped_at >= cutoff]

        for keyword in parsed.keywords:
            conditions.append(
                or_(
                    NewsArticle.title.ilike(f'%{keyword}%'),
                    NewsArticle.excerpt.ilike(f'%{keyword}%')
                )
            )

        articles = db.query(NewsArticle).filter(
            and_(*conditions)
        ).order_by(desc(NewsArticle.scraped_at)).limit(parsed.limit).all()

        return self._build_result(articles, parsed, f"search results for: {' '.join(parsed.keywords)}")

    def _build_result(self, articles: List, parsed: NewsQuery, context_desc: str) -> NewsResult:
        """Build NewsResult from query results with source verification."""
        article_dicts = []
        sources_used = set()

        # Import verifier for source checking
        try:
            from app.services.verifier_agent import quick_verify_source, TrustTier
            verifier_available = True
        except ImportError:
            verifier_available = False

        for a in articles:
            source_name = a.source_name or a.source or "Unknown"
            sources_used.add(source_name)

            # Verify source trust tier
            trust_tier = "UNKNOWN"
            trust_score = 0.5
            if verifier_available and a.url:
                verification = quick_verify_source(a.url)
                trust_tier = verification.get("trust_tier", "UNKNOWN")
                trust_score = verification.get("trust_score", 0.5)

            article_dicts.append({
                "id": a.article_id,
                "title": a.title,
                "url": a.url,
                "source": source_name,
                "excerpt": (a.excerpt or "")[:200],
                "scraped_at": a.scraped_at.isoformat() if a.scraped_at else None,
                "politicians": json.loads(a.politicians_json or "[]"),
                "topics": json.loads(a.topics_json or "[]"),
                "trust_tier": trust_tier,
                "trust_score": trust_score
            })

        # Format response for LLM context with trust indicators
        if article_dicts:
            # Sort by trust score (highest first)
            sorted_articles = sorted(article_dicts, key=lambda x: x.get("trust_score", 0), reverse=True)

            formatted_parts = [f"*{context_desc.title()}* ({len(article_dicts)} articles):\n"]
            for i, a in enumerate(sorted_articles[:5], 1):
                tier = a.get("trust_tier", "UNKNOWN")
                tier_indicator = "✓" if tier in ["OFFICIAL", "WATCHDOG", "VETTED_NEWS"] else "○"
                formatted_parts.append(f"{i}. {tier_indicator} **{a['title']}** ({a['source']})")
                if a['excerpt']:
                    formatted_parts.append(f"   {a['excerpt'][:150]}...")

            # Add trust legend if mixed tiers
            tiers = set(a.get("trust_tier") for a in sorted_articles[:5])
            if len(tiers) > 1:
                formatted_parts.append("\n_✓ = Verified source, ○ = Requires verification_")

            formatted_response = "\n".join(formatted_parts)
        else:
            formatted_response = f"No {context_desc} found in the last {parsed.hours_back} hours."

        return NewsResult(
            articles=article_dicts,
            issues=[],
            trending_topics=[],
            sources_used=list(sources_used),
            query_type=parsed.query_type,
            total_found=len(article_dicts),
            formatted_response=formatted_response,
            confidence=0.9 if article_dicts else 0.3
        )

    # =========================================================================
    # CONTINUOUS PROCESSING
    # =========================================================================

    async def process_unprocessed_articles(self, limit: int = 20) -> Dict[str, Any]:
        """
        Process unprocessed articles through issue extraction.
        Called by scheduler or background worker.

        Args:
            limit: Max articles to process in one batch

        Returns:
            Dict with processing stats
        """
        from app.database import NewsArticle
        from app.services.issue_pipeline import process_article_for_issues

        db = self._get_db()

        # Get unprocessed articles
        articles = db.query(NewsArticle).filter(
            NewsArticle.is_processed == False,
            or_(
                NewsArticle.full_text.isnot(None),
                NewsArticle.excerpt.isnot(None)
            )
        ).order_by(desc(NewsArticle.scraped_at)).limit(limit).all()

        stats = {
            "total": len(articles),
            "processed": 0,
            "issues_created": 0,
            "failed": 0,
            "skipped": 0
        }

        for article in articles:
            try:
                issue_id = process_article_for_issues(article)
                stats["processed"] += 1
                if issue_id:
                    stats["issues_created"] += 1
            except Exception as e:
                logger.error(f"Failed to process article {article.article_id}: {e}")
                stats["failed"] += 1

        logger.info(f"News processing complete: {stats}")
        return stats

    async def get_news_for_rag(self, query: str, limit: int = 5) -> str:
        """
        Get news context formatted for RAG.

        Args:
            query: User query
            limit: Max articles

        Returns:
            Formatted string for LLM context
        """
        result = await self.query(query, {"limit": limit})
        return result.formatted_response


# =============================================================================
# TOOL FUNCTION FOR AGENTIC RETRIEVAL
# =============================================================================

async def news_agent_tool(query: str, entities: Dict, context: Dict) -> Dict:
    """
    Tool function for agentic retrieval integration.

    This is the entry point when called from agentic_retrieval.py

    Args:
        query: User query
        entities: Extracted entities
        context: User context (state, preferences, etc.)

    Returns:
        Tool result dict
    """
    from app.services.agentic_retrieval import ToolResult

    try:
        with NewsAgent() as agent:
            # Add context to entities
            if context.get("state"):
                entities.setdefault("state", context["state"])

            result = await agent.query(query, entities)

            if result.articles:
                return ToolResult(
                    tool_name="news_db",
                    success=True,
                    data={
                        "articles": result.articles,
                        "issues": result.issues,
                        "trending": result.trending_topics,
                        "formatted": result.formatted_response
                    },
                    confidence=result.confidence,
                    source="local_news_db",
                    metadata={
                        "query_type": result.query_type.value,
                        "total_found": result.total_found,
                        "sources": result.sources_used
                    }
                )
            else:
                return ToolResult(
                    tool_name="news_db",
                    success=False,
                    data=None,
                    confidence=0.2,
                    source="local_news_db",
                    error="No news articles found matching query",
                    handoff_to="web_search"  # Fallback to web search
                )

    except Exception as e:
        logger.error(f"News agent error: {e}")
        return ToolResult(
            tool_name="news_db",
            success=False,
            data=None,
            confidence=0.0,
            source="local_news_db",
            error=str(e),
            handoff_to="web_search"
        )


# =============================================================================
# BACKGROUND WORKER
# =============================================================================

class NewsWorker:
    """
    Background worker for continuous news processing.

    Runs as a daemon and:
    - Monitors for new articles
    - Triggers issue extraction
    - Maintains news freshness
    """

    def __init__(self, poll_interval: int = 300):
        """
        Initialize worker.

        Args:
            poll_interval: Seconds between processing runs
        """
        self.poll_interval = poll_interval
        self._running = False
        self._stats = {
            "runs": 0,
            "articles_processed": 0,
            "issues_created": 0,
            "errors": 0,
            "started_at": None,
            "last_run": None
        }

    async def start(self):
        """Start the background worker."""
        logger.info(f"Starting NewsWorker (poll interval: {self.poll_interval}s)")
        self._running = True
        self._stats["started_at"] = datetime.now().isoformat()

        while self._running:
            try:
                await self._process_cycle()
            except Exception as e:
                logger.error(f"Worker cycle error: {e}")
                self._stats["errors"] += 1

            await asyncio.sleep(self.poll_interval)

    def stop(self):
        """Stop the background worker."""
        logger.info("Stopping NewsWorker")
        self._running = False

    async def _process_cycle(self):
        """Run one processing cycle."""
        self._stats["runs"] += 1
        self._stats["last_run"] = datetime.now().isoformat()

        with NewsAgent() as agent:
            result = await agent.process_unprocessed_articles(limit=30)
            self._stats["articles_processed"] += result["processed"]
            self._stats["issues_created"] += result["issues_created"]

        logger.info(f"Worker cycle complete: {result}")

    def get_stats(self) -> Dict:
        """Get worker statistics."""
        return self._stats.copy()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_news_agent: Optional[NewsAgent] = None
_news_worker: Optional[NewsWorker] = None


def get_news_agent() -> NewsAgent:
    """Get singleton NewsAgent instance."""
    global _news_agent
    if _news_agent is None:
        _news_agent = NewsAgent()
    return _news_agent


def get_news_worker(poll_interval: int = 300) -> NewsWorker:
    """Get singleton NewsWorker instance."""
    global _news_worker
    if _news_worker is None:
        _news_worker = NewsWorker(poll_interval=poll_interval)
    return _news_worker


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="News Agent CLI")
    parser.add_argument("--query", type=str, help="Query news")
    parser.add_argument("--process", action="store_true", help="Process unprocessed articles")
    parser.add_argument("--worker", action="store_true", help="Run as background worker")
    parser.add_argument("--interval", type=int, default=300, help="Worker poll interval")

    args = parser.parse_args()

    async def main():
        if args.query:
            with NewsAgent() as agent:
                result = await agent.query(args.query)
                print(result.formatted_response)
                print(f"\nFound {result.total_found} articles from: {', '.join(result.sources_used)}")

        elif args.process:
            with NewsAgent() as agent:
                stats = await agent.process_unprocessed_articles()
                print(f"Processing stats: {json.dumps(stats, indent=2)}")

        elif args.worker:
            worker = get_news_worker(poll_interval=args.interval)
            try:
                await worker.start()
            except KeyboardInterrupt:
                worker.stop()

    asyncio.run(main())
