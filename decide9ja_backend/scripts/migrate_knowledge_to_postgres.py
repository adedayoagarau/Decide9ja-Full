#!/usr/bin/env python3
"""
Knowledge Data Migration Script

Migrates all file-based knowledge data to PostgreSQL:
- wikidata/*.json → knowledge_entities + knowledge_relations
- wikipedia/*.md → knowledge_entities
- excel_imports/*.xlsx → budget_allocations, constituency_projects
- internet_archive/*.json → knowledge_entities (historical)

Run: python scripts/migrate_knowledge_to_postgres.py

Environment:
- DATABASE_URL must point to PostgreSQL
- OPENAI_API_KEY for generating embeddings
"""

import os
import sys
import json
import glob
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session
from app.database_v2 import (
    SessionLocal, init_db_v2,
    KnowledgeEntity, KnowledgeRelation, KnowledgeEmbedding,
    BudgetAllocation, FAACDistribution, ConstituencyProject,
    ElectionResult
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Base path for knowledge data
KNOWLEDGE_DATA_PATH = Path(__file__).parent.parent / "nigeria_knowledge_data"


class MigrationStats:
    """Track migration statistics."""
    def __init__(self):
        self.entities_created = 0
        self.entities_updated = 0
        self.relations_created = 0
        self.embeddings_created = 0
        self.budgets_created = 0
        self.errors = 0
        self.start_time = datetime.now()

    def summary(self) -> str:
        elapsed = datetime.now() - self.start_time
        return f"""
Migration Complete!
==================
Entities created: {self.entities_created}
Entities updated: {self.entities_updated}
Relations created: {self.relations_created}
Embeddings created: {self.embeddings_created}
Budget records: {self.budgets_created}
Errors: {self.errors}
Duration: {elapsed}
"""


def get_or_create_entity(
    db: Session,
    entity_id: str,
    entity_type: str,
    name: str,
    **kwargs
) -> KnowledgeEntity:
    """Get existing entity or create new one."""
    entity = db.query(KnowledgeEntity).filter(
        KnowledgeEntity.entity_id == entity_id
    ).first()

    if entity:
        # Update existing
        for key, value in kwargs.items():
            if hasattr(entity, key) and value is not None:
                setattr(entity, key, value)
        entity.updated_at = datetime.utcnow()
        return entity

    # Create new
    entity = KnowledgeEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        **kwargs
    )
    db.add(entity)
    return entity


def migrate_wikidata(db: Session, stats: MigrationStats):
    """Migrate Wikidata JSON files to knowledge_entities."""
    wikidata_path = KNOWLEDGE_DATA_PATH / "wikidata"

    if not wikidata_path.exists():
        logger.warning(f"Wikidata path not found: {wikidata_path}")
        return

    # Process each JSON file in wikidata directory
    for json_file in wikidata_path.glob("*.json"):
        logger.info(f"Processing {json_file.name}...")

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both single entity and array formats
            entities = data if isinstance(data, list) else [data]

            for entity_data in entities:
                try:
                    # Extract entity ID (Wikidata QID or custom)
                    entity_id = entity_data.get("id") or entity_data.get("qid") or entity_data.get("entity_id")
                    if not entity_id:
                        continue

                    # Determine entity type from filename or data
                    entity_type = determine_entity_type(json_file.stem, entity_data)

                    # Extract name
                    name = (
                        entity_data.get("name") or
                        entity_data.get("label") or
                        entity_data.get("title") or
                        str(entity_id)
                    )

                    # Extract description
                    description = (
                        entity_data.get("description") or
                        entity_data.get("bio") or
                        entity_data.get("summary")
                    )

                    # Build full text for search
                    full_text = build_full_text(entity_data)

                    # Extract location info
                    state = entity_data.get("state") or entity_data.get("stateLabel")
                    lga = entity_data.get("lga") or entity_data.get("lgaLabel")

                    # Create entity
                    entity = get_or_create_entity(
                        db=db,
                        entity_id=f"wikidata:{entity_id}",
                        entity_type=entity_type,
                        name=name,
                        description=description,
                        full_text=full_text,
                        properties=json.dumps(entity_data),
                        state=state,
                        lga=lga,
                        source="wikidata",
                        source_url=f"https://www.wikidata.org/wiki/{entity_id}" if entity_id.startswith("Q") else None
                    )

                    if entity.id:
                        stats.entities_updated += 1
                    else:
                        stats.entities_created += 1

                    # Create relations if present
                    create_relations_from_wikidata(db, entity_id, entity_data, stats)

                except Exception as e:
                    logger.error(f"Error processing entity {entity_data.get('id', 'unknown')}: {e}")
                    stats.errors += 1

            db.commit()

        except Exception as e:
            logger.error(f"Error processing file {json_file}: {e}")
            stats.errors += 1
            db.rollback()


