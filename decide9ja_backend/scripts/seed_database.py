"""
Database Seeding Script
Loads all JSON data from decide9ja_scraper/data/ into SQLite.
Generates embeddings for semantic search.
"""
import os
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, SessionLocal, Document, Politician
from app.services.embeddings import get_embedding, embedding_to_json

# Path to scraped data
DATA_DIR = Path(__file__).parent.parent.parent / "decide9ja_scraper" / "data"


def load_json_file(filepath: Path) -> dict:
    """Load a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def safe_add_or_update(db, model_class, unique_key, unique_value, **kwargs):
    """Safely add or update a record, handling duplicates."""
    existing = db.query(model_class).filter(getattr(model_class, unique_key) == unique_value).first()
    if existing:
        # Update existing record
        for key, value in kwargs.items():
            setattr(existing, key, value)
        return existing, False  # Existed
    else:
        # Create new record
        obj = model_class(**{unique_key: unique_value, **kwargs})
        db.add(obj)
        return obj, True  # New


def seed_senators(db):
    """Load senator data."""
    print("\n📥 Loading Senators...")
    senate_dir = DATA_DIR / "candidates" / "senate"
    
    if not senate_dir.exists():
        print("  ⚠️ Senate directory not found")
        return 0
    
    count = 0
    skipped = 0
    for filepath in senate_dir.glob("*.json"):
        if filepath.name.startswith("_"):  # Skip index files
            continue
            
        try:
            data = load_json_file(filepath)
            
            # Handle nested name structure
            raw_name = data.get("name", "Unknown")
            if isinstance(raw_name, dict):
                name = raw_name.get("full", raw_name.get("common", "Unknown"))
            else:
                name = str(raw_name)
            
            party = data.get("party", "Unknown")
            state = data.get("state", "")
            district = data.get("senatorial_district", data.get("constituency", ""))
            
            content = f"""
Senator: {name}
Party: {party}
State: {state}
Senatorial District: {district}
Term: {data.get('term', '')}
Committee Assignments: {data.get('committee_assignments', 'N/A')}
Contact: {data.get('contact', 'N/A')}
"""
            
            # Generate embedding
            embedding = get_embedding(content)
            
            # Create document (use doc_id as unique key)
            _, doc_is_new = safe_add_or_update(
                db, Document, "doc_id", filepath.stem,
                doc_type="senator",
                title=f"Senator {name} ({party}) - {district}",
                content=content.strip(),
                metadata_json=json.dumps(data),
                embedding_json=embedding_to_json(embedding),
                state=state,
                party=party,
                position="Senator"
            )
            
            # Also add to politicians table
            _, pol_is_new = safe_add_or_update(
                db, Politician, "slug", filepath.stem,
                name=name,
                party=party,
                position="Senator",
                state=state,
                constituency=district,
                data_json=json.dumps(data)
            )
            
            if doc_is_new or pol_is_new:
                count += 1
            else:
                skipped += 1
                
            if (count + skipped) % 20 == 0:
                print(f"  Processed {count + skipped} senators ({skipped} skipped)...")
                db.commit()
                
        except Exception as e:
            db.rollback()  # Rollback on error to keep session valid
            print(f"  ⚠️ Error loading {filepath.name}: {e}")
    
    db.commit()
    print(f"  ✅ Loaded {count} senators ({skipped} already existed)")
    return count


def seed_house_of_reps(db):
    """Load House of Representatives data."""
    print("\n📥 Loading House of Representatives...")
    house_dir = DATA_DIR / "candidates" / "house_of_reps"
    
    if not house_dir.exists():
        print("  ⚠️ House of Reps directory not found")
        return 0
    
    count = 0
    skipped = 0
    for filepath in house_dir.glob("*.json"):
        if filepath.name.startswith("_"):
            continue
            
        try:
            data = load_json_file(filepath)
            
            # Handle nested name structure
            raw_name = data.get("name", "Unknown")
            if isinstance(raw_name, dict):
                name = raw_name.get("full", raw_name.get("common", "Unknown"))
            else:
                name = str(raw_name)
            
            party = data.get("party", "Unknown")
            state = data.get("state", "")
            constituency = data.get("constituency", data.get("federal_constituency", ""))
            
            content = f"""
