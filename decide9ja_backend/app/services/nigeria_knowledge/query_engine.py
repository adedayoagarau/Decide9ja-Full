"""
Query Engine for Nigeria Knowledge Graph

Provides natural language query capabilities over the knowledge graph,
translating user questions into graph traversals and returning
structured, context-rich results.

Supports:
- Entity lookup (politicians, states, LGAs, parties)
- Relationship queries (who represents X, members of Y)
- Historical queries (events in year Z, coups, elections)
- Financial queries (budget data, allocations, economic indicators)
- Comparison queries (compare politician A vs B)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum

from .knowledge_graph import (
    NigeriaKnowledgeGraph,
    Entity,
    EntityType,
    RelationType,
    get_knowledge_graph,
)

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries the engine can handle."""
    ENTITY_LOOKUP = "entity_lookup"
    RELATIONSHIP = "relationship"
    HISTORICAL = "historical"
    FINANCIAL = "financial"
    COMPARISON = "comparison"
    LIST = "list"
    AGGREGATE = "aggregate"


@dataclass
class QueryResult:
    """Result from a knowledge graph query."""
    success: bool
    query_type: QueryType
    entities: List[Entity] = field(default_factory=list)
    relationships: List[Dict] = field(default_factory=list)
    context: str = ""
    confidence: float = 1.0
    sources: List[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Format result as context string for LLM."""
        if not self.success:
            return f"No results found. {self.context}"

        parts = []

        # Add entity information
        for entity in self.entities:
            parts.append(f"=== {entity.entity_type.value.upper()}: {entity.name} ===")

            # Add key properties
            for key, value in entity.properties.items():
                if value and key not in ["full_text", "sample_records"]:
                    if isinstance(value, list):
                        value = ", ".join(str(v) for v in value[:5])
                    parts.append(f"{key.replace('_', ' ').title()}: {value}")

            # Add dates if available
            if entity.start_date:
                parts.append(f"Birth/Start Date: {entity.start_date}")
            if entity.end_date:
                parts.append(f"Death/End Date: {entity.end_date}")

            parts.append("")  # Blank line

        # Add relationship information
        if self.relationships:
            parts.append("=== RELATIONSHIPS ===")
            for rel in self.relationships[:10]:  # Limit to 10
                parts.append(f"- {rel.get('source_name')} {rel.get('relation')} {rel.get('target_name')}")

        # Add sources
        if self.sources:
            parts.append(f"\nSources: {', '.join(set(self.sources))}")

        return "\n".join(parts)


class QueryEngine:
    """
    Natural language query engine for the Nigeria Knowledge Graph.

    Translates user queries into graph operations and returns
    structured results suitable for LLM context injection.
    """

    def __init__(self, graph: Optional[NigeriaKnowledgeGraph] = None):
        self.graph = graph or get_knowledge_graph()

        # Nigerian-specific query patterns
        self.patterns = {
            # Representative queries
            r"(?:who is|who's) (?:the |my )?senator (?:for |of |representing )?(.+)": self._query_senator,
            r"(?:who is|who's) (?:the |my )?(?:house of reps|representative|rep) (?:for |of |representing )?(.+)": self._query_representative,
            r"(?:who is|who's) (?:the )?governor (?:of |for )?(.+)": self._query_governor,

            # Politician lookup
            r"(?:tell me about|who is|info on|profile of) (.+)": self._query_politician,

            # Party queries
            r"(?:members of|politicians in|who (?:is|are) in) (apc|pdp|lp|nnpp|apga|.+party)": self._query_party_members,
            r"(?:what is|tell me about) (.+party|apc|pdp|lp|nnpp|apga)": self._query_party,

            # Geographic queries
            r"(?:lgas?|local governments?) (?:in |of )(.+)": self._query_lgas_in_state,
            r"(?:which state is|what state) (.+) in": self._query_lga_state,
            r"senatorial districts? (?:in |of )(.+)": self._query_senatorial_districts,

            # Historical queries
            r"(?:coups?|military takeovers?) (?:in )?(?:nigeria)?": self._query_coups,
            r"(?:elections?|voting) (?:in |of )?(\d{4})": self._query_elections,
            r"(?:what happened|events?) (?:in |during )?(\d{4})": self._query_year_events,

            # Financial queries
            r"(?:interest rate|inflation|exchange rate) (?:in |for )?(\d{4})?": self._query_economic_indicator,
            r"(?:budget|allocation|expenditure) (?:for |of )?(.+)": self._query_budget,
            r"(?:faac|federal allocation) (?:for |to )?(.+)": self._query_faac,

            # Comparison queries
            r"compare (.+) (?:and|vs|versus|with) (.+)": self._query_compare,

            # News queries
            r"(?:news|articles?) (?:about|on|regarding|mentioning) (.+)": self._query_politician_news,
            r"(?:recent|latest) (?:news|articles?) (?:about|on|for) (.+)": self._query_politician_news,
            r"what.* (?:news|media|press) (?:say|said|saying|report) (?:about|on) (.+)": self._query_politician_news,
            r"who (?:is|are) (?:being )?(?:mentioned|discussed|talked about) (?:in )?(?:the )?news": self._query_trending_politicians,
            r"who (?:is|are) (.+) (?:often )?mentioned with": self._query_co_mentioned,
        }

    def query(self, user_query: str) -> QueryResult:
        """
        Process a natural language query.

        Args:
            user_query: The user's question

        Returns:
            QueryResult with entities, relationships, and context
        """
        query_lower = user_query.lower().strip()

        # Try pattern matching first
        for pattern, handler in self.patterns.items():
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                try:
                    return handler(match)
                except Exception as e:
                    logger.error(f"Error in query handler: {e}")
                    continue

        # Fallback to fuzzy entity search
        return self._fuzzy_search(user_query)

    def _query_senator(self, match) -> QueryResult:
        """Find senator for a state/district."""
        location = match.group(1).strip()
        entities = []
        sources = []

        # Search for politicians with senator position in this location
        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.POLITICIAN:
                continue

            positions = entity.properties.get("positions", [])
            state = entity.properties.get("state", "").lower()
            constituency = entity.properties.get("constituency", "").lower()

            is_senator = any("senator" in p.lower() or "senate" in p.lower() for p in positions)
            matches_location = location.lower() in state or location.lower() in constituency

            if is_senator and matches_location:
                entities.append(entity)
                sources.extend(entity.sources)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.ENTITY_LOOKUP,
            entities=entities,
            context=f"Senator(s) for {location}" if entities else f"No senator found for {location}",
            sources=sources,
        )

    def _query_representative(self, match) -> QueryResult:
        """Find House of Reps member for a constituency."""
        location = match.group(1).strip()
        entities = []
        sources = []

        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.POLITICIAN:
                continue

            positions = entity.properties.get("positions", [])
            constituency = entity.properties.get("constituency", "").lower()

            is_rep = any("representative" in p.lower() or "house of rep" in p.lower() for p in positions)
            matches_location = location.lower() in constituency

            if is_rep and matches_location:
                entities.append(entity)
                sources.extend(entity.sources)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.ENTITY_LOOKUP,
            entities=entities,
            context=f"Representative(s) for {location}" if entities else f"No representative found for {location}",
            sources=sources,
        )

    def _query_governor(self, match) -> QueryResult:
        """Find governor of a state."""
        state = match.group(1).strip()
        entities = []
        sources = []

        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.POLITICIAN:
                continue

            positions = entity.properties.get("positions", [])
            entity_state = entity.properties.get("state", "").lower()

            is_governor = any("governor" in p.lower() for p in positions)
            matches_state = state.lower() in entity_state or state.lower() in entity.name.lower()

            if is_governor and matches_state:
                entities.append(entity)
                sources.extend(entity.sources)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.ENTITY_LOOKUP,
            entities=entities,
            context=f"Governor of {state}" if entities else f"No governor found for {state}",
            sources=sources,
        )

    def _query_politician(self, match) -> QueryResult:
        """Look up a politician by name."""
        name = match.group(1).strip()

        # Try exact match first
        entity = self.graph.find_entity(name)
        if entity and entity.entity_type in [EntityType.POLITICIAN, EntityType.MILITARY_OFFICER]:
            return QueryResult(
                success=True,
                query_type=QueryType.ENTITY_LOOKUP,
                entities=[entity],
                sources=entity.sources,
            )

        # Fuzzy search
        candidates = []
        name_lower = name.lower()
        for entity in self.graph.entities.values():
            if entity.entity_type not in [EntityType.POLITICIAN, EntityType.MILITARY_OFFICER]:
                continue
            if name_lower in entity.name.lower():
                candidates.append(entity)

        return QueryResult(
            success=len(candidates) > 0,
            query_type=QueryType.ENTITY_LOOKUP,
            entities=candidates[:5],  # Top 5 matches
            context=f"Politician(s) matching '{name}'" if candidates else f"No politician found matching '{name}'",
            sources=[s for e in candidates for s in e.sources],
        )

    def _query_party_members(self, match) -> QueryResult:
        """Find members of a political party."""
        party_name = match.group(1).strip()
        entities = []
        sources = []

        # Normalize party name
        party_aliases = {
            "apc": "all progressives congress",
            "pdp": "peoples democratic party",
            "lp": "labour party",
            "nnpp": "new nigeria peoples party",
            "apga": "all progressives grand alliance",
        }
        party_full = party_aliases.get(party_name.lower(), party_name.lower())

        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.POLITICIAN:
                continue

            current_party = entity.properties.get("current_party", "").lower()
            party_history = [p.lower() for p in entity.properties.get("party_history", [])]

            if party_full in current_party or party_name.lower() in current_party:
                entities.append(entity)
                sources.extend(entity.sources)
            elif any(party_full in p or party_name.lower() in p for p in party_history):
                entities.append(entity)
                sources.extend(entity.sources)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.LIST,
            entities=entities[:20],  # Limit to 20
            context=f"Members of {party_name.upper()}: {len(entities)} found",
            sources=sources,
        )

    def _query_party(self, match) -> QueryResult:
        """Get information about a political party."""
        party_name = match.group(1).strip()

        party_aliases = {
            "apc": "all progressives congress",
            "pdp": "peoples democratic party",
            "lp": "labour party",
            "nnpp": "new nigeria peoples party",
            "apga": "all progressives grand alliance",
        }
        party_full = party_aliases.get(party_name.lower(), party_name.lower())

        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.POLITICAL_PARTY:
                continue
            if party_full in entity.name.lower() or party_name.lower() in entity.name.lower():
                return QueryResult(
                    success=True,
                    query_type=QueryType.ENTITY_LOOKUP,
                    entities=[entity],
                    sources=entity.sources,
                )

        return QueryResult(
            success=False,
            query_type=QueryType.ENTITY_LOOKUP,
            context=f"Political party '{party_name}' not found",
        )

    def _query_lgas_in_state(self, match) -> QueryResult:
        """Find LGAs in a state."""
        state = match.group(1).strip()
        entities = []

        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.LGA:
                continue
            if state.lower() in entity.properties.get("state", "").lower():
                entities.append(entity)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.LIST,
            entities=entities,
            context=f"LGAs in {state}: {len(entities)} found",
            sources=["inec"],
        )

    def _query_lga_state(self, match) -> QueryResult:
        """Find which state an LGA is in."""
        lga = match.group(1).strip()

        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.LGA:
                continue
            if lga.lower() in entity.name.lower():
                return QueryResult(
                    success=True,
                    query_type=QueryType.ENTITY_LOOKUP,
                    entities=[entity],
                    context=f"{entity.name} is in {entity.properties.get('state', 'Unknown')} State",
                    sources=["inec"],
                )

        return QueryResult(
            success=False,
            query_type=QueryType.ENTITY_LOOKUP,
            context=f"LGA '{lga}' not found",
        )

    def _query_senatorial_districts(self, match) -> QueryResult:
        """Find senatorial districts in a state."""
        state = match.group(1).strip()
        # This would require additional data structure
        return QueryResult(
            success=False,
            query_type=QueryType.LIST,
            context=f"Senatorial districts query for {state} - data structure pending",
        )

    def _query_coups(self, match) -> QueryResult:
        """Find information about military coups."""
        entities = []

        for entity in self.graph.entities.values():
            if entity.entity_type == EntityType.COUP:
                entities.append(entity)

        # Sort by date
        entities.sort(key=lambda e: e.start_date or date(1900, 1, 1))

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.HISTORICAL,
            entities=entities,
            context=f"Military coups in Nigeria: {len(entities)} recorded",
            sources=["wikipedia"],
        )

    def _query_elections(self, match) -> QueryResult:
        """Find information about elections in a year."""
        year = match.group(1) if match.lastindex else None
        entities = []

        for entity in self.graph.entities.values():
            if entity.entity_type == EntityType.ELECTION:
                if year:
                    entity_year = entity.properties.get("year") or (entity.start_date.year if entity.start_date else None)
                    if str(entity_year) == str(year):
                        entities.append(entity)
                else:
                    entities.append(entity)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.HISTORICAL,
            entities=entities,
            context=f"Elections{' in ' + year if year else ''}: {len(entities)} found",
            sources=["wikipedia", "inec"],
        )

    def _query_year_events(self, match) -> QueryResult:
        """Find events that happened in a specific year."""
        year = int(match.group(1))
        entities = []

        for entity in self.graph.entities.values():
            if entity.start_date and entity.start_date.year == year:
                entities.append(entity)
            elif entity.properties.get("year") == year:
                entities.append(entity)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.HISTORICAL,
            entities=entities,
            context=f"Events in {year}: {len(entities)} found",
            sources=list(set(s for e in entities for s in e.sources)),
        )

    def _query_economic_indicator(self, match) -> QueryResult:
        """Query economic indicators."""
        year = match.group(1) if match.lastindex else None
        query_text = match.group(0).lower()
        entities = []

        # Determine which indicator
        indicator_type = None
        if "interest" in query_text:
            indicator_type = "interest rate"
        elif "inflation" in query_text:
            indicator_type = "inflation"
        elif "exchange" in query_text:
            indicator_type = "exchange rate"

        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.ECONOMIC_SECTOR:
                continue

            entity_indicator = entity.properties.get("indicator_type", "").lower()
            entity_year = entity.properties.get("year")

            if indicator_type and indicator_type not in entity_indicator:
                continue
            if year and str(entity_year) != str(year):
                continue

            entities.append(entity)

        # Sort by year
        entities.sort(key=lambda e: e.properties.get("year", 0))

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.FINANCIAL,
            entities=entities,
            context=f"Economic data: {len(entities)} records found",
            sources=["budgit", "cbn"],
        )

    def _query_budget(self, match) -> QueryResult:
        """Query budget data."""
        subject = match.group(1).strip()
        entities = []

        for entity in self.graph.entities.values():
            if entity.entity_type != EntityType.REPORT:
                continue
            if entity.properties.get("category") in ["budget", "state_expenditure"]:
                if not subject or subject.lower() in entity.name.lower():
                    entities.append(entity)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.FINANCIAL,
            entities=entities,
            context=f"Budget data for {subject}: {len(entities)} datasets found",
            sources=["budgit"],
        )

    def _query_faac(self, match) -> QueryResult:
        """Query Federal Account Allocation Committee data."""
        location = match.group(1).strip() if match.lastindex else None
        entities = []

        for entity in self.graph.entities.values():
            if entity.entity_type == EntityType.REPORT:
                if "faac" in entity.name.lower() or "allocation" in entity.name.lower():
                    entities.append(entity)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.FINANCIAL,
            entities=entities,
            context=f"FAAC allocation data{' for ' + location if location else ''}: {len(entities)} datasets",
            sources=["budgit"],
        )

    def _query_compare(self, match) -> QueryResult:
        """Compare two politicians."""
        entity1_name = match.group(1).strip()
        entity2_name = match.group(2).strip()

        entity1 = self.graph.find_entity(entity1_name)
        entity2 = self.graph.find_entity(entity2_name)

        entities = []
        if entity1:
            entities.append(entity1)
        if entity2:
            entities.append(entity2)

        return QueryResult(
            success=len(entities) == 2,
            query_type=QueryType.COMPARISON,
            entities=entities,
            context=f"Comparison: {entity1_name} vs {entity2_name}",
            sources=list(set(s for e in entities for s in e.sources)) if entities else [],
        )

    def _query_politician_news(self, match) -> QueryResult:
        """Find news articles mentioning a politician."""
        politician_name = match.group(1).strip()
        entities = []
        relationships = []
        sources = []

        # First, find the politician
        politician_entity = self.graph.find_entity(politician_name)

        if not politician_entity:
            # Try searching by partial name
            for entity in self.graph.entities.values():
                if entity.entity_type == EntityType.POLITICIAN:
                    if politician_name.lower() in entity.name.lower():
                        politician_entity = entity
                        break

        if not politician_entity:
            return QueryResult(
                success=False,
                query_type=QueryType.RELATIONSHIP,
                context=f"Politician '{politician_name}' not found in knowledge graph",
                confidence=0.0,
            )

        entities.append(politician_entity)

        # Get MENTIONED_IN relationships (outgoing from politician)
        news_relationships = self.graph.get_relationships(
            politician_entity.id,
            relation_type=RelationType.MENTIONED_IN,
            direction="outgoing"
        )

        # Get article entities
        article_entities = []
        for source_id, target_id, data in news_relationships[:10]:
            article_entity = self.graph.get_entity(target_id)
            if article_entity:
                article_entities.append(article_entity)
                relationships.append({
                    "source_name": politician_entity.name,
                    "relation": "mentioned_in",
                    "target_name": article_entity.name,
                    "mention_type": data.get("mention_type", "mentioned"),
                })
                sources.extend(article_entity.sources)

        entities.extend(article_entities)

        return QueryResult(
            success=len(article_entities) > 0,
            query_type=QueryType.RELATIONSHIP,
            entities=entities,
            relationships=relationships,
            context=f"Found {len(article_entities)} news articles mentioning {politician_entity.name}",
            confidence=0.85,
            sources=sources,
        )

    def _query_trending_politicians(self, match) -> QueryResult:
        """Find politicians frequently mentioned in recent news."""
        # Count news mentions per politician
        mention_counts = {}

        for entity_id, entity in self.graph.entities.items():
            if entity.entity_type == EntityType.POLITICIAN:
                # Count MENTIONED_IN relationships
                relationships = self.graph.get_relationships(
                    entity_id,
                    relation_type=RelationType.MENTIONED_IN,
                    direction="outgoing"
                )
                if relationships:
                    mention_counts[entity_id] = len(relationships)

        # Sort by mention count
        sorted_politicians = sorted(
            mention_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        entities = []
        for entity_id, count in sorted_politicians:
            entity = self.graph.get_entity(entity_id)
            if entity:
                # Add mention count to properties for context
                entity.properties["news_mention_count"] = count
                entities.append(entity)

        return QueryResult(
            success=len(entities) > 0,
            query_type=QueryType.LIST,
            entities=entities,
            context=f"Top {len(entities)} politicians mentioned in news",
            confidence=0.8,
            sources=["news_articles"],
        )

    def _query_co_mentioned(self, match) -> QueryResult:
        """Find politicians frequently mentioned alongside another."""
        politician_name = match.group(1).strip()

        # Find the politician
        politician_entity = self.graph.find_entity(politician_name)
        if not politician_entity:
            return QueryResult(
                success=False,
                query_type=QueryType.RELATIONSHIP,
                context=f"Politician '{politician_name}' not found",
                confidence=0.0,
            )

        # Get articles mentioning this politician
        news_relationships = self.graph.get_relationships(
            politician_entity.id,
            relation_type=RelationType.MENTIONED_IN,
            direction="outgoing"
        )

        article_ids = {target_id for _, target_id, _ in news_relationships}

        # Find other politicians in those articles
        co_mention_counts = {}
        for article_id in article_ids:
            # Get incoming MENTIONED_IN edges to this article
            incoming = self.graph.get_relationships(
                article_id,
                relation_type=RelationType.MENTIONED_IN,
                direction="incoming"
            )

            for source_id, _, _ in incoming:
                if source_id != politician_entity.id and source_id.startswith("politician_"):
                    co_mention_counts[source_id] = co_mention_counts.get(source_id, 0) + 1

        # Get top co-mentioned politicians
        sorted_co_mentions = sorted(
            co_mention_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        entities = [politician_entity]  # Include original politician
        relationships = []

        for entity_id, count in sorted_co_mentions:
            entity = self.graph.get_entity(entity_id)
            if entity:
                entity.properties["co_mention_count"] = count
                entities.append(entity)
                relationships.append({
                    "source_name": politician_entity.name,
                    "relation": f"co-mentioned {count} times with",
                    "target_name": entity.name,
                })

        return QueryResult(
            success=len(entities) > 1,
            query_type=QueryType.RELATIONSHIP,
            entities=entities,
            relationships=relationships,
            context=f"Politicians frequently mentioned with {politician_entity.name}",
            confidence=0.8,
            sources=["news_articles"],
        )

    def _fuzzy_search(self, query: str) -> QueryResult:
        """Fallback fuzzy search across all entities."""
        query_lower = query.lower()
        matches = []

        for entity in self.graph.entities.values():
            score = 0

            # Check name
            if query_lower in entity.name.lower():
                score += 10

            # Check aliases
            for alias in entity.aliases:
                if query_lower in alias.lower():
                    score += 8

            # Check properties
            for value in entity.properties.values():
                if isinstance(value, str) and query_lower in value.lower():
                    score += 3
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and query_lower in item.lower():
                            score += 2

            if score > 0:
                matches.append((score, entity))

        # Sort by score
        matches.sort(key=lambda x: x[0], reverse=True)
        top_matches = [entity for _, entity in matches[:10]]

        return QueryResult(
            success=len(top_matches) > 0,
            query_type=QueryType.ENTITY_LOOKUP,
            entities=top_matches,
            context=f"Search results for '{query}': {len(top_matches)} matches",
            confidence=0.7 if top_matches else 0.0,
            sources=list(set(s for e in top_matches for s in e.sources)),
        )


# Convenience function for direct queries
def query_knowledge(query: str) -> QueryResult:
    """Query the knowledge graph with a natural language question."""
    engine = QueryEngine()
    return engine.query(query)


# For import
from datetime import date
