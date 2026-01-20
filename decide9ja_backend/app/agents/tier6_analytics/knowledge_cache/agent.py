"""
KnowledgeCacheAgent
===================
Manages the knowledge cache - the central data store for all researched information.

Operations:
- Get/save politician profiles
- Get/save promises
- Get/save news summaries
- Track cache misses for research prioritization

Cost: FREE (database operations only)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from app.agents.base import (
    DatabaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class KnowledgeCacheAgent(DatabaseAgent):
    """Manages the knowledge cache - read/write structured data"""

    name = "knowledge_cache"
    description = "Cache layer for researched political knowledge"
    tier = AgentTier.ANALYTICS
    cost_level = CostLevel.FREE
    handled_intents = []  # Not user-facing

    # Cache staleness thresholds
    POLITICIAN_STALE_HOURS = 48
    NEWS_STALE_HOURS = 6
    PROMISES_STALE_HOURS = 168  # 1 week

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def can_handle(self, input: AgentInput) -> bool:
        return False  # Not user-facing

    async def query_database(self, input: AgentInput) -> Optional[Dict]:
        """Not used - this agent has specific methods"""
        return None

    # ===================
    # POLITICIAN METHODS
    # ===================

    async def get_politician(self, name: str) -> Optional[Dict]:
        """
        Get cached politician data.

        Args:
            name: Politician name (fuzzy matched)

        Returns:
            Dict with data, updated_at, sources, is_stale
        """
        if not self.db:
            return None

        try:
            result = await self.db.knowledge_cache.find_one({
                "entity_type": "politician",
                "entity_name": {"$regex": name, "$options": "i"}
            })

            if result:
                updated_at = result.get("updated_at")
                return {
                    "data": result.get("data", {}),
                    "updated_at": updated_at,
                    "sources": result.get("sources", []),
                    "is_stale": self._is_stale(updated_at, self.POLITICIAN_STALE_HOURS),
                    "cache_id": str(result.get("_id"))
                }

            return None

        except Exception as e:
            logger.error(f"Error getting politician {name}: {e}")
            return None

    async def save_politician(
        self,
        name: str,
        data: Dict,
        sources: List[str]
    ) -> bool:
        """
        Save or update politician data in cache.

        Args:
            name: Politician name
            data: Structured profile data
            sources: List of source URLs

        Returns:
            True if successful
        """
        if not self.db:
            return False

        try:
            await self.db.knowledge_cache.update_one(
                {
                    "entity_type": "politician",
                    "entity_name": name
                },
                {
                    "$set": {
                        "data": data,
                        "sources": sources,
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            logger.info(f"Cached politician: {name}")
            return True

        except Exception as e:
            logger.error(f"Error saving politician {name}: {e}")
            return False

    async def search_politicians(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search cached politicians by name.

        Args:
            query: Search string
            limit: Max results

        Returns:
            List of matching politician summaries
        """
        if not self.db:
            return []

        try:
            cursor = self.db.knowledge_cache.find(
                {
                    "entity_type": "politician",
                    "entity_name": {"$regex": query, "$options": "i"}
                }
            ).limit(limit)

            results = []
            async for doc in cursor:
                data = doc.get("data", {})
                results.append({
                    "name": doc.get("entity_name"),
                    "party": data.get("party"),
                    "position": data.get("current_position"),
                    "state": data.get("state_of_origin"),
                    "updated_at": doc.get("updated_at"),
                    "is_stale": self._is_stale(doc.get("updated_at"), self.POLITICIAN_STALE_HOURS)
                })

            return results

        except Exception as e:
            logger.error(f"Error searching politicians: {e}")
            return []

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
        Get cached promises for a politician.

        Args:
            politician_name: Politician name
            topic: Optional topic filter
            status: Optional status filter (pending, in_progress, kept, broken)

        Returns:
            List of promise dicts
        """
        if not self.db:
            return []

        try:
            query = {
                "politician_name": {"$regex": politician_name, "$options": "i"}
            }

            if topic:
                query["topic"] = topic
            if status:
                query["status"] = status

            cursor = self.db.promises_cache.find(query).sort("date_made", -1)
            promises = await cursor.to_list(100)

            return [
                {
                    "id": str(p.get("_id")),
                    "politician_name": p.get("politician_name"),
                    "promise_text": p.get("promise_text"),
                    "topic": p.get("topic"),
                    "status": p.get("status"),
                    "status_evidence": p.get("status_evidence"),
                    "date_made": p.get("date_made"),
                    "source_url": p.get("source_url"),
                    "updated_at": p.get("updated_at")
                }
                for p in promises
            ]

        except Exception as e:
            logger.error(f"Error getting promises for {politician_name}: {e}")
            return []

    async def save_promises(
        self,
        politician_name: str,
        promises: List[Dict]
    ) -> int:
        """
        Save or update promises in cache.

        Args:
            politician_name: Politician name
            promises: List of promise dicts

        Returns:
            Number of promises saved
        """
        if not self.db or not promises:
            return 0

        saved = 0
        for promise in promises:
            try:
                await self.db.promises_cache.update_one(
                    {
                        "politician_name": politician_name,
                        "promise_text": promise.get("promise_text")
                    },
                    {
                        "$set": {
                            "topic": promise.get("topic"),
                            "status": promise.get("status", "unknown"),
                            "status_evidence": promise.get("status_evidence"),
                            "source_url": promise.get("source_url"),
                            "date_made": promise.get("date_made"),
                            "updated_at": datetime.utcnow()
                        },
                        "$setOnInsert": {
                            "created_at": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                saved += 1

            except Exception as e:
                logger.error(f"Error saving promise: {e}")
                continue

        logger.info(f"Saved {saved} promises for {politician_name}")
        return saved

    async def update_promise_status(
        self,
        promise_id: str,
        status: str,
        evidence: str
    ) -> bool:
        """Update the status of a specific promise"""
        if not self.db:
            return False

        try:
            from bson import ObjectId
            await self.db.promises_cache.update_one(
                {"_id": ObjectId(promise_id)},
                {
                    "$set": {
                        "status": status,
                        "status_evidence": evidence,
                        "status_updated_at": datetime.utcnow()
                    }
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error updating promise status: {e}")
            return False

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
        Get cached news items.

        Args:
            politician_name: Filter by politician
            topic: Filter by topic
            days: How many days back
            limit: Max results

        Returns:
            List of news items
        """
        if not self.db:
            return []

        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = {"created_at": {"$gte": cutoff}}

            if politician_name:
                query["politician_name"] = {"$regex": politician_name, "$options": "i"}
            if topic:
                query["topic"] = topic

            cursor = self.db.news_cache.find(query).sort("published_date", -1).limit(limit)
            news = await cursor.to_list(limit)

            return [
                {
                    "id": str(n.get("_id")),
                    "headline": n.get("headline"),
                    "summary": n.get("summary"),
                    "source": n.get("source"),
                    "url": n.get("url"),
                    "published_date": n.get("published_date"),
                    "politician_name": n.get("politician_name"),
                    "sentiment": n.get("sentiment"),
                    "topic": n.get("topic")
                }
                for n in news
            ]

        except Exception as e:
            logger.error(f"Error getting news: {e}")
            return []

    async def save_news(self, news_items: List[Dict]) -> int:
        """Save news items to cache (deduplicates by URL)"""
        if not self.db or not news_items:
            return 0

        saved = 0
        for item in news_items:
            try:
                # Skip if no URL (can't dedupe)
                if not item.get("url"):
                    continue

                await self.db.news_cache.update_one(
                    {"url": item["url"]},
                    {
                        "$set": {
                            "headline": item.get("headline"),
                            "summary": item.get("summary"),
                            "source": item.get("source"),
                            "published_date": item.get("date"),
                            "politician_name": item.get("politician_name"),
                            "sentiment": item.get("sentiment"),
                            "topic": item.get("topic"),
                            "updated_at": datetime.utcnow()
                        },
                        "$setOnInsert": {
                            "created_at": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                saved += 1

            except Exception as e:
                logger.debug(f"Error saving news item: {e}")
                continue

        return saved

    # ===================
    # MANIFESTO METHODS
    # ===================

    async def get_manifesto(
        self,
        party: str,
        topic: Optional[str] = None
    ) -> List[Dict]:
        """
        Get cached manifesto data for a party.

        Args:
            party: Party code (APC, PDP, LP, etc.)
            topic: Optional topic filter

        Returns:
            List of manifesto sections
        """
        if not self.db:
            return []

        try:
            query = {"party_code": party.upper()}
            if topic:
                query["topic"] = {"$regex": topic, "$options": "i"}

            cursor = self.db.manifesto_cache.find(query).sort("section_order", 1)
            sections = await cursor.to_list(50)

            return [
                {
                    "id": str(s.get("_id")),
                    "party": s.get("party_code"),
                    "title": s.get("title"),
                    "content": s.get("content"),
                    "topic": s.get("topic"),
                    "page": s.get("page_number"),
                    "year": s.get("year", 2023)
                }
                for s in sections
            ]

        except Exception as e:
            logger.error(f"Error getting manifesto for {party}: {e}")
            return []

    async def save_manifesto(
        self,
        party: str,
        sections: List[Dict],
        year: int = 2023
    ) -> int:
        """
        Save manifesto sections to cache.

        Args:
            party: Party code
            sections: List of manifesto sections
            year: Manifesto year

        Returns:
            Number of sections saved
        """
        if not self.db or not sections:
            return 0

        saved = 0
        for i, section in enumerate(sections):
            try:
                await self.db.manifesto_cache.update_one(
                    {
                        "party_code": party.upper(),
                        "title": section.get("title"),
                        "year": year
                    },
                    {
                        "$set": {
                            "content": section.get("content"),
                            "topic": section.get("topic"),
                            "page_number": section.get("page"),
                            "section_order": i,
                            "updated_at": datetime.utcnow()
                        },
                        "$setOnInsert": {
                            "created_at": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                saved += 1

            except Exception as e:
                logger.error(f"Error saving manifesto section: {e}")
                continue

        logger.info(f"Saved {saved} manifesto sections for {party}")
        return saved

    # ===================
    # VOTING RECORD METHODS
    # ===================

    async def get_voting_records(
        self,
        politician_name: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get voting records for a legislator.

        Args:
            politician_name: Name of the legislator
            limit: Max records to return

        Returns:
            List of voting record dicts
        """
        if not self.db:
            return []

        try:
            cursor = self.db.voting_records.find({
                "politician_name": {"$regex": politician_name, "$options": "i"}
            }).sort("vote_date", -1).limit(limit)

            records = await cursor.to_list(limit)

            return [
                {
                    "id": str(r.get("_id")),
                    "politician_name": r.get("politician_name"),
                    "bill_name": r.get("bill_name"),
                    "bill_id": r.get("bill_id"),
                    "vote": r.get("vote"),  # YES, NO, ABSTAIN
                    "date": r.get("vote_date"),
                    "summary": r.get("bill_summary"),
                    "chamber": r.get("chamber"),  # Senate, House
                    "session": r.get("session")
                }
                for r in records
            ]

        except Exception as e:
            logger.error(f"Error getting voting records for {politician_name}: {e}")
            return []

    async def save_voting_records(
        self,
        records: List[Dict]
    ) -> int:
        """
        Save voting records to cache.

        Args:
            records: List of voting record dicts

        Returns:
            Number of records saved
        """
        if not self.db or not records:
            return 0

        saved = 0
        for record in records:
            try:
                await self.db.voting_records.update_one(
                    {
                        "politician_name": record.get("politician_name"),
                        "bill_id": record.get("bill_id")
                    },
                    {
                        "$set": {
                            "bill_name": record.get("bill_name"),
                            "vote": record.get("vote"),
                            "vote_date": record.get("date"),
                            "bill_summary": record.get("summary"),
                            "chamber": record.get("chamber"),
                            "session": record.get("session"),
                            "updated_at": datetime.utcnow()
                        },
                        "$setOnInsert": {
                            "created_at": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                saved += 1

            except Exception as e:
                logger.error(f"Error saving voting record: {e}")
                continue

        logger.info(f"Saved {saved} voting records")
        return saved

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

        Args:
            query: User's query text
            intent: Classified intent
            entity: Specific entity requested (if identified)
        """
        if not self.db:
            return

        try:
            await self.db.cache_misses.insert_one({
                "query_text": query[:500],  # Limit size
                "intent_topic": intent,
                "query_entity": entity,
                "created_at": datetime.utcnow()
            })
        except Exception as e:
            logger.debug(f"Error recording cache miss: {e}")

    async def get_cache_miss_stats(self, hours: int = 24) -> Dict:
        """Get cache miss statistics for research prioritization"""
        if not self.db:
            return {}

        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            # Count by intent topic
            pipeline = [
                {"$match": {"created_at": {"$gte": cutoff}}},
                {"$group": {
                    "_id": "$intent_topic",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]

            results = await self.db.cache_misses.aggregate(pipeline).to_list(50)

            return {
                "total_misses": sum(r["count"] for r in results),
                "by_topic": {r["_id"]: r["count"] for r in results if r["_id"]},
                "period_hours": hours
            }

        except Exception as e:
            logger.error(f"Error getting cache miss stats: {e}")
            return {}

    # ===================
    # UTILITY METHODS
    # ===================

    def _is_stale(self, updated_at: Optional[datetime], hours: int) -> bool:
        """Check if data is stale"""
        if not updated_at:
            return True
        return (datetime.utcnow() - updated_at).total_seconds() > hours * 3600

    async def get_cache_stats(self) -> Dict:
        """Get overall cache statistics"""
        if not self.db:
            return {}

        try:
            politician_count = await self.db.knowledge_cache.count_documents(
                {"entity_type": "politician"}
            )
            promise_count = await self.db.promises_cache.count_documents({})
            news_count = await self.db.news_cache.count_documents({})

            # Stale counts
            stale_cutoff = datetime.utcnow() - timedelta(hours=self.POLITICIAN_STALE_HOURS)
            stale_politicians = await self.db.knowledge_cache.count_documents({
                "entity_type": "politician",
                "updated_at": {"$lt": stale_cutoff}
            })

            return {
                "politicians": {
                    "total": politician_count,
                    "stale": stale_politicians,
                    "fresh": politician_count - stale_politicians
                },
                "promises": promise_count,
                "news": news_count,
                "cache_misses_24h": await self._count_recent_misses(24)
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    async def _count_recent_misses(self, hours: int) -> int:
        """Count cache misses in last N hours"""
        if not self.db:
            return 0

        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            return await self.db.cache_misses.count_documents({
                "created_at": {"$gte": cutoff}
            })
        except:
            return 0

    async def clear_stale_data(self, older_than_days: int = 30) -> Dict:
        """Clear very old cached data"""
        if not self.db:
            return {"error": "No database connection"}

        cutoff = datetime.utcnow() - timedelta(days=older_than_days)

        try:
            # Clear old news (keep recent)
            news_result = await self.db.news_cache.delete_many({
                "created_at": {"$lt": cutoff}
            })

            # Clear old cache misses
            misses_result = await self.db.cache_misses.delete_many({
                "created_at": {"$lt": cutoff}
            })

            return {
                "news_deleted": news_result.deleted_count,
                "cache_misses_deleted": misses_result.deleted_count,
                "cutoff_date": cutoff.isoformat()
            }

        except Exception as e:
            logger.error(f"Error clearing stale data: {e}")
            return {"error": str(e)}
