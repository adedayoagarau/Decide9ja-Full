#!/usr/bin/env python3
"""
Advanced Knowledge Graph Features

Implements:
1. Predictive Analysis - Patterns and trends prediction
2. News Caching - Hourly news fetch and graph updates
3. Graph Complexity - Deeper relationship analysis
4. Data Categorization - Enhanced tagging and schema
5. Auto-Updates - Keep knowledge fresh

Run: python scripts/advanced_knowledge_features.py
"""

import json
import logging
import re
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import statistics

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent / "nigeria_knowledge_data"
ENHANCED_DIR = BASE_DIR / "enhanced"
PREDICTIONS_DIR = BASE_DIR / "predictions"
NEWS_CACHE_DIR = BASE_DIR / "news_cache"

PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
NEWS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ===========================================
# DATA CLASSES
# ===========================================

@dataclass
class EconomicTrend:
    """Economic trend analysis"""
    indicator: str
    direction: str  # "up", "down", "stable"
    change_percent: float
    start_year: int
    end_year: int
    data_points: List[Dict] = field(default_factory=list)
    prediction_next_year: Optional[float] = None
    confidence: float = 0.0


@dataclass
class PoliticalPattern:
    """Political pattern detection"""
    pattern_type: str  # "succession", "party_dominance", "regional_voting"
    description: str
    entities_involved: List[str] = field(default_factory=list)
    time_period: str = ""
    strength: float = 0.0  # 0-1


@dataclass
class EntityCategory:
    """Enhanced entity categorization"""
    entity_id: str
    primary_category: str
    secondary_categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    importance_score: float = 0.0
    last_updated: str = ""


# ===========================================
# PREDICTIVE ANALYSIS
# ===========================================

