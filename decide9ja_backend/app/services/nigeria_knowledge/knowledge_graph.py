"""
Nigeria Knowledge Graph

Core knowledge graph implementation using NetworkX for representing
relationships between Nigerian historical entities, events, and concepts.
"""

import networkx as nx
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, date
import json
import logging

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Types of entities in the knowledge graph"""
    # People
    PERSON = "person"
    POLITICIAN = "politician"
    MILITARY_OFFICER = "military_officer"
    ACTIVIST = "activist"
    JOURNALIST = "journalist"
    TRADITIONAL_RULER = "traditional_ruler"
    BUSINESSPERSON = "businessperson"

    # Organizations
    POLITICAL_PARTY = "political_party"
    GOVERNMENT_AGENCY = "government_agency"
    MILITARY_UNIT = "military_unit"
    COMPANY = "company"
    NEWSPAPER = "newspaper"
    UNIVERSITY = "university"
    NGO = "ngo"
    LABOR_UNION = "labor_union"

    # Places
    COUNTRY = "country"
    STATE = "state"
    LGA = "lga"
    CITY = "city"
    REGION = "region"
    CONSTITUENCY = "constituency"

    # Events
    ELECTION = "election"
    COUP = "coup"
    PROTEST = "protest"
    WAR = "war"
    POLICY = "policy"
    CRISIS = "crisis"
    TREATY = "treaty"
    INAUGURATION = "inauguration"
    TRIAL = "trial"

    # Concepts
    ERA = "era"
    IDEOLOGY = "ideology"
    ETHNIC_GROUP = "ethnic_group"
    RELIGION = "religion"
    ECONOMIC_SECTOR = "economic_sector"

    # Documents
    CONSTITUTION = "constitution"
    LAW = "law"
    REPORT = "report"
    SPEECH = "speech"
    NEWSPAPER_ARTICLE = "newspaper_article"


class RelationType(Enum):
    """Types of relationships between entities"""
    # Political relationships
    MEMBER_OF = "member_of"
    LEADER_OF = "leader_of"
    FOUNDED = "founded"
    SUCCEEDED = "succeeded"
    PRECEDED = "preceded"
    ALLIED_WITH = "allied_with"
    OPPOSED = "opposed"
    APPOINTED = "appointed"
    REMOVED = "removed"
    ELECTED_IN = "elected_in"
    CONTESTED = "contested"

    # Hierarchical
    PART_OF = "part_of"
    CONTAINS = "contains"
    REPORTS_TO = "reports_to"
    CONTROLS = "controls"

    # Temporal
    OCCURRED_IN = "occurred_in"
    STARTED_IN = "started_in"
    ENDED_IN = "ended_in"
    DURING = "during"
    CAUSED = "caused"
    RESULTED_IN = "resulted_in"

    # Geographic
    LOCATED_IN = "located_in"
    BORN_IN = "born_in"
    DIED_IN = "died_in"
    GOVERNED = "governed"
    REPRESENTS = "represents"

    # Social
    MARRIED_TO = "married_to"
    CHILD_OF = "child_of"
    SIBLING_OF = "sibling_of"
    MENTORED = "mentored"
    STUDIED_AT = "studied_at"
    WORKED_AT = "worked_at"

    # Events
    PARTICIPATED_IN = "participated_in"
    ORGANIZED = "organized"
    VICTIM_OF = "victim_of"
    BENEFICIARY_OF = "beneficiary_of"

    # Documents
    AUTHORED = "authored"
    SIGNED = "signed"
    MENTIONED_IN = "mentioned_in"
    QUOTED_IN = "quoted_in"

    # Ethnic/Religious
    BELONGS_TO_ETHNIC = "belongs_to_ethnic"
    PRACTICES_RELIGION = "practices_religion"


@dataclass
class Entity:
    """An entity in the knowledge graph"""
    id: str
    name: str
    entity_type: EntityType
    properties: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)

    # Temporal bounds
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # Source tracking
    sources: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.entity_type.value,
            "properties": self.properties,
            "aliases": self.aliases,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "sources": self.sources,
            "confidence": self.confidence,
        }


@dataclass
class Relationship:
    """A relationship between two entities"""
    source_id: str
    target_id: str
    relation_type: RelationType
    properties: Dict[str, Any] = field(default_factory=dict)

    # Temporal bounds for the relationship
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # Source tracking
    sources: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.relation_type.value,
            "properties": self.properties,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "sources": self.sources,
            "confidence": self.confidence,
        }


class NigeriaKnowledgeGraph:
    """
    Comprehensive knowledge graph for Nigerian history, politics,
    governance, military, infrastructure, and society.
    """

    def __init__(self):
        self.graph = nx.MultiDiGraph()  # MultiDiGraph allows multiple edges between nodes
        self.entities: Dict[str, Entity] = {}
        self.name_index: Dict[str, str] = {}  # name/alias -> entity_id

        # Statistics
        self.stats = {
            "entities_added": 0,
            "relationships_added": 0,
            "last_updated": None,
        }

        # Seed with historical data
        self._seed_historical_data()

    def add_entity(self, entity: Entity) -> str:
        """Add an entity to the graph"""
        self.entities[entity.id] = entity

        # Add to graph
        self.graph.add_node(
            entity.id,
            name=entity.name,
            type=entity.entity_type.value,
            **entity.properties
        )

        # Index by name and aliases
        self.name_index[entity.name.lower()] = entity.id
        for alias in entity.aliases:
            self.name_index[alias.lower()] = entity.id

        self.stats["entities_added"] += 1
        self.stats["last_updated"] = datetime.now().isoformat()

        return entity.id

    def add_relationship(self, relationship: Relationship) -> bool:
        """Add a relationship between entities"""
        if relationship.source_id not in self.entities:
            logger.warning(f"Source entity {relationship.source_id} not found")
            return False
        if relationship.target_id not in self.entities:
            logger.warning(f"Target entity {relationship.target_id} not found")
            return False

        self.graph.add_edge(
            relationship.source_id,
            relationship.target_id,
            relation=relationship.relation_type.value,
            **relationship.properties
        )

        self.stats["relationships_added"] += 1
        self.stats["last_updated"] = datetime.now().isoformat()

        return True

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID"""
        return self.entities.get(entity_id)

    def find_entity(self, name: str) -> Optional[Entity]:
        """Find an entity by name or alias"""
        entity_id = self.name_index.get(name.lower())
        if entity_id:
            return self.entities.get(entity_id)

        # Fuzzy match
        for indexed_name, eid in self.name_index.items():
            if name.lower() in indexed_name or indexed_name in name.lower():
                return self.entities.get(eid)

        return None

    def get_relationships(
        self,
        entity_id: str,
        relation_type: Optional[RelationType] = None,
        direction: str = "both"  # "outgoing", "incoming", "both"
    ) -> List[Tuple[str, str, Dict]]:
        """Get relationships for an entity"""
        relationships = []

        if direction in ("outgoing", "both"):
            for _, target, data in self.graph.out_edges(entity_id, data=True):
                if relation_type is None or data.get("relation") == relation_type.value:
                    relationships.append((entity_id, target, data))

        if direction in ("incoming", "both"):
            for source, _, data in self.graph.in_edges(entity_id, data=True):
                if relation_type is None or data.get("relation") == relation_type.value:
                    relationships.append((source, entity_id, data))

        return relationships

    def get_entity_context(self, entity_id: str, depth: int = 2) -> Dict:
        """Get full context for an entity including related entities"""
        entity = self.get_entity(entity_id)
        if not entity:
            return {}

        context = {
            "entity": entity.to_dict(),
            "relationships": [],
            "related_entities": {},
        }

        # BFS to get related entities up to depth
        visited = {entity_id}
        queue = [(entity_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)
            if current_depth >= depth:
                continue

            for rel in self.get_relationships(current_id):
                source, target, data = rel
                other_id = target if source == current_id else source

                context["relationships"].append({
                    "source": source,
                    "target": target,
                    "relation": data.get("relation"),
                })

                if other_id not in visited:
                    visited.add(other_id)
                    other_entity = self.get_entity(other_id)
                    if other_entity:
                        context["related_entities"][other_id] = other_entity.to_dict()
                        queue.append((other_id, current_depth + 1))

        return context

    def query_by_type(
        self,
        entity_type: EntityType,
        filters: Optional[Dict] = None
    ) -> List[Entity]:
        """Query entities by type with optional filters"""
        results = []
        for entity in self.entities.values():
            if entity.entity_type != entity_type:
                continue

            if filters:
                match = True
                for key, value in filters.items():
                    if entity.properties.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            results.append(entity)

        return results

    def query_by_era(self, era: str) -> List[Entity]:
        """Get all entities from a specific era"""
        era_mapping = {
            "pre_colonial": (None, date(1861, 1, 1)),
            "colonial": (date(1861, 1, 1), date(1960, 10, 1)),
            "first_republic": (date(1960, 10, 1), date(1966, 1, 15)),
            "civil_war": (date(1967, 7, 6), date(1970, 1, 15)),
            "military_1": (date(1966, 1, 15), date(1979, 10, 1)),
            "second_republic": (date(1979, 10, 1), date(1983, 12, 31)),
            "military_2": (date(1983, 12, 31), date(1999, 5, 29)),
            "fourth_republic": (date(1999, 5, 29), None),
        }

        if era.lower() not in era_mapping:
            return []

        start, end = era_mapping[era.lower()]
        results = []

        for entity in self.entities.values():
            # Check if entity's timeframe overlaps with era
            entity_start = entity.start_date
            entity_end = entity.end_date or date.today()

            if entity_start is None:
                # No date info, check properties
                if entity.properties.get("era", "").lower() == era.lower():
                    results.append(entity)
                continue

            era_start = start or date(1800, 1, 1)
            era_end = end or date.today()

            if entity_start <= era_end and entity_end >= era_start:
                results.append(entity)

        return results

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5
    ) -> Optional[List[str]]:
        """Find shortest path between two entities"""
        try:
            path = nx.shortest_path(
                self.graph.to_undirected(),
                source_id,
                target_id
            )
            if len(path) <= max_depth:
                return path
        except nx.NetworkXNoPath:
            pass
        return None

    def get_statistics(self) -> Dict:
        """Get graph statistics"""
        type_counts = {}
        for entity in self.entities.values():
            t = entity.entity_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_entities": len(self.entities),
            "total_relationships": self.graph.number_of_edges(),
            "entity_types": type_counts,
            "last_updated": self.stats["last_updated"],
        }

    def export_to_json(self, filepath: str):
        """Export graph to JSON file"""
        data = {
            "entities": [e.to_dict() for e in self.entities.values()],
            "relationships": [
                {
                    "source": u,
                    "target": v,
                    **d
                }
                for u, v, d in self.graph.edges(data=True)
            ],
            "statistics": self.get_statistics(),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _seed_historical_data(self):
        """Seed the graph with comprehensive Nigerian historical data"""
        from .historical_data import seed_knowledge_graph
        seed_knowledge_graph(self)


# Singleton instance
_knowledge_graph: Optional[NigeriaKnowledgeGraph] = None


def get_knowledge_graph() -> NigeriaKnowledgeGraph:
    """Get the singleton knowledge graph instance"""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = NigeriaKnowledgeGraph()
    return _knowledge_graph
