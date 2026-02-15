#!/usr/bin/env python3
"""
Decide9ja — Budget Data Ingester

Ingests budget data from `data/naijadata` into `catalog.db`.
Supports:
1. Federal Budget (2024) - `budget_items.json`
2. State Budgets (Lagos, Kano, etc.) - `all_years_budget_data.json`

Schema:
- budgets (id, year, jurisdiction, mda, project, amount, source_file, page)
- budgets_fts (rowid, project, mda)
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Config
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CATALOG_DB = DATA_DIR / "catalog.db"
NAIJADATA_DIR = DATA_DIR / "naijadata" / "data"

def init_db():
    conn = sqlite3.connect(str(CATALOG_DB))
    
    # Main table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            jurisdiction TEXT NOT NULL,
            mda TEXT,
            project TEXT NOT NULL,
            amount REAL,
            source_file TEXT,
            page INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Indexes for filtering
    conn.execute("CREATE INDEX IF NOT EXISTS idx_budgets_year ON budgets(year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_budgets_jurisdiction ON budgets(jurisdiction)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_budgets_mda ON budgets(mda)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_budgets_amount ON budgets(amount)")

    # FTS table for search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS budgets_fts USING fts5(
            project,
            mda,
            content=budgets,
            content_rowid=id
        )
    """)
    
    # Triggers to keep FTS in sync
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS budgets_ai AFTER INSERT ON budgets BEGIN
            INSERT INTO budgets_fts(rowid, project, mda) VALUES (new.id, new.project, new.mda);
        END;
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS budgets_ad AFTER DELETE ON budgets BEGIN
            INSERT INTO budgets_fts(budgets_fts, rowid, project, mda) VALUES('delete', old.id, old.project, old.mda);
        END;
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS budgets_au AFTER UPDATE ON budgets BEGIN
            INSERT INTO budgets_fts(budgets_fts, rowid, project, mda) VALUES('delete', old.id, old.project, old.mda);
            INSERT INTO budgets_fts(rowid, project, mda) VALUES (new.id, new.project, new.mda);
        END;
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized.")

def ingest_federal(dry_run: bool = False):
    """Ingest Federal budget data."""
    federal_dir = NAIJADATA_DIR / "federal"
    if not federal_dir.exists():
        logger.warning(f"Federal data not found at {federal_dir}")
        return

    logger.info("Scanning Federal budgets...")
    json_files = sorted(federal_dir.rglob("budget_items.json"))
    
    total_records = 0
    records_to_insert = []

    for f in json_files:
        try:
            with open(f, "r") as json_file:
                data = json.load(json_file)
                items = data.get("items", [])
                logger.info(f"  Found {len(items)} items in {f}")
                
                for item in items:
                    records_to_insert.append((
                        item.get("year"),
                        "Federal",
                        item.get("mda", "Unknown"),
                        item.get("description", "Unknown Project"),
                        item.get("amount", 0.0),
                        item.get("source_file", ""),
                        item.get("page", 0)
                    ))
        except Exception as e:
            logger.error(f"Failed to process {f}: {e}")

    total_records = len(records_to_insert)
    logger.info(f"Prepared {total_records} Federal records.")

    if not dry_run and records_to_insert:
        _bulk_insert(records_to_insert)

def ingest_states(dry_run: bool = False):
    """Ingest State budget data."""
    states_dir = NAIJADATA_DIR / "states"
    if not states_dir.exists():
        logger.warning(f"State data not found at {states_dir}")
        return

    logger.info("Scanning State budgets...")
    json_files = sorted(states_dir.rglob("all_years_budget_data.json"))
    
    total_records = 0
    records_to_insert = []

    for f in json_files:
        state_name = f.parent.name.replace("_", " ").title()
        try:
            with open(f, "r") as json_file:
                data = json.load(json_file)
                
                items = []
                if isinstance(data, dict):
                    if "items" in data and isinstance(data["items"], list):
                         items = data["items"]
                    else:
                         # Fallback if it's a single item or different structure
                         items = [data]
                elif isinstance(data, list):
                    items = data
                
                logger.info(f"  Found {len(items)} items for {state_name}")
                
                for item in items:
                    # State schema might differ slightly, normalizing...
                    # Inspecting Lagos data: usually keys are "year", "mda", "project_name", "amount"
                    # But earlier view federal had "description".
                    # I'll try to be robust.

                    
                    year = item.get("year")
                    if not year:
                        # Try to infer from path if inside a year folder
                        if f.parent.name.isdigit():
                            year = int(f.parent.name)
                        else:
                            # Skip if year is absolutely missing
                            # logger.warning(f"Skipping item without year in {state_name}")
                            continue
                    
                    try:
                        year = int(year)
                    except (ValueError, TypeError):
                         continue

                    # Amount cleaning
                    # Check amount, approved_amount, primary_amount, or amounts array (take first)
                    raw_amount = item.get("amount") or item.get("approved_amount") or item.get("primary_amount")
                    
                    if raw_amount is None:
                         amounts = item.get("amounts")
                         if isinstance(amounts, list) and amounts:
                             raw_amount = amounts[0]
                    
                    try:
                       if isinstance(raw_amount, str):
                           amount = float(raw_amount.replace(",", "").replace("₦", "").strip())
                       elif isinstance(raw_amount, (int, float)):
                           amount = float(raw_amount)
                       else:
                           amount = 0.0
                    except:
                        amount = 0.0

                    project = item.get("project_name") or item.get("description") or item.get("activity") or "Unknown"
                    mda = item.get("mda") or item.get("ministry") or "Unknown"
                    
                    records_to_insert.append((
                        year,
                        state_name,
                        mda,
                        project,
                        amount,
                        item.get("source_file", ""),
                        item.get("page", 0)
                    ))

        except Exception as e:
            logger.error(f"Failed to process {f}: {e}")

    total_records = len(records_to_insert)
    logger.info(f"Prepared {total_records} State records.")

    if not dry_run and records_to_insert:
        _bulk_insert(records_to_insert)

def _bulk_insert(records: List):
    conn = sqlite3.connect(str(CATALOG_DB))
    cursor = conn.cursor()
    
    logger.info(f"Inserting {len(records)} records into DB...")
    cursor.executemany("""
        INSERT INTO budgets (year, jurisdiction, mda, project, amount, source_file, page)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, records)
    
    conn.commit()
    conn.close()
    logger.info("Insert complete.")

def main():
    parser = argparse.ArgumentParser(description="Ingest Budget Data")
    parser.add_argument("--dry-run", action="store_true", help="Scan but do not insert")
    parser.add_argument("--reset", action="store_true", help="Clear existing budget data before ingestion")
    args = parser.parse_args()

    if not NAIJADATA_DIR.exists():
        logger.error(f"Naijadata not found at {NAIJADATA_DIR}")
        sys.exit(1)

    init_db()

    if args.reset:
        logger.info("Resetting budgets table...")
        conn = sqlite3.connect(str(CATALOG_DB))
        conn.execute("DELETE FROM budgets")
        conn.execute("DELETE FROM budgets_fts")
        conn.commit()
        conn.close()

    ingest_federal(args.dry_run)
    ingest_states(args.dry_run)

    # Verification
    if not args.dry_run:
        conn = sqlite3.connect(str(CATALOG_DB))
        count = conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0]
        logger.info(f"Total budget records in DB: {count}")
        conn.close()

if __name__ == "__main__":
    main()