House Member: {name}
Party: {party}
State: {state}
Federal Constituency: {constituency}
Term: {data.get('term', '')}
"""
            
            embedding = get_embedding(content)
            
            _, doc_is_new = safe_add_or_update(
                db, Document, "doc_id", filepath.stem,
                doc_type="house_member",
                title=f"Hon. {name} ({party}) - {constituency}",
                content=content.strip(),
                metadata_json=json.dumps(data),
                embedding_json=embedding_to_json(embedding),
                state=state,
                party=party,
                position="House of Representatives"
            )
            
            _, pol_is_new = safe_add_or_update(
                db, Politician, "slug", filepath.stem,
                name=name,
                party=party,
                position="House of Representatives",
                state=state,
                constituency=constituency,
                data_json=json.dumps(data)
            )
            
            if doc_is_new or pol_is_new:
                count += 1
            else:
                skipped += 1
                
            if (count + skipped) % 50 == 0:
                print(f"  Processed {count + skipped} House members ({skipped} skipped)...")
                db.commit()
                
        except Exception as e:
            db.rollback()
            print(f"  ⚠️ Error loading {filepath.name}: {e}")
    
    db.commit()
    print(f"  ✅ Loaded {count} House members ({skipped} already existed)")
    return count


def seed_governors(db):
    """Load governor data."""
    print("\n📥 Loading Governors...")
    gov_dir = DATA_DIR / "candidates" / "governors"
    
    if not gov_dir.exists():
        print("  ⚠️ Governors directory not found")
        return 0
    
    count = 0
    skipped = 0
    for filepath in gov_dir.glob("*.json"):
        if filepath.name.startswith("_"):
            continue
            
        try:
            data = load_json_file(filepath)
            
            # Handle nested name structure
            raw_name = data.get("name", "Unknown")
            if isinstance(raw_name, dict):
                name = raw_name.get("full", raw_name.get("common", "Unknown"))
            else:
                name = str(raw_name)
            
            party = data.get("party", "Unknown")
            state = data.get("state", "")
            
            content = f"""
Governor: {name}
Party: {party}
State: {state}
Term: {data.get('term', '')}
Deputy: {data.get('deputy_governor', 'N/A')}
"""
            
            embedding = get_embedding(content)
            
            _, doc_is_new = safe_add_or_update(
                db, Document, "doc_id", filepath.stem,
                doc_type="governor",
                title=f"Governor {name} ({party}) - {state}",
                content=content.strip(),
                metadata_json=json.dumps(data),
                embedding_json=embedding_to_json(embedding),
                state=state,
                party=party,
                position="Governor"
            )
            
            _, pol_is_new = safe_add_or_update(
                db, Politician, "slug", filepath.stem,
                name=name,
                party=party,
                position="Governor",
                state=state,
                constituency=state,
                data_json=json.dumps(data)
            )
            
            if doc_is_new or pol_is_new:
                count += 1
            else:
                skipped += 1
                
        except Exception as e:
            db.rollback()
            print(f"  ⚠️ Error loading {filepath.name}: {e}")
    
    db.commit()
    print(f"  ✅ Loaded {count} governors ({skipped} already existed)")
    return count


def seed_election_results(db):
    """Load election results."""
    print("\n📥 Loading Election Results...")
    
    results_file = DATA_DIR / "elections" / "presidential_2023_official.json"
    
    if not results_file.exists():
        print("  ⚠️ Election results file not found")
        return 0
    
    try:
        data = load_json_file(results_file)
        
        # Create one document per state result
        count = 0
        for state_result in data:
            state = state_result.get("state", "Unknown")
            
            content = f"""
2023 Presidential Election Results - {state}
APC (Tinubu): {state_result.get('apc_tinubu', 0):,} votes
PDP (Atiku): {state_result.get('pdp_atiku', 0):,} votes
LP (Obi): {state_result.get('lp_obi', 0):,} votes
NNPP (Kwankwaso): {state_result.get('nnpp_kwankwaso', 0):,} votes
"""
            
            embedding = get_embedding(content)
            
            doc = Document(
                doc_type="election_result",
                doc_id=f"presidential_2023_{state.lower().replace(' ', '_')}",
                title=f"2023 Presidential Results - {state}",
                content=content.strip(),
                metadata_json=json.dumps(state_result),
                embedding_json=embedding_to_json(embedding),
                state=state,
                category="election"
            )
            db.add(doc)
            count += 1
        
        db.commit()
        print(f"  ✅ Loaded {count} state election results")
        return count
        
    except Exception as e:
        print(f"  ⚠️ Error loading election results: {e}")
        return 0


def seed_presidential_candidates(db):
    """Load presidential candidates data (including current President)."""
    print("\n📥 Loading Presidential Candidates...")
    pres_dir = DATA_DIR / "candidates" / "2023" / "presidential"

    if not pres_dir.exists():
        print("  ⚠️ Presidential candidates directory not found")
        return 0

    count = 0
    skipped = 0
    for filepath in pres_dir.glob("*.json"):
        if filepath.name.startswith("_"):  # Skip index files
            continue

        try:
            data = load_json_file(filepath)

            # Handle nested name structure
            raw_name = data.get("name", "Unknown")
            if isinstance(raw_name, dict):
                name = raw_name.get("full", raw_name.get("common", "Unknown"))
            else:
                name = str(raw_name)

            # Determine current position from positions_held
            political_career = data.get("political_career", {})
            positions_held = political_career.get("positions_held", [])

            # Find current position (period contains "present")
            current_position = "Presidential Candidate (2023)"
            for pos in positions_held:
                period = pos.get("period", "")
                if "present" in period.lower():
                    current_position = pos.get("position", current_position)
                    break

            # Get party from party_history (most recent)
            party_history = political_career.get("party_history", [])
            party = "Unknown"
            for ph in party_history:
                if ph.get("left") is None:  # Current party
                    party = ph.get("party", "Unknown")
                    break
            if party == "Unknown" and party_history:
                party = party_history[-1].get("party", "Unknown")

            # Get state of origin
            personal = data.get("personal", {})
            state = personal.get("state_of_origin", "")

            # Build content for embedding
            policy_summary = ""
            for policy in data.get("policy_positions", [])[:3]:
                issue = policy.get("issue_area", "")
                stance = policy.get("stance_summary", "")[:200]
                if issue and stance:
                    policy_summary += f"{issue}: {stance}\n"

            track_record = ""
            for achievement in data.get("track_record", {}).get("achievements", [])[:3]:
                track_record += f"• {achievement.get('achievement', '')}\n"

            content = f"""
{current_position}: {name}
Party: {party}
State of Origin: {state}

