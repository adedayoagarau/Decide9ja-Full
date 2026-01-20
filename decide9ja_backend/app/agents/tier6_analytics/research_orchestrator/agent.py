"""
ResearchOrchestratorAgent
=========================
Decides what to research next based on:
1. Priority politician list (2027 candidates, key legislators)
2. Cache staleness (data older than 48 hours)
3. User query patterns (cache misses = demand signal)

Runs every 6 hours via background job.
Cost: FREE (just database queries)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class ResearchOrchestratorAgent(BaseAgent):
    """Decides what to research and schedules research tasks"""

    name = "research_orchestrator"
    description = "Orchestrates autonomous research to build knowledge cache"
    tier = AgentTier.ANALYTICS
    cost_level = CostLevel.FREE
    handled_intents = []  # Background agent, not user-facing

    # Priority politicians (2027 candidates + key legislators)
    PRIORITY_LIST = [
        # Presidential candidates
        "Bola Ahmed Tinubu",
        "Atiku Abubakar",
        "Peter Obi",
        "Rabiu Kwankwaso",
        # Vice President & Key Cabinet
        "Kashim Shettima",
        "Wale Edun",
        "Nyesom Wike",
        # Senate Leadership
        "Godswill Akpabio",
        "Barau Jibrin",
        "Opeyemi Bamidele",
        # House Leadership
        "Tajudeen Abbas",
        "Benjamin Kalu",
        # Key Governors
        "Babajide Sanwo-Olu",
        "Ademola Adeleke",
        "Peter Mbah",
        "Siminalayi Fubara",
        "Dapo Abiodun",
        "Seyi Makinde",
        "Hope Uzodinma",
        "Charles Soludo",
        "Nasir El-Rufai",
        "Abdullahi Ganduje",
        # Former candidates / Key figures
        "Yemi Osinbajo",
        "Rotimi Amaechi",
        "Bukola Saraki",
        "Dino Melaye",
        # APC Leadership
        "Abdullahi Ganduje",
        # PDP Leadership
        "Umar Damagum",
        # LP Leadership
        "Julius Abure",
    ]

    # Research topics for trend tracking
    TOPICS = [
        "education",
        "healthcare",
        "security",
        "economy",
        "infrastructure",
        "agriculture",
        "corruption",
        "youth",
        "technology",
        "fuel subsidy",
        "naira",
        "electricity",
    ]

    # Cache staleness thresholds (in hours)
    FULL_PROFILE_STALE_HOURS = 48
    NEWS_STALE_HOURS = 6
    PROMISES_STALE_HOURS = 168  # 1 week

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def can_handle(self, input: AgentInput) -> bool:
        return False  # Background agent, not user-facing

    async def handle(self, input: AgentInput) -> AgentOutput:
        """Not used - this agent is called directly via get_next_research_tasks()"""
        return self.fail("ResearchOrchestrator is a background agent", "NOT_USER_FACING")

    async def get_next_research_tasks(self) -> List[Dict]:
        """
        Determine what needs researching based on cache staleness and user demand.

        Returns prioritized list of research tasks:
        - Priority 1: Never researched (full_profile)
        - Priority 2: Stale data (refresh)
        - Priority 3: User demand (trending queries with cache misses)
        """
        tasks = []

        # 1. Check priority politicians
        for politician in self.PRIORITY_LIST:
            cache_entry = await self._get_cache_status(politician)

            if not cache_entry:
                # Never researched - highest priority
                tasks.append({
                    "type": "full_profile",
                    "entity": politician,
                    "entity_type": "politician",
                    "priority": 1,
                    "reason": "never_researched"
                })
            elif self._is_stale(cache_entry.get("updated_at"), self.FULL_PROFILE_STALE_HOURS):
                # Stale data - needs refresh
                tasks.append({
                    "type": "refresh",
                    "entity": politician,
                    "entity_type": "politician",
                    "priority": 2,
                    "reason": "stale_data",
                    "last_updated": cache_entry.get("updated_at")
                })

        # 2. Check trending topics from user queries (cache misses = demand signal)
        trending = await self._get_trending_queries()
        for topic in trending:
            tasks.append({
                "type": "topic_research",
                "entity": topic["intent_topic"],
                "entity_type": "topic",
                "priority": 3,
                "reason": "user_demand",
                "query_count": topic["count"]
            })

        # 3. Check for specific politician mentions in cache misses
        politician_mentions = await self._get_politician_cache_misses()
        for mention in politician_mentions:
            if mention["politician_name"] not in [t["entity"] for t in tasks]:
                tasks.append({
                    "type": "full_profile",
                    "entity": mention["politician_name"],
                    "entity_type": "politician",
                    "priority": 2,
                    "reason": "user_requested",
                    "query_count": mention["count"]
                })

        # Sort by priority
        tasks = sorted(tasks, key=lambda x: (x["priority"], -x.get("query_count", 0)))

        logger.info(f"Research orchestrator: {len(tasks)} tasks queued")
        return tasks

    async def _get_cache_status(self, entity_name: str) -> Optional[Dict]:
        """Get cache status for an entity"""
        if not self.db:
            return None

        try:
            result = await self.db.knowledge_cache.find_one({
                "entity_type": "politician",
                "entity_name": {"$regex": entity_name, "$options": "i"}
            })
            return result
        except Exception as e:
            logger.error(f"Error checking cache for {entity_name}: {e}")
            return None

    async def _get_trending_queries(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """Get topics users are asking about that had cache misses"""
        if not self.db:
            return []

        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            pipeline = [
                {"$match": {"created_at": {"$gte": cutoff}}},
                {"$group": {
                    "_id": "$intent_topic",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": limit},
                {"$project": {
                    "_id": 0,
                    "intent_topic": "$_id",
                    "count": 1
                }}
            ]

            results = await self.db.cache_misses.aggregate(pipeline).to_list(limit)
            return results
        except Exception as e:
            logger.error(f"Error getting trending queries: {e}")
            return []

    async def _get_politician_cache_misses(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """Get specific politicians users asked about with no cache data"""
        if not self.db:
            return []

        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            pipeline = [
                {"$match": {
                    "created_at": {"$gte": cutoff},
                    "intent_topic": "politician_info"
                }},
                {"$group": {
                    "_id": "$query_entity",
                    "count": {"$sum": 1}
                }},
                {"$match": {"_id": {"$ne": None}}},
                {"$sort": {"count": -1}},
                {"$limit": limit},
                {"$project": {
                    "_id": 0,
                    "politician_name": "$_id",
                    "count": 1
                }}
            ]

            results = await self.db.cache_misses.aggregate(pipeline).to_list(limit)
            return results
        except Exception as e:
            logger.error(f"Error getting politician cache misses: {e}")
            return []

    def _is_stale(self, updated_at: Optional[datetime], hours: int) -> bool:
        """Check if data is stale based on threshold"""
        if not updated_at:
            return True
        return (datetime.utcnow() - updated_at).total_seconds() > hours * 3600

    async def get_research_stats(self) -> Dict:
        """Get statistics about research coverage"""
        if not self.db:
            return {}

        try:
            total_politicians = len(self.PRIORITY_LIST)

            # Count cached politicians
            cached_count = await self.db.knowledge_cache.count_documents({
                "entity_type": "politician"
            })

            # Count stale entries
            stale_cutoff = datetime.utcnow() - timedelta(hours=self.FULL_PROFILE_STALE_HOURS)
            stale_count = await self.db.knowledge_cache.count_documents({
                "entity_type": "politician",
                "updated_at": {"$lt": stale_cutoff}
            })

            # Count promises
            promise_count = await self.db.promises_cache.count_documents({})

            # Recent cache misses
            miss_cutoff = datetime.utcnow() - timedelta(hours=24)
            miss_count = await self.db.cache_misses.count_documents({
                "created_at": {"$gte": miss_cutoff}
            })

            return {
                "priority_politicians": total_politicians,
                "cached_politicians": cached_count,
                "stale_entries": stale_count,
                "fresh_entries": cached_count - stale_count,
                "total_promises": promise_count,
                "cache_misses_24h": miss_count,
                "coverage_percent": round((cached_count / total_politicians) * 100, 1) if total_politicians > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting research stats: {e}")
            return {}
