#!/usr/bin/env python3
"""
Excel Data Ingester for Nigeria Knowledge System

Ingests Excel files (financial data, economic indicators, etc.)
into the knowledge graph and database.

Usage:
    python scripts/ingest_excel_data.py /path/to/your/file.xlsx
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Output directory
DATA_DIR = Path("./nigeria_knowledge_data/excel_imports")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_excel_file(filepath: str) -> Dict[str, List[Dict]]:
    """
    Read Excel file and return all sheets as dictionaries.

    Returns:
        Dict mapping sheet names to list of row dictionaries
    """
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas not installed. Run: pip3 install pandas openpyxl")
        sys.exit(1)

    try:
        import openpyxl
    except ImportError:
        logger.error("openpyxl not installed. Run: pip3 install openpyxl")
        sys.exit(1)

    filepath = Path(filepath)
    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        sys.exit(1)

    logger.info(f"Reading Excel file: {filepath}")

    # Read all sheets
    excel_file = pd.ExcelFile(filepath)
    sheets_data = {}

    for sheet_name in excel_file.sheet_names:
        logger.info(f"  Reading sheet: {sheet_name}")
        df = pd.read_excel(excel_file, sheet_name=sheet_name)

        # Clean column names
        df.columns = [str(col).strip().replace('\n', ' ') for col in df.columns]

        # Convert to list of dicts
        records = df.to_dict('records')

        # Clean up NaN values
        cleaned_records = []
        for record in records:
            cleaned = {}
            for key, value in record.items():
                if pd.isna(value):
                    cleaned[key] = None
                elif isinstance(value, (int, float)):
                    cleaned[key] = value
                else:
                    cleaned[key] = str(value)
            cleaned_records.append(cleaned)

        sheets_data[sheet_name] = cleaned_records
        logger.info(f"    Found {len(cleaned_records)} rows, {len(df.columns)} columns")

    return sheets_data


def categorize_financial_data(sheets_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """
    Categorize and structure financial data for the knowledge graph.

    Detects common financial data patterns:
    - GDP, inflation, exchange rates
    - Budget data (revenue, expenditure)
    - Sector-specific data (oil, agriculture, etc.)
    - State-level data
    """

    categorized = {
        "economic_indicators": [],
        "budget_data": [],
        "sector_data": [],
        "state_data": [],
        "other": [],
    }

    # Keywords for categorization
    economic_keywords = ['gdp', 'inflation', 'exchange', 'rate', 'growth', 'cpi', 'interest']
    budget_keywords = ['budget', 'revenue', 'expenditure', 'allocation', 'spending', 'fiscal']
    sector_keywords = ['oil', 'gas', 'agriculture', 'manufacturing', 'services', 'trade', 'sector']
    state_keywords = ['state', 'lagos', 'kano', 'rivers', 'oyo', 'kaduna', 'federal']

    for sheet_name, records in sheets_data.items():
        sheet_lower = sheet_name.lower()

        # Determine category
        if any(kw in sheet_lower for kw in economic_keywords):
            category = "economic_indicators"
        elif any(kw in sheet_lower for kw in budget_keywords):
            category = "budget_data"
        elif any(kw in sheet_lower for kw in sector_keywords):
            category = "sector_data"
        elif any(kw in sheet_lower for kw in state_keywords):
            category = "state_data"
        else:
            category = "other"

        categorized[category].append({
            "sheet_name": sheet_name,
            "record_count": len(records),
            "columns": list(records[0].keys()) if records else [],
            "records": records,
        })

    return categorized


def extract_time_series(records: List[Dict]) -> List[Dict]:
    """
    Extract time series data from records.

    Looks for year columns (2011, 2012, etc.) and pivots them.
    """

    if not records:
        return []

    # Check if columns contain years
    first_record = records[0]
    year_columns = []
    label_columns = []

    for col in first_record.keys():
        try:
            year = int(str(col).strip())
            if 1960 <= year <= 2030:
                year_columns.append((col, year))
            else:
                label_columns.append(col)
        except ValueError:
            label_columns.append(col)

    if not year_columns:
        return records  # Not time series format

    # Pivot: convert year columns to rows
    time_series = []
    for record in records:
        # Get labels for this row
        labels = {col: record.get(col) for col in label_columns}

        # Create entry for each year
        for col, year in year_columns:
            value = record.get(col)
            if value is not None:
                entry = {
                    **labels,
                    "year": year,
                    "value": value,
                }
                time_series.append(entry)

    return time_series


def generate_knowledge_graph_entities(categorized_data: Dict) -> List[Dict]:
    """
    Generate knowledge graph entities from categorized data.
    """

    entities = []

    # Economic indicators -> create entities
    for sheet_data in categorized_data.get("economic_indicators", []):
        for record in sheet_data["records"]:
            # Try to identify the indicator name
            indicator_name = None
            for key in ['indicator', 'name', 'description', 'item', 'category']:
                if key in record and record[key]:
                    indicator_name = record[key]
                    break

            if indicator_name:
                entities.append({
                    "type": "economic_indicator",
                    "name": str(indicator_name),
                    "source_sheet": sheet_data["sheet_name"],
                    "data": record,
                })

    # Budget data -> create entities
    for sheet_data in categorized_data.get("budget_data", []):
        for record in sheet_data["records"]:
            item_name = None
            for key in ['item', 'ministry', 'mda', 'agency', 'category', 'description']:
                if key in record and record[key]:
                    item_name = record[key]
                    break

            if item_name:
                entities.append({
                    "type": "budget_item",
                    "name": str(item_name),
                    "source_sheet": sheet_data["sheet_name"],
                    "data": record,
                })

    # State data -> create entities
    for sheet_data in categorized_data.get("state_data", []):
        for record in sheet_data["records"]:
            state_name = None
            for key in ['state', 'state_name', 'name', 'region']:
                if key.lower() in {k.lower() for k in record.keys()}:
                    for k, v in record.items():
                        if k.lower() == key.lower() and v:
                            state_name = v
                            break
                if state_name:
                    break

            if state_name:
                entities.append({
                    "type": "state_data",
                    "name": str(state_name),
                    "source_sheet": sheet_data["sheet_name"],
                    "data": record,
                })

    return entities


def save_processed_data(
    filepath: str,
    sheets_data: Dict,
    categorized_data: Dict,
    entities: List[Dict]
):
    """Save processed data to JSON files."""

    filename = Path(filepath).stem
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save raw sheets data
    raw_file = DATA_DIR / f"{filename}_raw_{timestamp}.json"
    with open(raw_file, 'w', encoding='utf-8') as f:
        json.dump({
            "source_file": filepath,
            "processed_at": datetime.now().isoformat(),
            "sheets": sheets_data,
        }, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Saved raw data: {raw_file}")

    # Save categorized data
    cat_file = DATA_DIR / f"{filename}_categorized_{timestamp}.json"
    with open(cat_file, 'w', encoding='utf-8') as f:
        json.dump({
            "source_file": filepath,
            "processed_at": datetime.now().isoformat(),
            "categorized": categorized_data,
        }, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Saved categorized data: {cat_file}")

    # Save entities for knowledge graph
    entities_file = DATA_DIR / f"{filename}_entities_{timestamp}.json"
    with open(entities_file, 'w', encoding='utf-8') as f:
        json.dump({
            "source_file": filepath,
            "processed_at": datetime.now().isoformat(),
            "total_entities": len(entities),
            "entities": entities,
        }, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Saved entities: {entities_file}")

    return {
        "raw_file": str(raw_file),
        "categorized_file": str(cat_file),
        "entities_file": str(entities_file),
    }


def print_summary(sheets_data: Dict, categorized_data: Dict, entities: List[Dict]):
    """Print summary of processed data."""

    print("\n" + "=" * 60)
    print("EXCEL DATA INGESTION SUMMARY")
    print("=" * 60)

    print(f"\nSheets processed: {len(sheets_data)}")
    for sheet_name, records in sheets_data.items():
        print(f"  - {sheet_name}: {len(records)} rows")

    print(f"\nCategorized data:")
    for category, items in categorized_data.items():
        total_records = sum(item['record_count'] for item in items)
        if total_records > 0:
            print(f"  - {category}: {len(items)} sheets, {total_records} records")

    print(f"\nKnowledge graph entities: {len(entities)}")
    entity_types = {}
    for entity in entities:
        t = entity['type']
        entity_types[t] = entity_types.get(t, 0) + 1
    for t, count in entity_types.items():
        print(f"  - {t}: {count}")

    print("\n" + "=" * 60)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_excel_data.py <excel_file_path>")
        print("\nExample:")
        print("  python scripts/ingest_excel_data.py ~/Documents/nigeria_financial_data.xlsx")
        sys.exit(1)

    filepath = sys.argv[1]

    # Read Excel
    sheets_data = read_excel_file(filepath)

    # Categorize
    categorized_data = categorize_financial_data(sheets_data)

    # Extract entities for knowledge graph
    entities = generate_knowledge_graph_entities(categorized_data)

    # Save processed data
    output_files = save_processed_data(filepath, sheets_data, categorized_data, entities)

    # Print summary
    print_summary(sheets_data, categorized_data, entities)

    print(f"\nOutput files saved to: {DATA_DIR}")
    print("\nNext steps:")
    print("  1. Review the entities file for knowledge graph ingestion")
    print("  2. Run the knowledge graph loader (coming soon)")
    print("  3. Query the data through Tade chatbot")


if __name__ == "__main__":
    main()