class PredictiveAnalyzer:
    """Analyzes patterns and makes predictions"""

    def __init__(self, economic_data: List[Dict], entities: Dict, relationships: List[Dict]):
        self.economic_data = economic_data
        self.entities = entities
        self.relationships = relationships
        self.trends: List[EconomicTrend] = []
        self.patterns: List[PoliticalPattern] = []

    def analyze_economic_trends(self) -> List[EconomicTrend]:
        """Analyze economic data for trends and predictions"""
        logger.info("Analyzing economic trends...")

        # Group data by indicator
        by_indicator = defaultdict(list)
        for dp in self.economic_data:
            indicator = dp.get("indicator", "")
            if indicator:
                by_indicator[indicator].append(dp)

        trends = []
        for indicator, data_points in by_indicator.items():
            # Sort by year
            sorted_data = sorted(data_points, key=lambda x: x.get("year", 0))
            if len(sorted_data) < 3:
                continue

            # Get values
            values = []
            years = []
            for dp in sorted_data:
                val = dp.get("value")
                year = dp.get("year")
                if val is not None and year:
                    try:
                        values.append(float(val))
                        years.append(int(year))
                    except (ValueError, TypeError):
                        continue

            if len(values) < 3:
                continue

            # Calculate trend
            first_val = values[0]
            last_val = values[-1]

            if first_val != 0:
                change_percent = ((last_val - first_val) / abs(first_val)) * 100
            else:
                change_percent = 0

            # Determine direction
            if change_percent > 5:
                direction = "up"
            elif change_percent < -5:
                direction = "down"
            else:
                direction = "stable"

            # Simple linear prediction for next year
            if len(values) >= 3:
                recent_changes = [values[i] - values[i-1] for i in range(1, len(values))]
                avg_change = statistics.mean(recent_changes[-3:]) if len(recent_changes) >= 3 else statistics.mean(recent_changes)
                prediction = last_val + avg_change

                # Calculate confidence based on variance
                if len(recent_changes) > 1:
                    variance = statistics.variance(recent_changes) if len(recent_changes) > 1 else 0
                    confidence = max(0.1, min(0.9, 1 - (variance / (abs(avg_change) + 1))))
                else:
                    confidence = 0.5
            else:
                prediction = None
                confidence = 0.0

            trend = EconomicTrend(
                indicator=indicator,
                direction=direction,
                change_percent=round(change_percent, 2),
                start_year=min(years),
                end_year=max(years),
                data_points=sorted_data,
                prediction_next_year=round(prediction, 2) if prediction else None,
                confidence=round(confidence, 2)
            )
            trends.append(trend)

        self.trends = trends
        logger.info(f"  Analyzed {len(trends)} economic trends")
        return trends

    def detect_political_patterns(self) -> List[PoliticalPattern]:
        """Detect political patterns from entities and relationships"""
        logger.info("Detecting political patterns...")

        patterns = []

        # Pattern 1: Party Dominance
        party_counts = defaultdict(int)
        for entity in self.entities.values():
            party = entity.get("party") or entity.get("partyLabel")
            if party:
                party_counts[party] += 1

        if party_counts:
            dominant_party = max(party_counts, key=party_counts.get)
            total = sum(party_counts.values())
            dominance = party_counts[dominant_party] / total if total > 0 else 0

            if dominance > 0.3:
                patterns.append(PoliticalPattern(
                    pattern_type="party_dominance",
                    description=f"{dominant_party} dominates with {dominance*100:.1f}% of politicians",
                    entities_involved=[dominant_party],
                    strength=dominance
                ))

        # Pattern 2: Regional Political Distribution
        zone_parties = defaultdict(lambda: defaultdict(int))
        for entity in self.entities.values():
            zone = entity.get("geopolitical_zone", "")
            party = entity.get("party") or entity.get("partyLabel")
            if zone and party:
                zone_parties[zone][party] += 1

        for zone, parties in zone_parties.items():
            if parties:
                dominant = max(parties, key=parties.get)
                total = sum(parties.values())
                dominance = parties[dominant] / total if total > 0 else 0

                if dominance > 0.5:
                    patterns.append(PoliticalPattern(
                        pattern_type="regional_voting",
                        description=f"{zone} strongly favors {dominant} ({dominance*100:.1f}%)",
                        entities_involved=[zone, dominant],
                        strength=dominance
                    ))

        # Pattern 3: Succession Patterns
        succession_count = sum(1 for r in self.relationships if r.get("type") == "succeeded")
        if succession_count > 5:
            patterns.append(PoliticalPattern(
                pattern_type="succession",
                description=f"Tracked {succession_count} leadership transitions",
                strength=min(1.0, succession_count / 20)
            ))

        # Pattern 4: Military-Civilian Alternation
        leaders = [e for e in self.entities.values() if e.get("type") == "person_leader"]
        military_civilian_switches = 0
        prev_type = None
        for leader in sorted(leaders, key=lambda x: x.get("start_date", "") or ""):
            pos = leader.get("position", "").lower()
            is_military = "military" in pos
            if prev_type is not None and prev_type != is_military:
                military_civilian_switches += 1
            prev_type = is_military

        if military_civilian_switches > 3:
            patterns.append(PoliticalPattern(
                pattern_type="governance_alternation",
                description=f"Nigeria has alternated between military and civilian rule {military_civilian_switches} times",
                strength=min(1.0, military_civilian_switches / 10)
            ))

        self.patterns = patterns
        logger.info(f"  Detected {len(patterns)} political patterns")
        return patterns

    def generate_predictions(self) -> Dict[str, Any]:
        """Generate predictions based on analyzed data"""
        logger.info("Generating predictions...")

        predictions = {
            "generated_at": datetime.now().isoformat(),
            "economic_predictions": [],
            "political_insights": [],
            "confidence_scores": {}
        }

        # Economic predictions
        for trend in self.trends:
            if trend.prediction_next_year and trend.confidence > 0.3:
                predictions["economic_predictions"].append({
                    "indicator": trend.indicator,
                    "current_value": trend.data_points[-1].get("value") if trend.data_points else None,
                    "current_year": trend.end_year,
                    "predicted_value": trend.prediction_next_year,
                    "predicted_year": trend.end_year + 1,
                    "direction": trend.direction,
                    "confidence": trend.confidence,
                    "trend_period": f"{trend.start_year}-{trend.end_year}"
                })

        # Political insights
        for pattern in self.patterns:
            predictions["political_insights"].append({
                "type": pattern.pattern_type,
                "insight": pattern.description,
                "strength": pattern.strength,
                "entities": pattern.entities_involved
            })

        # Overall confidence
        if self.trends:
            predictions["confidence_scores"]["economic"] = round(
                statistics.mean(t.confidence for t in self.trends if t.confidence > 0), 2
            )
        if self.patterns:
            predictions["confidence_scores"]["political"] = round(
                statistics.mean(p.strength for p in self.patterns), 2
            )

        return predictions


# ===========================================
# NEWS CACHING SYSTEM
# ===========================================

