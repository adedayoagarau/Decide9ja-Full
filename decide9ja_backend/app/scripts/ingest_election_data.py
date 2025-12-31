import os
import json
import glob
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal, Politician, init_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = "/Users/Admin/Decide9ja/decide9ja_scraper/data"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def parse_candidate_json(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None

def determine_current_position(data):
    """Infer current position from career data."""
    career = data.get("political_career", {})
    
    # Check current roles first
    positions = career.get("positions_held", [])
    for pos in positions:
        period = pos.get("period", "").lower()
        if "present" in period or "incumbent" in period:
            return pos.get("position"), pos.get("constituency")
            
    # Fallback: Check election history for 2023 wins
    history = career.get("election_history", [])
    for elect in history:
        if elect.get("year") == 2023 and "won" in elect.get("result", "").lower():
            return elect.get("position"), None # Constituency hard to guess from here
            
    return None, None

def ingest_candidates(db: Session):
    logger.info("Starting Candidate Ingestion...")
    
    # Pattern to match candidate JSONs
    # We look in specific subfolders to know the role context if needed
    files = glob.glob(f"{DATA_DIR}/candidates/**/*.json", recursive=True)
    logger.info(f"Found {len(files)} candidate files.")
    
    count = 0
    updated = 0
    seen_slugs = set()
    
    for file_path in files:
        if "_index.json" in file_path:
            continue
            
        data = parse_candidate_json(file_path)
        if not data:
            continue
            
        slug = data.get("slug")
        if not slug:
            continue
            
        if slug in seen_slugs:
            logger.warning(f"Duplicate slug found in batch, skipping: {slug} ({file_path})")
            continue
        
        seen_slugs.add(slug)

        name = data.get("name", {}).get("common", data.get("name", {}).get("full"))
        # ... rest of loop ...
        state = data.get("state")
        
        # Determine current status
        position, constituency = determine_current_position(data)
        
        # Determine party (last known)
        party = "Unknown"
        party_hist = data.get("political_career", {}).get("party_history", [])
        if party_hist:
            party = party_hist[-1].get("party", "Unknown")
        
        # Upsert
        existing = db.query(Politician).filter(Politician.slug == slug).first()
        if existing:
            existing.data_json = json.dumps(data)
            # Update fields if missing or just trust the new scraped data
            # trusting scraped data as fresh
            existing.name = name
            existing.party = party
            existing.state = state
            if position: existing.position = position
            if constituency: existing.constituency = constituency
            updated += 1
        else:
            pol = Politician(
                slug=slug,
                name=name,
                party=party,
                state=state,
                position=position or "Politician", # Default
                constituency=constituency,
                data_json=json.dumps(data)
            )
            db.add(pol)
            count += 1
            
        if (count + updated) % 100 == 0:
            db.commit()
            logger.info(f"Processed {count + updated} candidates...")
            
    db.commit()
    logger.info(f"Ingestion Complete. Created: {count}, Updated: {updated}")

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    ingest_candidates(db)
    db.close()
