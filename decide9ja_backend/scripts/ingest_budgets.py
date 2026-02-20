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

import json
import logging
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

# Add backend to path
sys.path.append(str(BASE_DIR / "decide9ja_backend"))
from app.database import SessionLocal, Budget

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
    session = SessionLocal()
    logger.info(f"Inserting {len(records)} records into DB using bulk mechanism...")
    try:
        mappings = [
            {
                "year": r[0],
                "jurisdiction": r[1],
                "mda": r[2],
                "project": r[3],
                "amount": r[4],
                "source_file": r[5],
                "page": r[6]
            }
            for r in records
        ]
        
        batch_size = 10000
        total_batches = (len(mappings) + batch_size - 1) // batch_size
        
        for i in range(0, len(mappings), batch_size):
            batch = mappings[i:i + batch_size]
            session.bulk_insert_mappings(Budget, batch)
            session.commit()
            if (i // batch_size + 1) % 10 == 0 or (i // batch_size + 1) == total_batches:
                logger.info(f"  Inserted batch {i // batch_size + 1}/{total_batches}")
                
        logger.info("Bulk insert complete.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to insert records: {e}")
    finally:
        session.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Budget Data")
    parser.add_argument("--dry-run", action="store_true", help="Scan but do not insert")
    parser.add_argument("--reset", action="store_true", help="Clear existing budget data before ingestion")
    args = parser.parse_args()

    if not NAIJADATA_DIR.exists():
        logger.error(f"Naijadata not found at {NAIJADATA_DIR}")
        sys.exit(1)

    if args.reset:
        logger.info("Resetting budgets table...")
        session = SessionLocal()
        try:
            session.query(Budget).delete()
            session.commit()
        except:
            session.rollback()
        finally:
            session.close()

    ingest_federal(args.dry_run)
    ingest_states(args.dry_run)

    # Verification
    if not args.dry_run:
        session = SessionLocal()
        count = session.query(Budget).count()
        logger.info(f"Total budget records in DB: {count}")
        session.close()

if __name__ == "__main__":
    main()
