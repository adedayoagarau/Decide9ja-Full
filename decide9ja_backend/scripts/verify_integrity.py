#!/usr/bin/env python3
"""
Decide9ja — Comprehensive Data Integrity Test

Verifies:
1. Budget data mapping (Year, Jurisdiction, Amount validity).
2. Historical news coverage (1999 transition).
3. Search robustness and edge cases.
"""

import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Add app to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.services.budget_search import get_budget_service
from app.services.catalog_search import get_catalog_service

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("integrity_test")

DB_PATH = Path("/Volumes/Crucial X10/Decide9ja/data/catalog.db")

def check_budget_mapping():
    print("\n📊 --- BUDGET DATA INTEGRITY (Comprehensive) ---")
    
    if not DB_PATH.exists():
        print("❌ Database not found!")
        return

    conn = sqlite3.connect(DB_PATH, timeout=60)
    cursor = conn.cursor()

    try:
        # 1. Year Distribution
        print("\n[Check 1] Year Distribution (Top 10):")
        cursor.execute("SELECT year, COUNT(*) as c FROM budgets GROUP BY year ORDER BY c DESC LIMIT 10")
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]:,} records")

        # 2. Jurisdiction Distribution
        print("\n[Check 2] Jurisdiction Distribution (Top 10):")
        cursor.execute("SELECT jurisdiction, COUNT(*) as c FROM budgets GROUP BY jurisdiction ORDER BY c DESC LIMIT 10")
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]:,} records")

        # 3. Amount Validity
        print("\n[Check 3] Amount Validity:")
        cursor.execute("SELECT COUNT(*) FROM budgets WHERE amount IS NULL OR amount = 0")
        zeros = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM budgets WHERE amount > 1000000000") # > 1 Billion
        large = cursor.fetchone()[0]
        print(f"   Records with Zero/Null Amount: {zeros:,}")
        print(f"   Records > ₦1 Billion: {large:,}")

    except sqlite3.OperationalError as e:
        print(f"   ⚠️ SQL Error: {e}")
    finally:
        conn.close()

def check_historical_news():
    print("\n📰 --- HISTORICAL NEWS VERIFICATION (1999) ---")
    service = get_catalog_service()
    
    # 1. Search for 1999 transition keywords
    queries = [
        "Obasanjo inauguration 1999",
        "transition to democracy",
        "fourth republic",
        "May 29 1999"
    ]
    
    for q in queries:
        print(f"\n🔍 Query: '{q}'")
        res = service.search(q, limit=3, year_from=1998, year_to=2000)
        if res.has_results:
            for item in res.articles:
                print(f"   ✅ [{item.published_date}] {item.title} ({item.source_id})")
        else:
            print("   ⚠️ No direct matches found (Note: OCR is still in progress)")

def check_edge_cases():
    print("\n🧪 --- ROBUSTNESS & EDGE CASES ---")
    budget_svc = get_budget_service()

    # 1. Mixed Case Query
    print("\n[Edge 1] Mixed Case: 'lAgOs HeAlTh'")
    res = budget_svc.search("lAgOs HeAlTh", limit=2)
    print(f"   Matches: {res.total_matches}")
    for item in res.items:
        print(f"   - {item.project[:50]}... (₦{item.amount:,.2f})")

    # 2. LGA Keyword Search (Indirect LGA mapping)
    print("\n[Edge 2] Local Government Keywords (e.g., 'Ikeja', 'Alimosho')")
    lgas = ["Ikeja", "Alimosho", "Ketu", "Epe"]
    for lga in lgas:
        res = budget_svc.search(lga, limit=1)
        if res.has_results:
            print(f"   ✅ Found data for '{lga}': {res.items[0].project[:50]}... ({res.items[0].jurisdiction})")
        else:
            print(f"   ❌ No specific data found for LGA keyword '{lga}'")

    # 3. Non-existent Jurisdiction
    print("\n[Edge 3] Jurisdiction: 'Atlantis'")
    res = budget_svc.search("health", jurisdiction="Atlantis", limit=5)
    print(f"   Matches: {res.total_matches} (Expected: 0)")


if __name__ == "__main__":
    check_budget_mapping()
    check_historical_news()
    check_edge_cases()
