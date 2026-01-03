"""
Nigeria Knowledge Query Engine

Provides natural language query capabilities over the enhanced knowledge graph,
including entities, economic data, full-text search, state profiles, and timeline.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Path to knowledge graph data
BASE_DIR = Path(__file__).parent.parent.parent.parent / "nigeria_knowledge_data"
ENHANCED_DIR = BASE_DIR / "enhanced"
KG_DIR = BASE_DIR / "knowledge_graph"


class QueryEngine:
    """
    Enhanced query engine for the Nigeria Knowledge Graph.

    Supports queries like:
    - "Who was the president in 1999?"
    - "What was Nigeria's GDP in 2015?"
    - "What was inflation in 2020?"
    - "Tell me about Olusegun Obasanjo"
    - "What happened during the civil war?"
    - "Show me economic data for Lagos"
    - "What happened in 1966?"
    - "Tell me about Lagos State"
    """

    def __init__(self):
        self.entities: Dict[str, Dict] = {}
        self.relationships: List[Dict] = []
        self.search_index: Dict[str, List[str]] = {}
        self.full_text_index: Dict[str, List[str]] = {}
        self.economic_data: List[Dict] = []
        self.timeline: Dict[int, List[Dict]] = {}
        self.state_profiles: Dict[str, Dict] = {}
        self.loaded = False
        self._load_knowledge_graph()

    def _load_knowledge_graph(self):
        """Load the enhanced knowledge graph from disk"""
        try:
            # Try enhanced data first
            enhanced_latest = ENHANCED_DIR / "latest.json"
            kg_latest = KG_DIR / "latest.json"

            if enhanced_latest.exists():
                logger.info("Loading enhanced knowledge graph...")
                self._load_enhanced_data(enhanced_latest)
            elif kg_latest.exists():
                logger.info("Loading basic knowledge graph...")
                self._load_basic_data(kg_latest)
            else:
                # Try to find any entities file
                self._load_fallback_data()

            self.loaded = bool(self.entities)

        except Exception as e:
            logger.error(f"Error loading knowledge graph: {e}")
            self.loaded = False

    def _load_enhanced_data(self, latest_file: Path):
        """Load enhanced knowledge graph data"""
        with open(latest_file, encoding="utf-8") as f:
            latest = json.load(f)

        # Load entities
        entities_file = Path(latest.get("entities_file", ""))
        if entities_file.exists():
            with open(entities_file, encoding="utf-8") as f:
                data = json.load(f)
                self.entities = data.get("entities", {})
            logger.info(f"  Loaded {len(self.entities)} entities")

        # Load relationships
        rel_file = Path(latest.get("relationships_file", ""))
        if rel_file.exists():
            with open(rel_file, encoding="utf-8") as f:
                data = json.load(f)
                self.relationships = data.get("relationships", [])
            logger.info(f"  Loaded {len(self.relationships)} relationships")

        # Load full-text index
        index_file = Path(latest.get("full_text_index_file", ""))
        if index_file.exists():
            with open(index_file, encoding="utf-8") as f:
                data = json.load(f)
                self.full_text_index = data.get("index", {})
            logger.info(f"  Loaded full-text index with {len(self.full_text_index)} words")

        # Load economic data
        econ_file = Path(latest.get("economic_data_file", ""))
        if econ_file.exists():
            with open(econ_file, encoding="utf-8") as f:
                data = json.load(f)
                self.economic_data = data.get("data_points", [])
            logger.info(f"  Loaded {len(self.economic_data)} economic data points")

        # Load timeline
        timeline_file = Path(latest.get("timeline_file", ""))
        if timeline_file.exists():
            with open(timeline_file, encoding="utf-8") as f:
                data = json.load(f)
                # Convert string keys to int
                self.timeline = {int(k): v for k, v in data.get("timeline", {}).items()}
            logger.info(f"  Loaded timeline with {len(self.timeline)} years")

        # Load state profiles
        states_file = Path(latest.get("states_file", ""))
        if states_file.exists():
            with open(states_file, encoding="utf-8") as f:
                data = json.load(f)
                self.state_profiles = data.get("states", {})
            logger.info(f"  Loaded {len(self.state_profiles)} state profiles")

    def _load_basic_data(self, latest_file: Path):
        """Load basic knowledge graph data"""
        with open(latest_file, encoding="utf-8") as f:
            latest = json.load(f)

        entities_file = Path(latest.get("entities_file", ""))
        if entities_file.exists():
            with open(entities_file, encoding="utf-8") as f:
                data = json.load(f)
                self.entities = data.get("entities", {})

        rel_file = Path(latest.get("relationships_file", ""))
        if rel_file.exists():
            with open(rel_file, encoding="utf-8") as f:
                data = json.load(f)
                self.relationships = data.get("relationships", [])

        index_file = Path(latest.get("index_file", ""))
        if index_file.exists():
            with open(index_file, encoding="utf-8") as f:
                self.search_index = json.load(f)

    def _load_fallback_data(self):
        """Load data without latest.json file"""
        for data_dir in [ENHANCED_DIR, KG_DIR]:
            entities_files = list(data_dir.glob("entities*.json"))
            if entities_files:
                latest = max(entities_files, key=lambda f: f.stat().st_mtime)
                with open(latest, encoding="utf-8") as f:
                    data = json.load(f)
                    self.entities = data.get("entities", {})
                logger.info(f"Loaded {len(self.entities)} entities from {latest}")
                break

    # ===========================================
    # SEARCH METHODS
    # ===========================================

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for entities using full-text index"""
        if not self.loaded:
            return []

        query_lower = query.lower()
        query_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', query_lower))

        results = []
        seen_ids = set()
        scores = {}

        # Use full-text index if available
        if self.full_text_index:
            for word in query_words:
                if word in self.full_text_index:
                    for entity_id in self.full_text_index[word]:
                        if entity_id in self.entities:
                            scores[entity_id] = scores.get(entity_id, 0) + 1

            # Sort by score
            sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            for entity_id in sorted_ids[:limit]:
                if entity_id not in seen_ids:
                    seen_ids.add(entity_id)
                    results.append({
                        "entity": self.entities[entity_id],
                        "score": scores[entity_id] / len(query_words) if query_words else 0,
                        "match_type": "full_text"
                    })

        # Fallback to name matching
        if not results:
            for entity_id, entity in self.entities.items():
                name = entity.get("name", "").lower()
                if query_lower in name or any(w in name for w in query_words):
                    if entity_id not in seen_ids:
                        seen_ids.add(entity_id)
                        results.append({
                            "entity": entity,
                            "score": 0.5,
                            "match_type": "name"
                        })

        return results[:limit]

    def search_by_type(self, entity_type: str, limit: int = 20) -> List[Dict]:
        """Search entities by type"""
        results = []
        for entity_id, entity in self.entities.items():
            if entity.get("type") == entity_type:
                results.append(entity)
                if len(results) >= limit:
                    break
        return results

    # ===========================================
    # ECONOMIC DATA QUERIES
    # ===========================================

    def query_economic_data(
        self,
        indicator: Optional[str] = None,
        year: Optional[int] = None,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Query specific economic data points.

        Args:
            indicator: Indicator name (e.g., "inflation", "gdp", "exchange rate")
            year: Specific year
            category: Category (e.g., "inflation", "gdp_growth", "oil_production")
            limit: Maximum results

        Returns:
            List of matching economic data points
        """
        if not self.economic_data:
            return []

        results = []

        for data_point in self.economic_data:
            # Filter by indicator
            if indicator:
                ind_name = data_point.get("indicator", "").lower()
                if indicator.lower() not in ind_name:
                    continue

            # Filter by year
            if year and data_point.get("year") != year:
                continue

            # Filter by category
            if category:
                cat = data_point.get("category", "").lower()
                if category.lower() not in cat:
                    continue

            results.append(data_point)
            if len(results) >= limit:
                break

        return results

    def get_economic_value(self, indicator: str, year: int) -> Optional[Dict]:
        """Get a specific economic value for an indicator and year"""
        for data_point in self.economic_data:
            ind_name = data_point.get("indicator", "").lower()
            if indicator.lower() in ind_name and data_point.get("year") == year:
                return data_point
        return None

    def get_economic_trend(self, indicator: str, start_year: int = None, end_year: int = None) -> List[Dict]:
        """Get trend data for an indicator over time"""
        results = []
        for data_point in self.economic_data:
            ind_name = data_point.get("indicator", "").lower()
            if indicator.lower() not in ind_name:
                continue

            year = data_point.get("year", 0)
            if start_year and year < start_year:
                continue
            if end_year and year > end_year:
                continue

            results.append(data_point)

        return sorted(results, key=lambda x: x.get("year", 0))

    # ===========================================
    # TIMELINE QUERIES
    # ===========================================

    def get_events_for_year(self, year: int) -> List[Dict]:
        """Get all events/data for a specific year"""
        return self.timeline.get(year, [])

    def get_events_in_range(self, start_year: int, end_year: int) -> Dict[int, List[Dict]]:
        """Get events for a range of years"""
        return {
            year: events
            for year, events in self.timeline.items()
            if start_year <= year <= end_year
        }

    def get_era_info(self, era_name: str) -> Optional[Dict]:
        """Get information about a historical era"""
        era_lower = era_name.lower()
        for entity_id, entity in self.entities.items():
            if entity.get("type") == "era":
                name = entity.get("name", "").lower()
                if era_lower in name or era_lower in entity_id:
                    return entity
        return None

    # ===========================================
    # STATE QUERIES
    # ===========================================

    def get_state_profile(self, state_name: str) -> Optional[Dict]:
        """Get profile for a Nigerian state"""
        state_lower = state_name.lower().replace(" state", "").strip()

        for state_id, profile in self.state_profiles.items():
            short_name = profile.get("short_name", "").lower()
            name = profile.get("name", "").lower()
            if state_lower in short_name or state_lower in name or state_lower in state_id:
                return profile

        return None

    def get_states_by_zone(self, zone: str) -> List[Dict]:
        """Get all states in a geopolitical zone"""
        zone_lower = zone.lower()
        return [
            profile for profile in self.state_profiles.values()
            if zone_lower in profile.get("geopolitical_zone", "").lower()
        ]

    # ===========================================
    # RELATIONSHIP QUERIES
    # ===========================================

    def get_related(self, entity_id: str, relation_type: str = None, limit: int = 10) -> List[Dict]:
        """Get entities related to the given entity"""
        related = []
        seen = set()

        for rel in self.relationships:
            if rel.get("source") == entity_id:
                if relation_type and rel.get("type") != relation_type:
                    continue
                target_id = rel.get("target")
                if target_id not in seen and target_id in self.entities:
                    seen.add(target_id)
                    related.append({
                        "entity": self.entities[target_id],
                        "relation": rel.get("type"),
                        "direction": "outgoing"
                    })
            elif rel.get("target") == entity_id:
                if relation_type and rel.get("type") != relation_type:
                    continue
                source_id = rel.get("source")
                if source_id not in seen and source_id in self.entities:
                    seen.add(source_id)
                    related.append({
                        "entity": self.entities[source_id],
                        "relation": rel.get("type"),
                        "direction": "incoming"
                    })

        return related[:limit]

    def get_succession_chain(self, position: str = "president") -> List[Dict]:
        """Get succession chain for a position (e.g., presidents)"""
        leaders = []
        for entity_id, entity in self.entities.items():
            if entity.get("type") == "person_leader":
                pos = entity.get("position", "").lower()
                if position.lower() in pos:
                    leaders.append(entity)

        # Sort by start date
        return sorted(leaders, key=lambda x: x.get("start_date", "") or "")

    # ===========================================
    # NATURAL LANGUAGE QUERY
    # ===========================================

    def query_natural_language(self, query: str) -> Dict[str, Any]:
        """Process a natural language query and return relevant results"""
        query_lower = query.lower()
        query_type = self._classify_query(query_lower)

        response = {
            "query": query,
            "query_type": query_type,
            "results": [],
            "context": "",
            "sources": [],
            "follow_ups": []
        }

        # Extract year from query
        year_match = re.search(r'\b(19|20)\d{2}\b', query)
        year = int(year_match.group()) if year_match else None

        if query_type == "economic":
            response = self._handle_economic_query(query, year, response)

        elif query_type == "historical":
            response = self._handle_historical_query(query, year, response)

        elif query_type == "state":
            response = self._handle_state_query(query, response)

        elif query_type == "person":
            response = self._handle_person_query(query, response)

        elif query_type == "timeline":
            response = self._handle_timeline_query(query, year, response)

        else:
            # General search
            results = self.search(query, limit=10)
            if results:
                response["results"] = [r["entity"] for r in results]
                response["context"] = self._format_general_context(results)
                response["sources"] = list(set(r["entity"].get("source", "") for r in results))

        return response

    def _classify_query(self, query: str) -> str:
        """Classify the type of query"""
        # Economic indicators
        if any(word in query for word in ["gdp", "inflation", "budget", "revenue", "expenditure",
                                          "debt", "economy", "naira", "oil price", "exchange rate",
                                          "interest rate", "monetary", "fiscal"]):
            return "economic"

        # State queries
        if any(word in query for word in ["state", "lagos", "kano", "rivers", "oyo", "kaduna",
                                          "governor", "lga", "capital"]):
            return "state"

        # Timeline/year queries
        if re.search(r'what happened in \d{4}|in \d{4}|year \d{4}', query):
            return "timeline"

        # Historical queries
        if any(word in query for word in ["history", "civil war", "independence", "colonial",
                                          "coup", "biafra", "republic", "era", "1960", "1966",
                                          "military rule"]):
            return "historical"

        # Person queries
        if any(word in query for word in ["who", "president", "senator", "minister", "chief",
                                          "obasanjo", "buhari", "tinubu", "jonathan"]):
            return "person"

        return "general"

    def _handle_economic_query(self, query: str, year: Optional[int], response: Dict) -> Dict:
        """Handle economic data queries"""
        # Try to find specific data point
        if year:
            # Look for specific indicators
            indicators = ["inflation", "gdp", "exchange rate", "interest rate", "oil"]
            for ind in indicators:
                if ind in query.lower():
                    data = self.query_economic_data(indicator=ind, year=year, limit=5)
                    if data:
                        response["results"] = data
                        response["context"] = self._format_economic_context(data, year)
                        response["sources"] = ["excel_financial"]
                        response["follow_ups"] = [
                            f"How did {ind} change over time?",
                            f"What was {ind} in {year - 1}?"
                        ]
                        return response

        # General economic data
        data = self.query_economic_data(limit=10)
        if data:
            response["results"] = data[:10]
            response["context"] = self._format_economic_context(data)
            response["sources"] = ["excel_financial"]
            response["follow_ups"] = ["What specific indicator do you want to know about?"]

        # Also search entities
        search_results = self.search(query, limit=5)
        for sr in search_results:
            if sr["entity"] not in response["results"]:
                response["results"].append(sr["entity"])

        return response

    def _handle_historical_query(self, query: str, year: Optional[int], response: Dict) -> Dict:
        """Handle historical queries"""
        results = self.search(query, limit=5)
        if results:
            response["results"] = [r["entity"] for r in results]
            response["context"] = self._format_historical_context(results)
            response["sources"] = list(set(r["entity"].get("source", "") for r in results))
            response["follow_ups"] = ["What led to this?", "What happened after?"]

        # Add era info if relevant
        for era_name in ["civil war", "colonial", "republic", "military"]:
            if era_name in query.lower():
                era = self.get_era_info(era_name)
                if era:
                    response["results"].insert(0, era)
                break

        return response

    def _handle_state_query(self, query: str, response: Dict) -> Dict:
        """Handle state-related queries"""
        # Try to identify state name
        for state_name in ["lagos", "kano", "rivers", "oyo", "kaduna", "delta", "edo",
                          "imo", "anambra", "enugu", "abia", "cross river", "akwa ibom",
                          "bayelsa", "benue", "plateau", "kwara", "niger", "sokoto", "zamfara"]:
            if state_name in query.lower():
                profile = self.get_state_profile(state_name)
                if profile:
                    response["results"] = [profile]
                    response["context"] = self._format_state_context(profile)
                    response["sources"] = ["reference_data"]
                    response["follow_ups"] = [
                        f"Who is the governor of {state_name.title()}?",
                        f"What is the population of {state_name.title()}?"
                    ]
                    return response

        # General state search
        results = self.search(query, limit=10)
        response["results"] = [r["entity"] for r in results]
        return response

    def _handle_person_query(self, query: str, response: Dict) -> Dict:
        """Handle person queries"""
        results = self.search(query, limit=5)
        if results:
            response["results"] = [r["entity"] for r in results]
            response["context"] = self._format_person_context(results[0]["entity"])
            response["sources"] = [results[0]["entity"].get("source", "knowledge_graph")]
            response["follow_ups"] = ["What is their political party?", "What positions have they held?"]
        return response

    def _handle_timeline_query(self, query: str, year: Optional[int], response: Dict) -> Dict:
        """Handle timeline queries"""
        if year:
            events = self.get_events_for_year(year)
            if events:
                response["results"] = events
                response["context"] = f"**Events in {year}:**\n\n"
                for event in events[:10]:
                    if event.get("type") == "event":
                        response["context"] += f"• {event.get('name')}: {event.get('description', '')}\n"
                    elif event.get("type") == "economic":
                        response["context"] += f"• {event.get('description')}\n"
                    else:
                        response["context"] += f"• {event.get('name', 'Unknown')}\n"
                response["sources"] = ["timeline"]
                response["follow_ups"] = [f"What happened in {year + 1}?", f"What happened in {year - 1}?"]
        return response

    # ===========================================
    # FORMATTING METHODS
    # ===========================================

    def _format_economic_context(self, data: List[Dict], year: int = None) -> str:
        """Format economic data as context"""
        if not data:
            return "No economic data found."

        context = ""
        if year:
            context = f"**Economic Data for {year}:**\n\n"
        else:
            context = "**Nigerian Economic Data:**\n\n"

        for item in data[:8]:
            indicator = item.get("indicator", "Unknown")
            value = item.get("value")
            item_year = item.get("year", "")
            unit = item.get("unit", "")

            if value is not None:
                if unit == "percent":
                    context += f"• {indicator} ({item_year}): {value}%\n"
                elif unit in ["NGN", "USD"]:
                    context += f"• {indicator} ({item_year}): {unit} {value:,.2f}\n" if isinstance(value, (int, float)) else f"• {indicator} ({item_year}): {value}\n"
                else:
                    context += f"• {indicator} ({item_year}): {value}\n"

        return context

    def _format_person_context(self, entity: Dict) -> str:
        """Format person entity as context"""
        name = entity.get("name", "Unknown")
        entity_type = entity.get("type", "person").replace("_", " ").title()
        description = entity.get("description", "")

        context = f"**{name}** ({entity_type})\n\n"
        if description:
            context += f"{description}\n\n"

        for key in ["party", "position", "state", "start_date", "end_date"]:
            value = entity.get(key) or entity.get(f"{key}Label")
            if value:
                context += f"• {key.replace('_', ' ').title()}: {value}\n"

        return context

    def _format_state_context(self, profile: Dict) -> str:
        """Format state profile as context"""
        name = profile.get("name", "Unknown")
        context = f"**{name}**\n\n"

        for key in ["capital", "geopolitical_zone", "year_created"]:
            value = profile.get(key)
            if value:
                label = key.replace("_", " ").title()
                context += f"• {label}: {value}\n"

        return context

    def _format_historical_context(self, results: List[Dict]) -> str:
        """Format historical data as context"""
        if not results:
            return "No historical information found."

        context = ""
        for result in results[:5]:
            entity = result.get("entity", result)
            name = entity.get("name", "")
            content = entity.get("content", entity.get("description", entity.get("content_preview", "")))
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            content = str(content)[:500] if content else ""

            context += f"**{name}**\n{content}\n\n---\n\n"

        return context

    def _format_general_context(self, results: List[Dict]) -> str:
        """Format general search results as context"""
        if not results:
            return "No relevant information found."

        context = ""
        for result in results[:5]:
            entity = result.get("entity", result)
            name = entity.get("name", "")
            entity_type = entity.get("type", "").replace("_", " ").title()
            context += f"• **{name}** [{entity_type}]\n"

        return context

    # ===========================================
    # UTILITY METHODS
    # ===========================================

    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get a specific entity by ID"""
        return self.entities.get(entity_id)

    def get_stats(self) -> Dict:
        """Get statistics about the knowledge graph"""
        if not self.loaded:
            return {"loaded": False, "message": "Knowledge graph not loaded"}

        type_counts = {}
        source_counts = {}

        for entity in self.entities.values():
            entity_type = entity.get("type", "unknown")
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

            source = entity.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

        return {
            "loaded": True,
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
            "economic_data_points": len(self.economic_data),
            "full_text_index_words": len(self.full_text_index),
            "timeline_years": len(self.timeline),
            "state_profiles": len(self.state_profiles),
            "by_type": type_counts,
            "by_source": source_counts
        }


# Singleton instance
_query_engine: Optional[QueryEngine] = None


def get_query_engine() -> QueryEngine:
    """Get the singleton query engine instance"""
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine


def query_knowledge(query: str) -> Dict[str, Any]:
    """Convenience function to query the knowledge graph"""
    engine = get_query_engine()
    return engine.query_natural_language(query)
