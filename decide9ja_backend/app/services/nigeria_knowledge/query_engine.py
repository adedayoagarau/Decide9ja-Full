"""
Nigeria Knowledge Query Engine

Provides natural language query capabilities over the knowledge graph,
including the built entities from Wikipedia, Wikidata, Excel financial data,
news, and Internet Archive documents.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Path to knowledge graph data
DATA_DIR = Path(__file__).parent.parent.parent.parent / "nigeria_knowledge_data" / "knowledge_graph"


class QueryEngine:
    """
    Query engine for the Nigeria Knowledge Graph.

    Supports queries like:
    - "Who was the president in 1999?"
    - "What was Nigeria's GDP in 2015?"
    - "Tell me about Olusegun Obasanjo"
    - "What happened during the civil war?"
    - "Show me economic data for Lagos"
    """

    def __init__(self):
        self.entities: Dict[str, Dict] = {}
        self.relationships: List[Dict] = []
        self.search_index: Dict[str, List[str]] = {}
        self.loaded = False
        self._load_knowledge_graph()

    def _load_knowledge_graph(self):
        """Load the built knowledge graph from disk"""
        try:
            # Find the latest files
            latest_file = DATA_DIR / "latest.json"

            if not latest_file.exists():
                # Try to find any entities file
                entities_files = list(DATA_DIR.glob("entities_*.json"))
                if not entities_files:
                    logger.warning("No knowledge graph data found. Run build_knowledge_graph.py first.")
                    return

                # Use most recent
                entities_file = max(entities_files, key=lambda f: f.stat().st_mtime)
                index_files = list(DATA_DIR.glob("search_index_*.json"))
                index_file = max(index_files, key=lambda f: f.stat().st_mtime) if index_files else None
                rel_files = list(DATA_DIR.glob("relationships_*.json"))
                rel_file = max(rel_files, key=lambda f: f.stat().st_mtime) if rel_files else None
            else:
                with open(latest_file, encoding="utf-8") as f:
                    latest = json.load(f)

                entities_file = Path(latest.get("entities_file", ""))
                index_file = Path(latest.get("index_file", ""))
                rel_file = Path(latest.get("relationships_file", ""))

            # Load entities
            if entities_file and entities_file.exists():
                with open(entities_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.entities = data.get("entities", {})
                logger.info(f"Loaded {len(self.entities)} entities from knowledge graph")

            # Load relationships
            if rel_file and rel_file.exists():
                with open(rel_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.relationships = data.get("relationships", [])
                logger.info(f"Loaded {len(self.relationships)} relationships")

            # Load search index
            if index_file and index_file.exists():
                with open(index_file, encoding="utf-8") as f:
                    self.search_index = json.load(f)
                logger.info(f"Loaded search index with {len(self.search_index.get('by_name', {}))} name entries")

            self.loaded = bool(self.entities)

        except Exception as e:
            logger.error(f"Error loading knowledge graph: {e}")
            self.loaded = False

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for entities matching the query.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching entities with relevance scores
        """
        if not self.loaded:
            return []

        query_lower = query.lower()
        query_words = set(query_lower.split())

        results = []
        seen_ids = set()

        # Search by name index
        by_name = self.search_index.get("by_name", {})

        # Exact match
        if query_lower in by_name:
            for entity_id in by_name[query_lower]:
                if entity_id not in seen_ids and entity_id in self.entities:
                    seen_ids.add(entity_id)
                    results.append({
                        "entity": self.entities[entity_id],
                        "score": 1.0,
                        "match_type": "exact"
                    })

        # Word matches
        for word in query_words:
            if len(word) < 3:
                continue
            if word in by_name:
                for entity_id in by_name[word]:
                    if entity_id not in seen_ids and entity_id in self.entities:
                        seen_ids.add(entity_id)
                        results.append({
                            "entity": self.entities[entity_id],
                            "score": 0.7,
                            "match_type": "word"
                        })

        # Partial match search
        for name, entity_ids in by_name.items():
            if query_lower in name or name in query_lower:
                for entity_id in entity_ids:
                    if entity_id not in seen_ids and entity_id in self.entities:
                        seen_ids.add(entity_id)
                        results.append({
                            "entity": self.entities[entity_id],
                            "score": 0.5,
                            "match_type": "partial"
                        })

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def search_by_type(self, entity_type: str, limit: int = 20) -> List[Dict]:
        """Search entities by type"""
        if not self.loaded:
            return []

        by_type = self.search_index.get("by_type", {})
        entity_ids = by_type.get(entity_type, [])

        results = []
        for entity_id in entity_ids[:limit]:
            if entity_id in self.entities:
                results.append(self.entities[entity_id])

        return results

    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get a specific entity by ID"""
        return self.entities.get(entity_id)

    def get_related(self, entity_id: str, limit: int = 10) -> List[Dict]:
        """Get entities related to the given entity"""
        related = []
        seen = set()

        for rel in self.relationships:
            if rel.get("source") == entity_id:
                target_id = rel.get("target")
                if target_id not in seen and target_id in self.entities:
                    seen.add(target_id)
                    related.append({
                        "entity": self.entities[target_id],
                        "relation": rel.get("type"),
                        "direction": "outgoing"
                    })
            elif rel.get("target") == entity_id:
                source_id = rel.get("source")
                if source_id not in seen and source_id in self.entities:
                    seen.add(source_id)
                    related.append({
                        "entity": self.entities[source_id],
                        "relation": rel.get("type"),
                        "direction": "incoming"
                    })

        return related[:limit]

    def query_financial_data(
        self,
        indicator: Optional[str] = None,
        year: Optional[int] = None,
        state: Optional[str] = None
    ) -> List[Dict]:
        """
        Query financial/economic data from Excel imports.

        Args:
            indicator: Economic indicator name (gdp, inflation, budget, etc.)
            year: Specific year
            state: State name for state-level data
        """
        results = []

        # Keywords that indicate economic data
        economic_keywords = ["gdp", "inflation", "budget", "revenue", "expenditure",
                           "debt", "growth", "fiscal", "monetary", "trade", "export",
                           "import", "oil", "gas", "agriculture", "sector"]

        # Search for economic indicators
        for entity_id, entity in self.entities.items():
            entity_type = entity.get("type", "")

            # Include explicit economic types
            if entity_type in ["economic_indicator", "budget_data", "state_financial_data", "sector_data"]:
                # Filter by indicator name if specified
                if indicator:
                    name = entity.get("name", "").lower()
                    columns = " ".join(entity.get("columns", [])).lower()
                    if indicator.lower() not in name and indicator.lower() not in columns:
                        continue

                # Filter by state if specified
                if state:
                    name = entity.get("name", "").lower()
                    if state.lower() not in name:
                        continue

                results.append(entity)

            # Also search Wikipedia/archive for economic content
            elif indicator:
                name = entity.get("name", "").lower()
                content = entity.get("content", entity.get("content_preview", "")).lower()[:500]
                search_term = indicator.lower()

                # Check if it's an economic topic
                if any(kw in search_term for kw in economic_keywords):
                    if search_term in name or search_term in content:
                        results.append(entity)

        return results

    def query_natural_language(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language query and return relevant results.

        Args:
            query: Natural language query

        Returns:
            Dict with results, context, and suggested follow-ups
        """
        query_lower = query.lower()

        # Detect query type
        query_type = self._classify_query(query_lower)

        response = {
            "query": query,
            "query_type": query_type,
            "results": [],
            "context": "",
            "sources": [],
            "follow_ups": []
        }

        if query_type == "person":
            # Search for person
            results = self.search(query, limit=5)
            if results:
                response["results"] = [r["entity"] for r in results]
                response["context"] = self._format_person_context(results[0]["entity"])
                response["sources"] = [results[0]["entity"].get("source", "knowledge_graph")]
                response["follow_ups"] = ["What is their political party?", "What positions have they held?"]

        elif query_type == "economic":
            # Search for economic data
            year_match = re.search(r'\b(19|20)\d{2}\b', query)
            year = int(year_match.group()) if year_match else None

            # First try to find specific economic data
            results = self.query_financial_data(indicator=query, year=year)

            # If no specific results, get all financial data
            if not results:
                results = self.query_financial_data()

            # Also search for general entities matching the query
            search_results = self.search(query, limit=5)
            for sr in search_results:
                if sr["entity"] not in results:
                    results.append(sr["entity"])

            if results:
                response["results"] = results[:8]
                response["context"] = self._format_economic_context(results)
                response["sources"] = ["excel_financial", "knowledge_graph"]
                response["follow_ups"] = ["How did this change over time?", "What about other economic indicators?"]

        elif query_type == "historical":
            # Search for historical events
            results = self.search(query, limit=5)
            if results:
                response["results"] = [r["entity"] for r in results]
                response["context"] = self._format_historical_context(results)
                response["sources"] = list(set(r["entity"].get("source", "") for r in results))
                response["follow_ups"] = ["What led to this?", "What happened after?"]

        elif query_type == "news":
            # Search news articles
            results = self._search_news(query)
            if results:
                response["results"] = results[:5]
                response["context"] = self._format_news_context(results)
                response["sources"] = ["news_rss"]
                response["follow_ups"] = ["Any more recent updates?", "What is the government saying?"]

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
        # Person indicators
        if any(word in query for word in ["who", "president", "governor", "senator", "minister", "chief"]):
            return "person"

        # Economic indicators
        if any(word in query for word in ["gdp", "inflation", "budget", "economy", "naira", "oil", "revenue", "debt"]):
            return "economic"

        # Historical indicators
        if any(word in query for word in ["history", "civil war", "independence", "colonial", "coup", "1960", "1966", "1967", "1999"]):
            return "historical"

        # News indicators
        if any(word in query for word in ["news", "recent", "today", "latest", "happening"]):
            return "news"

        return "general"

    def _search_news(self, query: str) -> List[Dict]:
        """Search news articles"""
        results = []
        query_lower = query.lower()

        for entity_id, entity in self.entities.items():
            if entity.get("type") != "news_article":
                continue

            name = entity.get("name", "").lower()
            content = entity.get("content", "").lower()

            if query_lower in name or query_lower in content:
                results.append(entity)

        return results

    def _format_person_context(self, entity: Dict) -> str:
        """Format person entity as context string"""
        name = entity.get("name", "Unknown")
        entity_type = entity.get("type", "person")
        description = entity.get("description", "")

        context = f"**{name}**"
        if entity_type:
            context += f" ({entity_type.replace('_', ' ').title()})"
        if description:
            context += f"\n\n{description}"

        # Add any additional properties
        for key in ["party", "position", "state", "birthDate", "deathDate"]:
            value = entity.get(key) or entity.get(f"{key}Label")
            if value:
                context += f"\n- {key.title()}: {value}"

        return context

    def _format_economic_context(self, results: List[Dict]) -> str:
        """Format economic data as context string"""
        if not results:
            return "No economic data found."

        context_parts = []
        for entity in results[:3]:
            name = entity.get("name", "")
            record_count = entity.get("record_count", 0)
            columns = entity.get("columns", [])

            part = f"**{name}**\n- Records: {record_count}"
            if columns:
                part += f"\n- Data fields: {', '.join(columns[:5])}"

            context_parts.append(part)

        return "\n\n".join(context_parts)

    def _format_historical_context(self, results: List[Dict]) -> str:
        """Format historical data as context string"""
        if not results:
            return "No historical information found."

        context_parts = []
        for result in results[:3]:
            entity = result["entity"]
            name = entity.get("name", "")
            content = entity.get("content", entity.get("content_preview", ""))[:500]

            part = f"**{name}**\n{content}"
            context_parts.append(part)

        return "\n\n---\n\n".join(context_parts)

    def _format_news_context(self, results: List[Dict]) -> str:
        """Format news articles as context string"""
        if not results:
            return "No recent news found."

        context_parts = []
        for article in results[:3]:
            title = article.get("name", "")
            content = article.get("content", "")[:300]
            source = article.get("source_name", "")
            published = article.get("published", "")

            part = f"**{title}**"
            if source:
                part += f" ({source})"
            if published:
                part += f" - {published}"
            if content:
                part += f"\n{content}..."

            context_parts.append(part)

        return "\n\n".join(context_parts)

    def _format_general_context(self, results: List[Dict]) -> str:
        """Format general search results as context"""
        if not results:
            return "No relevant information found."

        context_parts = []
        for result in results[:5]:
            entity = result["entity"]
            name = entity.get("name", "")
            entity_type = entity.get("type", "")

            part = f"• **{name}**"
            if entity_type:
                part += f" [{entity_type}]"

            context_parts.append(part)

        return "\n".join(context_parts)

    def get_stats(self) -> Dict:
        """Get statistics about the knowledge graph"""
        if not self.loaded:
            return {"loaded": False, "message": "Knowledge graph not loaded"}

        type_counts = {}
        source_counts = {}

        for entity in self.entities.values():
            # Count by type
            entity_type = entity.get("type", "unknown")
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

            # Count by source
            source = entity.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

        return {
            "loaded": True,
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
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
    """
    Convenience function to query the knowledge graph.

    Args:
        query: Natural language query

    Returns:
        Query results with context
    """
    engine = get_query_engine()
    return engine.query_natural_language(query)