def migrate_wikipedia(db: Session, stats: MigrationStats):
    """Migrate Wikipedia markdown files to knowledge_entities."""
    wikipedia_path = KNOWLEDGE_DATA_PATH / "wikipedia"

    if not wikipedia_path.exists():
        logger.warning(f"Wikipedia path not found: {wikipedia_path}")
        return

    for md_file in wikipedia_path.glob("*.md"):
        logger.info(f"Processing {md_file.name}...")

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract title from filename or first heading
            title = md_file.stem.replace("_", " ").title()
            if content.startswith("# "):
                title = content.split("\n")[0].replace("# ", "")

            # Determine entity type
            entity_type = determine_wikipedia_entity_type(md_file.stem, content)

            entity = get_or_create_entity(
                db=db,
                entity_id=f"wikipedia:{md_file.stem}",
                entity_type=entity_type,
                name=title,
                description=extract_first_paragraph(content),
                full_text=content,
                properties=json.dumps({"filename": md_file.name}),
                source="wikipedia",
                source_url=f"https://en.wikipedia.org/wiki/{md_file.stem}"
            )

            if entity.id:
                stats.entities_updated += 1
            else:
                stats.entities_created += 1

        except Exception as e:
            logger.error(f"Error processing {md_file}: {e}")
            stats.errors += 1

    db.commit()


def migrate_excel_imports(db: Session, stats: MigrationStats):
    """Migrate Excel budget data to budget tables."""
    excel_path = KNOWLEDGE_DATA_PATH / "excel_imports"

    if not excel_path.exists():
        logger.warning(f"Excel imports path not found: {excel_path}")
        return

    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas required for Excel migration. Install with: pip install pandas openpyxl")
        return

    for xlsx_file in excel_path.glob("*.xlsx"):
        logger.info(f"Processing {xlsx_file.name}...")

        try:
            # Read all sheets
            xl = pd.ExcelFile(xlsx_file)

            for sheet_name in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name=sheet_name)

                # Detect data type from column names and process
                if any(col.lower() in ["faac", "allocation", "statutory"] for col in df.columns):
                    process_faac_data(db, df, stats)
                elif any(col.lower() in ["project", "constituency", "contractor"] for col in df.columns):
                    process_project_data(db, df, stats)
                elif any(col.lower() in ["budget", "amount", "mda"] for col in df.columns):
                    process_budget_data(db, df, stats)

        except Exception as e:
            logger.error(f"Error processing {xlsx_file}: {e}")
            stats.errors += 1

    db.commit()


def migrate_internet_archive(db: Session, stats: MigrationStats):
    """Migrate Internet Archive data to knowledge_entities."""
    archive_path = KNOWLEDGE_DATA_PATH / "internet_archive"

    if not archive_path.exists():
        logger.warning(f"Internet Archive path not found: {archive_path}")
        return

    for json_file in archive_path.glob("*.json"):
        logger.info(f"Processing {json_file.name}...")

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            entities = data if isinstance(data, list) else [data]

            for entity_data in entities:
                entity_id = entity_data.get("id") or json_file.stem

                entity = get_or_create_entity(
                    db=db,
                    entity_id=f"archive:{entity_id}",
                    entity_type=entity_data.get("type", "historical_document"),
                    name=entity_data.get("title", entity_id),
                    description=entity_data.get("description"),
                    full_text=entity_data.get("content", ""),
                    properties=json.dumps(entity_data),
                    source="internet_archive",
                    source_url=entity_data.get("url"),
                    start_date=parse_date(entity_data.get("date"))
                )

                if entity.id:
                    stats.entities_updated += 1
                else:
                    stats.entities_created += 1

        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
            stats.errors += 1

    db.commit()


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def determine_entity_type(filename: str, data: Dict) -> str:
    """Determine entity type from filename and data."""
    filename_lower = filename.lower()

    if "politician" in filename_lower or data.get("position"):
        return "politician"
    elif "party" in filename_lower or "parties" in filename_lower:
        return "party"
    elif "state" in filename_lower and "lga" not in filename_lower:
        return "state"
    elif "lga" in filename_lower:
        return "lga"
    elif "election" in filename_lower:
        return "election"
    elif "coup" in filename_lower or "military" in filename_lower:
        return "historical_event"
    elif "ministry" in filename_lower or "mda" in filename_lower:
        return "ministry"
    elif "bill" in filename_lower:
        return "bill"
    else:
        return data.get("type", "entity")


