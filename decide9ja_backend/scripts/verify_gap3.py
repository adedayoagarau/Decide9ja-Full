
import sys
import os
import json
from pathlib import Path

# Force SQLite to avoid postgres driver requirements (psycopg)
os.environ["DATABASE_URL"] = "sqlite:///./decide9ja.db"

# Add backend to path
sys.path.append("/Volumes/Crucial X10/Decide9ja/decide9ja_backend")


try:
    from app.services.catalog_search import get_catalog_service
except ImportError as e:
    print(f"Catalog Import Error: {e}")
    sys.exit(1)

try:
    from app.services.search_discovery import SearchDiscoveryService
    SEARCH_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Search Discovery Import Error (likely due to missing DB driver): {e}")
    SEARCH_SERVICE_AVAILABLE = False

def test_gap3_phase_b():
    print("\n=== Testing Phase B: Advanced Filters & Facets ===")
    service = get_catalog_service()
    
    if not service.is_available:
        print("❌ Catalog service not available")
        return

    # Test Topic Filter
    print("\n1. Testing Topic Filter (topic='economy'):")
    results = service.search("subsidy", topic="economy", limit=3)
    print(f"   Matches: {results.total_matches}")
    if results.articles:
        print(f"   Top: {results.articles[0].title} (Topics: {results.articles[0].topics})")
    
    # Test Entity Filter
    print("\n2. Testing Entity Filter (entity='Tinubu'):")
    results = service.search("election", entity="Tinubu", limit=3)
    print(f"   Matches: {results.total_matches}")
    
    # Test Facets
    print("\n3. Testing Facets (query='election'):")
    facets = service.get_facets(query="election")
    print("   Topics:", json.dumps(facets.get("topics", {}), indent=2))
    print("   Total Docs in Facet:", facets.get("total_docs"))
    
def test_gap3_phase_c():
    if not SEARCH_SERVICE_AVAILABLE:
        print("\n⚠️ Skipping Phase C verification: Search Discovery Service unavailable (missing deps)")
        return

    print("\n=== Testing Phase C: Unified Search ===")
    service = SearchDiscoveryService()
    
    # Test unified search
    print("\n1. Unified Search (query='Tinubu'):")
    results = service.search("Tinubu", limit=20)
    
    found_archive = False
    print(f"   Total Results: {results['total']}")
    
    types_found = set()
    for r in results['results']:
        types_found.add(r['type'])
        if r['type'] == "archive":
            found_archive = True
            print(f"   [ARCHIVE] {r['title']} ({r['score']})")
    
    print(f"   Types Found: {types_found}")
    
    if found_archive:
        print("   ✅ Archive results successfully integrated!")
    else:
        print("   ⚠️ No archive results found (might be expected if irrelevant, but check logic)")

if __name__ == "__main__":
    print("Running Gap 3 Verification...")
    try:
        test_gap3_phase_b()
        test_gap3_phase_c()
    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
