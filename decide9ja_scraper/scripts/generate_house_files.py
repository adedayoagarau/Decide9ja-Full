#!/usr/bin/env python3
"""Generate individual House of Representatives member JSON files from the _index.json data."""

import json
import os
from pathlib import Path

# Base directory for House of Reps files
base_dir = Path("/Users/Admin/Decide9ja/decide9ja_scraper/data/candidates/house_of_reps")

# Read the index file
with open(base_dir / "_index.json", "r") as f:
    index_data = json.load(f)

def create_member_file(state, member_data):
    """Create a House member JSON file."""
    constituency = member_data["constituency"]
    name = member_data["name"]
    party = member_data["party"]
    
    # Create slug from name
    slug = name.lower().replace("'", "").replace(".", "").replace(" ", "-")
    
    # Create ID
    name_parts = name.split()
    if len(name_parts) >= 2:
        id_str = f"{name_parts[-1].lower()}_{name_parts[0].lower()}"
    else:
        id_str = name.lower().replace(" ", "_")
    
    data = {
        "id": id_str,
        "slug": slug,
        "state": state,
        "federal_constituency": constituency,
        "name": {
            "full": name,
            "common": name,
            "aliases": []
        },
        "party": party,
        "personal": {
            "date_of_birth": None,
            "state_of_origin": state,
            "lga_of_origin": None,
            "religion": None,
            "education": []
        },
        "political_career": {
            "positions_held": [
                {
                    "position": "Member, House of Representatives",
                    "constituency": f"{constituency} Federal Constituency",
                    "period": "2023-present"
                }
            ]
        },
        "house_info": {
            "committee_memberships": [],
            "bills_sponsored": [],
            "motions": [],
            "legislative_focus": []
        },
        "social_media": {
            "twitter": None,
            "facebook": None,
            "website": None
        },
        "metadata": {
            "data_quality_score": 0.45,
            "last_updated": "2025-12-27T21:30:00Z"
        }
    }
    
    return data

# Count created files
created = 0
skipped = 0

# Create files for each state's members
for state, state_data in index_data.get("state_constituencies", {}).items():
    for member in state_data.get("members", []):
        filename = member.get("file")
        if not filename:
            continue
            
        filepath = base_dir / filename
        
        # Skip if file already exists
        if filepath.exists():
            skipped += 1
            continue
        
        # Create the member data
        member_json = create_member_file(state, member)
        
        # Write to file
        with open(filepath, "w") as f:
            json.dump(member_json, f, indent=2)
        
        created += 1
        print(f"Created: {filename}")

print(f"\nDone! Created: {created}, Skipped (exists): {skipped}")
