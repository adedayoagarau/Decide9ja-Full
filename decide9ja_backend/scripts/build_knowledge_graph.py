#!/usr/bin/env python3
"""
Nigeria Knowledge Graph Builder

Builds a comprehensive knowledge graph from all collected data:
- Wikipedia articles
- Wikidata entities
- Internet Archive documents
- News articles
- Excel financial data

Run: python scripts/build_knowledge_graph.py
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Data paths
DATA_DIR = Path("./nigeria_knowledge_data")
OUTPUT_DIR = DATA_DIR / "knowledge_graph"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class NigeriaKnowledgeGraphBuilder:
    """Builds knowledge graph from collected data"""

    def __init__(self):
        self.entities = {}  # id -> entity
        self.relationships = []
        self.stats = {
            "wikipedia_entities": 0,
            "wikidata_entities": 0,
            "excel_entities": 0,
            "news_entities": 0,
            "archive_entities": 0,
            "relationships": 0,
        }

    def load_wikipedia(self):
        """Load Wikipedia articles as entities"""
        wiki_dir = DATA_DIR / "wikipedia"
        if not wiki_dir.exists():
            logger.warning("Wikipedia data not found")
            return

        logger.info("Loading Wikipedia articles...")

        for file_path in wiki_dir.glob("*.json"):
            if file_path.name.startswith("_"):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    article = json.load(f)

                entity_id = f"wiki_{article.get('id', file_path.stem)}"

                self.entities[entity_id] = {
                    "id": entity_id,
                    "type": "wikipedia_article",
                    "name": article.get("title", ""),
                    "content": article.get("content", "")[:5000],  # Limit content size
                    "url": article.get("url", ""),
                    "categories": article.get("categories", []),
                    "source": "wikipedia",
                }

                self.stats["wikipedia_entities"] += 1

            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        logger.info(f"  Loaded {self.stats['wikipedia_entities']} Wikipedia articles")

    def load_wikidata(self):
        """Load Wikidata entities"""
        wiki_dir = DATA_DIR / "wikidata"
        if not wiki_dir.exists():
            logger.warning("Wikidata not found")
            return

        logger.info("Loading Wikidata entities...")

        for file_path in wiki_dir.glob("*.json"):
            if file_path.name.startswith("_"):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                query_name = data.get("query_name", file_path.stem)
                results = data.get("results", [])

                for item in results:
                    # Extract Wikidata ID from URL
                    person_url = item.get("person", "")
                    wikidata_id = person_url.split("/")[-1] if person_url else None

                    if not wikidata_id:
                        continue

                    entity_id = f"wd_{wikidata_id}"

                    # Merge with existing entity if present
                    if entity_id in self.entities:
                        existing = self.entities[entity_id]
                        # Merge attributes
                        for key, value in item.items():
                            if value and key not in existing:
                                existing[key] = value
                    else:
                        self.entities[entity_id] = {
                            "id": entity_id,
                            "type": self._determine_entity_type(query_name),
                            "name": item.get("personLabel", "Unknown"),
                            "description": item.get("personDescription", ""),
                            "wikidata_id": wikidata_id,
                            "source": "wikidata",
                            "query_source": query_name,
                            **{k: v for k, v in item.items() if v and k not in ["person", "personLabel", "personDescription"]}
                        }
                        self.stats["wikidata_entities"] += 1

            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        logger.info(f"  Loaded {self.stats['wikidata_entities']} Wikidata entities")

    def _determine_entity_type(self, query_name: str) -> str:
        """Determine entity type from Wikidata query name"""
        type_mapping = {
            "politician": "person_politician",
            "president": "person_president",
            "governor": "person_governor",
            "military": "person_military",
            "state": "place_state",
            "city": "place_city",
            "party": "organization_party",
            "ethnic": "group_ethnic",
            "university": "organization_university",
            "company": "organization_company",
            "newspaper": "organization_newspaper",
            "election": "event_election",
            "event": "event_general",
        }

        query_lower = query_name.lower()
        for key, value in type_mapping.items():
            if key in query_lower:
                return value

        return "entity"

    def load_excel_data(self):
        """Load Excel financial data"""
        excel_dir = DATA_DIR / "excel_imports"
        if not excel_dir.exists():
            logger.warning("Excel data not found")
            return

        logger.info("Loading Excel financial data...")

        # Load the most recent categorized file
        cat_files = list(excel_dir.glob("*_categorized_*.json"))
        if not cat_files:
            logger.warning("No categorized Excel data found")
            return

        latest_file = max(cat_files, key=lambda f: f.stat().st_mtime)

        try:
            with open(latest_file, encoding="utf-8") as f:
                data = json.load(f)

            categorized = data.get("categorized", {})

            # Process economic indicators
            for sheet_data in categorized.get("economic_indicators", []):
                sheet_name = sheet_data.get("sheet_name", "")
                entity_id = f"econ_{sheet_name.lower().replace(' ', '_')[:30]}"

                self.entities[entity_id] = {
                    "id": entity_id,
                    "type": "economic_indicator",
                    "name": sheet_name,
                    "record_count": sheet_data.get("record_count", 0),
                    "columns": sheet_data.get("columns", []),
                    "source": "excel_financial",
                    "data_sample": sheet_data.get("records", [])[:10],  # Sample only
                }
                self.stats["excel_entities"] += 1

            # Process budget data
            for sheet_data in categorized.get("budget_data", []):
                sheet_name = sheet_data.get("sheet_name", "")
                entity_id = f"budget_{sheet_name.lower().replace(' ', '_')[:30]}"

                self.entities[entity_id] = {
                    "id": entity_id,
                    "type": "budget_data",
                    "name": sheet_name,
                    "record_count": sheet_data.get("record_count", 0),
                    "columns": sheet_data.get("columns", []),
                    "source": "excel_financial",
                    "data_sample": sheet_data.get("records", [])[:10],
                }
                self.stats["excel_entities"] += 1

            # Process state data
            for sheet_data in categorized.get("state_data", []):
                sheet_name = sheet_data.get("sheet_name", "")
                entity_id = f"state_data_{sheet_name.lower().replace(' ', '_')[:30]}"

                self.entities[entity_id] = {
                    "id": entity_id,
                    "type": "state_financial_data",
                    "name": sheet_name,
                    "record_count": sheet_data.get("record_count", 0),
                    "columns": sheet_data.get("columns", []),
                    "source": "excel_financial",
                    "data_sample": sheet_data.get("records", [])[:10],
                }
                self.stats["excel_entities"] += 1

            # Process sector data
            for sheet_data in categorized.get("sector_data", []):
                sheet_name = sheet_data.get("sheet_name", "")
                entity_id = f"sector_{sheet_name.lower().replace(' ', '_')[:30]}"

                self.entities[entity_id] = {
                    "id": entity_id,
                    "type": "sector_data",
                    "name": sheet_name,
                    "record_count": sheet_data.get("record_count", 0),
                    "columns": sheet_data.get("columns", []),
                    "source": "excel_financial",
                    "data_sample": sheet_data.get("records", [])[:10],
                }
                self.stats["excel_entities"] += 1

        except Exception as e:
            logger.error(f"Error loading Excel data: {e}")

        logger.info(f"  Loaded {self.stats['excel_entities']} Excel data entities")

    def load_news(self):
        """Load news articles"""
        news_dir = DATA_DIR / "news"
        if not news_dir.exists():
            logger.warning("News data not found")
            return

        logger.info("Loading news articles...")

        for file_path in news_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                articles = data.get("articles", [])

                for article in articles:
                    entity_id = f"news_{article.get('id', '')}"

                    self.entities[entity_id] = {
                        "id": entity_id,
                        "type": "news_article",
                        "name": article.get("title", ""),
                        "content": article.get("content", "")[:2000],
                        "url": article.get("link", ""),
                        "published": article.get("published", ""),
                        "source_name": article.get("source", ""),
                        "source": "news_rss",
                    }
                    self.stats["news_entities"] += 1

            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        logger.info(f"  Loaded {self.stats['news_entities']} news articles")

    def load_internet_archive(self):
        """Load Internet Archive documents"""
        archive_dir = DATA_DIR / "internet_archive"
        if not archive_dir.exists():
            logger.warning("Internet Archive data not found")
            return

        logger.info("Loading Internet Archive documents...")

        for file_path in archive_dir.glob("*.json"):
            if file_path.name.startswith("_"):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    doc = json.load(f)

                entity_id = f"ia_{doc.get('id', file_path.stem)}"

                # Get content preview
                full_text = doc.get("full_text", "")
                content_preview = full_text[:3000] if full_text else ""

                self.entities[entity_id] = {
                    "id": entity_id,
                    "type": "historical_document",
                    "name": doc.get("title", ""),
                    "date": doc.get("date", ""),
                    "creator": doc.get("creator", ""),
                    "description": doc.get("description", ""),
                    "url": doc.get("url", ""),
                    "has_full_text": bool(full_text),
                    "content_preview": content_preview,
                    "source": "internet_archive",
                }
                self.stats["archive_entities"] += 1

            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        logger.info(f"  Loaded {self.stats['archive_entities']} Internet Archive documents")

    def build_relationships(self):
        """Build relationships between entities"""
        logger.info("Building relationships...")

        # Connect politicians to parties (from Wikidata)
        for entity_id, entity in self.entities.items():
            if entity.get("partyLabel"):
                party_name = entity["partyLabel"]
                # Find or create party entity
                party_id = f"party_{party_name.lower().replace(' ', '_')}"

                if party_id not in self.entities:
                    self.entities[party_id] = {
                        "id": party_id,
                        "type": "organization_party",
                        "name": party_name,
                        "source": "inferred",
                    }

                self.relationships.append({
                    "source": entity_id,
                    "target": party_id,
                    "type": "member_of",
                })
                self.stats["relationships"] += 1

            # Connect to states
            if entity.get("stateLabel"):
                state_name = entity["stateLabel"]
                state_id = f"state_{state_name.lower().replace(' ', '_')}"

                if state_id not in self.entities:
                    self.entities[state_id] = {
                        "id": state_id,
                        "type": "place_state",
                        "name": state_name,
                        "source": "inferred",
                    }

                self.relationships.append({
                    "source": entity_id,
                    "target": state_id,
                    "type": "represents",
                })
                self.stats["relationships"] += 1

        logger.info(f"  Built {self.stats['relationships']} relationships")

    def create_search_index(self) -> Dict:
        """Create a simple search index for quick lookups"""
        logger.info("Creating search index...")

        index = {
            "by_name": {},  # name -> [entity_ids]
            "by_type": {},  # type -> [entity_ids]
            "by_source": {},  # source -> [entity_ids]
        }

        for entity_id, entity in self.entities.items():
            # Index by name
            name = entity.get("name", "").lower()
            if name:
                if name not in index["by_name"]:
                    index["by_name"][name] = []
                index["by_name"][name].append(entity_id)

                # Also index partial names (first word, last word)
                words = name.split()
                for word in words:
                    if len(word) > 2:
                        if word not in index["by_name"]:
                            index["by_name"][word] = []
                        if entity_id not in index["by_name"][word]:
                            index["by_name"][word].append(entity_id)

            # Index by type
            entity_type = entity.get("type", "unknown")
            if entity_type not in index["by_type"]:
                index["by_type"][entity_type] = []
            index["by_type"][entity_type].append(entity_id)

            # Index by source
            source = entity.get("source", "unknown")
            if source not in index["by_source"]:
                index["by_source"][source] = []
            index["by_source"][source].append(entity_id)

        return index

    def save(self):
        """Save the knowledge graph to files"""
        logger.info("Saving knowledge graph...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save entities
        entities_file = OUTPUT_DIR / f"entities_{timestamp}.json"
        with open(entities_file, "w", encoding="utf-8") as f:
            json.dump({
                "total": len(self.entities),
                "entities": self.entities,
            }, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved entities: {entities_file}")

        # Save relationships
        relationships_file = OUTPUT_DIR / f"relationships_{timestamp}.json"
        with open(relationships_file, "w", encoding="utf-8") as f:
            json.dump({
                "total": len(self.relationships),
                "relationships": self.relationships,
            }, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved relationships: {relationships_file}")

        # Save search index
        index = self.create_search_index()
        index_file = OUTPUT_DIR / f"search_index_{timestamp}.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved search index: {index_file}")

        # Save stats
        stats_file = OUTPUT_DIR / f"stats_{timestamp}.json"
        self.stats["total_entities"] = len(self.entities)
        self.stats["total_relationships"] = len(self.relationships)
        self.stats["built_at"] = datetime.now().isoformat()

        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)
        logger.info(f"  Saved stats: {stats_file}")

        # Save latest reference
        latest_file = OUTPUT_DIR / "latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump({
                "entities_file": str(entities_file),
                "relationships_file": str(relationships_file),
                "index_file": str(index_file),
                "stats_file": str(stats_file),
                "built_at": datetime.now().isoformat(),
            }, f, indent=2)

        return {
            "entities_file": str(entities_file),
            "relationships_file": str(relationships_file),
            "index_file": str(index_file),
        }

    def build(self):
        """Build the complete knowledge graph"""
        print("=" * 60)
        print("NIGERIA KNOWLEDGE GRAPH BUILDER")
        print("=" * 60)

        # Load all data sources
        self.load_wikipedia()
        self.load_wikidata()
        self.load_excel_data()
        self.load_news()
        self.load_internet_archive()

        # Build relationships
        self.build_relationships()

        # Save
        output_files = self.save()

        # Print summary
        print("\n" + "=" * 60)
        print("KNOWLEDGE GRAPH COMPLETE")
        print("=" * 60)
        print(f"\nTotal Entities: {len(self.entities)}")
        print(f"  - Wikipedia: {self.stats['wikipedia_entities']}")
        print(f"  - Wikidata: {self.stats['wikidata_entities']}")
        print(f"  - Excel Financial: {self.stats['excel_entities']}")
        print(f"  - News: {self.stats['news_entities']}")
        print(f"  - Internet Archive: {self.stats['archive_entities']}")
        print(f"\nRelationships: {len(self.relationships)}")
        print(f"\nOutput: {OUTPUT_DIR}")
        print("=" * 60)

        return output_files


def main():
    builder = NigeriaKnowledgeGraphBuilder()
    builder.build()


if __name__ == "__main__":
    main()
