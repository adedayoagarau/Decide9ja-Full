"""
Jurisdiction Card Generator for RAG Knowledge Base.
Generates cards that map administrative units to electoral units and officeholders.

Card Types:
1. State Cards (37) - State overview with all representatives
2. Senatorial District Cards (109) - District with senator and LGAs
3. Federal Constituency Cards (360) - Constituency with house rep and LGAs
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict

from app.database import SessionLocal, Politician, Document
from app.services.embeddings import get_embedding, embedding_to_json

logger = logging.getLogger(__name__)


@dataclass
class StateCard:
    """Card for a Nigerian state."""
    state_id: str
    state_name: str
    geopolitical_zone: str
    
    # Representatives
    governor: Optional[Dict] = None  # {name, party}
    senators: List[Dict] = field(default_factory=list)  # [{name, party, district}]
    house_reps_count: int = 0
    
    # Geography
    senatorial_districts: List[str] = field(default_factory=list)
    federal_constituencies: List[str] = field(default_factory=list)
    
    # Metadata
    last_updated: str = ""
    
    def to_rag_document(self) -> str:
        """Convert to RAG-optimized document."""
        lines = []
        
        # Header
        lines.append(f"# {self.state_name} State")
        lines.append(f"**Geopolitical Zone:** {self.geopolitical_zone}")
        lines.append("")
        
        # Governor
        if self.governor:
            lines.append(f"## Governor")
            lines.append(f"**{self.governor['name']}** ({self.governor['party']})")
            lines.append("")
        
        # Senators
        if self.senators:
            lines.append(f"## Senators ({len(self.senators)})")
            for sen in self.senators:
                lines.append(f"- **{sen['name']}** ({sen['party']}) - {self.state_name} {sen['district']}")
            lines.append("")
        
        # Senatorial Districts
        if self.senatorial_districts:
            lines.append(f"## Senatorial Districts ({len(self.senatorial_districts)})")
            for dist in self.senatorial_districts:
                lines.append(f"- {self.state_name} {dist}")
            lines.append("")
        
        # Federal Constituencies
        if self.federal_constituencies:
            lines.append(f"## Federal Constituencies ({len(self.federal_constituencies)})")
            for const in self.federal_constituencies[:10]:  # Limit display
                lines.append(f"- {const}")
            if len(self.federal_constituencies) > 10:
                lines.append(f"- ... and {len(self.federal_constituencies) - 10} more")
            lines.append("")
        
        # House Reps count
        lines.append(f"**Total House Representatives:** {self.house_reps_count}")
        lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"*Source: Decide9ja Jurisdiction Database | Updated: {self.last_updated[:10] if self.last_updated else 'Unknown'}*")
        
        return "\n".join(lines)
    
    def get_search_text(self) -> str:
        """Get text optimized for embedding."""
        terms = [
            self.state_name,
            f"{self.state_name} State",
            self.geopolitical_zone,
            f"representatives in {self.state_name}",
            f"politicians from {self.state_name}",
        ]
        if self.governor:
            terms.append(f"governor of {self.state_name}")
        if self.senators:
            terms.append(f"senators from {self.state_name}")
        return " | ".join(terms)


@dataclass
class SenatorialDistrictCard:
    """Card for a senatorial district."""
    district_id: str
    district_name: str  # e.g., "East", "Central", "North"
    state: str
    full_name: str  # e.g., "Lagos East"
    
    # Senator
    senator: Optional[Dict] = None  # {name, party, term}
    
    # Geography
    lgas_covered: List[str] = field(default_factory=list)
    
    # Metadata
    last_updated: str = ""
    
    def to_rag_document(self) -> str:
        """Convert to RAG-optimized document."""
        lines = []
        
        # Header
        lines.append(f"# {self.full_name} Senatorial District")
        lines.append(f"**State:** {self.state}")
        lines.append("")
        
        # Senator
        if self.senator:
            lines.append(f"## Current Senator")
            lines.append(f"**{self.senator['name']}** ({self.senator['party']})")
            if self.senator.get('term'):
                lines.append(f"Term: {self.senator['term']}")
            lines.append("")
        
        # LGAs
        if self.lgas_covered:
            lines.append(f"## Local Government Areas ({len(self.lgas_covered)})")
            for lga in self.lgas_covered:
                lines.append(f"- {lga}")
            lines.append("")
        
        # Helpful text for queries
        lines.append("---")
        lines.append(f"If you live in {self.state} State in any of the above LGAs, this is your senatorial district.")
        lines.append(f"Your senator is **{self.senator['name']}** ({self.senator['party']})." if self.senator else "Senator information not available.")
        lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"*Source: Decide9ja Jurisdiction Database | Updated: {self.last_updated[:10] if self.last_updated else 'Unknown'}*")
        
        return "\n".join(lines)
    
    def get_search_text(self) -> str:
        terms = [
            self.full_name,
            f"{self.full_name} Senatorial District",
            f"{self.state} {self.district_name}",
            f"senator for {self.full_name}",
            f"who represents {self.full_name}",
        ]
        if self.senator:
            terms.append(self.senator['name'])
        if self.lgas_covered:
            terms.extend([f"{lga} senator" for lga in self.lgas_covered[:5]])
        return " | ".join(terms)


@dataclass
class FederalConstituencyCard:
    """Card for a federal constituency."""
    constituency_id: str
    constituency_name: str
    state: str
    
    # House Representative
    house_rep: Optional[Dict] = None  # {name, party, term}
    
    # Geography
    lgas_covered: List[str] = field(default_factory=list)
    
    # Metadata
    last_updated: str = ""
    
    def to_rag_document(self) -> str:
        """Convert to RAG-optimized document."""
        lines = []
        
        # Header
        lines.append(f"# {self.constituency_name} Federal Constituency")
        lines.append(f"**State:** {self.state}")
        lines.append("")
        
        # House Rep
        if self.house_rep:
            lines.append(f"## House of Representatives Member")
            lines.append(f"**{self.house_rep['name']}** ({self.house_rep['party']})")
            if self.house_rep.get('term'):
                lines.append(f"Term: {self.house_rep['term']}")
            lines.append("")
        
        # LGAs
        lgas = self.lgas_covered or self._parse_lgas_from_name()
        if lgas:
            lines.append(f"## Local Government Areas")
            for lga in lgas:
                lines.append(f"- {lga}")
            lines.append("")
        
        # Helpful text
        lines.append("---")
        lines.append(f"If you live in {self.state} State in the above LGAs, this is your federal constituency.")
        if self.house_rep:
            lines.append(f"Your House of Representatives member is **{self.house_rep['name']}** ({self.house_rep['party']}).")
        lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"*Source: Decide9ja Jurisdiction Database | Updated: {self.last_updated[:10] if self.last_updated else 'Unknown'}*")
        
        return "\n".join(lines)
    
    def _parse_lgas_from_name(self) -> List[str]:
        """Parse LGA names from constituency name (often in format LGA1/LGA2/LGA3)."""
        if "/" in self.constituency_name:
            return [lga.strip() for lga in self.constituency_name.split("/")]
        return [self.constituency_name]
    
    def get_search_text(self) -> str:
        terms = [
            self.constituency_name,
            f"{self.constituency_name} Federal Constituency",
            f"{self.state} {self.constituency_name}",
            f"house of representatives {self.constituency_name}",
            f"who represents {self.constituency_name}",
        ]
        if self.house_rep:
            terms.append(self.house_rep['name'])
        # Add LGA search terms
        lgas = self.lgas_covered or self._parse_lgas_from_name()
        terms.extend([f"{lga} representative" for lga in lgas[:5]])
        return " | ".join(terms)


# Geopolitical zones mapping
STATE_ZONES = {
    # South-West
    "Lagos": "South-West", "Ogun": "South-West", "Oyo": "South-West",
    "Osun": "South-West", "Ondo": "South-West", "Ekiti": "South-West",
    # South-East
    "Abia": "South-East", "Anambra": "South-East", "Ebonyi": "South-East",
    "Enugu": "South-East", "Imo": "South-East",
    # South-South
    "Akwa Ibom": "South-South", "Bayelsa": "South-South", "Cross River": "South-South",
    "Delta": "South-South", "Edo": "South-South", "Rivers": "South-South",
    # North-Central
    "Benue": "North-Central", "Kogi": "North-Central", "Kwara": "North-Central",
    "Nasarawa": "North-Central", "Niger": "North-Central", "Plateau": "North-Central",
    "FCT": "North-Central",
    # North-East
    "Adamawa": "North-East", "Bauchi": "North-East", "Borno": "North-East",
    "Gombe": "North-East", "Taraba": "North-East", "Yobe": "North-East",
    # North-West
    "Jigawa": "North-West", "Kaduna": "North-West", "Kano": "North-West",
    "Katsina": "North-West", "Kebbi": "North-West", "Sokoto": "North-West",
    "Zamfara": "North-West",
}


def generate_jurisdiction_cards(db_session=None):
    """Generate all jurisdiction cards from politician database."""
    if db_session is None:
        db_session = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        politicians = db_session.query(Politician).all()
        
        # Organize by state
        states_data = defaultdict(lambda: {
            "governor": None,
            "senators": [],
            "house_reps": [],
            "senatorial_districts": set(),
            "federal_constituencies": set(),
        })
        
        for p in politicians:
            state = p.state
            if not state:
                continue
            
            # Parse data_json
            data = {}
            if p.data_json:
                try:
                    data = json.loads(p.data_json)
                except:
                    pass
            
            # Get party
            party = p.party or "Unknown"
            if party == "Unknown":
                pc = data.get("political_career", {})
                ph = pc.get("party_history", [])
                if ph:
                    for h in ph:
                        if h.get("left") is None:
                            party = h.get("party", "Unknown")
                            break
            
            # Get term
            positions = data.get("political_career", {}).get("positions_held", [])
            term = positions[0].get("period", "") if positions else ""
            
            if p.position == "Governor":
                states_data[state]["governor"] = {"name": p.name, "party": party, "term": term}
            
            elif p.position == "Senator":
                district = data.get("senatorial_district", p.constituency or "")
                states_data[state]["senators"].append({
                    "name": p.name, "party": party, "district": district, "term": term
                })
                if district:
                    states_data[state]["senatorial_districts"].add(district)
            
            elif p.position == "House of Representatives":
                constituency = data.get("federal_constituency", p.constituency or "")
                states_data[state]["house_reps"].append({
                    "name": p.name, "party": party, "constituency": constituency, "term": term
                })
                if constituency:
                    states_data[state]["federal_constituencies"].add(constituency)
        
        # Generate cards
        state_cards = []
        senatorial_cards = []
        constituency_cards = []
        
        now = datetime.now().isoformat()
        
        for state, data in states_data.items():
            # State card
            state_card = StateCard(
                state_id=state.lower().replace(" ", "_"),
                state_name=state,
                geopolitical_zone=STATE_ZONES.get(state, "Unknown"),
                governor=data["governor"],
                senators=data["senators"],
                house_reps_count=len(data["house_reps"]),
                senatorial_districts=sorted(list(data["senatorial_districts"])),
                federal_constituencies=sorted(list(data["federal_constituencies"])),
                last_updated=now,
            )
            state_cards.append(state_card)
            
            # Senatorial district cards
            for senator in data["senators"]:
                district = senator["district"]
                if district:
                    sd_card = SenatorialDistrictCard(
                        district_id=f"{state}_{district}".lower().replace(" ", "_"),
                        district_name=district,
                        state=state,
                        full_name=f"{state} {district}",
                        senator={"name": senator["name"], "party": senator["party"], "term": senator["term"]},
                        lgas_covered=[],  # Would need additional data
                        last_updated=now,
                    )
                    senatorial_cards.append(sd_card)
            
            # Federal constituency cards
            for rep in data["house_reps"]:
                constituency = rep["constituency"]
                if constituency:
                    fc_card = FederalConstituencyCard(
                        constituency_id=f"{state}_{constituency}".lower().replace(" ", "_").replace("/", "_"),
                        constituency_name=constituency,
                        state=state,
                        house_rep={"name": rep["name"], "party": rep["party"], "term": rep["term"]},
                        lgas_covered=[],  # Parsed from name
                        last_updated=now,
                    )
                    constituency_cards.append(fc_card)
        
        logger.info(f"Generated {len(state_cards)} state cards, {len(senatorial_cards)} senatorial cards, {len(constituency_cards)} constituency cards")
        
        return state_cards, senatorial_cards, constituency_cards
        
    finally:
        if should_close:
            db_session.close()


def save_jurisdiction_cards_to_rag(state_cards, senatorial_cards, constituency_cards, db_session=None):
    """Save jurisdiction cards to RAG."""
    if db_session is None:
        db_session = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        count = 0
        
        # Save state cards
        for card in state_cards:
            doc_id = f"state_card_{card.state_id}"
            content = card.to_rag_document()
            search_text = card.get_search_text()
            
            embedding = get_embedding(f"{search_text}\n\n{content}")
            embedding_json = embedding_to_json(embedding)
            
            metadata = {
                "source_type": "jurisdiction_card",
                "jurisdiction_type": "state",
                "state": card.state_name,
                "zone": card.geopolitical_zone,
            }
            
            existing = db_session.query(Document).filter(Document.doc_id == doc_id).first()
            if existing:
                existing.title = f"State: {card.state_name}"
                existing.content = content
                existing.doc_type = "jurisdiction_card"
                existing.embedding_json = embedding_json
                existing.metadata_json = json.dumps(metadata)
                existing.state = card.state_name
            else:
                doc = Document(
                    doc_id=doc_id,
                    title=f"State: {card.state_name}",
                    content=content,
                    doc_type="jurisdiction_card",
                    embedding_json=embedding_json,
                    metadata_json=json.dumps(metadata),
                    state=card.state_name,
                )
                db_session.add(doc)
            count += 1
        
        # Save senatorial district cards
        for card in senatorial_cards:
            doc_id = f"senatorial_card_{card.district_id}"
            content = card.to_rag_document()
            search_text = card.get_search_text()
            
            embedding = get_embedding(f"{search_text}\n\n{content}")
            embedding_json = embedding_to_json(embedding)
            
            metadata = {
                "source_type": "jurisdiction_card",
                "jurisdiction_type": "senatorial_district",
                "state": card.state,
                "district": card.district_name,
            }
            
            existing = db_session.query(Document).filter(Document.doc_id == doc_id).first()
            if existing:
                existing.title = f"Senatorial District: {card.full_name}"
                existing.content = content
                existing.doc_type = "jurisdiction_card"
                existing.embedding_json = embedding_json
                existing.metadata_json = json.dumps(metadata)
                existing.state = card.state
            else:
                doc = Document(
                    doc_id=doc_id,
                    title=f"Senatorial District: {card.full_name}",
                    content=content,
                    doc_type="jurisdiction_card",
                    embedding_json=embedding_json,
                    metadata_json=json.dumps(metadata),
                    state=card.state,
                )
                db_session.add(doc)
            count += 1
        
        # Save federal constituency cards
        for card in constituency_cards:
            doc_id = f"constituency_card_{card.constituency_id}"
            content = card.to_rag_document()
            search_text = card.get_search_text()
            
            embedding = get_embedding(f"{search_text}\n\n{content}")
            embedding_json = embedding_to_json(embedding)
            
            metadata = {
                "source_type": "jurisdiction_card",
                "jurisdiction_type": "federal_constituency",
                "state": card.state,
                "constituency": card.constituency_name,
            }
            
            existing = db_session.query(Document).filter(Document.doc_id == doc_id).first()
            if existing:
                existing.title = f"Federal Constituency: {card.constituency_name}"
                existing.content = content
                existing.doc_type = "jurisdiction_card"
                existing.embedding_json = embedding_json
                existing.metadata_json = json.dumps(metadata)
                existing.state = card.state
            else:
                doc = Document(
                    doc_id=doc_id,
                    title=f"Federal Constituency: {card.constituency_name}",
                    content=content,
                    doc_type="jurisdiction_card",
                    embedding_json=embedding_json,
                    metadata_json=json.dumps(metadata),
                    state=card.state,
                )
                db_session.add(doc)
            count += 1
        
        db_session.commit()
        logger.info(f"Saved {count} jurisdiction cards to RAG")
        return count
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to save jurisdiction cards: {e}")
        raise
        
    finally:
        if should_close:
            db_session.close()


def run_jurisdiction_generation():
    """Run the full jurisdiction card generation pipeline."""
    print("=== JURISDICTION CARD GENERATION ===")
    print()
    
    # Generate cards
    print("Step 1: Generating jurisdiction cards from database...")
    state_cards, senatorial_cards, constituency_cards = generate_jurisdiction_cards()
    print(f"  State cards: {len(state_cards)}")
    print(f"  Senatorial district cards: {len(senatorial_cards)}")
    print(f"  Federal constituency cards: {len(constituency_cards)}")
    print(f"  Total: {len(state_cards) + len(senatorial_cards) + len(constituency_cards)}")
    
    # Show sample
    print()
    print("Step 2: Sample cards:")
    if state_cards:
        print("-" * 50)
        print("STATE CARD:")
        print(state_cards[0].to_rag_document()[:500])
        print("...")
        print("-" * 50)
    
    if senatorial_cards:
        print("SENATORIAL DISTRICT CARD:")
        print(senatorial_cards[0].to_rag_document()[:400])
        print("...")
        print("-" * 50)
    
    # Save to RAG
    print()
    print("Step 3: Saving to RAG document store...")
    count = save_jurisdiction_cards_to_rag(state_cards, senatorial_cards, constituency_cards)
    print(f"  Saved {count} cards")
    
    print()
    print("=== COMPLETE ===")
    return count


if __name__ == "__main__":
    run_jurisdiction_generation()
