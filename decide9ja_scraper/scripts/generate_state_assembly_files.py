#!/usr/bin/env python3
"""
Generate individual State Assembly member JSON files from state index files.
"""

import json
from pathlib import Path
from datetime import datetime

base_dir = Path("/Users/Admin/Decide9ja/decide9ja_scraper/data/candidates/state_assembly")

def create_filename(constituency):
    """Generate filename from constituency"""
    filename = constituency.lower()
    filename = filename.replace("/", "_").replace(" ", "_").replace("-", "_").replace("'", "")
    while "__" in filename:
        filename = filename.replace("__", "_")
    return f"{filename}.json"

def create_member_data(state, member, state_data):
    """Create member JSON data"""
    name = member["name"]
    constituency = member["constituency"]
    party = member["party"]
    
    # Generate ID and slug
    name_clean = name.replace("Hon.", "").replace("Rt.", "").replace("Barr.", "").replace("Chief", "").replace("Mrs.", "").replace("Engr.", "").replace("Comr.", "").strip()
    slug = name_clean.lower().replace("'", "").replace(".", "").replace(" ", "-")
    name_parts = name_clean.split()
    if len(name_parts) >= 2:
        id_str = f"{name_parts[-1].lower()}_{name_parts[0].lower()}"
    else:
        id_str = name_clean.lower().replace(" ", "_")
    
    member_json = {
        "id": id_str,
        "slug": slug,
        "state": state,
        "state_constituency": constituency,
        "name": {
            "full": name,
            "common": name_clean,
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
                    "position": "Member, State House of Assembly",
                    "constituency": f"{constituency} State Constituency",
                    "period": "2023-present"
                }
            ]
        },
        "assembly_info": {
            "assembly_term": state_data.get("assembly_term", "10th Assembly"),
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
            "data_quality_score": 0.50,
            "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    }
    
    # Add role if present
    if "role" in member:
        member_json["assembly_info"]["role"] = member["role"]
    
    # Add defection info if present
    if member.get("defected"):
        member_json["political_career"]["defection"] = {
            "defected": True,
            "original_party": "PDP",
            "new_party": "APC",
            "date": "December 2023"
        }
    
    return member_json

def process_state(state_dir):
    """Process a state directory and generate member files"""
    index_file = state_dir / "_index.json"
    if not index_file.exists():
        return 0
    
    with open(index_file, "r") as f:
        state_data = json.load(f)
    
    state = state_data.get("state", state_dir.name.replace("_", " ").title())
    created = 0
    
    for member in state_data.get("members", []):
        filename = create_filename(member["constituency"])
        filepath = state_dir / filename
        
        if filepath.exists():
            continue
        
        member_json = create_member_data(state, member, state_data)
        
        with open(filepath, "w") as f:
            json.dump(member_json, f, indent=2)
        
        created += 1
    
    return created

# Process all state directories
total_created = 0
for state_dir in sorted(base_dir.iterdir()):
    if state_dir.is_dir():
        count = process_state(state_dir)
        if count > 0:
            print(f"{state_dir.name}: Created {count} member files")
            total_created += count

print(f"\nTotal member files created: {total_created}")

# Count all files
total_files = 0
for state_dir in base_dir.iterdir():
    if state_dir.is_dir():
        files = list(state_dir.glob("*.json"))
        total_files += len(files)
        
print(f"Total JSON files in state_assembly: {total_files}")
