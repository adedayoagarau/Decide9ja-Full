"""
Politician Lookup Service with Fuzzy Matching and Location Awareness.

Multi-layer matching strategy:
1. Exact match → return immediately
2. Fuzzy match (>=80%) → return with confidence
3. Location match → suggest user's representatives  
4. Partial match → return candidates
5. Web search → fallback for unknown politicians

Dependencies:
    pip install rapidfuzz
"""
import re
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


@dataclass
class PoliticianMatch:
    """Result of politician lookup."""
    politician: Optional[Dict] = None
    confidence: float = 0.0
    match_type: str = "none"  # exact, fuzzy, location, partial, web
    suggestion: Optional[str] = None
    candidates: List[Dict] = field(default_factory=list)


# Similarity thresholds
EXACT_THRESHOLD = 100
FUZZY_THRESHOLD = 75
PARTIAL_THRESHOLD = 65
LOCATION_THRESHOLD = 70


def clean_query(query: str) -> str:
    """Clean and normalize query string."""
    prefixes = [
        "who is", "tell me about", "what about", "info on",
        "information on", "about", "the", "senator", "governor",
        "representative", "hon", "hon.", "honorable", "dr", "dr.",
        "chief", "alhaji", "prince", "princess", "engr", "engr.",
        "barrister", "barr", "barr.", "prof", "prof."
    ]
    
    query_lower = query.lower().strip()
    
    for prefix in prefixes:
        if query_lower.startswith(prefix + " "):
            query_lower = query_lower[len(prefix):].strip()
    
    # Remove punctuation
    query_lower = re.sub(r'[^\w\s]', '', query_lower)
    
    return query_lower.strip()


async def find_politician(
    query: str, 
    user_state = None,
    db = None
) -> PoliticianMatch:
    """
    Find a politician using multi-layer matching.
    
    Args:
        query: User's search query (name, position, etc.)
        user_state: Current user state for location context
        db: Database session (optional, will create if not provided)
    
    Returns:
        PoliticianMatch with politician data and match metadata
    """
    query_clean = clean_query(query)
    
    if not query_clean:
        return PoliticianMatch(match_type="none")
    
    # Get database session
    try:
        from app.database import get_db, Politician
        if db is None:
            db = next(get_db())
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return PoliticianMatch(match_type="none")
    
    # Layer 1: Exact match
    exact_result = db.query(Politician).filter(
        Politician.name.ilike(f"%{query_clean}%")
    ).first()
    
    if exact_result:
        return PoliticianMatch(
            politician=_politician_to_dict(exact_result),
            confidence=1.0,
            match_type="exact"
        )
    
    # Layer 2: Fuzzy match against all politicians
    all_politicians = db.query(Politician).limit(500).all()
    
    if all_politicians:
        names = [p.name for p in all_politicians]
        result = process.extractOne(
            query_clean,
            names,
            scorer=fuzz.token_set_ratio
        )
        
        if result and result[1] >= FUZZY_THRESHOLD:
            matched_name = result[0]
            confidence = result[1] / 100
            politician = next(p for p in all_politicians if p.name == matched_name)
            
            suggestion = None
            if result[1] < EXACT_THRESHOLD:
                suggestion = f"Did you mean {matched_name}?"
            
            return PoliticianMatch(
                politician=_politician_to_dict(politician),
                confidence=confidence,
                match_type="fuzzy",
                suggestion=suggestion
            )
    
    # Layer 3: Location-aware matching
    if user_state and user_state.state:
        state_reps = db.query(Politician).filter(
            Politician.state.ilike(f"%{user_state.state}%")
        ).all()
        
        if state_reps:
            query_parts = query_clean.lower().split()
            
            for rep in state_reps:
                rep_name_parts = rep.name.lower().split()
                
                for qp in query_parts:
                    for np in rep_name_parts:
                        similarity = fuzz.ratio(qp, np)
                        if similarity >= LOCATION_THRESHOLD:
                            return PoliticianMatch(
                                politician=_politician_to_dict(rep),
                                confidence=similarity / 100,
                                match_type="location",
                                suggestion=f"Did you mean {rep.name}? They're your {rep.position or 'representative'} for {user_state.state}."
                            )
    
    # Layer 4: Partial match - return multiple candidates
    if all_politicians:
        partial_matches = process.extract(
            query_clean,
            [p.name for p in all_politicians],
            scorer=fuzz.partial_ratio,
            limit=5
        )
        
        candidates = []
        for match_name, score, _ in partial_matches:
            if score >= PARTIAL_THRESHOLD:
                politician = next(p for p in all_politicians if p.name == match_name)
                candidates.append(_politician_to_dict(politician))
        
        if len(candidates) == 1:
            return PoliticianMatch(
                politician=candidates[0],
                confidence=0.7,
                match_type="partial",
                suggestion=f"Did you mean {candidates[0]['name']}?"
            )
        elif len(candidates) > 1:
            return PoliticianMatch(
                match_type="partial",
                candidates=candidates,
                suggestion="I found several possible matches:"
            )
    
    # Layer 5: Web search fallback
    try:
        from app.services.realtime import fetch_web_search
        web_results = fetch_web_search(f"{query} Nigeria politician", limit=3)
        
        if web_results:
            return PoliticianMatch(
                match_type="web",
                politician={
                    "name": query.title(),
                    "source": "web_search",
                    "search_results": web_results
                },
                confidence=0.5
            )
    except Exception as e:
        logger.warning(f"Web search fallback failed: {e}")
    
    return PoliticianMatch(match_type="none")


def _politician_to_dict(politician) -> Dict:
    """Convert Politician ORM object to dictionary."""
    return {
        "id": politician.id,
        "name": politician.name,
        "party": politician.party,
        "position": politician.position,
        "state": politician.state,
        "constituency": getattr(politician, 'constituency', None),
        "bio": getattr(politician, 'bio', None),
        "email": getattr(politician, 'email', None),
        "phone": getattr(politician, 'phone_number', None),
    }


async def get_representatives(state: str, lga: str = None, db = None) -> List[Dict]:
    """Get all representatives for a location."""
    try:
        from app.database import get_db, Politician
        if db is None:
            db = next(get_db())
        
        query = db.query(Politician).filter(
            Politician.state.ilike(f"%{state}%")
        )
        
        reps = query.limit(20).all()
        
        # Sort by position importance
        position_order = {"governor": 1, "senator": 2, "representative": 3, "house": 4}
        
        rep_list = [_politician_to_dict(r) for r in reps]
        rep_list.sort(
            key=lambda x: position_order.get(
                (x.get("position") or "").lower().split()[0] if x.get("position") else "zzz", 
                99
            )
        )
        
        return rep_list
        
    except Exception as e:
        logger.error(f"Error getting representatives: {e}")
        return []


async def search_politicians(query: str, limit: int = 10, db = None) -> List[Dict]:
    """Search politicians by any field with fuzzy matching."""
    try:
        from app.database import get_db, Politician
        if db is None:
            db = next(get_db())
        
        # Try multiple search strategies
        results = []
        
        # Exact field matches
        for field in ['name', 'state', 'party', 'position']:
            matches = db.query(Politician).filter(
                getattr(Politician, field).ilike(f"%{query}%")
            ).limit(limit).all()
            results.extend(matches)
        
        # Deduplicate by ID
        seen_ids = set()
        unique_results = []
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                unique_results.append(_politician_to_dict(r))
        
        return unique_results[:limit]
        
    except Exception as e:
        logger.error(f"Error searching politicians: {e}")
        return []
