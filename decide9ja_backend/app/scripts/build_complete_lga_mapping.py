#!/usr/bin/env python3
"""Build complete LGA-to-representative mapping from scraped data."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

# Paths
SCRAPER_DATA = "/Users/Admin/Decide9ja/decide9ja_scraper/data"
LGAS_FILE = f"{SCRAPER_DATA}/processed/lgas.json"
GOVERNORS_DIR = f"{SCRAPER_DATA}/candidates/governors"
SENATE_INDEX = f"{SCRAPER_DATA}/candidates/senate/_index.json"

# LGA to Senatorial District mapping
# Format: state -> {lga: senatorial_district}
LGA_TO_SENATORIAL = {
    "Abia": {
        # Abia North: Bende, Isuikwuato, Ohafia, Arochukwu, Umu Nneochi
        "Bende": "North", "Isuikwuato": "North", "Ohafia": "North", "Arochukwu": "North", "Umu Nneochi": "North",
        # Abia Central: Ikwuano, Umuahia North, Umuahia South, Isiala Ngwa North, Isiala Ngwa South
        "Ikwuano": "Central", "Umuahia North": "Central", "Umuahia South": "Central", "Isiala Ngwa North": "Central", "Isiala Ngwa South": "Central",
        # Abia South: Aba North, Aba South, Obingwa, Osisioma, Ugwunagbo, Ukwa East, Ukwa West, Obi Ngwa
        "Aba North": "South", "Aba South": "South", "Obingwa": "South", "Osisioma": "South", "Ugwunagbo": "South", "Ukwa East": "South", "Ukwa West": "South", "Obi Ngwa": "South",
    },
    "Lagos": {
        # Lagos Central: Lagos Island, Lagos Mainland, Surulere, Apapa, Eti-Osa
        "Lagos Island": "Central", "Lagos Mainland": "Central", "Surulere": "Central", "Apapa": "Central", "Eti-Osa": "Central",
        # Lagos East: Shomolu, Kosofe, Ibeju-Lekki, Ikorodu, Epe
        "Shomolu": "East", "Kosofe": "East", "Ibeju-Lekki": "East", "Ikorodu": "East", "Epe": "East",
        # Lagos West: Agege, Ifako-Ijaiye, Alimosho, Badagry, Ojo, Ajeromi-Ifelodun, Amuwo-Odofin, Oshodi-Isolo, Ikeja, Mushin
        "Agege": "West", "Ifako-Ijaiye": "West", "Alimosho": "West", "Badagry": "West", "Ojo": "West",
        "Ajeromi-Ifelodun": "West", "Amuwo-Odofin": "West", "Oshodi-Isolo": "West", "Ikeja": "West", "Mushin": "West",
    },
    "Ogun": {
        # Ogun Central: Abeokuta North, Abeokuta South, Ewekoro, Ifo, Obafemi-Owode, Odeda
        "Abeokuta North": "Central", "Abeokuta South": "Central", "Ewekoro": "Central", "Ifo": "Central", "Obafemi-Owode": "Central", "Odeda": "Central",
        # Ogun East: Ijebu East, Ijebu North, Ijebu North East, Ijebu-Ode, Ikenne, Odogbolu, Ogun Waterside, Remo North, Sagamu
        "Ijebu East": "East", "Ijebu North": "East", "Ijebu North East": "East", "Ijebu-Ode": "East", "Ikenne": "East", "Odogbolu": "East", "Ogun Waterside": "East", "Remo North": "East", "Sagamu": "East",
        # Ogun West: Ado-Odo/Ota, Ipokia, Yewa North, Yewa South, Imeko-Afon
        "Ado-Odo/Ota": "West", "Ipokia": "West", "Yewa North": "West", "Yewa South": "West", "Imeko-Afon": "West",
    },
    "FCT": {
        "Abaji": "FCT", "Bwari": "FCT", "Gwagwalada": "FCT", "Kuje": "FCT", "Kwali": "FCT", "Municipal Area Council": "FCT",
    },
}

def load_lgas():
    """Load all LGAs from JSON file."""
    with open(LGAS_FILE) as f:
        return json.load(f)

def load_governors():
    """Load governor data from individual state files."""
    governors = {}
    index_file = f"{GOVERNORS_DIR}/_index.json"
    
    with open(index_file) as f:
        index = json.load(f)
    
    for gov in index.get("governors", []):
        state = gov.get("state")
        governors[state] = {
            "name": gov.get("name"),
            "party": gov.get("party")
        }
    
    return governors

def load_senators():
    """Load senator data from index file."""
    senators = {}  # {(state, district): {name, party}}
    
    with open(SENATE_INDEX) as f:
        data = json.load(f)
    
    for sen in data.get("senators", []):
        state = sen.get("state")
        district = sen.get("district")
        senators[(state, district)] = {
            "name": sen.get("name"),
            "party": sen.get("party")
        }
    
    return senators

def get_senator_for_lga(state, lga, senators):
    """Find the senator for a given state/LGA."""
    # Try exact mapping first
    if state in LGA_TO_SENATORIAL and lga in LGA_TO_SENATORIAL[state]:
        district = LGA_TO_SENATORIAL[state][lga]
        key = (state, district)
        if key in senators:
            return senators[key], f"{state} {district}"
    
    # Try all senators for this state
    for (s, d), sen in senators.items():
        if s == state:
            # Return first match for state (will be improved with full mapping)
            return sen, f"{state} {d}"
    
    return None, None

def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not set")
        return
    
    print("Loading data...")
    lgas = load_lgas()
    governors = load_governors()
    senators = load_senators()
    
    print(f"Loaded {len(lgas)} LGAs, {len(governors)} governors, {len(senators)} senators")
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Ensure table exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS lga_representatives (
                id SERIAL PRIMARY KEY,
                state VARCHAR(50) NOT NULL,
                lga VARCHAR(100) NOT NULL,
                senatorial_district VARCHAR(100),
                governor_name VARCHAR(100),
                governor_party VARCHAR(20),
                senator_name VARCHAR(100),
                senator_party VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(state, lga)
            )
        """))
        conn.commit()
        
        inserted = 0
        for lga in lgas:
            state = lga["state"]
            lga_name = lga["name"]
            
            # Get governor
            gov = governors.get(state, {})
            gov_name = gov.get("name")
            gov_party = gov.get("party")
            
            # Get senator
            sen, sen_district = get_senator_for_lga(state, lga_name, senators)
            sen_name = sen.get("name") if sen else None
            sen_party = sen.get("party") if sen else None
            
            # Insert
            conn.execute(text("""
                INSERT INTO lga_representatives (state, lga, senatorial_district, governor_name, governor_party, senator_name, senator_party)
                VALUES (:state, :lga, :district, :gov_name, :gov_party, :sen_name, :sen_party)
                ON CONFLICT (state, lga) DO UPDATE SET
                    senatorial_district = EXCLUDED.senatorial_district,
                    governor_name = EXCLUDED.governor_name,
                    governor_party = EXCLUDED.governor_party,
                    senator_name = EXCLUDED.senator_name,
                    senator_party = EXCLUDED.senator_party,
                    updated_at = CURRENT_TIMESTAMP
            """), {
                "state": state, 
                "lga": lga_name, 
                "district": sen_district,
                "gov_name": gov_name, 
                "gov_party": gov_party, 
                "sen_name": sen_name, 
                "sen_party": sen_party
            })
            inserted += 1
        
        conn.commit()
        
        # Verify
        result = conn.execute(text("SELECT COUNT(*) FROM lga_representatives"))
        count = result.scalar()
        print(f"Inserted {inserted} LGA mappings, total in DB: {count}")
        
        # Test queries
        print("\n=== Test Queries ===")
        for test in [("Ogun", "Ijebu North"), ("Lagos", "Ikeja"), ("Abia", "Aba South")]:
            result = conn.execute(text("""
                SELECT state, lga, governor_name, governor_party, senator_name, senator_party
                FROM lga_representatives WHERE state = :state AND lga = :lga
            """), {"state": test[0], "lga": test[1]})
            row = result.fetchone()
            if row:
                print(f"{row[1]}, {row[0]}: Gov={row[2]} ({row[3]}), Sen={row[4]} ({row[5]})")

if __name__ == "__main__":
    main()
