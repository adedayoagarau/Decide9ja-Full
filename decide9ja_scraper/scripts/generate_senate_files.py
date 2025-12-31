#!/usr/bin/env python3
"""Generate individual senator JSON files from the _index.json data."""

import json
import os
from pathlib import Path

# Base directory for senate files
base_dir = Path("/Users/Admin/Decide9ja/decide9ja_scraper/data/candidates/senate")

# Read the index file
with open(base_dir / "_index.json", "r") as f:
    index_data = json.load(f)

# Template for a senator file
def create_senator_file(senator_data):
    """Create a senator JSON file."""
    state = senator_data["state"]
    district = senator_data["district"]
    name = senator_data["name"]
    party = senator_data["party"]
    
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
        "senatorial_district": district,
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
                    "position": "Senator",
                    "constituency": f"{state} {district}",
                    "period": "2023-present"
                }
            ]
        },
        "senate_info": {
            "committee_memberships": [],
            "bills_sponsored": [],
            "legislative_focus": []
        },
        "social_media": {
            "twitter": None,
            "facebook": None,
            "website": None
        },
        "metadata": {
            "data_quality_score": 0.45,
            "last_updated": "2025-12-27T21:00:00Z"
        }
    }
    
    return data

# Count created files
created = 0
skipped = 0

# Create files for each senator
for senator in index_data["senators"]:
    filename = senator["file"]
    filepath = base_dir / filename
    
    # Skip if file already exists
    if filepath.exists():
        skipped += 1
        continue
    
    # Create the senator data
    senator_data = create_senator_file(senator)
    
    # Write to file
    with open(filepath, "w") as f:
        json.dump(senator_data, f, indent=2)
    
    created += 1
    print(f"Created: {filename}")

print(f"\nDone! Created: {created}, Skipped (exists): {skipped}")
