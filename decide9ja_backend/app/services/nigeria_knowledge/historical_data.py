"""
Historical Data Seeder for Nigeria Knowledge Graph

Seeds the knowledge graph with comprehensive Nigerian data from:
- Wikidata (politicians, states, parties, military officers, events)
- Wikipedia articles (historical events, coups, biographies)
- INEC scraped data (LGAs, senatorial districts, election results)
- BudgIT financial data (budgets, allocations, projects)

This module transforms raw collected data into graph entities and relationships.
"""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .knowledge_graph import (
    NigeriaKnowledgeGraph,
    Entity,
    Relationship,
    EntityType,
    RelationType,
)

logger = logging.getLogger(__name__)

# Base path for knowledge data
KNOWLEDGE_DATA_PATH = Path(__file__).parent.parent.parent.parent / "nigeria_knowledge_data"


def seed_knowledge_graph(graph: NigeriaKnowledgeGraph) -> Dict[str, int]:
    """
    Seed the knowledge graph with all available Nigerian data.

    Returns:
        Dict with counts of entities and relationships added
    """
    stats = {
        "politicians": 0,
        "states": 0,
        "lgas": 0,
        "parties": 0,
        "events": 0,
        "economic_data": 0,
        "budget_data": 0,
        "relationships": 0,
    }

    try:
        # 1. Load core geographic entities first (states, LGAs)
        stats["states"] = _seed_states(graph)
        stats["lgas"] = _seed_lgas(graph)

        # 2. Load political parties
        stats["parties"] = _seed_parties(graph)

        # 3. Load politicians from Wikidata
        stats["politicians"] = _seed_politicians(graph)

        # 4. Load historical events from Wikipedia
        stats["events"] = _seed_events(graph)

        # 5. Load economic/budget data from BudgIT
        stats["economic_data"] = _seed_economic_data(graph)
        stats["budget_data"] = _seed_budget_data(graph)

        # 6. Create relationships between entities
        stats["relationships"] = _create_relationships(graph)

        logger.info(f"Knowledge graph seeded: {stats}")

    except Exception as e:
        logger.error(f"Error seeding knowledge graph: {e}")

    return stats


