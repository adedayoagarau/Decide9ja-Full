#!/usr/bin/env python3
"""
Verify Gap 5: Budget Search Integration
"""

import sys
import os
from pathlib import Path

# Add app to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.services.budget_search import get_budget_service

def main():
    print("💰 Verifying Budget Search Service...")
    service = get_budget_service()
    
    if not service.is_available:
        print("❌ Service not available")
        return

    # Test 1: Federal Query
    print("\n🔍 Test 1: Federal Query 'Construction'")
    res1 = service.search("construction", jurisdiction="Federal", limit=3)
    print(f"   Matches: {res1.total_matches}")
    for item in res1.items:
        print(f"   - {item.project[:60]}... (₦{item.amount:,.2f})")

    # Test 2: State Query
    print("\n🔍 Test 2: Lagos Query 'Health'")
    res2 = service.search("health", jurisdiction="Lagos", limit=3)
    print(f"   Matches: {res2.total_matches}")
    for item in res2.items:
        print(f"   - {item.project[:60]}... (₦{item.amount:,.2f})")

    # Test 3: Specific MDA
    print("\n🔍 Test 3: Kano Works Ministry")
    res3 = service.search("", jurisdiction="Kano", mda_filter="Works", limit=3)
    print(f"   Matches: {res3.total_matches}")
    for item in res3.items:
        print(f"   - {item.project[:60]}... (₦{item.amount:,.2f})")

if __name__ == "__main__":
    main()
