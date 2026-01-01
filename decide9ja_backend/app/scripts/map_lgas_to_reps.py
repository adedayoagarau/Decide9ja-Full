"""
Script to map LGAs to their representatives.
Creates entries in the representatives table for each LGA.
"""
import json
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, Politician


def load_lgas():
    """Load LGA data from JSON file."""
    lga_file = "/Users/Admin/Decide9ja/decide9ja_scraper/data/processed/lgas.json"
    with open(lga_file) as f:
        return json.load(f)


def get_representatives_for_state(db, state: str):
    """Get all representatives for a state."""
    from sqlalchemy import text
    
    result = db.execute(text("""
        SELECT r.id, r.position, r.senatorial_district, r.federal_constituency, 
               p.id as politician_id, p.name, p.party
        FROM representatives r
        JOIN politicians p ON r.politician_id = p.id
        WHERE r.state = :state
    """), {"state": state})
    
    reps = []
    for row in result:
        reps.append({
            "id": row[0],
            "position": row[1],
            "senatorial_district": row[2],
            "federal_constituency": row[3],
            "politician_id": row[4],
            "name": row[5],
            "party": row[6]
        })
    return reps


def match_lga_to_constituency(lga_name: str, constituency: str) -> bool:
    """Check if an LGA name appears in a constituency name."""
    if not constituency:
        return False
    
    # Normalize both
    lga_lower = lga_name.lower().strip()
    constituency_lower = constituency.lower()
    
    # Direct match
    if lga_lower in constituency_lower:
        return True
    
    # Handle variations (e.g., "Ijebu North" matches "Ijebu-North")
    lga_normalized = lga_lower.replace(" ", "-")
    if lga_normalized in constituency_lower:
        return True
    
    lga_normalized = lga_lower.replace(" ", "")
    if lga_normalized in constituency_lower.replace("-", "").replace("/", ""):
        return True
    
    return False


def map_lgas_to_reps():
    """Map each LGA to its representatives."""
    lgas = load_lgas()
    db = next(get_db())
    
    stats = {"total": 0, "governors": 0, "senators": 0, "house_reps": 0, "unmapped_hr": []}
    
    # Group LGAs by state
    lgas_by_state = {}
    for lga in lgas:
        state = lga["state"]
        if state not in lgas_by_state:
            lgas_by_state[state] = []
        lgas_by_state[state].append(lga)
    
    print(f"Total LGAs: {len(lgas)}")
    print(f"States: {len(lgas_by_state)}")
    print()
    
    from sqlalchemy import text
    
    # For each state, map LGAs to representatives
    for state, state_lgas in lgas_by_state.items():
        reps = get_representatives_for_state(db, state)
        
        # Separate by type
        governor = [r for r in reps if r["position"] == "Governor"]
        senators = [r for r in reps if r["position"] == "Senator"]
        house_reps = [r for r in reps if r["position"] == "House Representative"]
        
        print(f"\n{state}: {len(state_lgas)} LGAs")
        
        # For each LGA
        for lga in state_lgas:
            lga_name = lga["name"]
            stats["total"] += 1
            
            # 1. Governor - same for all LGAs in state
            if governor:
                db.execute(text("""
                    INSERT INTO representatives (state, lga, position, politician_id)
                    VALUES (:state, :lga, 'Governor', :politician_id)
                    ON CONFLICT DO NOTHING
                """), {"state": state, "lga": lga_name, "politician_id": governor[0]["politician_id"]})
                stats["governors"] += 1
            
            # 2. Find matching Senator by senatorial district
            # We need to determine which senatorial district this LGA belongs to
            # For now, we'll skip this as it requires constituency boundary data
            
            # 3. Find matching House Rep by constituency
            matched_house_rep = None
            for hr in house_reps:
                if match_lga_to_constituency(lga_name, hr["federal_constituency"]):
                    matched_house_rep = hr
                    break
            
            if matched_house_rep:
                db.execute(text("""
                    INSERT INTO representatives (state, lga, position, federal_constituency, politician_id)
                    VALUES (:state, :lga, 'House Representative', :constituency, :politician_id)
                    ON CONFLICT DO NOTHING
                """), {
                    "state": state, 
                    "lga": lga_name, 
                    "constituency": matched_house_rep["federal_constituency"],
                    "politician_id": matched_house_rep["politician_id"]
                })
                stats["house_reps"] += 1
            else:
                stats["unmapped_hr"].append(f"{state}/{lga_name}")
    
    db.commit()
    
    print(f"\n=== SUMMARY ===")
    print(f"Total LGAs: {stats['total']}")
    print(f"Governor mappings created: {stats['governors']}")
    print(f"House Rep mappings created: {stats['house_reps']}")
    print(f"Unmapped House Reps: {len(stats['unmapped_hr'])}")
    
    # Show final counts
    result = db.execute(text("SELECT position, COUNT(*) FROM representatives GROUP BY position"))
    print("\nFinal representatives table:")
    for row in result:
        print(f"  {row[0]}: {row[1]}")


if __name__ == "__main__":
    map_lgas_to_reps()