def _load_json(filename: str, subfolder: str = "") -> Optional[Dict]:
    """Load a JSON file from the knowledge data directory."""
    if subfolder:
        path = KNOWLEDGE_DATA_PATH / subfolder / filename
    else:
        path = KNOWLEDGE_DATA_PATH / filename

    if not path.exists():
        logger.warning(f"File not found: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {path}: {e}")
        return None


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse various date formats to date object."""
    if not date_str:
        return None
    try:
        # Handle ISO format with time (Wikidata format)
        if "T" in str(date_str):
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        # Handle year only
        if len(str(date_str)) == 4:
            return date(int(date_str), 1, 1)
        return None
    except:
        return None


def _seed_states(graph: NigeriaKnowledgeGraph) -> int:
    """Seed Nigerian states from Wikidata and scraped data."""
    count = 0

    # Try wikidata first
    wikidata = _load_json("nigerian_states.json", "wikidata")
    if wikidata and "results" in wikidata:
        for item in wikidata["results"]:
            entity_id = f"state_{item.get('stateLabel', '').lower().replace(' ', '_')}"
            entity = Entity(
                id=entity_id,
                name=item.get("stateLabel", ""),
                entity_type=EntityType.STATE,
                properties={
                    "wikidata_id": item.get("state", "").split("/")[-1] if item.get("state") else None,
                    "capital": item.get("capitalLabel"),
                    "population": item.get("population"),
                    "area": item.get("area"),
                    "governor": item.get("governorLabel"),
                    "geopolitical_zone": item.get("zoneLabel"),
                },
                aliases=[],
                sources=["wikidata"],
            )
            graph.add_entity(entity)
            count += 1

    # Also load from INEC scraped data for more details
    inec_states = _load_json("states.json", "../decide9ja_scraper/data/processed")
    if inec_states:
        # Merge with existing state entities
        pass

    logger.info(f"Seeded {count} states")
    return count


def _seed_lgas(graph: NigeriaKnowledgeGraph) -> int:
    """Seed Local Government Areas."""
    count = 0

    # Load from INEC scraped data
    lgas_data = _load_json("lgas.json", "../decide9ja_scraper/data/processed")
    if not lgas_data:
        # Try alternate path
        lga_path = KNOWLEDGE_DATA_PATH.parent / "decide9ja_scraper" / "data" / "processed" / "lgas.json"
        if lga_path.exists():
            with open(lga_path) as f:
                lgas_data = json.load(f)

    if lgas_data:
        for lga in lgas_data if isinstance(lgas_data, list) else lgas_data.get("lgas", []):
            lga_name = lga.get("name", "") if isinstance(lga, dict) else lga
            state_name = lga.get("state", "") if isinstance(lga, dict) else ""

            entity_id = f"lga_{lga_name.lower().replace(' ', '_')}_{state_name.lower().replace(' ', '_')}"
            entity = Entity(
                id=entity_id,
                name=lga_name,
                entity_type=EntityType.LGA,
                properties={
                    "state": state_name,
                    "senatorial_district": lga.get("senatorial_district") if isinstance(lga, dict) else None,
                    "federal_constituency": lga.get("federal_constituency") if isinstance(lga, dict) else None,
                },
                sources=["inec"],
            )
            graph.add_entity(entity)
            count += 1

    logger.info(f"Seeded {count} LGAs")
    return count


def _seed_parties(graph: NigeriaKnowledgeGraph) -> int:
    """Seed political parties."""
    count = 0

    wikidata = _load_json("nigerian_political_parties.json", "wikidata")
    if wikidata and "results" in wikidata:
        seen_parties = set()
        for item in wikidata["results"]:
            party_name = item.get("partyLabel", "")
            if party_name in seen_parties:
                continue
            seen_parties.add(party_name)

            entity_id = f"party_{party_name.lower().replace(' ', '_')}"
            entity = Entity(
                id=entity_id,
                name=party_name,
                entity_type=EntityType.POLITICAL_PARTY,
                properties={
                    "wikidata_id": item.get("party", "").split("/")[-1] if item.get("party") else None,
                    "acronym": item.get("acronym"),
                    "founded": item.get("founded"),
                    "ideology": item.get("ideologyLabel"),
                    "chairman": item.get("chairmanLabel"),
                },
                aliases=[item.get("acronym")] if item.get("acronym") else [],
                sources=["wikidata"],
            )
            graph.add_entity(entity)
            count += 1

    logger.info(f"Seeded {count} political parties")
    return count


def _seed_politicians(graph: NigeriaKnowledgeGraph) -> int:
    """Seed politicians from Wikidata."""
    count = 0
    seen_politicians = {}  # Track by wikidata ID to merge duplicates

    wikidata = _load_json("nigerian_politicians.json", "wikidata")
    if wikidata and "results" in wikidata:
        for item in wikidata["results"]:
            wikidata_id = item.get("person", "").split("/")[-1] if item.get("person") else None
            if not wikidata_id:
                continue

            # If we've seen this politician, merge positions/parties
            if wikidata_id in seen_politicians:
                existing = seen_politicians[wikidata_id]
                # Add new position
                if item.get("positionLabel"):
                    positions = existing.properties.get("positions", [])
                    if item["positionLabel"] not in positions:
                        positions.append(item["positionLabel"])
                        existing.properties["positions"] = positions
                # Add new party affiliation
                if item.get("partyLabel"):
                    parties = existing.properties.get("party_history", [])
                    if item["partyLabel"] not in parties:
                        parties.append(item["partyLabel"])
                        existing.properties["party_history"] = parties
                continue

            entity_id = f"politician_{wikidata_id}"
            entity = Entity(
                id=entity_id,
                name=item.get("personLabel", ""),
                entity_type=EntityType.POLITICIAN,
                properties={
                    "wikidata_id": wikidata_id,
                    "description": item.get("personDescription"),
                    "positions": [item.get("positionLabel")] if item.get("positionLabel") else [],
                    "current_party": item.get("partyLabel"),
                    "party_history": [item.get("partyLabel")] if item.get("partyLabel") else [],
                    "gender": item.get("genderLabel"),
                    "image_url": item.get("image"),
                    "state": item.get("stateLabel"),
                    "constituency": item.get("constituencyLabel"),
                },
                start_date=_parse_date(item.get("birthDate")),
                end_date=_parse_date(item.get("deathDate")),
                sources=["wikidata"],
            )
            graph.add_entity(entity)
            seen_politicians[wikidata_id] = entity
            count += 1

    # Also load military officers
    military = _load_json("nigerian_military_officers.json", "wikidata")
    if military and "results" in military:
        for item in military["results"]:
            wikidata_id = item.get("person", "").split("/")[-1] if item.get("person") else None
            if not wikidata_id or wikidata_id in seen_politicians:
                continue

            entity_id = f"military_{wikidata_id}"
            entity = Entity(
                id=entity_id,
                name=item.get("personLabel", ""),
                entity_type=EntityType.MILITARY_OFFICER,
                properties={
                    "wikidata_id": wikidata_id,
                    "description": item.get("personDescription"),
                    "rank": item.get("rankLabel"),
                    "service_branch": item.get("branchLabel"),
                },
                start_date=_parse_date(item.get("birthDate")),
                end_date=_parse_date(item.get("deathDate")),
                sources=["wikidata"],
            )
            graph.add_entity(entity)
            count += 1

    logger.info(f"Seeded {count} politicians and military officers")
    return count


def _seed_events(graph: NigeriaKnowledgeGraph) -> int:
    """Seed historical events from Wikipedia articles."""
    count = 0
    wikipedia_path = KNOWLEDGE_DATA_PATH / "wikipedia"

    if not wikipedia_path.exists():
        return count

    # Categorize events by type based on filename patterns
    event_patterns = {
        "coup": EntityType.COUP,
        "election": EntityType.ELECTION,
        "war": EntityType.WAR,
        "crisis": EntityType.CRISIS,
        "riot": EntityType.PROTEST,
        "protest": EntityType.PROTEST,
    }

    for json_file in wikipedia_path.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Determine event type from filename
            filename_lower = json_file.stem.lower()
            event_type = EntityType.POLICY  # default
            for pattern, etype in event_patterns.items():
                if pattern in filename_lower:
                    event_type = etype
                    break

            # Extract year from filename if present
            year_match = None
            for part in filename_lower.split("_"):
                if part.isdigit() and len(part) == 4:
                    year_match = int(part)
                    break

            entity_id = f"event_{json_file.stem}"
            entity = Entity(
                id=entity_id,
                name=data.get("title", json_file.stem.replace("_", " ")),
                entity_type=event_type,
                properties={
                    "wikipedia_id": data.get("pageid"),
                    "summary": data.get("extract", "")[:1000],  # First 1000 chars
                    "full_text": data.get("extract"),
                    "url": data.get("fullurl"),
                    "year": year_match,
                },
                start_date=date(year_match, 1, 1) if year_match else None,
                sources=["wikipedia"],
            )
            graph.add_entity(entity)
            count += 1

        except Exception as e:
            logger.warning(f"Error processing {json_file}: {e}")
            continue

    logger.info(f"Seeded {count} historical events from Wikipedia")
    return count


def _seed_economic_data(graph: NigeriaKnowledgeGraph) -> int:
    """Seed economic indicators from BudgIT data."""
    count = 0

    # Find the categorized BudgIT file
    excel_path = KNOWLEDGE_DATA_PATH / "excel_imports"
    if not excel_path.exists():
        return count

    for json_file in excel_path.glob("*_categorized_*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            categorized = data.get("categorized", {})

            # Process economic indicators
            for sheet_data in categorized.get("economic_indicators", []):
                sheet_name = sheet_data.get("sheet_name", "")
                for record in sheet_data.get("records", []):
                    year = record.get("YEAR")
                    indicator = record.get("INDICATOR", sheet_name)
                    value = record.get("VALUE (%)") or record.get("VALUE") or record.get("RATE")

                    if not year or not value:
                        continue

                    entity_id = f"economic_{indicator.lower().replace(' ', '_')}_{year}"
                    entity = Entity(
                        id=entity_id,
                        name=f"{indicator} ({year})",
                        entity_type=EntityType.ECONOMIC_SECTOR,
                        properties={
                            "indicator_type": indicator,
                            "year": year,
                            "value": value,
                            "source": record.get("SOURCE", "BudgIT"),
                            "unit": "%" if "%" in str(sheet_data.get("columns", [])) else None,
                        },
                        start_date=date(int(year), 1, 1) if year else None,
                        sources=["budgit"],
                    )
                    graph.add_entity(entity)
                    count += 1

        except Exception as e:
            logger.warning(f"Error processing {json_file}: {e}")
            continue

    logger.info(f"Seeded {count} economic indicators")
    return count


def _seed_budget_data(graph: NigeriaKnowledgeGraph) -> int:
    """Seed budget and allocation data from BudgIT."""
    count = 0

    excel_path = KNOWLEDGE_DATA_PATH / "excel_imports"
    if not excel_path.exists():
        return count

    for json_file in excel_path.glob("*_categorized_*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            categorized = data.get("categorized", {})

            # Process budget data - create summary entities, not individual records
            for sheet_data in categorized.get("budget_data", []):
                sheet_name = sheet_data.get("sheet_name", "")
                record_count = sheet_data.get("record_count", 0)

                # Create a summary entity for this budget category
                entity_id = f"budget_{sheet_name.lower().replace(' ', '_')[:50]}"
                entity = Entity(
                    id=entity_id,
                    name=sheet_name,
                    entity_type=EntityType.REPORT,
                    properties={
                        "category": "budget",
                        "record_count": record_count,
                        "columns": sheet_data.get("columns", []),
                        "sample_records": sheet_data.get("records", [])[:5],  # Store sample
                    },
                    sources=["budgit"],
                )
                graph.add_entity(entity)
                count += 1

            # Process state data summaries
            for sheet_data in categorized.get("state_data", []):
                sheet_name = sheet_data.get("sheet_name", "")
                record_count = sheet_data.get("record_count", 0)

                entity_id = f"state_data_{sheet_name.lower().replace(' ', '_')[:50]}"
                entity = Entity(
                    id=entity_id,
                    name=sheet_name,
                    entity_type=EntityType.REPORT,
                    properties={
                        "category": "state_expenditure",
                        "record_count": record_count,
                        "columns": sheet_data.get("columns", []),
                    },
                    sources=["budgit"],
                )
                graph.add_entity(entity)
                count += 1

        except Exception as e:
            logger.warning(f"Error processing {json_file}: {e}")
            continue

    logger.info(f"Seeded {count} budget data summaries")
    return count


def _create_relationships(graph: NigeriaKnowledgeGraph) -> int:
    """Create relationships between entities."""
    count = 0

    # Link politicians to parties
    for entity_id, entity in graph.entities.items():
        if entity.entity_type == EntityType.POLITICIAN:
            party_name = entity.properties.get("current_party")
            if party_name:
                party_id = f"party_{party_name.lower().replace(' ', '_')}"
                if party_id in graph.entities:
                    rel = Relationship(
                        source_id=entity_id,
                        target_id=party_id,
                        relation_type=RelationType.MEMBER_OF,
                    )
                    if graph.add_relationship(rel):
                        count += 1

            # Link to state if known
            state_name = entity.properties.get("state")
            if state_name:
                state_id = f"state_{state_name.lower().replace(' ', '_')}"
                if state_id in graph.entities:
                    rel = Relationship(
                        source_id=entity_id,
                        target_id=state_id,
                        relation_type=RelationType.REPRESENTS,
                    )
                    if graph.add_relationship(rel):
                        count += 1

    # Link LGAs to states
    for entity_id, entity in graph.entities.items():
        if entity.entity_type == EntityType.LGA:
            state_name = entity.properties.get("state")
            if state_name:
                state_id = f"state_{state_name.lower().replace(' ', '_')}"
                if state_id in graph.entities:
                    rel = Relationship(
                        source_id=entity_id,
                        target_id=state_id,
                        relation_type=RelationType.PART_OF,
                    )
                    if graph.add_relationship(rel):
                        count += 1

    logger.info(f"Created {count} relationships")
    return count


# Data availability summary for system prompt
def get_data_summary() -> Dict[str, Any]:
    """
    Get a summary of available data for the system prompt.
    This helps the LLM understand what data it can access.
    """
    summary = {
        "politicians": {
            "count": 0,
            "sources": ["wikidata", "wikipedia"],
            "includes": ["senators", "representatives", "governors", "ministers", "presidents"],
        },
        "geography": {
            "states": 37,
            "lgas": 774,
            "senatorial_districts": 109,
            "federal_constituencies": 360,
        },
        "political_parties": {
            "count": 18,
            "major": ["APC", "PDP", "LP", "NNPP", "APGA"],
        },
        "historical_events": {
            "types": ["coups", "elections", "protests", "crises"],
            "period": "1960-present",
        },
        "financial_data": {
            "source": "BudgIT",
            "includes": [
                "Interest rates (2010-2024)",
                "Exchange rates",
                "Inflation data",
                "Federal budget expenditure",
                "LGA FAAC allocations",
                "State sectoral expenditure",
                "MDA project expenditure",
                "Zonal intervention projects",
            ],
        },
        "elections": {
            "covered": ["2023", "2019", "2015", "2011", "2007"],
            "types": ["presidential", "gubernatorial", "senatorial", "house of reps"],
        },
    }

    # Load actual counts if available
    try:
        stats_path = KNOWLEDGE_DATA_PATH / "_collection_stats.json"
        if stats_path.exists():
            with open(stats_path) as f:
                stats = json.load(f)
                summary["total_documents"] = stats.get("wikidata", 0) + stats.get("wikipedia", 0)

        index_path = KNOWLEDGE_DATA_PATH / "wikidata" / "_index.json"
        if index_path.exists():
            with open(index_path) as f:
                index = json.load(f)
                summary["politicians"]["count"] = index.get("total_entities", 0)
    except:
        pass

    return summary
