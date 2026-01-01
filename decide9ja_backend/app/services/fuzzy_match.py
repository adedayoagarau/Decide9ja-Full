"""
Fuzzy Matching Service for Politician Names

Handles typos and misspellings like "Gbenga Dienel" → "Gbenga Daniel"
Uses rapidfuzz for efficient fuzzy string matching.

Enhanced with Nigerian-specific normalization from the Nigerian Fuzzy Matching Handbook.
"""
import logging
from typing import Optional, List, Dict, Tuple
from rapidfuzz import fuzz, process

# Import Nigerian-specific normalization
from app.utils.nigerian_matcher import (
    normalize_name, 
    strip_honorifics,
    match_state,
    match_party,
    NigerianMatcher
)

logger = logging.getLogger(__name__)

# Minimum similarity threshold (0-100)
SIMILARITY_THRESHOLD = 75  # 75% match required


def fuzzy_find_politician(
    query: str,
    candidates: List[Dict],
    name_key: str = "name",
    threshold: int = SIMILARITY_THRESHOLD
) -> Optional[Tuple[Dict, int, str]]:
    """
    Find best matching politician using fuzzy matching.
    
    Enhanced with Nigerian-specific normalization:
    - Strips honorifics (Dr., Sen., Alhaji, Chief, etc.)
    - Handles multi-word honorifics ("His Excellency")
    - Normalizes text (lowercase, remove punctuation)
    
    Args:
        query: User's search query (potentially misspelled)
        candidates: List of politician dicts with 'name' key
        name_key: Key to use for name field
        threshold: Minimum match percentage (0-100)
    
    Returns:
        Tuple of (matched_politician, similarity_score, suggestion_text) or None
        
    Examples:
        "Gbenga Dienel" → "Gbenga Daniel" (93% match)
        "President Tinubu" → "Bola Ahmed Tinubu" (85% match)
        "Sen. Orji Kalu" → "Orji Uzor Kalu" (90% match)
    """
    if not candidates or not query:
        return None
    
    # Apply Nigerian normalization (strips honorifics)
    query_normalized = normalize_name(query)
    
    # Create name mapping with normalization
    name_to_politician = {}
    normalized_names = []
    
    for p in candidates:
        if p.get(name_key):
            original_name = p[name_key]
            normalized = normalize_name(original_name)
            name_to_politician[normalized] = p
            normalized_names.append(normalized)
    
    if not normalized_names:
        return None
    
    # Find best match using token_set_ratio (handles word order)
    result = process.extractOne(
        query_normalized,
        normalized_names,
        scorer=fuzz.token_set_ratio
    )
    
    if result and result[1] >= threshold:
        matched_normalized = result[0]
        similarity = result[1]
        politician = name_to_politician[matched_normalized]
        
        # Generate suggestion text if not exact match
        if similarity < 100:
            suggestion = f"Did you mean {politician[name_key]}?"
        else:
            suggestion = None
            
        logger.info(f"Fuzzy match: '{query}' → '{politician[name_key]}' ({similarity}%)")
        return (politician, similarity, suggestion)
    
    return None


def fuzzy_find_among_representatives(
    query: str,
    user_state: str,
    user_lga: str = None,
    db = None
) -> Optional[Tuple[Dict, str]]:
    """
    Find a politician among user's representatives with fuzzy matching.
    Prioritizes user's own reps when there's ambiguity.
    
    Args:
        query: User's search query
        user_state: User's Nigerian state
        user_lga: User's LGA (optional)
        db: Database session
    
    Returns:
        Tuple of (politician_dict, context_note) or None
    """
    if not db or not user_state:
        return None
        
    try:
        from app.database import Politician
        
        # Get user's state representatives
        reps = db.query(Politician).filter(
            Politician.state.ilike(f"%{user_state}%")
        ).all()
        
        if not reps:
            return None
        
        # Convert to dicts for fuzzy matching
        rep_dicts = [
            {
                "id": r.id,
                "name": r.name,
                "party": r.party,
                "position": r.position,
                "state": r.state,
                "constituency": r.constituency,
                "bio": r.bio
            }
            for r in reps
        ]
        
        result = fuzzy_find_politician(query, rep_dicts)
        
        if result:
            politician, similarity, suggestion = result
            position = politician.get("position", "representative")
            context = f"They're your {position} for {user_state}."
            return (politician, context if suggestion else None)
            
    except Exception as e:
        logger.error(f"Error in fuzzy rep search: {e}")
    
    return None


def extract_politician_name_from_text(text: str) -> str:
    """
    Extract likely politician name from user query.
    
    Enhanced with Nigerian honorific stripping for queries like:
        "Who is Sen. Orji Kalu?" → "Orji Kalu"
        "Tell me about President Tinubu" → "Tinubu"
        "Alhaji Chief Bola Tinubu" → "Bola Tinubu"
    
    Examples:
        "Who is Gbenga Daniel?" → "Gbenga Daniel"
        "Tell me about Tinubu" → "Tinubu"
        "I want to know about the governor" → ""
    """
    import re
    
    # Pattern: "Who is X?" or "Tell me about X"
    patterns = [
        r"(?:who is|about|know about|info on|information about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"(?:who is|about|know about|info on|information about)\s+(.+?)(?:\?|$)",
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)$",  # Just a capitalized name
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Filter out non-name words
            stop_words = {"the", "senator", "governor", "representative", "president", "minister"}
            if name.lower() not in stop_words:
                # Strip Nigerian honorifics (Dr., Sen., Alhaji, etc.)
                return strip_honorifics(name)
    
    # Fallback: strip honorifics from full text
    return strip_honorifics(text.strip())


def find_closest_match(
    query: str,
    options: List[str],
    threshold: int = 70
) -> Optional[str]:
    """
    Simple fuzzy match for any list of strings.
    
    Args:
        query: Search string
        options: List of options to match against
        threshold: Minimum match percentage
    
    Returns:
        Best matching string or None
    """
    if not options:
        return None
    
    result = process.extractOne(
        query.lower(),
        [o.lower() for o in options],
        scorer=fuzz.ratio
    )
    
    if result and result[1] >= threshold:
        # Return original case version
        index = [o.lower() for o in options].index(result[0])
        return options[index]
    
    return None


def fuzzy_match_nigerian_state(query: str) -> Optional[Tuple[str, float]]:
    """
    Match input to a Nigerian state using the Nigerian matcher.
    
    Handles variations like:
        "Lagos state" → "Lagos"
        "FCT" → "FCT" 
        "Akwa-Ibom" → "Akwa Ibom"
        "crossriver" → "Cross River"
    
    Returns:
        (state_name, confidence) or None
    """
    return match_state(query)


def fuzzy_match_party(query: str) -> Optional[Tuple[str, str, float]]:
    """
    Match input to a Nigerian political party.
    
    Handles variations like:
        "APC" → ("APC", "All Progressives Congress", 1.0)
        "P.D.P." → ("PDP", "Peoples Democratic Party", 0.95)
        "Labour Party" → ("LP", "Labour Party", 1.0)
    
    Returns:
        (acronym, full_name, confidence) or None
    """
    return match_party(query)


# Export the Nigerian matcher for advanced use cases
nigerian_matcher = NigerianMatcher()
