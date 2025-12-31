import json
import logging
import os
from datetime import datetime
from app.database import SessionLocal, Document, init_db
from app.services.embeddings import get_embedding, embedding_to_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "/Users/Admin/Decide9ja/decide9ja_scraper/data/elections/presidential_2023_official.json"

def ingest_presidential_results():
    if not os.path.exists(DATA_FILE):
        logger.error(f"Data file not found: {DATA_FILE}")
        return

    with open(DATA_FILE, 'r') as f:
        results = json.load(f)

    db = SessionLocal()
    count = 0
    
    try:
        now = datetime.now().isoformat()

        for res in results:
            state = res.get("state")
            if not state: continue

            # Extract votes
            votes = {
                "APC (Tinubu)": res.get("apc_tinubu", 0),
                "PDP (Atiku)": res.get("pdp_atiku", 0),
                "LP (Obi)": res.get("lp_obi", 0),
                "NNPP (Kwankwaso)": res.get("nnpp_kwankwaso", 0)
            }
            
            # Sort by votes
            sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
            winner, win_votes = sorted_votes[0]
            total_votes = sum(votes.values())
            
            # Content Generation
            lines = []
            lines.append(f"# 2023 Presidential Election Result: {state} State")
            lines.append(f"**Winner:** {winner} - {win_votes:,} votes ({win_votes/total_votes*100:.1f}%)")
            lines.append("")
            lines.append("## Full Breakdown")
            for party, v in sorted_votes:
                lines.append(f"- **{party}:** {v:,} ({v/total_votes*100:.1f}%)")
            
            lines.append("")
            lines.append("---")
            lines.append(f"*Source: INEC Official Results | Ingested: {now[:10]}*")
            
            content = "\n".join(lines)
            
            # Metadata
            doc_id = f"election_2023_pres_{state.lower().replace(' ', '_')}"
            metadata = {
                "source_type": "election_result_card",
                "election_type": "presidential",
                "year": 2023,
                "state": state,
                "winner": winner
            }
            
            # Embedding
            search_text = f"2023 presidential election result {state} who won in {state} tinubu atiku obi votes"
            embedding = get_embedding(f"{search_text}\n\n{content}")
            
            # Upsert
            existing = db.query(Document).filter(Document.doc_id == doc_id).first()
            if existing:
                existing.content = content
                existing.embedding_json = embedding_to_json(embedding)
                existing.metadata_json = json.dumps(metadata)
                existing.title = f"2023 Presidential Result: {state}"
            else:
                doc = Document(
                    doc_id=doc_id,
                    title=f"2023 Presidential Result: {state}",
                    content=content,
                    doc_type="election_result_card",
                    embedding_json=embedding_to_json(embedding),
                    metadata_json=json.dumps(metadata),
                    state=state
                )
                db.add(doc)
            count += 1
        
        db.commit()
        logger.info(f"Ingested {count} Presidential Result Cards")
        
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    ingest_presidential_results()