class NewsCacheManager:
    """Manages hourly news caching and knowledge graph updates"""

    # Nigerian news RSS feeds
    RSS_FEEDS = {
        "punch": "https://punchng.com/feed/",
        "premium_times": "https://www.premiumtimesng.com/feed",
        "channels": "https://www.channelstv.com/feed/",
        "vanguard": "https://www.vanguardngr.com/feed/",
        "thisday": "https://www.thisdaylive.com/index.php/feed/",
        "guardian": "https://guardian.ng/feed/",
        "daily_trust": "https://dailytrust.com/feed/",
        "leadership": "https://leadership.ng/feed/",
    }

    def __init__(self):
        self.cache_file = NEWS_CACHE_DIR / "news_cache.json"
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load existing cache"""
        if self.cache_file.exists():
            with open(self.cache_file, encoding="utf-8") as f:
                return json.load(f)
        return {"articles": [], "last_updated": None, "stats": {}}

    def _save_cache(self):
        """Save cache to disk"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False, default=str)

    def _hash_article(self, title: str, link: str) -> str:
        """Generate unique hash for article"""
        content = f"{title}:{link}"
        return hashlib.md5(content.encode()).hexdigest()

    def fetch_news(self) -> List[Dict]:
        """Fetch news from all RSS feeds"""
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed. Run: pip install feedparser")
            return []

        logger.info("Fetching news from RSS feeds...")
        new_articles = []
        existing_hashes = {a.get("hash") for a in self.cache.get("articles", [])}

        for source, url in self.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:20]:  # Limit per source
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    article_hash = self._hash_article(title, link)

                    if article_hash not in existing_hashes:
                        article = {
                            "hash": article_hash,
                            "title": title,
                            "link": link,
                            "summary": entry.get("summary", "")[:500],
                            "published": entry.get("published", ""),
                            "source": source,
                            "fetched_at": datetime.now().isoformat(),
                            "categories": self._extract_categories(title, entry.get("summary", "")),
                            "entities_mentioned": self._extract_entities(title + " " + entry.get("summary", ""))
                        }
                        new_articles.append(article)
                        existing_hashes.add(article_hash)

                logger.info(f"  Fetched from {source}: {len(feed.entries)} entries")
            except Exception as e:
                logger.warning(f"  Failed to fetch from {source}: {e}")

        logger.info(f"  Total new articles: {len(new_articles)}")
        return new_articles

    def _extract_categories(self, title: str, summary: str) -> List[str]:
        """Extract article categories based on content"""
        text = (title + " " + summary).lower()
        categories = []

        category_keywords = {
            "politics": ["president", "governor", "senator", "election", "party", "apc", "pdp", "vote"],
            "economy": ["naira", "inflation", "gdp", "budget", "economy", "cbn", "dollar", "oil"],
            "security": ["army", "police", "bandits", "terrorism", "kidnap", "military", "boko haram"],
            "education": ["university", "school", "asuu", "student", "education", "exam"],
            "health": ["hospital", "doctor", "health", "disease", "covid", "vaccine"],
            "infrastructure": ["road", "power", "electricity", "water", "transport"],
        }

        for category, keywords in category_keywords.items():
            if any(kw in text for kw in keywords):
                categories.append(category)

        return categories or ["general"]

    def _extract_entities(self, text: str) -> List[str]:
        """Extract entity mentions from text"""
        entities = []

        # Nigerian politicians and figures
        known_entities = [
            "Tinubu", "Buhari", "Obasanjo", "Jonathan", "Atiku", "Obi",
            "Akpabio", "Wike", "El-Rufai", "Sanwo-Olu", "Shettima"
        ]

        # States
        states = [
            "Lagos", "Kano", "Rivers", "Oyo", "Kaduna", "Delta", "Edo",
            "FCT", "Abuja", "Enugu", "Anambra", "Imo"
        ]

        for entity in known_entities + states:
            if entity.lower() in text.lower():
                entities.append(entity)

        return entities

    def update_cache(self, new_articles: List[Dict]):
        """Update cache with new articles"""
        # Add new articles
        self.cache["articles"] = new_articles + self.cache.get("articles", [])

        # Keep only last 7 days of articles
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        self.cache["articles"] = [
            a for a in self.cache["articles"]
            if a.get("fetched_at", "") > cutoff
        ]

        # Update stats
        self.cache["last_updated"] = datetime.now().isoformat()
        self.cache["stats"] = {
            "total_articles": len(self.cache["articles"]),
            "by_source": defaultdict(int),
            "by_category": defaultdict(int)
        }

        for article in self.cache["articles"]:
            self.cache["stats"]["by_source"][article.get("source", "unknown")] += 1
            for cat in article.get("categories", []):
                self.cache["stats"]["by_category"][cat] += 1

        # Convert defaultdicts to regular dicts
        self.cache["stats"]["by_source"] = dict(self.cache["stats"]["by_source"])
        self.cache["stats"]["by_category"] = dict(self.cache["stats"]["by_category"])

        self._save_cache()
        logger.info(f"Cache updated: {len(self.cache['articles'])} total articles")

    def get_recent_news(self, category: str = None, limit: int = 10) -> List[Dict]:
        """Get recent news articles"""
        articles = self.cache.get("articles", [])

        if category:
            articles = [a for a in articles if category in a.get("categories", [])]

        return articles[:limit]

    def get_trending_topics(self, limit: int = 10) -> List[Dict]:
        """Get trending topics from recent news"""
        entity_counts = defaultdict(int)
        category_counts = defaultdict(int)

        for article in self.cache.get("articles", [])[:100]:
            for entity in article.get("entities_mentioned", []):
                entity_counts[entity] += 1
            for cat in article.get("categories", []):
                category_counts[cat] += 1

        trending = []
        for entity, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:limit]:
            trending.append({"topic": entity, "mentions": count, "type": "entity"})

        return trending


