#!/usr/bin/env python3
"""Add House of Representatives mapping to lga_representatives table."""
import os
import sys
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

HOUSE_REPS_INDEX = "/Users/Admin/Decide9ja/decide9ja_scraper/data/candidates/house_of_reps/_index.json"

def normalize(name):
    """Normalize name for matching."""
    name = name.strip().lower()
    name = name.replace("-", " ").replace("'", "").replace("/", " ")
    name = re.sub(r'\s+', ' ', name)
    return name

def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not set")
        return
    
    # Load House of Reps data
    with open(HOUSE_REPS_INDEX) as f:
        house_data = json.load(f)
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Add house rep columns if they don't exist
        conn.execute(text("""
            ALTER TABLE lga_representatives 
            ADD COLUMN IF NOT EXISTS house_rep_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS house_rep_party VARCHAR(20),
            ADD COLUMN IF NOT EXISTS federal_constituency VARCHAR(200)
        """))
        conn.commit()
        
        # Get all LGAs from database
        result = conn.execute(text("SELECT id, state, lga FROM lga_representatives"))
        db_rows = list(result)
        print(f"Found {len(db_rows)} LGAs in database")
        
        # Build constituency lookup by state
        state_constituencies = {}
        for state, state_data in house_data.get("state_constituencies", {}).items():
            state_constituencies[state] = []
            for member in state_data.get("members", []):
                state_constituencies[state].append({
                    "constituency": member["constituency"],
                    "name": member["name"],
                    "party": member["party"],
                    "lgas": [normalize(p) for p in member["constituency"].split("/")]
                })
        
        matched = 0
        for row in db_rows:
            db_id, state, lga = row
            norm_lga = normalize(lga)
            
            # Find matching constituency for this state
            constituencies = state_constituencies.get(state, [])
            for const in constituencies:
                # Check if LGA name appears in constituency
                if norm_lga in const["lgas"] or any(norm_lga in c or c in norm_lga for c in const["lgas"]):
                    conn.execute(text("""
                        UPDATE lga_representatives 
                        SET house_rep_name = :name, house_rep_party = :party, federal_constituency = :constituency
                        WHERE id = :id
                    """), {"id": db_id, "name": const["name"], "party": const["party"], "constituency": const["constituency"]})
                    matched += 1
                    break
        
        conn.commit()
        print(f"Matched: {matched} LGAs")
        
        # Final count
        result = conn.execute(text("SELECT COUNT(*) FROM lga_representatives WHERE house_rep_name IS NOT NULL"))
        total_with_reps = result.scalar()
        print(f"Total LGAs with House Rep data: {total_with_reps}")
        
        # Test queries
        print("\n=== Test Queries ===")
        for test in [("Ogun", "Ijebu North"), ("Lagos", "Ikeja"), ("Abia", "Aba South"), ("FCT", "Bwari")]:
            result = conn.execute(text("""
                SELECT lga, house_rep_name, house_rep_party, federal_constituency
                FROM lga_representatives WHERE state = :state AND lga = :lga
            """), {"state": test[0], "lga": test[1]})
            row = result.fetchone()
            if row and row[1]:
                print(f"{row[0]}, {test[0]}: {row[1]} ({row[2]})")
            else:
                print(f"{test[1]}, {test[0]}: No House Rep found")

if __name__ == "__main__":
    main()
