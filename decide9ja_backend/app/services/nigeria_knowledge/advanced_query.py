"""
Advanced Query Interface

Enhanced natural language processing for knowledge graph queries:
1. Intent classification with confidence scores
2. Entity extraction with type detection
3. Temporal reasoning (date parsing, era detection)
4. Comparison queries
5. Aggregation queries
6. Context-aware follow-ups
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Types of query intents"""
    # Information retrieval
    PERSON_INFO = "person_info"
    STATE_INFO = "state_info"
    ECONOMIC_DATA = "economic_data"
    HISTORICAL_EVENT = "historical_event"

    # Comparisons
    COMPARE_VALUES = "compare_values"
    COMPARE_ENTITIES = "compare_entities"

    # Trends and analysis
    TREND_ANALYSIS = "trend_analysis"
    PREDICTION = "prediction"

    # Timeline
    TIMELINE_QUERY = "timeline_query"
    ERA_QUERY = "era_query"

    # Aggregations
    COUNT = "count"
    LIST = "list"
    TOP_N = "top_n"

    # Navigation
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"

    # Other
    GENERAL = "general"
    UNKNOWN = "unknown"


@dataclass
class ExtractedEntity:
    """Extracted entity from query"""
    text: str
    entity_type: str
    confidence: float = 0.0
    normalized: str = ""


@dataclass
class TemporalReference:
    """Temporal reference extracted from query"""
    year: Optional[int] = None
    era: Optional[str] = None
    relative: Optional[str] = None  # "last year", "current", etc.
    range_start: Optional[int] = None
    range_end: Optional[int] = None


@dataclass
class ParsedQuery:
    """Fully parsed query with all extracted information"""
    original: str
    intent: QueryIntent
    confidence: float
    entities: List[ExtractedEntity] = field(default_factory=list)
    temporal: Optional[TemporalReference] = None
    comparison_type: Optional[str] = None
    aggregation_type: Optional[str] = None
    limit: Optional[int] = None
    filters: Dict[str, Any] = field(default_factory=dict)


