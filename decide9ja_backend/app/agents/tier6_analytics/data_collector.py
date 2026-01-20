"""
DataCollectorAgent
==================
Passive data collection for B2B analytics.
Runs AFTER every response to tag and store interaction data.

This is how we build the campaign intelligence product.
Every user interaction = free market research.

Cost: FREE (just stores data)
"""

from datetime import datetime
from typing import Dict, List
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
class DataCollectorAgent(BaseAgent):
    name = "data_collector"
    description = "Passive analytics collection for B2B"
    tier = AgentTier.ANALYTICS
    cost_level = CostLevel.FREE
    handled_intents = []  # Doesn't handle intents - called after response

    # Topic keywords for classification
    TOPIC_KEYWORDS = {
        "education": ["school", "education", "university", "student", "teacher", "exam", "jamb", "waec"],
        "health": ["hospital", "health", "doctor", "medicine", "clinic", "disease", "covid"],
        "security": ["security", "police", "crime", "kidnap", "bandit", "terrorist", "army"],
        "economy": ["economy", "job", "employment", "salary", "price", "naira", "dollar", "inflation"],
        "infrastructure": ["road", "electricity", "water", "bridge", "nepa", "phcn", "light"],
        "corruption": ["corrupt", "steal", "embezzle", "fraud", "efcc", "icpc"],
        "election": ["election", "vote", "inec", "pvc", "ballot", "campaign", "candidate"],
        "governance": ["government", "minister", "policy", "budget", "law", "bill", "senate"],
    }

    # Sentiment keywords
    POSITIVE_WORDS = [
        "good", "great", "excellent", "thank", "happy", "love", "best",
        "wonderful", "amazing", "helpful", "appreciate", "well done"
    ]
    NEGATIVE_WORDS = [
        "bad", "terrible", "worst", "hate", "angry", "useless", "corrupt",
        "failed", "poor", "disappointed", "frustrated", "shame"
    ]

    async def can_handle(self, input: AgentInput) -> bool:
        return False  # Never directly handles - called by orchestrator

    async def handle(self, input: AgentInput) -> AgentOutput:
        # Not used directly - use collect() instead
        return AgentOutput(success=False, error="Use collect() method instead")

    async def collect(self, input: AgentInput, output: AgentOutput):
        """
        Collect anonymized interaction data.
        Called after every successful response.
        """
        if not self.db:
            logger.debug("No database configured for analytics")
            return

        try:
            # Build analytics record
            record = {
                "timestamp": datetime.utcnow(),

                # Location (anonymized, for regional aggregation)
                "state": input.user.state,
                "lga": input.user.lga,

                # Intent & classification
                "intent": input.intent,
                "confidence": input.confidence,
                "entities": input.entities,

                # Query characteristics
                "query_length": len(input.raw_text) if input.raw_text else 0,
                "has_media": bool(input.image_urls or input.voice_url or input.video_url),
                "language": input.user.language,

                # Response characteristics
                "response_success": output.success,
                "response_cached": output.cached,
                "cost_level": output.cost_level.value if hasattr(output.cost_level, 'value') else output.cost_level,

                # Analytics tags from specialist agents
                "agent_tags": output.analytics_tags,

                # Extracted insights
                "politicians_mentioned": self._extract_politicians(input, output),
                "topics": self._extract_topics(input.raw_text),
                "sentiment": self._estimate_sentiment(input.raw_text),

                # Session info
                "session_id": input.session_id,
                "conversation_turn": input.conversation_turn,
            }

            # Store in analytics collection
            await self._store_record(record)

            # Update aggregate counters
            await self._update_counters(record)

        except Exception as e:
            logger.error(f"Analytics collection failed: {e}")

    def _extract_politicians(self, input: AgentInput, output: AgentOutput) -> List[str]:
        """Extract mentioned politicians for tracking"""
        politicians = set()

        # From entities
        if input.entities.get("politician"):
            politicians.add(input.entities["politician"])
        if input.entities.get("potential_names"):
            politicians.update(input.entities["potential_names"])

        # From analytics tags
        if output.analytics_tags.get("politician_mentioned"):
            politicians.add(output.analytics_tags["politician_mentioned"])

        # Check for known politicians in text
        text_lower = (input.raw_text or "").lower()
        known_politicians = [
            "tinubu", "atiku", "obi", "buhari", "jonathan",
            "sanwo-olu", "wike", "fubara", "el-rufai",
            "shettima", "okowa", "kwankwaso", "lawan"
        ]
        for name in known_politicians:
            if name in text_lower:
                politicians.add(name)

        return list(politicians)

    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text for trend analysis"""
        if not text:
            return []

        text_lower = text.lower()
        topics = []

        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)

        return topics

    def _estimate_sentiment(self, text: str) -> str:
        """Simple sentiment estimation (no LLM needed)"""
        if not text:
            return "neutral"

        text_lower = text.lower()

        pos_count = sum(1 for word in self.POSITIVE_WORDS if word in text_lower)
        neg_count = sum(1 for word in self.NEGATIVE_WORDS if word in text_lower)

        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        else:
            return "neutral"

    async def _store_record(self, record: Dict):
        """Store analytics record in database"""
        # Adapt to your database
        # For MongoDB:
        # await self.db.analytics.insert_one(record)

        # For SQLAlchemy:
        # analytics = AnalyticsRecord(**record)
        # self.db.add(analytics)
        # await self.db.commit()

        logger.debug(f"Analytics recorded: {record.get('intent')} - {record.get('state')}")

    async def _update_counters(self, record: Dict):
        """Update real-time counters for dashboards"""
        if not self.db:
            return

        today = record["timestamp"].strftime("%Y-%m-%d")

        try:
            # Adapt to your database
            # For MongoDB:
            # await self.db.counters.update_one(
            #     {"date": today, "state": record["state"]},
            #     {
            #         "$inc": {
            #             "total_queries": 1,
            #             f"intents.{record['intent']}": 1,
            #         }
            #     },
            #     upsert=True
            # )

            # Track politician mentions
            for politician in record.get("politicians_mentioned", []):
                # await self.db.politician_mentions.update_one(...)
                pass

        except Exception as e:
            logger.error(f"Counter update failed: {e}")

    def get_stats(self) -> Dict:
        """Get collection statistics"""
        return {
            "name": self.name,
            "calls": self._call_count,
            "cost_level": "FREE"
        }