# ===========================================
# ENHANCED DATA CATEGORIZATION
# ===========================================

class DataCategorizer:
    """Enhanced data categorization and tagging"""

    CATEGORY_HIERARCHY = {
        "people": {
            "politicians": ["president", "governor", "senator", "minister", "representative"],
            "military": ["general", "colonel", "military_head"],
            "traditional": ["oba", "emir", "obi", "sultan"],
            "business": ["ceo", "founder", "businessman"],
        },
        "places": {
            "states": ["state"],
            "cities": ["city", "town"],
            "regions": ["zone", "region"],
            "institutions": ["university", "hospital", "ministry"],
        },
        "events": {
            "political": ["election", "inauguration", "coup"],
            "economic": ["budget", "policy"],
            "historical": ["war", "independence", "crisis"],
        },
        "data": {
            "economic": ["gdp", "inflation", "revenue", "debt"],
            "demographic": ["population", "census"],
            "fiscal": ["budget", "expenditure", "allocation"],
        }
    }

    def __init__(self, entities: Dict):
        self.entities = entities
        self.categorized: Dict[str, EntityCategory] = {}

    def categorize_all(self) -> Dict[str, EntityCategory]:
        """Categorize all entities"""
        logger.info("Categorizing entities...")

        for entity_id, entity in self.entities.items():
            category = self._categorize_entity(entity_id, entity)
            self.categorized[entity_id] = category

        logger.info(f"  Categorized {len(self.categorized)} entities")
        return self.categorized

    def _categorize_entity(self, entity_id: str, entity: Dict) -> EntityCategory:
        """Categorize a single entity"""
        entity_type = entity.get("type", "").lower()
        name = entity.get("name", "").lower()
        content = str(entity.get("content", entity.get("description", ""))).lower()

        primary = "uncategorized"
        secondary = []
        tags = []

        # Determine primary category
        for main_cat, sub_cats in self.CATEGORY_HIERARCHY.items():
            for sub_cat, keywords in sub_cats.items():
                if any(kw in entity_type or kw in name for kw in keywords):
                    primary = main_cat
                    secondary.append(sub_cat)
                    break

        # Add tags based on content
        tag_keywords = {
            "current": ["2024", "2025", "current", "present"],
            "historical": ["1960", "1970", "1980", "colonial", "independence"],
            "controversial": ["crisis", "scandal", "corruption", "protest"],
            "economic": ["naira", "budget", "gdp", "inflation"],
            "security": ["military", "police", "security", "terrorism"],
        }

        for tag, keywords in tag_keywords.items():
            if any(kw in content or kw in name for kw in keywords):
                tags.append(tag)

        # Calculate importance score
        importance = self._calculate_importance(entity)

        return EntityCategory(
            entity_id=entity_id,
            primary_category=primary,
            secondary_categories=list(set(secondary)),
            tags=list(set(tags)),
            importance_score=importance,
            last_updated=datetime.now().isoformat()
        )

    def _calculate_importance(self, entity: Dict) -> float:
        """Calculate entity importance score (0-1)"""
        score = 0.0

        # Position-based importance
        position = entity.get("position", "").lower()
        if "president" in position:
            score += 0.5
        elif "governor" in position:
            score += 0.3
        elif "senator" in position or "minister" in position:
            score += 0.2

        # Source quality
        source = entity.get("source", "")
        if source == "wikidata":
            score += 0.2
        elif source == "wikipedia":
            score += 0.15

        # Recency
        if entity.get("end_date") is None:  # Currently active
            score += 0.2

        return min(1.0, score)

    def get_by_category(self, category: str) -> List[str]:
        """Get entity IDs by category"""
        return [
            eid for eid, cat in self.categorized.items()
            if cat.primary_category == category or category in cat.secondary_categories
        ]

    def get_by_tag(self, tag: str) -> List[str]:
        """Get entity IDs by tag"""
        return [
            eid for eid, cat in self.categorized.items()
            if tag in cat.tags
        ]


