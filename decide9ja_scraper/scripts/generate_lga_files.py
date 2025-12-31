import os
import json
import datetime

BASE_DIR = "data/candidates/lga_chairmen"

def generate_lga_files():
    total_generated = 0
    total_skipped = 0
    
    # Iterate through all state directories
    if not os.path.exists(BASE_DIR):
        print(f"Error: Base directory {BASE_DIR} not found.")
        return

    for state_dir in os.listdir(BASE_DIR):
        state_path = os.path.join(BASE_DIR, state_dir)
        
        # Skip files, only process directories
        if not os.path.isdir(state_path):
            continue
            
        index_file = os.path.join(state_path, "_index.json")
        if not os.path.exists(index_file):
            print(f"Skipping {state_dir}: No _index.json found")
            continue
            
        try:
            with open(index_file, 'r') as f:
                state_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error decoding JSON in {index_file}")
            continue

        state_name = state_data.get("state") or state_data.get("territory")
        chairmen = state_data.get("chairmen", []) or state_data.get("area_councils", [])
        
        print(f"Processing {state_name} ({len(chairmen)} LGAs)...")

        for lga in chairmen:
            filename = lga.get("file")
            if not filename:
                continue
                
            file_path = os.path.join(state_path, filename)
            
            # Don't overwrite if manually created (though mostly they aren't yet)
            # Actually, for this bulk gen, let's allow overwrite or update if needed, 
            # but for now standard creation.
            
            lga_name = lga.get("lga") or lga.get("area_council")
            chairman_name = lga.get("name", "DATA_PENDING")
            party = lga.get("party", "Unknown")
            
            # Basic structure for individual file
            lga_data = {
                "id": f"{state_name.lower().replace(' ', '_')}_{lga_name.lower().replace(' ', '_').replace('/', '_')}",
                "name": chairman_name,
                "party": party,
                "position": "LGA Chairman",
                "lga": lga_name,
                "state": state_name,
                "election_date": state_data.get("last_lga_election") or state_data.get("last_area_council_election"),
                "term_end": state_data.get("next_election_due"),
                "data_status": "VERIFIED" if chairman_name != "DATA_PENDING" else "MISSING_NAME",
                "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
            }
            
            with open(file_path, 'w') as out_f:
                json.dump(lga_data, out_f, indent=2)
                total_generated += 1

    print(f"\nCompleted! Generated {total_generated} individual LGA files.")

if __name__ == "__main__":
    generate_lga_files()