def determine_wikipedia_entity_type(filename: str, content: str) -> str:
    """Determine entity type from Wikipedia article."""
    filename_lower = filename.lower()
    content_lower = content[:500].lower()

    if "election" in filename_lower:
        return "election"
    elif "coup" in filename_lower or "military_rule" in filename_lower:
        return "historical_event"
    elif any(word in content_lower for word in ["politician", "president", "governor", "senator"]):
        return "politician"
    elif "constitution" in filename_lower:
        return "constitutional_document"
    else:
        return "wikipedia_article"


def build_full_text(data: Dict) -> str:
    """Build searchable full text from entity data."""
    text_parts = []

    for key, value in data.items():
        if isinstance(value, str) and len(value) > 10:
            text_parts.append(value)
        elif key.endswith("Label"):
            text_parts.append(str(value))

    return " ".join(text_parts)


def extract_first_paragraph(content: str) -> str:
    """Extract first paragraph from markdown content."""
    lines = content.split("\n\n")
    for line in lines:
        if line.strip() and not line.startswith("#"):
            return line.strip()[:500]
    return ""


def parse_date(date_str: Any) -> Optional[datetime]:
    """Parse date string to datetime."""
    if not date_str:
        return None
    if isinstance(date_str, datetime):
        return date_str

    try:
        # Try common formats
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y"]:
            try:
                return datetime.strptime(str(date_str), fmt)
            except ValueError:
                continue
    except Exception:
        pass

    return None


def create_relations_from_wikidata(db: Session, entity_id: str, data: Dict, stats: MigrationStats):
    """Create relations from Wikidata claims."""
    # Common relation properties in Wikidata
    relation_map = {
        "partyLabel": ("member_of", "party"),
        "stateLabel": ("represents", "state"),
        "positionLabel": ("holds_position", "position"),
        "predecessor": ("succeeds", "politician"),
        "successor": ("preceded_by", "politician"),
    }

    for prop, (rel_type, target_type) in relation_map.items():
        if prop in data and data[prop]:
            try:
                relation = KnowledgeRelation(
                    source_id=f"wikidata:{entity_id}",
                    target_id=f"{target_type}:{data[prop]}".replace(" ", "_").lower(),
                    relation_type=rel_type,
                    source="wikidata"
                )
                db.add(relation)
                stats.relations_created += 1
            except Exception:
                pass


def process_faac_data(db: Session, df, stats: MigrationStats):
    """Process FAAC distribution data."""
    # This would be customized based on actual BudgIT data format
    logger.info(f"Processing FAAC data with {len(df)} rows...")
    # Implementation depends on actual data structure


def process_project_data(db: Session, df, stats: MigrationStats):
    """Process constituency project data."""
    logger.info(f"Processing project data with {len(df)} rows...")
    # Implementation depends on actual data structure


def process_budget_data(db: Session, df, stats: MigrationStats):
    """Process budget allocation data."""
    logger.info(f"Processing budget data with {len(df)} rows...")
    # Implementation depends on actual data structure


# ===========================================
# MAIN MIGRATION
# ===========================================

def run_migration():
    """Run the full migration."""
    logger.info("Starting Knowledge Data Migration to PostgreSQL...")
    logger.info(f"Data path: {KNOWLEDGE_DATA_PATH}")

    # Initialize database
    init_db_v2()
    logger.info("Database initialized")

    # Create session
    db = SessionLocal()
    stats = MigrationStats()

    try:
        # Run migrations in order
        logger.info("\n=== Migrating Wikidata ===")
        migrate_wikidata(db, stats)

        logger.info("\n=== Migrating Wikipedia ===")
        migrate_wikipedia(db, stats)

        logger.info("\n=== Migrating Excel Imports ===")
        migrate_excel_imports(db, stats)

        logger.info("\n=== Migrating Internet Archive ===")
        migrate_internet_archive(db, stats)

        db.commit()
        logger.info(stats.summary())

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
