#!/usr/bin/env python3
"""
Decide9ja — Entity & Topic Normalization Script

Normalizes the existing JSON data in catalog.db documents into proper
relational tables:
  - documents.topics (JSON) → document_topics junction table
  - documents.entities (JSON) → entities table + document_entities junction table

This ensures entities like "Tinubu", "PDP", "Lagos" are first-class indexed
records that can be queried, counted, and linked to documents.

Usage:
    python3 scripts/normalize_catalog_entities.py --dry-run
    python3 scripts/normalize_catalog_entities.py               # live run
"""

import json
import sqlite3
import os
import sys
import re
import hashlib
from collections import Counter
from datetime import datetime

# Database path
CATALOG_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "catalog.db"
)

# Entity type mappings
ENTITY_TYPES = {
    "people": "person",
    "organizations": "organization",
    "locations": "location",
}


def slugify(text: str) -> str:
    """Create a URL-safe slug from text."""
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug[:100]  # Cap length


def normalize_entity_name(name: str) -> str:
    """Clean and normalize an entity name."""
    name = name.strip()
    # Remove common OCR artifacts
    name = re.sub(r'^(Hon\.|Sen\.|Dr\.|Chief\.|Alhaji\.|Prof\.)\s*', '', name)
    # Remove trailing punctuation
    name = re.sub(r'[,.:;!]+$', '', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def entity_id(name: str, etype: str) -> str:
    """Generate a deterministic ID for an entity."""
    key = f"{etype}:{name.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def run_normalization(dry_run: bool = False):
    """Run the entity and topic normalization."""
    print(f"{'=' * 60}")
    print(f"Catalog Entity & Topic Normalization")
    print(f"{'=' * 60}")
    print(f"Database: {CATALOG_DB}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Started: {datetime.now().isoformat()}")
    print()

    if not os.path.exists(CATALOG_DB):
        print(f"❌ Database not found: {CATALOG_DB}")
        sys.exit(1)

    conn = sqlite3.connect(CATALOG_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- Phase 1: Topic Classification ---
    print("Phase 1: Topic Classification")
    print("-" * 40)

    # Get predefined topics
    cursor.execute("SELECT id, name, keywords FROM topics")
    topic_defs = {}
    for row in cursor.fetchall():
        keywords = row["keywords"].split(",") if row["keywords"] else []
        topic_defs[row["id"]] = {
            "name": row["name"],
            "keywords": [k.strip().lower() for k in keywords],
        }
    print(f"  Predefined topics: {len(topic_defs)}")

    # Get all documents with topics JSON
    cursor.execute("SELECT id, topics FROM documents WHERE topics IS NOT NULL AND topics != ''")
    docs = cursor.fetchall()
    print(f"  Documents with topics: {len(docs)}")

    topic_links = 0
    topic_counts = Counter()
    topic_errors = 0

    for doc in docs:
        doc_id = doc["id"]
        topics_json = doc["topics"]

        try:
            topics_data = json.loads(topics_json)
        except (json.JSONDecodeError, TypeError):
            topic_errors += 1
            continue

        if isinstance(topics_data, list):
            for item in topics_data:
                if isinstance(item, dict):
                    topic_name = item.get("topic", "").lower().strip()
                    confidence = item.get("confidence", 0.5)
                else:
                    topic_name = str(item).lower().strip()
                    confidence = 0.5

                # Map to predefined topic IDs
                topic_id = None
                for tid, tdef in topic_defs.items():
                    if topic_name == tdef["name"].lower() or topic_name == tid:
                        topic_id = tid
                        break
                    # Check keywords  
                    if any(kw in topic_name for kw in tdef["keywords"]):
                        topic_id = tid
                        break

                if topic_id:
                    topic_counts[topic_id] += 1
                    if not dry_run:
                        try:
                            cursor.execute(
                                "INSERT OR IGNORE INTO document_topics (document_id, topic_id, confidence) VALUES (?, ?, ?)",
                                (doc_id, topic_id, confidence)
                            )
                        except sqlite3.Error:
                            pass
                    topic_links += 1

    print(f"  Topic links created: {topic_links}")
    print(f"  Parse errors: {topic_errors}")
    print(f"  Topic distribution:")
    for tid, count in topic_counts.most_common():
        name = topic_defs.get(tid, {}).get("name", tid)
        print(f"    {name:<20} {count:>6}")

    # Update topic document counts
    if not dry_run:
        for tid, count in topic_counts.items():
            cursor.execute(
                "UPDATE topics SET document_count = ? WHERE id = ?",
                (count, tid)
            )

    # --- Phase 2: Entity Normalization ---
    print(f"\nPhase 2: Entity Normalization")
    print("-" * 40)

    cursor.execute("SELECT id, entities FROM documents WHERE entities IS NOT NULL AND entities != ''")
    docs = cursor.fetchall()
    print(f"  Documents with entities: {len(docs)}")

    # Collect all entities globally first
    all_entities = {}  # (name_lower, type) -> {name, type, doc_count, doc_ids}
    entity_links = 0
    entity_errors = 0

    for doc in docs:
        doc_id = doc["id"]
        entities_json = doc["entities"]

        try:
            entities_data = json.loads(entities_json)
        except (json.JSONDecodeError, TypeError):
            entity_errors += 1
            continue

        if isinstance(entities_data, dict):
            for json_key, etype in ENTITY_TYPES.items():
                names = entities_data.get(json_key, [])
                if not isinstance(names, list):
                    continue

                for raw_name in names:
                    if not isinstance(raw_name, str) or len(raw_name) < 2:
                        continue

                    name = normalize_entity_name(raw_name)
                    if len(name) < 2 or len(name) > 100:
                        continue

                    key = (name.lower(), etype)
                    if key not in all_entities:
                        all_entities[key] = {
                            "name": name,
                            "type": etype,
                            "doc_ids": set(),
                        }
                    all_entities[key]["doc_ids"].add(doc_id)
                    entity_links += 1

    print(f"  Unique entities: {len(all_entities)}")
    print(f"  Entity-document links: {entity_links}")
    print(f"  Parse errors: {entity_errors}")

    # Count by type
    type_counts = Counter()
    for (_, etype), data in all_entities.items():
        type_counts[etype] += 1
    print(f"  By type:")
    for etype, count in type_counts.most_common():
        print(f"    {etype:<20} {count:>6}")

    # Top entities
    print(f"\n  Top 15 entities by mention count:")
    sorted_entities = sorted(
        all_entities.items(),
        key=lambda x: len(x[1]["doc_ids"]),
        reverse=True
    )
    for (_, etype), data in sorted_entities[:15]:
        print(f"    {data['name']:<30} ({etype:<12}) {len(data['doc_ids']):>5} docs")

    # Write to database
    if not dry_run:
        print(f"\n  Writing to database...")

        # Clear existing (re-run safe)
        cursor.execute("DELETE FROM document_entities")
        cursor.execute("DELETE FROM entities")

        # Insert entities
        for (name_lower, etype), data in all_entities.items():
            eid = entity_id(data["name"], etype)
            slug = slugify(f"{data['name']}-{etype}")
            if not slug:
                slug = eid  # Fallback for non-ASCII names

            try:
                cursor.execute(
                    """INSERT OR REPLACE INTO entities 
                       (id, name, type, slug, mention_count, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (eid, data["name"], etype, slug, len(data["doc_ids"]),
                     datetime.now().isoformat())
                )
            except sqlite3.IntegrityError:
                # Slug collision — add hash suffix
                slug = f"{slug}-{eid[:6]}"
                cursor.execute(
                    """INSERT OR REPLACE INTO entities 
                       (id, name, type, slug, mention_count, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (eid, data["name"], etype, slug, len(data["doc_ids"]),
                     datetime.now().isoformat())
                )

            # Insert document links
            for doc_id in data["doc_ids"]:
                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO document_entities (document_id, entity_id, confidence) VALUES (?, ?, ?)",
                        (doc_id, eid, 0.8)
                    )
                except sqlite3.Error:
                    pass

        conn.commit()

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Topic links:     {topic_links:,}")
    print(f"  Unique entities: {len(all_entities):,}")
    print(f"  Entity links:    {entity_links:,}")

    if not dry_run:
        cursor.execute("SELECT COUNT(*) FROM entities")
        print(f"\n  entities table:         {cursor.fetchone()[0]:,} rows")
        cursor.execute("SELECT COUNT(*) FROM document_entities")
        print(f"  document_entities:      {cursor.fetchone()[0]:,} rows")
        cursor.execute("SELECT COUNT(*) FROM document_topics")
        print(f"  document_topics:        {cursor.fetchone()[0]:,} rows")
        cursor.execute("SELECT id, name, document_count FROM topics ORDER BY document_count DESC")
        print(f"\n  Topic counts:")
        for row in cursor.fetchall():
            print(f"    {row[1]:<20} {row[2]:>6} docs")

    if dry_run:
        print(f"\n⚠️  DRY RUN — no changes made. Run without --dry-run to apply.")
    else:
        print(f"\n✅ Normalization complete.")

    conn.close()
    print(f"\nCompleted: {datetime.now().isoformat()}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_normalization(dry_run=dry_run)
