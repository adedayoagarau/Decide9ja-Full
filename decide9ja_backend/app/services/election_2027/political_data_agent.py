"""
Political Data Agent
====================

An automated agent that runs daily (or more frequently) to:
1. Collect news from Nigerian sources
2. Extract entities (politicians, parties, issues)
3. Analyze sentiment
4. Update candidate profiles
5. Detect trending topics
6. Store everything for Tade to use

Can be run as:
- Scheduled cron job
- Background task
- Manual trigger

Usage:
    python -m app.services.election_2027.political_data_agent
"""
import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import asyncio

logger = logging.getLogger(__name__)

# Nigerian news sources with political coverage
NEWS_SOURCES = {
    "punch": {
        "name": "Punch Nigeria",
        "rss": "https://punchng.com/feed/",
        "type": "rss",
        "bias": "center",
        "reliability": "high"
    },
    "premium_times": {
        "name": "Premium Times",
        "rss": "https://www.premiumtimesng.com/feed",
        "type": "rss",
        "bias": "center-left",
        "reliability": "high"
    },
    "vanguard": {
        "name": "Vanguard",
        "rss": "https://www.vanguardngr.com/feed/",
        "type": "rss",
        "bias": "center",
        "reliability": "high"
    },
    "dailypost": {
        "name": "Daily Post",
        "rss": "https://dailypost.ng/feed/",
        "type": "rss",
        "bias": "center",
        "reliability": "medium"
    },
    "thenation": {
        "name": "The Nation",
        "rss": "https://thenationonlineng.net/feed/",
        "type": "rss",
        "bias": "center-right",
        "reliability": "medium"
    },
    "guardian": {
        "name": "The Guardian Nigeria",
        "rss": "https://guardian.ng/feed/",
        "type": "rss",
        "bias": "center",
        "reliability": "high"
    },
    "thisday": {
        "name": "ThisDay",
        "rss": "https://www.thisdaylive.com/feed/",
        "type": "rss",
        "bias": "center",
        "reliability": "high"
    },
    "channels": {
        "name": "Channels TV",
        "rss": "https://www.channelstv.com/feed/",
        "type": "rss",
        "bias": "center",
        "reliability": "high"
    }
}

# Political keywords for filtering
POLITICAL_KEYWORDS = [
    # Positions
    "president", "governor", "senator", "minister", "speaker",
    "chairman", "commissioner", "lawmaker", "legislator",

    # Parties
    "apc", "pdp", "labour party", "nnpp", "apga", "sdp",
    "all progressives", "peoples democratic",

    # Institutions
    "inec", "national assembly", "senate", "house of rep",
    "state assembly", "court", "tribunal",

    # Election terms
    "election", "campaign", "primary", "nomination", "ballot",
    "vote", "polling", "candidate", "aspirant",

    # Policy areas
    "subsidy", "tax", "naira", "economy", "security", "education",
    "health", "infrastructure", "corruption", "efcc", "icpc",

    # Key figures (top politicians)
    "tinubu", "atiku", "obi", "kwankwaso", "wike", "fubara",
    "shettima", "akpabio", "gbajabiamila"
]

# Known politicians for entity extraction
KNOWN_POLITICIANS = {
    "tinubu": {"name": "Bola Tinubu", "party": "APC", "position": "President"},
    "atiku": {"name": "Atiku Abubakar", "party": "PDP", "position": "Opposition Leader"},
    "obi": {"name": "Peter Obi", "party": "LP", "position": "Opposition Leader"},
    "kwankwaso": {"name": "Rabiu Kwankwaso", "party": "NNPP", "position": "Opposition Leader"},
    "wike": {"name": "Nyesom Wike", "party": "APC-ally", "position": "FCT Minister"},
    "fubara": {"name": "Siminalayi Fubara", "party": "PDP", "position": "Rivers Governor"},
    "shettima": {"name": "Kashim Shettima", "party": "APC", "position": "Vice President"},
    "akpabio": {"name": "Godswill Akpabio", "party": "APC", "position": "Senate President"},
    # Add more as needed
}