POLICY POSITIONS:
{policy_summary}

TRACK RECORD:
{track_record}

PERSONAL:
Date of Birth: {personal.get('date_of_birth', 'N/A')}
Religion: {personal.get('religion', 'N/A')}
Education: {', '.join([e.get('institution', '') for e in personal.get('education', [])[-2:]])}
"""

            embedding = get_embedding(content)

            # Create document
            _, doc_is_new = safe_add_or_update(
                db, Document, "doc_id", filepath.stem,
                doc_type="presidential_candidate",
                title=f"{current_position} {name} ({party})",
                content=content.strip(),
                metadata_json=json.dumps(data),
                embedding_json=embedding_to_json(embedding),
                state=state,
                party=party,
                position=current_position
            )

            # Also add to politicians table
            _, pol_is_new = safe_add_or_update(
                db, Politician, "slug", filepath.stem,
                name=name,
                party=party,
                position=current_position,
                state=state,
                constituency="Federal",
                data_json=json.dumps(data)
            )

            if doc_is_new or pol_is_new:
                count += 1
            else:
                skipped += 1

        except Exception as e:
            db.rollback()
            print(f"  ⚠️ Error loading {filepath.name}: {e}")

    db.commit()
    print(f"  ✅ Loaded {count} presidential candidates ({skipped} already existed)")
    return count


def seed_polls(db):
    """Load polling data."""
    print("\n📥 Loading Polling Data...")

    polls_file = DATA_DIR / "polls" / "noi_polls" / "opinion_polls.json"
    
    if not polls_file.exists():
        print("  ⚠️ Polls file not found")
        return 0
    
    try:
        data = load_json_file(polls_file)
        polls = data.get("polls", [])
        
        count = 0
        for poll in polls:
            title = poll.get("title", "Unknown Poll")
            date = poll.get("date", "")
            
            content = f"""
Poll: {title}
Date: {date}
Category: {poll.get('category', 'General')}
Key Findings: {', '.join(poll.get('key_findings', []))}
Source: NOI Polls
"""
            
            embedding = get_embedding(content)
            
            doc = Document(
                doc_type="poll",
                doc_id=f"noi_poll_{count}",
                title=title,
                content=content.strip(),
                metadata_json=json.dumps(poll),
                embedding_json=embedding_to_json(embedding),
                category="poll"
            )
            db.add(doc)
            count += 1
        
        db.commit()
        print(f"  ✅ Loaded {count} polls")
        return count
        
    except Exception as e:
        print(f"  ⚠️ Error loading polls: {e}")
        return 0


def main():
    """Main seeding function."""
    print("=" * 50)
    print("🌱 DECIDE9JA DATABASE SEEDING")
    print("=" * 50)
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    
    # Check data directory
    if not DATA_DIR.exists():
        print(f"❌ Data directory not found: {DATA_DIR}")
        return
    
    print(f"📂 Data directory: {DATA_DIR}")
    
    # Create session
    db = SessionLocal()
    
    try:
        total = 0
        
        # Seed different data types
        total += seed_senators(db)
        total += seed_house_of_reps(db)
        total += seed_governors(db)
        total += seed_presidential_candidates(db)  # NEW: Load presidential data
        total += seed_election_results(db)
        total += seed_polls(db)
        
        print("\n" + "=" * 50)
        print(f"🎉 SEEDING COMPLETE: {total} documents loaded")
        print("=" * 50)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