class AdvancedQueryParser:
    """Advanced NLP query parser for knowledge graph"""

    # Nigerian political entities for recognition
    KNOWN_POLITICIANS = {
        "tinubu": "Bola Ahmed Tinubu",
        "buhari": "Muhammadu Buhari",
        "obasanjo": "Olusegun Obasanjo",
        "jonathan": "Goodluck Jonathan",
        "yar'adua": "Umaru Musa Yar'Adua",
        "atiku": "Atiku Abubakar",
        "obi": "Peter Obi",
        "wike": "Nyesom Wike",
        "el-rufai": "Nasir El-Rufai",
        "akpabio": "Godswill Akpabio",
        "shettima": "Kashim Shettima",
        "abacha": "Sani Abacha",
        "babangida": "Ibrahim Babangida",
        "gowon": "Yakubu Gowon",
        "azikiwe": "Nnamdi Azikiwe",
        "balewa": "Tafawa Balewa",
    }

    NIGERIAN_STATES = [
        "abia", "adamawa", "akwa ibom", "anambra", "bauchi", "bayelsa", "benue",
        "borno", "cross river", "delta", "ebonyi", "edo", "ekiti", "enugu",
        "gombe", "imo", "jigawa", "kaduna", "kano", "katsina", "kebbi", "kogi",
        "kwara", "lagos", "nasarawa", "niger", "ogun", "ondo", "osun", "oyo",
        "plateau", "rivers", "sokoto", "taraba", "yobe", "zamfara", "fct", "abuja"
    ]

    ECONOMIC_INDICATORS = {
        "gdp": ["gdp", "gross domestic product", "economic output"],
        "inflation": ["inflation", "price increase", "cpi", "consumer price"],
        "exchange_rate": ["exchange rate", "naira", "dollar", "forex", "fx"],
        "interest_rate": ["interest rate", "monetary policy rate", "mpr"],
        "debt": ["debt", "borrowing", "loan"],
        "budget": ["budget", "expenditure", "revenue", "fiscal"],
        "oil": ["oil", "crude", "petroleum", "barrel"],
        "population": ["population", "census", "people"],
    }

    ERAS = {
        "colonial": ["colonial", "british rule", "pre-independence"],
        "first_republic": ["first republic", "1960s"],
        "civil_war": ["civil war", "biafra", "biafran war"],
        "military": ["military rule", "military era", "military government"],
        "second_republic": ["second republic", "shagari era"],
        "fourth_republic": ["fourth republic", "democracy", "civilian rule"],
    }

    def __init__(self):
        self.context_stack: List[ParsedQuery] = []

    def parse(self, query: str, context: Dict = None) -> ParsedQuery:
        """
        Parse a natural language query.

        Args:
            query: The query string
            context: Optional context from previous queries

        Returns:
            ParsedQuery with all extracted information
        """
        query_lower = query.lower().strip()

        # Extract components
        intent, confidence = self._detect_intent(query_lower)
        entities = self._extract_entities(query_lower)
        temporal = self._extract_temporal(query_lower)
        comparison = self._detect_comparison(query_lower)
        aggregation = self._detect_aggregation(query_lower)
        limit = self._extract_limit(query_lower)
        filters = self._extract_filters(query_lower, entities)

        parsed = ParsedQuery(
            original=query,
            intent=intent,
            confidence=confidence,
            entities=entities,
            temporal=temporal,
            comparison_type=comparison,
            aggregation_type=aggregation,
            limit=limit,
            filters=filters
        )

        # Handle follow-ups
        if intent == QueryIntent.FOLLOW_UP and self.context_stack:
            parsed = self._resolve_follow_up(parsed)

        # Update context
        self.context_stack.append(parsed)
        if len(self.context_stack) > 5:
            self.context_stack.pop(0)

        return parsed

    def _detect_intent(self, query: str) -> Tuple[QueryIntent, float]:
        """Detect query intent with confidence score"""

        # Intent patterns with weights
        intent_patterns = {
            QueryIntent.PERSON_INFO: [
                (r"\bwho\b.*\b(is|was|are|were)\b", 0.9),
                (r"\btell me about\b.*\b(person|politician|president|governor)", 0.85),
                (r"\b(president|governor|senator|minister)\b", 0.7),
            ],
            QueryIntent.STATE_INFO: [
                (r"\b(state|lagos|kano|rivers|oyo)\b.*\b(capital|zone|governor)\b", 0.9),
                (r"\btell me about\b.*\b(state|lagos|kano)\b", 0.85),
                (r"\bstates? in\b.*\bzone\b", 0.8),
            ],
            QueryIntent.ECONOMIC_DATA: [
                (r"\b(gdp|inflation|exchange rate|interest rate|budget)\b", 0.9),
                (r"\bwhat (is|was)\b.*\b(economy|economic)\b", 0.8),
                (r"\b(naira|dollar|forex)\b", 0.75),
            ],
            QueryIntent.TREND_ANALYSIS: [
                (r"\b(trend|change|over time|from \d{4} to \d{4})\b", 0.9),
                (r"\bhow (has|have|did)\b.*\bchange\b", 0.85),
                (r"\b(increasing|decreasing|rising|falling)\b", 0.8),
            ],
            QueryIntent.COMPARE_VALUES: [
                (r"\bcompare\b", 0.95),
                (r"\bvs\.?\b|\bversus\b", 0.9),
                (r"\bdifference between\b", 0.85),
                (r"\bwhich (is|was) (higher|lower|better|worse)\b", 0.8),
            ],
            QueryIntent.TIMELINE_QUERY: [
                (r"\bwhat happened in \d{4}\b", 0.95),
                (r"\bevents? (in|of|during) \d{4}\b", 0.9),
                (r"\btimeline\b", 0.85),
            ],
            QueryIntent.ERA_QUERY: [
                (r"\b(colonial|first republic|civil war|military|fourth republic)\b.*\b(era|period)\b", 0.9),
                (r"\bduring (the )?(colonial|military|civilian)\b", 0.85),
            ],
            QueryIntent.TOP_N: [
                (r"\b(top|best|worst|highest|lowest) \d+\b", 0.9),
                (r"\branking\b", 0.8),
            ],
            QueryIntent.LIST: [
                (r"\b(list|show|all)\b.*\b(states?|governors?|senators?)\b", 0.85),
                (r"\bhow many\b", 0.7),
            ],
            QueryIntent.COUNT: [
                (r"\bhow many\b", 0.9),
                (r"\bnumber of\b", 0.85),
                (r"\bcount\b", 0.8),
            ],
            QueryIntent.HISTORICAL_EVENT: [
                (r"\b(civil war|coup|independence|biafra)\b", 0.85),
                (r"\bhistory\b", 0.7),
            ],
            QueryIntent.PREDICTION: [
                (r"\bpredict\b|\bforecast\b", 0.9),
                (r"\bwill\b.*\b(be|increase|decrease)\b", 0.75),
                (r"\bnext year\b", 0.7),
            ],
        }

        best_intent = QueryIntent.GENERAL
        best_score = 0.0

        for intent, patterns in intent_patterns.items():
            for pattern, weight in patterns:
                if re.search(pattern, query):
                    if weight > best_score:
                        best_score = weight
                        best_intent = intent

        # Check for follow-up
        follow_up_patterns = [
            r"^(what about|how about|and|also)\b",
            r"^(more|details|tell me more)\b",
            r"^\b(his|her|their|its|that|this)\b",
        ]
        for pattern in follow_up_patterns:
            if re.search(pattern, query):
                return QueryIntent.FOLLOW_UP, 0.8

        return best_intent, best_score

    def _extract_entities(self, query: str) -> List[ExtractedEntity]:
        """Extract entities from query"""
        entities = []

        # Check for known politicians
        for short, full in self.KNOWN_POLITICIANS.items():
            if short in query:
                entities.append(ExtractedEntity(
                    text=short,
                    entity_type="politician",
                    confidence=0.95,
                    normalized=full
                ))

        # Check for states
        for state in self.NIGERIAN_STATES:
            if state in query:
                entities.append(ExtractedEntity(
                    text=state,
                    entity_type="state",
                    confidence=0.9,
                    normalized=state.title()
                ))

        # Check for economic indicators
        for indicator, keywords in self.ECONOMIC_INDICATORS.items():
            for kw in keywords:
                if kw in query:
                    entities.append(ExtractedEntity(
                        text=kw,
                        entity_type="economic_indicator",
                        confidence=0.85,
                        normalized=indicator
                    ))
                    break

        # Check for parties
        parties = {
            "apc": "All Progressives Congress",
            "pdp": "Peoples Democratic Party",
            "labour party": "Labour Party",
            "lp": "Labour Party",
        }
        for short, full in parties.items():
            if short in query:
                entities.append(ExtractedEntity(
                    text=short,
                    entity_type="party",
                    confidence=0.9,
                    normalized=full
                ))

        return entities

    def _extract_temporal(self, query: str) -> Optional[TemporalReference]:
        """Extract temporal references from query"""
        temporal = TemporalReference()

        # Single year
        year_match = re.search(r'\b(19|20)\d{2}\b', query)
        if year_match:
            temporal.year = int(year_match.group())

        # Year range
        range_match = re.search(r'\b(19|20)\d{2}\s*(to|-)\s*(19|20)\d{2}\b', query)
        if range_match:
            years = re.findall(r'(19|20)\d{2}', range_match.group())
            if len(years) >= 2:
                temporal.range_start = int(years[0])
                temporal.range_end = int(years[1])

        # Era detection
        for era, keywords in self.ERAS.items():
            for kw in keywords:
                if kw in query:
                    temporal.era = era
                    break

        # Relative time
        relative_patterns = {
            "current": r"\b(current|now|today|present)\b",
            "last_year": r"\blast year\b",
            "this_year": r"\bthis year\b",
            "recent": r"\b(recent|lately)\b",
        }
        for rel, pattern in relative_patterns.items():
            if re.search(pattern, query):
                temporal.relative = rel
                break

        # Return None if nothing extracted
        if not any([temporal.year, temporal.era, temporal.relative, temporal.range_start]):
            return None

        return temporal

    def _detect_comparison(self, query: str) -> Optional[str]:
        """Detect comparison type"""
        if re.search(r'\bcompare\b|\bvs\.?\b|\bversus\b', query):
            return "explicit"
        if re.search(r'\bdifference\b', query):
            return "difference"
        if re.search(r'\b(higher|lower|more|less|better|worse)\b', query):
            return "relative"
        return None

    def _detect_aggregation(self, query: str) -> Optional[str]:
        """Detect aggregation type"""
        if re.search(r'\bhow many\b|\bcount\b|\bnumber of\b', query):
            return "count"
        if re.search(r'\btotal\b|\bsum\b', query):
            return "sum"
        if re.search(r'\baverage\b|\bmean\b', query):
            return "average"
        if re.search(r'\b(top|best|highest)\b', query):
            return "max"
        if re.search(r'\b(bottom|worst|lowest)\b', query):
            return "min"
        return None

    def _extract_limit(self, query: str) -> Optional[int]:
        """Extract limit/top-N from query"""
        match = re.search(r'\b(top|first|last)\s*(\d+)\b', query)
        if match:
            return int(match.group(2))

        match = re.search(r'\b(\d+)\s*(results?|items?|entries)\b', query)
        if match:
            return int(match.group(1))

        return None

    def _extract_filters(self, query: str, entities: List[ExtractedEntity]) -> Dict[str, Any]:
        """Extract filters from entities and query"""
        filters = {}

        for entity in entities:
            if entity.entity_type == "state":
                filters["state"] = entity.normalized
            elif entity.entity_type == "party":
                filters["party"] = entity.normalized
            elif entity.entity_type == "economic_indicator":
                filters["indicator"] = entity.normalized

        return filters

    def _resolve_follow_up(self, parsed: ParsedQuery) -> ParsedQuery:
        """Resolve follow-up query using context"""
        if not self.context_stack:
            return parsed

        prev = self.context_stack[-1]

        # Inherit entities if none extracted
        if not parsed.entities and prev.entities:
            parsed.entities = prev.entities

        # Inherit temporal if none extracted
        if not parsed.temporal and prev.temporal:
            parsed.temporal = prev.temporal

        # Inherit filters
        if prev.filters:
            for key, value in prev.filters.items():
                if key not in parsed.filters:
                    parsed.filters[key] = value

        return parsed


