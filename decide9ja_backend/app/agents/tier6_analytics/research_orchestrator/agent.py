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
from app.agents.registry import register_agent, registry

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
        "education", "healthcare", "security", "economy",
        "infrastructure", "agriculture", "corruption", "youth",
        "technology", "fuel subsidy", "naira", "electricity",
    ]

    # Cache staleness thresholds (in hours)
    FULL_PROFILE_STALE_HOURS = 48
    NEWS_STALE_HOURS = 6
    PROMISES_STALE_HOURS = 168  # 1 week

    async def can_handle(self, input: AgentInput) -> bool:
        return False  # Background agent, not user-facing

    async def handle(self, input: AgentInput) -> AgentOutput:
        """Not used - this agent is called directly via get_next_research_tasks()"""
        return AgentOutput(success=False, error="ResearchOrchestrator is a background agent")

    async def get_next_research_tasks(self) -> List[Dict]:
        """
        Determine what needs researching based on cache staleness and user demand.

        Returns prioritized list of research tasks:
        - Priority 1: Never researched (full_profile)
        - Priority 2: Stale data (refresh)
        """
        tasks = []

        # Get the knowledge cache agent
        cache = registry.get("knowledge_cache")
        if not cache:
            logger.warning("KnowledgeCacheAgent not available for research orchestration")
            return tasks

        # Check priority politicians
        for politician in self.PRIORITY_LIST:
            cache_entry = await cache.get_politician(politician)

            if not cache_entry:
                # Never researched - highest priority
                tasks.append({
                    "type": "full_profile",
                    "entity": politician,
                    "entity_type": "politician",
                    "priority": 1,
                    "reason": "never_researched"
                })
            elif cache_entry.get("is_stale"):
                # Stale data - needs refresh
                tasks.append({
                    "type": "refresh",
                    "entity": politician,
                    "entity_type": "politician",
                    "priority": 2,
                    "reason": "stale_data",
                    "last_updated": cache_entry.get("updated_at")
                })

        # Sort by priority
        tasks = sorted(tasks, key=lambda x: x["priority"])

        logger.info(f"Research orchestrator: {len(tasks)} tasks queued")
        return tasks

    async def get_research_stats(self) -> Dict:
        """Get statistics about research coverage."""
        cache = registry.get("knowledge_cache")
        if not cache:
            return {}

        try:
            total_politicians = len(self.PRIORITY_LIST)
            stats = await cache.get_cache_stats()

            cached_count = stats.get("politicians", 0)

            return {
                "priority_politicians": total_politicians,
                "cached_politicians": cached_count,
                "news_articles": stats.get("news_articles", 0),
                "voting_records": stats.get("voting_records", 0),
                "coverage_percent": round(
                    (cached_count / total_politicians) * 100, 1
                ) if total_politicians > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting research stats: {e}")
            return {}
