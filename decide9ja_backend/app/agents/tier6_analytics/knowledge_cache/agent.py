"""
KnowledgeCacheAgent
===================
Manages the knowledge cache - queries existing SQLAlchemy/PostgreSQL tables.

Provides a unified interface for other agents to access:
- Politician profiles (from politicians table)
- News articles (from news_articles table)
- Promises (from politician data_json)
- Voting records (from votes + bills tables)
- Manifesto data (from rag_documents table)
- Cache miss tracking (logged to database)

Cost: FREE (database operations only)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import or_, and_, desc, func, text
from sqlalchemy.orm import Session

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _get_db() -> Session:
    """Get a database session."""
    return SessionLocal()


@register_agent
class KnowledgeCacheAgent(BaseAgent):
    """Manages the knowledge cache - read/write structured data via SQLAlchemy"""

    name = "knowledge_cache"
    description = "Cache layer for researched political knowledge"
    tier = AgentTier.ANALYTICS
    cost_level = CostLevel.FREE
    handled_intents = []  # Not user-facing

    # Cache staleness thresholds
    POLITICIAN_STALE_HOURS = 48
    NEWS_STALE_HOURS = 6
    PROMISES_STALE_HOURS = 168  # 1 week

    async def can_handle(self, input: AgentInput) -> bool:
        return False  # Not user-facing

    async def handle(self, input: AgentInput) -> AgentOutput:
        return AgentOutput(success=False, error="Not user-facing")

    # ===================
    # POLITICIAN METHODS
    # ===================

    async def get_politician(self, name: str) -> Optional[Dict]:
        """
        Get politician data from the politicians table.

        Args:
            name: Politician name (fuzzy matched)

        Returns:
            Dict with data, updated_at, sources, is_stale
        """
        db = None
        try:
            from app.database import Politician
            db = _get_db()

            # Try exact match first, then fuzzy
            politician = db.query(Politician).filter(
                Politician.name.ilike(f"%{name}%")
            ).first()

            if politician:
                # Parse data_json if available
                data = {}
                if politician.data_json:
                    try:
                        data = json.loads(politician.data_json)
                    except (json.JSONDecodeError, TypeError):
                        pass

                data.update({
                    "name": politician.name,
                    "party": politician.party,
                    "position": politician.position,
                    "state": politician.state,
                    "constituency": politician.constituency,
                    "slug": politician.slug,
                })

                return {
                    "data": data,
                    "updated_at": politician.created_at,
                    "sources": data.get("sources", []),
                    "is_stale": self._is_stale(politician.created_at, self.POLITICIAN_STALE_HOURS),
                    "cache_id": str(politician.id)
                }

            return None

        except Exception as e:
            logger.error(f"Error getting politician {name}: {e}")
            return None
        finally:
            if db:
                db.close()

    async def search_politicians(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict]:
        """Search politicians by name."""
        db = None
        try:
            from app.database import Politician
            db = _get_db()

            results = db.query(Politician).filter(
                Politician.name.ilike(f"%{query}%")
            ).limit(limit).all()

            return [
                {
                    "name": p.name,
                    "party": p.party,
                    "position": p.position,
                    "state": p.state,
                    "slug": p.slug,
                    "updated_at": p.created_at,
                    "is_stale": self._is_stale(p.created_at, self.POLITICIAN_STALE_HOURS)
                }
                for p in results
            ]

        except Exception as e:
            logger.error(f"Error searching politicians: {e}")
            return []
        finally:
            if db:
                db.close()

    # ===================
    # PROMISES METHODS
    # ===================

    async def get_promises(
        self,
        politician_name: str,
        topic: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get promises for a politician from their data_json field.

        Args:
            politician_name: Politician name
            topic: Optional topic filter
            status: Optional status filter (pending, in_progress, kept, broken)

        Returns:
            List of promise dicts
        """
        db = None
        try:
            from app.database import Politician
            db = _get_db()

            politician = db.query(Politician).filter(
                Politician.name.ilike(f"%{politician_name}%")
            ).first()

            if not politician or not politician.data_json:
                return []

            data = json.loads(politician.data_json)
            promises = data.get("promises", [])

            # Apply filters
            if topic:
                topic_lower = topic.lower()
                promises = [
                    p for p in promises
                    if topic_lower in p.get("topic", "").lower()
                    or topic_lower in p.get("category", "").lower()
                ]

            if status:
                status_lower = status.lower()
                promises = [
                    p for p in promises
                    if p.get("status", "").lower() == status_lower
                ]

            return [
                {
                    "politician_name": politician.name,
                    "promise_text": p.get("promise_text", p.get("text", p.get("description", ""))),
                    "topic": p.get("topic", p.get("category", "")),
                    "status": p.get("status", "unknown"),
                    "status_evidence": p.get("evidence", p.get("status_evidence", "")),
                    "date_made": p.get("date_made", p.get("date", "")),
                    "source_url": p.get("source_url", p.get("source", "")),
                }
                for p in promises
            ]

        except Exception as e:
            logger.error(f"Error getting promises for {politician_name}: {e}")
            return []
        finally:
            if db:
                db.close()

    # ===================
    # NEWS METHODS
    # ===================

    async def get_news(
        self,
        politician_name: Optional[str] = None,
        topic: Optional[str] = None,
        days: int = 7,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get news articles from the news_articles table.

        Args:
            politician_name: Filter by politician mention
            topic: Filter by topic
            days: How many days back
            limit: Max results

        Returns:
            List of news items
        """
        db = None
        try:
            from app.database import NewsArticle
            db = _get_db()

            cutoff = datetime.utcnow() - timedelta(days=days)
            query = db.query(NewsArticle).filter(
                NewsArticle.published_date >= cutoff
            )

            if politician_name:
                # Search in title, excerpt, and politicians_json
                query = query.filter(
                    or_(
                        NewsArticle.title.ilike(f"%{politician_name}%"),
                        NewsArticle.excerpt.ilike(f"%{politician_name}%"),
                        NewsArticle.politicians_json.ilike(f"%{politician_name}%")
                    )
                )

            if topic:
                query = query.filter(
                    or_(
                        NewsArticle.title.ilike(f"%{topic}%"),
                        NewsArticle.topics_json.ilike(f"%{topic}%")
                    )
                )

            articles = query.order_by(
                desc(NewsArticle.published_date)
            ).limit(limit).all()

            return [
                {
                    "id": str(a.id),
                    "headline": a.title,
                    "summary": a.excerpt or "",
                    "source": a.source_name or a.source,
                    "url": a.url,
                    "published_date": a.published_date.isoformat() if a.published_date else None,
                    "politician_name": politician_name,
                    "topic": topic,
                }
                for a in articles
            ]

        except Exception as e:
            logger.error(f"Error getting news: {e}")
            return []
        finally:
            if db:
                db.close()

    # ===================
    # MANIFESTO METHODS
    # ===================

    async def get_manifesto(
        self,
        party: str,
        topic: Optional[str] = None
    ) -> List[Dict]:
        """
        Get manifesto data from the rag_documents table.
        Manifestos are stored as doc_type='manifesto'.

        Args:
            party: Party code (APC, PDP, LP, etc.)
            topic: Optional topic filter

        Returns:
            List of manifesto sections
        """
        db = None
        try:
            from app.database import Document
            db = _get_db()

            query = db.query(Document).filter(
                Document.doc_type == "manifesto",
                or_(
                    Document.doc_id.ilike(f"%{party}%"),
                    Document.title.ilike(f"%{party}%"),
                    Document.content.ilike(f"%{party}%")
                )
            )

            if topic:
                query = query.filter(
                    or_(
                        Document.title.ilike(f"%{topic}%"),
                        Document.content.ilike(f"%{topic}%")
                    )
                )

            docs = query.limit(50).all()

            return [
                {
                    "id": str(d.id),
                    "party": party.upper(),
                    "title": d.title or "",
                    "content": d.content[:2000] if d.content else "",
                    "topic": topic or "",
                    "doc_id": d.doc_id,
                }
                for d in docs
            ]

        except Exception as e:
            logger.error(f"Error getting manifesto for {party}: {e}")
            return []
        finally:
            if db:
                db.close()

    # ===================
    # VOTING RECORD METHODS
    # ===================

    async def get_voting_records(
        self,
        politician_name: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get voting records from the votes + bills tables.

        Args:
            politician_name: Name of the legislator
            limit: Max records to return

        Returns:
            List of voting record dicts
        """
        db = None
        try:
            from app.database import Vote, Bill, Politician
            db = _get_db()

            # First find the politician
            politician = db.query(Politician).filter(
                Politician.name.ilike(f"%{politician_name}%")
            ).first()

            if not politician:
                return []

            # Get their votes with bill info
            votes = db.query(Vote).filter(
                Vote.politician_slug == politician.slug
            ).order_by(desc(Vote.vote_date)).limit(limit).all()

            results = []
            for vote in votes:
                # Get the bill details
                bill = db.query(Bill).filter(
                    Bill.bill_id == vote.bill_id
                ).first()

                results.append({
                    "id": str(vote.id),
                    "politician_name": politician.name,
                    "bill_name": bill.title if bill else (vote.motion_title or vote.bill_id),
                    "bill_id": vote.bill_id,
                    "vote": vote.vote_cast,  # aye, nay, abstain, absent
                    "date": vote.vote_date.isoformat() if vote.vote_date else None,
                    "summary": bill.description if bill else (vote.motion_description or ""),
                    "chamber": vote.chamber,
                    "voted_with_party": vote.voted_with_party,
                })

            return results

        except Exception as e:
            logger.error(f"Error getting voting records for {politician_name}: {e}")
            return []
        finally:
            if db:
                db.close()

    # ===================
    # CACHE MISS TRACKING
    # ===================

    async def record_cache_miss(
        self,
        query: str,
        intent: str,
        entity: Optional[str] = None
    ):
        """
        Record a cache miss for research prioritization.
        Uses the Interaction table or logs for now.
        """
        # Log the miss for analytics — lightweight, no separate table needed
        logger.info(
            f"CACHE_MISS | intent={intent} | entity={entity} | query={query[:200]}"
        )

    async def get_cache_miss_stats(self, hours: int = 24) -> Dict:
        """Get cache miss statistics — placeholder until analytics table exists."""
        return {
            "total_misses": 0,
            "by_topic": {},
            "period_hours": hours,
            "note": "Check logs for CACHE_MISS entries"
        }

    # ===================
    # UTILITY METHODS
    # ===================

    def _is_stale(self, updated_at: Optional[datetime], hours: int) -> bool:
        """Check if data is stale"""
        if not updated_at:
            return True
        return (datetime.utcnow() - updated_at).total_seconds() > hours * 3600

    async def get_cache_stats(self) -> Dict:
        """Get overall cache statistics from real tables."""
        db = None
        try:
            from app.database import Politician, NewsArticle, Vote
            db = _get_db()

            politician_count = db.query(Politician).count()
            news_count = db.query(NewsArticle).count()
            vote_count = db.query(Vote).count()

            return {
                "politicians": politician_count,
                "news_articles": news_count,
                "voting_records": vote_count,
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
        finally:
            if db:
                db.close()