class QueryExecutor:
    """Execute parsed queries against knowledge graph"""

    def __init__(self, query_engine):
        """
        Args:
            query_engine: The knowledge graph query engine
        """
        self.engine = query_engine
        self.parser = AdvancedQueryParser()

    def execute(self, query: str, context: Dict = None) -> Dict[str, Any]:
        """
        Execute a natural language query.

        Args:
            query: Natural language query
            context: Optional conversation context

        Returns:
            Query results with formatted response
        """
        # Parse the query
        parsed = self.parser.parse(query, context)

        # Route to appropriate handler
        handlers = {
            QueryIntent.PERSON_INFO: self._handle_person,
            QueryIntent.STATE_INFO: self._handle_state,
            QueryIntent.ECONOMIC_DATA: self._handle_economic,
            QueryIntent.TREND_ANALYSIS: self._handle_trend,
            QueryIntent.COMPARE_VALUES: self._handle_comparison,
            QueryIntent.TIMELINE_QUERY: self._handle_timeline,
            QueryIntent.ERA_QUERY: self._handle_era,
            QueryIntent.TOP_N: self._handle_top_n,
            QueryIntent.LIST: self._handle_list,
            QueryIntent.COUNT: self._handle_count,
            QueryIntent.HISTORICAL_EVENT: self._handle_historical,
            QueryIntent.PREDICTION: self._handle_prediction,
        }

        handler = handlers.get(parsed.intent, self._handle_general)
        result = handler(parsed)

        return {
            "query": query,
            "parsed": {
                "intent": parsed.intent.value,
                "confidence": parsed.confidence,
                "entities": [{"text": e.text, "type": e.entity_type} for e in parsed.entities],
                "temporal": {
                    "year": parsed.temporal.year if parsed.temporal else None,
                    "era": parsed.temporal.era if parsed.temporal else None,
                } if parsed.temporal else None,
            },
            "results": result.get("results", []),
            "response": result.get("response", ""),
            "visualization": result.get("visualization"),
            "follow_ups": result.get("follow_ups", []),
        }

    def _handle_person(self, parsed: ParsedQuery) -> Dict:
        """Handle person info queries"""
        results = []

        for entity in parsed.entities:
            if entity.entity_type == "politician":
                search_results = self.engine.search(entity.normalized, limit=3)
                results.extend([r["entity"] for r in search_results])

        if not results:
            # General search
            results = self.engine.search(parsed.original, limit=5)
            results = [r["entity"] for r in results]

        return {
            "results": results,
            "response": self._format_person_response(results),
            "follow_ups": ["What is their political party?", "What positions have they held?"]
        }

    def _handle_state(self, parsed: ParsedQuery) -> Dict:
        """Handle state info queries"""
        state_name = parsed.filters.get("state")
        if state_name:
            profile = self.engine.get_state_profile(state_name)
            if profile:
                return {
                    "results": [profile],
                    "response": self._format_state_response(profile),
                    "follow_ups": [f"Who is the governor of {state_name}?", f"What is the population?"]
                }

        return {"results": [], "response": "State not found"}

    def _handle_economic(self, parsed: ParsedQuery) -> Dict:
        """Handle economic data queries"""
        indicator = parsed.filters.get("indicator")
        year = parsed.temporal.year if parsed.temporal else None

        data = self.engine.query_economic_data(indicator=indicator, year=year, limit=10)

        return {
            "results": data,
            "response": self._format_economic_response(data, indicator, year),
            "visualization": "economic_chart",
            "follow_ups": ["How has this changed over time?", "Compare with last year"]
        }

    def _handle_trend(self, parsed: ParsedQuery) -> Dict:
        """Handle trend analysis queries"""
        indicator = parsed.filters.get("indicator")
        start = parsed.temporal.range_start if parsed.temporal else None
        end = parsed.temporal.range_end if parsed.temporal else None

        data = self.engine.get_economic_trend(indicator or "", start, end)

        return {
            "results": data,
            "response": self._format_trend_response(data, indicator),
            "visualization": "line_chart"
        }

    def _handle_comparison(self, parsed: ParsedQuery) -> Dict:
        """Handle comparison queries"""
        # Compare entities
        if len(parsed.entities) >= 2:
            results = []
            for entity in parsed.entities[:2]:
                search = self.engine.search(entity.normalized or entity.text, limit=1)
                if search:
                    results.append(search[0]["entity"])

            return {
                "results": results,
                "response": self._format_comparison_response(results),
                "visualization": "comparison_chart"
            }

        return {"results": [], "response": "Need at least two items to compare"}

    def _handle_timeline(self, parsed: ParsedQuery) -> Dict:
        """Handle timeline queries"""
        year = parsed.temporal.year if parsed.temporal else None

        if year:
            events = self.engine.get_events_for_year(year)
            return {
                "results": events,
                "response": self._format_timeline_response(events, year),
                "visualization": "timeline"
            }

        return {"results": [], "response": "Please specify a year"}

    def _handle_era(self, parsed: ParsedQuery) -> Dict:
        """Handle era queries"""
        era = parsed.temporal.era if parsed.temporal else None

        if era:
            era_info = self.engine.get_era_info(era)
            if era_info:
                return {
                    "results": [era_info],
                    "response": self._format_era_response(era_info)
                }

        return {"results": [], "response": "Era not found"}

    def _handle_top_n(self, parsed: ParsedQuery) -> Dict:
        """Handle top-N queries"""
        limit = parsed.limit or 5
        results = self.engine.search(parsed.original, limit=limit)

        return {
            "results": [r["entity"] for r in results],
            "visualization": "leaderboard"
        }

    def _handle_list(self, parsed: ParsedQuery) -> Dict:
        """Handle list queries"""
        limit = parsed.limit or 10
        results = self.engine.search(parsed.original, limit=limit)

        return {
            "results": [r["entity"] for r in results],
        }

    def _handle_count(self, parsed: ParsedQuery) -> Dict:
        """Handle count queries"""
        # This would need actual count implementation
        results = self.engine.search(parsed.original, limit=100)
        count = len(results)

        return {
            "results": [{"count": count}],
            "response": f"Found {count} results"
        }

    def _handle_historical(self, parsed: ParsedQuery) -> Dict:
        """Handle historical event queries"""
        results = self.engine.search(parsed.original, limit=5)

        return {
            "results": [r["entity"] for r in results],
            "follow_ups": ["What led to this?", "What happened after?"]
        }

    def _handle_prediction(self, parsed: ParsedQuery) -> Dict:
        """Handle prediction queries"""
        indicator = parsed.filters.get("indicator")

        # This would use the predictive analyzer
        return {
            "results": [],
            "response": "Predictions require the predictive analysis module",
            "follow_ups": ["Show me historical trends instead"]
        }

    def _handle_general(self, parsed: ParsedQuery) -> Dict:
        """Handle general queries"""
        results = self.engine.search(parsed.original, limit=10)

        return {
            "results": [r["entity"] for r in results],
        }

    # Formatting methods
    def _format_person_response(self, results: List[Dict]) -> str:
        if not results:
            return "No information found"

        entity = results[0]
        name = entity.get("name", "Unknown")
        position = entity.get("position", "")
        party = entity.get("party", entity.get("partyLabel", ""))

        return f"*{name}*\nPosition: {position}\nParty: {party}"

    def _format_state_response(self, profile: Dict) -> str:
        name = profile.get("name", "Unknown")
        capital = profile.get("capital", "N/A")
        zone = profile.get("geopolitical_zone", "N/A")

        return f"*{name}*\nCapital: {capital}\nZone: {zone}"

    def _format_economic_response(self, data: List[Dict], indicator: str, year: int) -> str:
        if not data:
            return "No economic data found"

        lines = []
        for item in data[:5]:
            ind = item.get("indicator", "")
            val = item.get("value")
            yr = item.get("year", "")

            if val is not None:
                lines.append(f"• {ind} ({yr}): {val}")

        return "\n".join(lines)

    def _format_trend_response(self, data: List[Dict], indicator: str) -> str:
        if not data:
            return "No trend data found"

        if len(data) >= 2:
            first = data[0].get("value", 0)
            last = data[-1].get("value", 0)

            if first != 0:
                change = ((last - first) / abs(first)) * 100
                direction = "increased" if change > 0 else "decreased"
                return f"{indicator} has {direction} by {abs(change):.1f}%"

        return f"Found {len(data)} data points"

    def _format_comparison_response(self, results: List[Dict]) -> str:
        if len(results) < 2:
            return "Need two items to compare"

        lines = []
        for r in results:
            lines.append(f"• {r.get('name', 'Unknown')}")

        return "Comparing:\n" + "\n".join(lines)

    def _format_timeline_response(self, events: List[Dict], year: int) -> str:
        if not events:
            return f"No events found for {year}"

        lines = [f"*Events in {year}:*"]
        for event in events[:5]:
            name = event.get("name", event.get("entity_id", "Unknown"))
            lines.append(f"• {name}")

        return "\n".join(lines)

    def _format_era_response(self, era: Dict) -> str:
        name = era.get("name", "Unknown")
        desc = era.get("description", "")
        start = era.get("start_date", "")
        end = era.get("end_date", "Present")

        return f"*{name}*\n{start} - {end}\n\n{desc}"