@dataclass
class ProcessedNews:
    """A processed news item with analysis."""
    url: str
    url_hash: str
    source: str
    title: str
    content: str
    summary: str
    published_at: Optional[datetime]

    # Analysis
    is_political: bool
    entities: Dict  # {"politicians": [], "parties": [], "states": []}
    topics: List[str]
    sentiment: str
    sentiment_score: float
    mentioned_candidates: List[int]  # Candidate IDs


class PoliticalDataAgent:
    """
    The agent that collects and processes political news daily.

    Methods:
    - collect(): Gather news from all sources
    - process(): Analyze collected news
    - update_candidates(): Update candidate profiles based on news
    - compute_trends(): Calculate trending topics
    - run(): Execute full pipeline
    """

    def __init__(self, db_session=None):
        self.db = db_session
        self.sources = NEWS_SOURCES
        self.collected_items = []
        self.processed_items = []
        self.run_date = datetime.utcnow()

    async def collect(self, hours_back: int = 24) -> List[Dict]:
        """
        Collect news from all sources.

        Args:
            hours_back: How many hours of news to collect

        Returns:
            List of raw news items
        """
        logger.info(f"📰 Collecting news from {len(self.sources)} sources...")

        all_items = []
        cutoff = datetime.utcnow() - timedelta(hours=hours_back)

        for source_id, source_info in self.sources.items():
            try:
                items = await self._collect_from_source(source_id, source_info)
                all_items.extend(items)
                logger.info(f"  ✓ {source_info['name']}: {len(items)} items")
            except Exception as e:
                logger.error(f"  ✗ {source_info['name']}: {e}")

        self.collected_items = all_items
        logger.info(f"📰 Total collected: {len(all_items)} items")
        return all_items

    async def _collect_from_source(self, source_id: str, source_info: Dict) -> List[Dict]:
        """Collect from a single source."""
        import feedparser

        items = []

        if source_info["type"] == "rss":
            feed = feedparser.parse(source_info["rss"])

            for entry in feed.entries[:20]:  # Limit per source
                items.append({
                    "source": source_id,
                    "source_name": source_info["name"],
                    "url": entry.get("link", ""),
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                    "published_parsed": entry.get("published_parsed"),
                })

        return items

    def process(self, items: List[Dict] = None) -> List[ProcessedNews]:
        """
        Process collected news items.

        - Filter for political relevance
        - Extract entities
        - Classify topics
        - Analyze sentiment
        """
        items = items or self.collected_items

        logger.info(f"🔍 Processing {len(items)} items...")

        processed = []

        for item in items:
            try:
                result = self._process_item(item)
                if result and result.is_political:
                    processed.append(result)
            except Exception as e:
                logger.error(f"Error processing item: {e}")

        self.processed_items = processed
        logger.info(f"🔍 Processed: {len(processed)} political items")
        return processed

    def _process_item(self, item: Dict) -> Optional[ProcessedNews]:
        """Process a single news item."""
        title = item.get("title", "").lower()
        content = item.get("content", "").lower()
        full_text = f"{title} {content}"

        # Check political relevance
        is_political = any(kw in full_text for kw in POLITICAL_KEYWORDS)

        if not is_political:
            return None

        # Extract entities
        entities = self._extract_entities(full_text)

        # Classify topics
        topics = self._classify_topics(full_text)

        # Analyze sentiment
        sentiment, sentiment_score = self._analyze_sentiment(full_text)

        # Parse published date
        published_at = None
        if item.get("published_parsed"):
            try:
                published_at = datetime(*item["published_parsed"][:6])
            except:
                pass

        # Generate URL hash
        url_hash = hashlib.md5(item.get("url", "").encode()).hexdigest()

        return ProcessedNews(
            url=item.get("url", ""),
            url_hash=url_hash,
            source=item.get("source", ""),
            title=item.get("title", ""),
            content=item.get("content", ""),
            summary=item.get("content", "")[:300],  # Simple summary for now
            published_at=published_at,
            is_political=is_political,
            entities=entities,
            topics=topics,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            mentioned_candidates=[]
        )

    def _extract_entities(self, text: str) -> Dict:
        """Extract political entities from text."""
        entities = {
            "politicians": [],
            "parties": [],
            "states": [],
            "institutions": []
        }

        # Politicians
        for key, info in KNOWN_POLITICIANS.items():
            if key in text:
                entities["politicians"].append({
                    "name": info["name"],
                    "party": info["party"],
                    "keyword": key
                })

        # Parties
        party_keywords = {
            "apc": "APC",
            "all progressives": "APC",
            "pdp": "PDP",
            "peoples democratic": "PDP",
            "labour party": "LP",
            "nnpp": "NNPP"
        }
        for kw, party in party_keywords.items():
            if kw in text and party not in entities["parties"]:
                entities["parties"].append(party)

        # Nigerian states
        states = [
            "lagos", "kano", "rivers", "oyo", "kaduna", "enugu",
            "delta", "anambra", "imo", "ogun", "edo", "kwara"
        ]
        for state in states:
            if state in text:
                entities["states"].append(state.title())

        return entities

    def _classify_topics(self, text: str) -> List[str]:
        """Classify news into topics."""
        topics = []

        topic_keywords = {
            "economy": ["economy", "naira", "dollar", "inflation", "tax", "budget", "subsidy"],
            "security": ["security", "bandit", "terrorist", "kidnap", "military", "police"],
            "election": ["election", "vote", "inec", "ballot", "candidate", "primary"],
            "corruption": ["corruption", "efcc", "icpc", "fraud", "embezzle", "probe"],
            "education": ["education", "university", "asuu", "school", "student"],
            "health": ["health", "hospital", "doctor", "medicine", "disease"],
            "politics": ["governor", "senator", "minister", "president", "assembly"]
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in text for kw in keywords):
                topics.append(topic)

        return topics or ["general"]

    def _analyze_sentiment(self, text: str) -> Tuple[str, float]:
        """
        Simple sentiment analysis.
        For production, use Claude or a proper NLP model.
        """
        positive_words = [
            "success", "progress", "achieve", "improve", "growth",
            "praise", "commend", "excellent", "win", "victory",
            "development", "support", "approve", "celebrate"
        ]

        negative_words = [
            "fail", "crisis", "corrupt", "scandal", "problem",
            "attack", "condemn", "reject", "oppose", "worse",
            "suffering", "hardship", "criticize", "protest", "fraud"
        ]

        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)

        total = pos_count + neg_count
        if total == 0:
            return "neutral", 0.0

        score = (pos_count - neg_count) / total

        if score > 0.2:
            return "positive", score
        elif score < -0.2:
            return "negative", score
        else:
            return "neutral", score

    async def update_candidates(self):
        """
        Update candidate profiles based on processed news.
        - Update mention counts
        - Update sentiment scores
        - Add latest news
        """
        logger.info("👤 Updating candidate profiles...")

        # This would update the database
        # For now, we'll prepare the updates

        candidate_updates = {}

        for item in self.processed_items:
            for politician in item.entities.get("politicians", []):
                name = politician["name"]
                if name not in candidate_updates:
                    candidate_updates[name] = {
                        "mention_count": 0,
                        "sentiment_scores": [],
                        "latest_news": []
                    }

                candidate_updates[name]["mention_count"] += 1
                candidate_updates[name]["sentiment_scores"].append(item.sentiment_score)
                candidate_updates[name]["latest_news"].append({
                    "title": item.title[:100],
                    "source": item.source,
                    "sentiment": item.sentiment,
                    "date": item.published_at.isoformat() if item.published_at else None
                })

        logger.info(f"👤 Updates prepared for {len(candidate_updates)} candidates")
        return candidate_updates

    def compute_trends(self) -> List[Dict]:
        """
        Compute trending topics from processed news.
        """
        logger.info("📈 Computing trends...")

        topic_counts = {}
        entity_counts = {}

        for item in self.processed_items:
            # Count topics
            for topic in item.topics:
                if topic not in topic_counts:
                    topic_counts[topic] = {"count": 0, "headlines": [], "sentiment": []}
                topic_counts[topic]["count"] += 1
                topic_counts[topic]["headlines"].append(item.title[:80])
                topic_counts[topic]["sentiment"].append(item.sentiment_score)

            # Count entities
            for pol in item.entities.get("politicians", []):
                name = pol["name"]
                if name not in entity_counts:
                    entity_counts[name] = {"count": 0, "sentiment": []}
                entity_counts[name]["count"] += 1
                entity_counts[name]["sentiment"].append(item.sentiment_score)

        # Build trending list
        trends = []

        for topic, data in sorted(topic_counts.items(), key=lambda x: x[1]["count"], reverse=True):
            avg_sentiment = sum(data["sentiment"]) / len(data["sentiment"]) if data["sentiment"] else 0
            trends.append({
                "type": "topic",
                "name": topic,
                "count": data["count"],
                "sentiment_score": avg_sentiment,
                "sample_headlines": data["headlines"][:3]
            })

        for entity, data in sorted(entity_counts.items(), key=lambda x: x[1]["count"], reverse=True):
            avg_sentiment = sum(data["sentiment"]) / len(data["sentiment"]) if data["sentiment"] else 0
            trends.append({
                "type": "politician",
                "name": entity,
                "count": data["count"],
                "sentiment_score": avg_sentiment
            })

        logger.info(f"📈 Computed {len(trends)} trends")
        return trends

    async def run(self) -> Dict:
        """
        Execute the full pipeline.

        Returns:
            Summary of the run
        """
        start_time = datetime.utcnow()
        logger.info("=" * 50)
        logger.info("🚀 POLITICAL DATA AGENT - Starting run")
        logger.info(f"   Time: {start_time}")
        logger.info("=" * 50)

        # Step 1: Collect
        collected = await self.collect(hours_back=24)

        # Step 2: Process
        processed = self.process()

        # Step 3: Update candidates
        candidate_updates = await self.update_candidates()

        # Step 4: Compute trends
        trends = self.compute_trends()

        end_time = datetime.utcnow()
        duration = (end_time - start_time).seconds

        summary = {
            "run_date": start_time.isoformat(),
            "duration_seconds": duration,
            "items_collected": len(collected),
            "items_processed": len(processed),
            "candidates_updated": len(candidate_updates),
            "trends_computed": len(trends),
            "top_trends": trends[:5]
        }

        logger.info("=" * 50)
        logger.info("✅ POLITICAL DATA AGENT - Run complete")
        logger.info(f"   Duration: {duration}s")
        logger.info(f"   Collected: {len(collected)}")
        logger.info(f"   Processed: {len(processed)}")
        logger.info("=" * 50)

        return summary

    def get_latest_summary(self) -> str:
        """
        Get a human-readable summary for Tade.
        """
        if not self.processed_items:
            return "No recent news collected."

        summary = f"📰 *Latest Political News Summary*\n"
        summary += f"(Based on {len(self.processed_items)} articles from today)\n\n"

        # Top stories by topic
        by_topic = {}
        for item in self.processed_items[:20]:
            for topic in item.topics:
                if topic not in by_topic:
                    by_topic[topic] = []
                by_topic[topic].append(item)

        for topic, items in list(by_topic.items())[:3]:
            summary += f"*{topic.title()}*:\n"
            for item in items[:2]:
                emoji = "🟢" if item.sentiment == "positive" else "🔴" if item.sentiment == "negative" else "⚪"
                summary += f"{emoji} {item.title[:60]}...\n"
            summary += "\n"

        return summary


# === CONVENIENCE FUNCTIONS ===

_agent_instance = None

def get_agent() -> PoliticalDataAgent:
    """Get or create agent singleton."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = PoliticalDataAgent()
    return _agent_instance


async def run_daily_collection() -> Dict:
    """Run the daily collection pipeline."""
    agent = get_agent()
    return await agent.run()


def get_news_summary() -> str:
    """Get latest news summary for Tade."""
    agent = get_agent()
    return agent.get_latest_summary()


# === MAIN ===

if __name__ == "__main__":
    # Run the agent
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_daily_collection())