# ===========================================
# MAIN EXECUTION
# ===========================================

def load_enhanced_data() -> Tuple[Dict, List[Dict], List[Dict]]:
    """Load enhanced knowledge graph data"""
    latest_file = ENHANCED_DIR / "latest.json"
    if not latest_file.exists():
        logger.error("Enhanced data not found. Run enhance_knowledge_graph.py first.")
        return {}, [], []

    with open(latest_file, encoding="utf-8") as f:
        latest = json.load(f)

    entities = {}
    relationships = []
    economic_data = []

    # Load entities
    entities_file = Path(latest.get("entities_file", ""))
    if entities_file.exists():
        with open(entities_file, encoding="utf-8") as f:
            data = json.load(f)
            entities = data.get("entities", {})

    # Load relationships
    rel_file = Path(latest.get("relationships_file", ""))
    if rel_file.exists():
        with open(rel_file, encoding="utf-8") as f:
            data = json.load(f)
            relationships = data.get("relationships", [])

    # Load economic data
    econ_file = Path(latest.get("economic_data_file", ""))
    if econ_file.exists():
        with open(econ_file, encoding="utf-8") as f:
            data = json.load(f)
            economic_data = data.get("data_points", [])

    return entities, relationships, economic_data


def main():
    print("=" * 60)
    print("ADVANCED KNOWLEDGE GRAPH FEATURES")
    print("=" * 60)

    # Load data
    entities, relationships, economic_data = load_enhanced_data()
    if not entities:
        return

    logger.info(f"Loaded {len(entities)} entities, {len(relationships)} relationships, {len(economic_data)} economic data points")

    # 1. Predictive Analysis
    print("\n--- Predictive Analysis ---")
    analyzer = PredictiveAnalyzer(economic_data, entities, relationships)
    analyzer.analyze_economic_trends()
    analyzer.detect_political_patterns()
    predictions = analyzer.generate_predictions()

    # Save predictions
    pred_file = PREDICTIONS_DIR / f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(pred_file, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Saved predictions to {pred_file}")

    # 2. News Caching
    print("\n--- News Caching ---")
    news_manager = NewsCacheManager()
    new_articles = news_manager.fetch_news()
    if new_articles:
        news_manager.update_cache(new_articles)
        trending = news_manager.get_trending_topics(5)
        logger.info(f"Trending topics: {[t['topic'] for t in trending]}")

    # 3. Data Categorization
    print("\n--- Data Categorization ---")
    categorizer = DataCategorizer(entities)
    categorized = categorizer.categorize_all()

    # Save categorization
    cat_file = ENHANCED_DIR / f"categorization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(cat_file, "w", encoding="utf-8") as f:
        cat_data = {eid: asdict(cat) for eid, cat in categorized.items()}
        json.dump({"total": len(cat_data), "entities": cat_data}, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved categorization to {cat_file}")

    # Summary
    print("\n" + "=" * 60)
    print("ADVANCED FEATURES COMPLETE")
    print("=" * 60)
    print(f"\nPredictions:")
    print(f"  - Economic trends: {len(analyzer.trends)}")
    print(f"  - Political patterns: {len(analyzer.patterns)}")
    print(f"  - Predictions generated: {len(predictions.get('economic_predictions', []))}")
    print(f"\nNews Cache:")
    print(f"  - Articles cached: {news_manager.cache['stats'].get('total_articles', 0)}")
    print(f"\nCategorization:")
    print(f"  - Entities categorized: {len(categorized)}")

    # Category breakdown
    cat_counts = defaultdict(int)
    for cat in categorized.values():
        cat_counts[cat.primary_category] += 1
    print(f"  - By category: {dict(cat_counts)}")


if __name__ == "__main__":
    main()
