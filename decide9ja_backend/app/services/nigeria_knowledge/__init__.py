"""
Nigeria Knowledge System

A comprehensive knowledge graph and retrieval system for Nigerian history,
politics, governance, military, infrastructure, and society.

This module provides:
- Knowledge Graph: Relationships between people, events, organizations
- Historical Data: Curated Nigerian history from 1900 to present
- Entity Extraction: Extract entities from news and documents
- Archive Crawler: Ingest historical newspapers from archivi.ng
- OCR Pipeline: Process scanned documents
- Query Engine: Natural language queries over the knowledge graph
"""

from .knowledge_graph import (
    NigeriaKnowledgeGraph,
    Entity,
    Relationship,
    EntityType,
    RelationType,
    get_knowledge_graph,
)

from .entity_extractor import (
    EntityExtractor,
    ExtractedEntity,
    extract_entities_from_text,
)

from .query_engine import (
    QueryEngine,
    query_knowledge,
)

__all__ = [
    # Knowledge Graph
    "NigeriaKnowledgeGraph",
    "Entity",
    "Relationship",
    "EntityType",
    "RelationType",
    "get_knowledge_graph",

    # Entity Extraction
    "EntityExtractor",
    "ExtractedEntity",
    "extract_entities_from_text",

    # Query Engine
    "QueryEngine",
    "query_knowledge",
]
