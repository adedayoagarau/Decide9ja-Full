"""
Politician Card Generator for RAG Knowledge Base.
Generates retrieval-friendly "card" documents from structured politician data.

Each card is designed to:
1. Be self-contained (answers common questions without needing joins)
2. Include aliases for better matching
3. Have provenance metadata
4. Be optimized for embedding and retrieval
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict

from app.database import SessionLocal, Politician, Document
from app.services.embeddings import get_embedding, embedding_to_json

logger = logging.getLogger(__name__)


@dataclass
class PoliticianCard:
    """A RAG-optimized politician card."""
    # Identity
    politician_id: str
    name: str
    aliases: List[str]
    party: str
    party_full_name: str
    
    # Position
    position: str
    constituency: str
    state: str
    
    # Electoral geography (for jurisdiction matching)
    senatorial_district: Optional[str] = None
    federal_constituency: Optional[str] = None
    state_constituency: Optional[str] = None
    
    # Term info
    term_period: str = ""
    term_number: str = ""
    first_elected: Optional[int] = None
    
    # Background
    education: List[str] = None
    career_before_politics: str = ""
    
    # Legislative record
    committee_memberships: List[str] = None
    bills_sponsored: List[str] = None
    
    # Track record
    achievements: List[str] = None
    
    # Metadata
    data_quality: float = 0.0
    last_updated: str = ""
    source_type: str = "politician_database"
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.education is None:
            self.education = []
        if self.committee_memberships is None:
            self.committee_memberships = []
        if self.bills_sponsored is None:
            self.bills_sponsored = []
        if self.achievements is None:
            self.achievements = []
    
    def to_rag_document(self) -> str:
        """
        Convert to a RAG-optimized document string.
        Designed for embedding and retrieval.
        """
        lines = []
        
        # Header with key search terms
        lines.append(f"# {self.name}")
        if self.aliases:
            lines.append(f"Also known as: {', '.join(self.aliases)}")
        lines.append("")
        
        # Core identity block (most important for retrieval)
        lines.append(f"**Position:** {self.position}")
        lines.append(f"**Party:** {self.party} ({self.party_full_name})")
        lines.append(f"**State:** {self.state}")
        lines.append(f"**Constituency:** {self.constituency}")
        lines.append("")
        
        # Electoral geography (helps with jurisdiction queries)
        if self.position == "Senator" and self.senatorial_district:
            lines.append(f"**Senatorial District:** {self.state} {self.senatorial_district}")
        elif self.position == "House of Representatives" and self.federal_constituency:
            lines.append(f"**Federal Constituency:** {self.federal_constituency}")
        elif self.position == "Governor":
            lines.append(f"**Jurisdiction:** {self.state} State")
        lines.append("")
        
        # Term information
        if self.term_period:
            lines.append(f"**Term:** {self.term_period}")
        if self.term_number:
            lines.append(f"**Term Number:** {self.term_number}")
        if self.first_elected:
            lines.append(f"**First Elected:** {self.first_elected}")
        lines.append("")
        
        # Background
        if self.education:
            lines.append("**Education:**")
            for edu in self.education[:3]:  # Limit to 3
                lines.append(f"- {edu}")
            lines.append("")
        
        if self.career_before_politics:
            lines.append(f"**Background:** {self.career_before_politics}")
            lines.append("")
        
        # Legislative record
        if self.committee_memberships:
            lines.append("**Committee Memberships:**")
            for comm in self.committee_memberships[:5]:  # Limit to 5
                lines.append(f"- {comm}")
            lines.append("")
        
        if self.bills_sponsored:
            lines.append(f"**Bills Sponsored:** {len(self.bills_sponsored)} bills")
            lines.append("")
        
        # Achievements
        if self.achievements:
            lines.append("**Key Achievements:**")
            for ach in self.achievements[:3]:
                lines.append(f"- {ach}")
            lines.append("")
        
        # Provenance footer
        lines.append("---")
        lines.append(f"*Source: Decide9ja Politician Database | Updated: {self.last_updated[:10] if self.last_updated else 'Unknown'} | Data Quality: {self.data_quality:.0%}*")
        
        return "\n".join(lines)
    
    def get_search_text(self) -> str:
        """
        Get text optimized for embedding.
        Includes all searchable terms.
        """
        terms = [
            self.name,
            *self.aliases,
            self.party,
            self.party_full_name,
            self.position,
            self.constituency,
            self.state,
        ]
        
        if self.senatorial_district:
            terms.append(f"{self.state} {self.senatorial_district}")
            terms.append(f"{self.senatorial_district} Senatorial District")
        
        if self.federal_constituency:
            terms.append(self.federal_constituency)
            terms.append(f"{self.federal_constituency} Federal Constituency")
        
        return " | ".join([t for t in terms if t])


# Party name mapping
PARTY_FULL_NAMES = {
    "APC": "All Progressives Congress",
    "PDP": "Peoples Democratic Party",
    "LP": "Labour Party",
    "NNPP": "New Nigeria Peoples Party",
    "APGA": "All Progressives Grand Alliance",
    "YPP": "Young Progressives Party",
    "SDP": "Social Democratic Party",
    "ADC": "African Democratic Congress",
    "AA": "Action Alliance",
}


def extract_politician_card(politician: Politician) -> PoliticianCard:
    """
    Extract a PoliticianCard from a Politician database row.
    """
    data = {}
    if politician.data_json:
        try:
            data = json.loads(politician.data_json)
        except:
            pass
    
    # Get name and aliases
    name_data = data.get("name", {})
    if isinstance(name_data, dict):
        name = name_data.get("full", politician.name)
        aliases = name_data.get("aliases", [])
    else:
        name = politician.name
        aliases = []
    
    # Get party - check multiple locations
    party = politician.party
    if not party or party == "Unknown":
        party = data.get("party")
    if not party or party == "Unknown":
        # Check party_history (used by governors)
        political_career = data.get("political_career", {})
        party_history = political_career.get("party_history", [])
        if party_history:
            # Get current party (one without 'left' date)
            for ph in party_history:
                if ph.get("left") is None:
                    party = ph.get("party")
                    break
            if not party:
                party = party_history[0].get("party")
    if not party:
        party = "Unknown"
    
    party_full = PARTY_FULL_NAMES.get(party, party)
    
    # Get constituency based on position
    position = politician.position
    constituency = politician.constituency or ""
    
    senatorial_district = data.get("senatorial_district")
    federal_constituency = data.get("federal_constituency")
    
    if position == "Senator" and not constituency:
        constituency = f"{politician.state} {senatorial_district}" if senatorial_district else politician.state
    elif position == "House of Representatives" and not constituency:
        constituency = federal_constituency or ""
    elif position == "Governor":
        constituency = f"{politician.state} State"
    
    # Get term info
    term_info = data.get("term_info", {})
    political_career = data.get("political_career", {})
    
    positions_held = political_career.get("positions_held", [])
    term_period = ""
    if positions_held:
        current = positions_held[0]
        term_period = current.get("period", "")
    
    # Get background
    personal = data.get("personal", {})
    education = personal.get("education", [])
    if isinstance(education, list) and education and isinstance(education[0], dict):
        education = [f"{e.get('degree', '')} - {e.get('institution', '')}" for e in education if e.get('institution')]
    
    career_before = personal.get("career_before_politics", [])
    if isinstance(career_before, list) and career_before:
        if isinstance(career_before[0], dict):
            career_before = f"{career_before[0].get('role', '')} at {career_before[0].get('organization', '')}"
        else:
            career_before = ", ".join(career_before[:2])
    else:
        career_before = ""
    
    # Get legislative record
    senate_info = data.get("senate_info", {})
    house_info = data.get("house_info", {})
    legislative_info = senate_info if position == "Senator" else house_info
    
    committees = legislative_info.get("committee_memberships", [])
    bills = legislative_info.get("bills_sponsored", [])
    
    # Get achievements
    track_record = data.get("track_record", {})
    achievements = track_record.get("achievements", [])
    
    # Get metadata
    metadata = data.get("metadata", {})
    
    return PoliticianCard(
        politician_id=politician.slug or str(politician.id),
        name=name,
        aliases=aliases,
        party=party,
        party_full_name=party_full,
        position=position,
        constituency=constituency,
        state=politician.state or data.get("state", "Unknown"),
        senatorial_district=senatorial_district,
        federal_constituency=federal_constituency,
        term_period=term_period,
        term_number=term_info.get("current_term", ""),
        first_elected=term_info.get("first_elected"),
        education=education if isinstance(education, list) else [],
        career_before_politics=career_before if isinstance(career_before, str) else "",
        committee_memberships=committees,
        bills_sponsored=bills if isinstance(bills, list) else [],
        achievements=achievements if isinstance(achievements, list) else [],
        data_quality=metadata.get("data_quality_score", 0.5),
        last_updated=metadata.get("last_updated", datetime.now().isoformat()),
    )


def generate_all_politician_cards(db_session=None) -> List[PoliticianCard]:
    """
    Generate cards for all politicians in the database.
    """
    if db_session is None:
        db_session = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        politicians = db_session.query(Politician).all()
        cards = []
        
        for p in politicians:
            try:
                card = extract_politician_card(p)
                cards.append(card)
            except Exception as e:
                logger.warning(f"Failed to generate card for {p.name}: {e}")
        
        logger.info(f"Generated {len(cards)} politician cards")
        return cards
        
    finally:
        if should_close:
            db_session.close()


def save_cards_to_rag(cards: List[PoliticianCard], db_session=None) -> int:
    """
    Save politician cards to the RAG Document table.
    
    Returns:
        Number of documents created/updated
    """
    if db_session is None:
        db_session = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        created = 0
        
        for card in cards:
            # Generate document ID
            doc_id = f"politician_card_{card.politician_id}"
            
            # Check if exists
            existing = db_session.query(Document).filter(Document.doc_id == doc_id).first()
            
            # Generate content
            content = card.to_rag_document()
            search_text = card.get_search_text()
            
            # Generate embedding from search text + content
            embedding_text = f"{search_text}\n\n{content}"
            embedding = get_embedding(embedding_text)
            embedding_json = embedding_to_json(embedding)
            
            # Prepare metadata
            metadata = {
                "source_type": "politician_card",
                "politician_id": card.politician_id,
                "position": card.position,
                "party": card.party,
                "state": card.state,
                "data_quality": card.data_quality,
                "aliases": card.aliases,
            }
            
            if existing:
                # Update
                existing.title = f"Politician: {card.name}"
                existing.content = content
                existing.doc_type = "politician_card"
                existing.embedding_json = embedding_json
                existing.metadata_json = json.dumps(metadata)
                existing.state = card.state
                existing.party = card.party
            else:
                # Create
                doc = Document(
                    doc_id=doc_id,
                    title=f"Politician: {card.name}",
                    content=content,
                    doc_type="politician_card",
                    embedding_json=embedding_json,
                    metadata_json=json.dumps(metadata),
                    state=card.state,
                    party=card.party,
                )
                db_session.add(doc)
                created += 1
        
        db_session.commit()
        logger.info(f"Saved {len(cards)} politician cards ({created} new)")
        return len(cards)
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to save cards: {e}")
        raise
        
    finally:
        if should_close:
            db_session.close()


def run_card_generation():
    """
    Run the full card generation pipeline.
    """
    print("=== POLITICIAN CARD GENERATION ===")
    print()
    
    # Generate cards
    print("Step 1: Generating cards from database...")
    cards = generate_all_politician_cards()
    print(f"  Generated {len(cards)} cards")
    
    # Show sample
    print()
    print("Step 2: Sample card output:")
    if cards:
        sample = cards[0]
        print("-" * 50)
        print(sample.to_rag_document())
        print("-" * 50)
    
    # Save to RAG
    print()
    print("Step 3: Saving to RAG document store...")
    count = save_cards_to_rag(cards)
    print(f"  Saved {count} cards")
    
    print()
    print("=== COMPLETE ===")
    return count


# Test
if __name__ == "__main__":
    run_card_generation()
