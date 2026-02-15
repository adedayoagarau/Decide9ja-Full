#!/usr/bin/env python3
"""
Ingest Gap Data
===============
Ingests remaining high-value datasets into the RAG system:
1. Politician Dossiers -> Enriches `Politician` table
2. 2023 Presidential Election Results -> `rag_documents`
3. Party Metadata -> `rag_documents`
"""
import os
import sys
import json
import glob
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, Document, Politician, get_db
from app.services.embeddings import get_embedding, embedding_to_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Paths
DATA_ROOT = "/Volumes/Crucial X10/Decide9ja"
DOSSIER_DIR = os.path.join(DATA_ROOT, "decide9ja_backend/nigeria_knowledge_data/politician_dossiers")
ELECTION_RESULTS_FILE = os.path.join(DATA_ROOT, "decide9ja_scraper/data/elections/presidential_2023_official.json")
PARTIES_FILE = os.path.join(DATA_ROOT, "decide9ja_scraper/data/processed/parties.json")

def ingest_politician_dossiers(session):
    """Enrich existing politicians with dossier data."""
    logger.info("Starting Politician Dossier Enrichment...")
    files = glob.glob(os.path.join(DOSSIER_DIR, "*.json"))
    logger.info(f"Found {len(files)} dossier files.")
    
    updated_count = 0
    not_found_count = 0
    
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Identify politician (try slug matching first, then name)
            # The dossiers seem to use a location-based slug, so name is safer?
            # Let's try name query first
            pol = session.query(Politician).filter(Politician.name == data.get('name')).first()
            
            if not pol:
                # Try partial match or manual slug override if needed? 
                # For now let's skip to keep it safe.
                # logger.warning(f"Politician not found for dossier: {data.get('name')}")
                not_found_count += 1
                continue
                
            # Parse existing data_json
            pol_data = json.loads(pol.data_json) if pol.data_json else {}
            
            # Enrich with new fields if they exist and are not empty
            enrichment_fields = [
                'bills_sponsored', 'bills_passed', 'motions_moved', 
                'committee_memberships', 'voting_record', 'attendance_rate',
                'education', 'career_before_politics', 'issue_involvements',
                'timeline'
            ]
            
            for field in enrichment_fields:
                if data.get(field):
                    pol_data[field] = data[field]
            
            # Update source metadata
            pol_data['dossier_updated_at'] = datetime.now().isoformat()
            
            pol.data_json = json.dumps(pol_data)
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")
            
    session.commit()
    logger.info(f"Enriched {updated_count} politicians. {not_found_count} not found.")

def ingest_election_results(session):
    """Ingest 2023 Presidential Election Results as RAG Documents."""
    logger.info("Starting Election Results Ingestion...")
    if not os.path.exists(ELECTION_RESULTS_FILE):
        logger.error(f"Election results file not found: {ELECTION_RESULTS_FILE}")
        return

    with open(ELECTION_RESULTS_FILE, 'r') as f:
        results = json.load(f)
        
    documents = []
    
    for state_result in results:
        state = state_result.get('state')
        
        # Construct a narrative text for the embedding
        # "In Lagos state, LP candidate Peter Obi received 582,454 votes..."
        text_parts = [f"2023 Presidential Election Results for {state} State:"]
        
        # Map keys to readable names
        candidates = [
            ('apc_tinubu', 'Bola Ahmed Tinubu (APC)'),
            ('pdp_atiku', 'Atiku Abubakar (PDP)'),
            ('lp_obi', 'Peter Obi (LP)'),
            ('nnpp_kwankwaso', 'Rabiu Kwankwaso (NNPP)')
        ]
        
        # Sort by votes for better narrative
        votes = []
        for key, name in candidates:
            count = state_result.get(key, 0)
            votes.append((count, name))
        votes.sort(key=lambda x: x[0], reverse=True)
        
        winner_count, winner_name = votes[0]
        text_parts.append(f"The winner was {winner_name} with {winner_count:,} votes.")
        
        for count, name in votes[1:]:
            text_parts.append(f"{name} received {count:,} votes.")
            
        content = "\n".join(text_parts)
        
        # Check if already exists
        doc_id = f"election_result_2023_presidential_{state.lower().replace(' ', '_')}"
        if session.query(Document).filter(Document.doc_id == doc_id).first():
            continue
            
        # Create Document
        emb = get_embedding(content)
        
        doc = Document(
            doc_type="election_result",
            doc_id=doc_id,
            title=f"2023 Presidential Election Result - {state}",
            content=content,
            metadata_json=json.dumps({
                "state": state,
                "election_type": "presidential", 
                "year": 2023,
                "raw_data": state_result
            }),
            embedding_json=embedding_to_json(emb),
            category="election",
            state=state,
            created_at=datetime.now()
        )
        documents.append(doc)
        
    if documents:
        session.bulk_save_objects(documents)
        session.commit()
    logger.info(f"Ingested {len(documents)} election result documents.")

def ingest_party_metadata(session):
    """Ingest Party Metadata as RAG Documents."""
    logger.info("Starting Party Metadata Ingestion...")
    if not os.path.exists(PARTIES_FILE):
        logger.error(f"Parties file not found: {PARTIES_FILE}")
        return

    with open(PARTIES_FILE, 'r') as f:
        parties = json.load(f)
        
    documents = []
    
    for party in parties:
        # Create narrative content
        # "The Labour Party (LP) is led by Chairman X..."
        name = party.get("name")
        abbr = party.get("abbreviation")
        chairman = party.get("chairman")
        
        text_parts = [f"Political Party Profile: {name} ({abbr})"]
        if chairman:
            text_parts.append(f"Chairman: {chairman}")
        if party.get("secretary"):
            text_parts.append(f"Secretary: {party.get('secretary')}")
        if party.get("treasurer"):
            text_parts.append(f"Treasurer: {party.get('treasurer')}")
        if party.get("address"):
            text_parts.append(f"Address: {party.get('address')}")
            
        content = "\n".join(text_parts)
        
        doc_id = f"party_profile_{abbr.lower()}"
        if session.query(Document).filter(Document.doc_id == doc_id).first():
            continue
            
        emb = get_embedding(content)
        
        doc = Document(
            doc_type="party_profile",
            doc_id=doc_id,
            title=f"Political Party Profile: {name} ({abbr})",
            content=content,
            metadata_json=json.dumps(party),
            embedding_json=embedding_to_json(emb),
            category="politician", # Closest category
            party=abbr,
            created_at=datetime.now()
        )
        documents.append(doc)
        
    if documents:
        session.bulk_save_objects(documents)
        session.commit()
    logger.info(f"Ingested {len(documents)} party profiles.")

def main():
    # get_db is a generator, usage: next(get_db()) or with context
    db_gen = get_db()
    db = next(db_gen)
    try:
        ingest_politician_dossiers(db)
        ingest_election_results(db)
        ingest_party_metadata(db)
        logger.info("Gap Data Ingestion Complete.")
    finally:
        # DB session closed by generator cleanup or explicit close if needed
        # In this simple script pattern, just closing the session object is safer if yielded
        db.close()

if __name__ == "__main__":
    main()
