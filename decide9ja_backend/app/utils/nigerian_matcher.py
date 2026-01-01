"""
Nigerian Fuzzy Matching Module
Based on the Nigerian Fuzzy Matching Handbook

This module provides specialized fuzzy matching for Nigerian entities including:
- Person names (with honorifics, compound surnames)
- Place names (states, LGAs, cities)
- Political parties
- Organizations (MDAs, banks, telcos)
- Politicians

Key principles:
1. Normalize first, then match
2. Use type-specific thresholds
3. Prefer exact matches after normalization
4. Ask disambiguation questions when confidence is low
"""

import re
from typing import Optional, Tuple, List, Dict
from difflib import SequenceMatcher

# ==========================================
# LEXICONS FROM HANDBOOK
# ==========================================

# Honorifics and titles to strip during matching
HONORIFICS = {
    # Political
    "president", "vice president", "vice-president", "vp", "governor", "gov",
    "deputy governor", "senator", "sen", "honourable", "hon", "rt hon",
    "right honourable", "excellency", "his excellency", "her excellency",
    # Professional
    "dr", "doctor", "prof", "professor", "engr", "engineer", "arc", "architect",
    "barr", "barrister", "esq", "esquire", "chief", "alhaji", "alh", "hajia",
    "mallam", "malam", "oba", "obi", "igwe", "emir", "sultan", "otunba",
    "high chief", "pastor", "reverend", "rev", "bishop", "imam", "general",
    "gen", "brigadier", "brig", "colonel", "col", "captain", "capt",
    "commodore", "rear admiral", "air marshal", "air vice marshal",
    # Gender/social
    "mr", "mrs", "ms", "miss", "sir", "dame", "lady", "prince", "princess",
}

# Political parties (from INEC list)
POLITICAL_PARTIES = {
    "APC": {"canonical": "All Progressives Congress", "aliases": ["a.p.c.", "apc", "progressives congress", "all progressives"]},
    "PDP": {"canonical": "Peoples Democratic Party", "aliases": ["p.d.p.", "pdp", "peoples democratic", "people's democratic party"]},
    "LP": {"canonical": "Labour Party", "aliases": ["l.p.", "lp", "labour", "labor party"]},
    "APGA": {"canonical": "All Progressives Grand Alliance", "aliases": ["a.p.g.a.", "apga", "grand alliance"]},
    "NNPP": {"canonical": "New Nigeria Peoples Party", "aliases": ["n.n.p.p.", "nnpp", "new nigeria"]},
    "SDP": {"canonical": "Social Democratic Party", "aliases": ["s.d.p.", "sdp", "social democratic"]},
    "YPP": {"canonical": "Young Progressives Party", "aliases": ["y.p.p.", "ypp", "young progressives"]},
    "ADC": {"canonical": "African Democratic Congress", "aliases": ["a.d.c.", "adc", "african democratic"]},
    "ADP": {"canonical": "Action Democratic Party", "aliases": ["a.d.p.", "adp", "action democratic"]},
    "AA": {"canonical": "Action Alliance", "aliases": ["a.a.", "aa", "action alliance", "aa party"]},
    "AAC": {"canonical": "African Action Congress", "aliases": ["a.a.c.", "aac", "african action"]},
    "ACCORD": {"canonical": "Accord", "aliases": ["accord", "accord party", "accord nigeria"]},
    "ZLP": {"canonical": "Zenith Labour Party", "aliases": ["z.l.p.", "zlp", "zenith labour"]},
    "PRP": {"canonical": "Peoples Redemption Party", "aliases": ["p.r.p.", "prp", "peoples redemption"]},
    "APP": {"canonical": "Allied Peoples Movement", "aliases": ["a.p.p.", "app", "allied peoples"]},
}

# State variations and abbreviations
STATE_VARIATIONS = {
    "Abia": ["AB", "aba state", "abia st"],
    "Adamawa": ["AD", "adamawa st", "adamawa state"],
    "Akwa Ibom": ["AK", "akwa-ibom", "a/ibom", "akwaibom"],
    "Anambra": ["AN", "anambara", "anam bra"],
    "Bauchi": ["BA", "bauchi st"],
    "Bayelsa": ["BY", "bayelsa st", "yenegoa"],
    "Benue": ["BE", "benue st"],
    "Borno": ["BO", "borno st", "maiduguri state"],
    "Cross River": ["CR", "crossriver", "cross river st"],
    "Delta": ["DE", "delta st"],
    "Ebonyi": ["EB", "eboyni", "ebonyi st"],
    "Edo": ["ED", "edo st", "benin"],
    "Ekiti": ["EK", "ekiti st", "ado-ekiti"],
    "Enugu": ["EN", "enugu st"],
    "FCT": ["abuja", "federal capital territory", "fct abuja"],
    "Gombe": ["GO", "gombe st"],
    "Imo": ["IM", "imo st"],
    "Jigawa": ["JI", "jigawa st"],
    "Kaduna": ["KD", "kaduna st"],
    "Kano": ["KN", "kano st"],
    "Katsina": ["KT", "katsina st"],
    "Kebbi": ["KB", "kebbi st"],
    "Kogi": ["KO", "kogi st"],
    "Kwara": ["KW", "kwara st"],
    "Lagos": ["LA", "lagos st", "lagos state"],
    "Nasarawa": ["NA", "nasarawa st"],
    "Niger": ["NI", "niger st"],  # Note: Not Nigeria
    "Ogun": ["OG", "ogun st", "ogun state"],
    "Ondo": ["ON", "ondo st"],
    "Osun": ["OS", "osun st"],
    "Oyo": ["OY", "oyo st"],
    "Plateau": ["PL", "plateau st"],
    "Rivers": ["RI", "rivers st", "port harcourt state"],
    "Sokoto": ["SO", "sokoto st"],
    "Taraba": ["TA", "taraba st"],
    "Yobe": ["YO", "yobe st"],
    "Zamfara": ["ZA", "zamfara st"],
}

# MDA aliases
MDA_ALIASES = {
    "CBN": ["central bank of nigeria", "c.b.n.", "nigeria central bank"],
    "FIRS": ["federal inland revenue service", "f.i.r.s.", "inland revenue", "tax office"],
    "NIS": ["nigeria immigration service", "immigration", "n.i.s."],
    "EFCC": ["economic and financial crimes commission", "e.f.c.c.", "anti graft"],
    "ICPC": ["independent corrupt practices commission", "i.c.p.c."],
    "NAFDAC": ["national agency for food and drug", "n.a.f.d.a.c.", "food and drug"],
    "NCDC": ["nigeria centre for disease control", "n.c.d.c.", "disease control"],
    "NIMC": ["national identity management commission", "n.i.m.c.", "national id"],
    "JAMB": ["joint admissions and matriculation board", "j.a.m.b.", "admissions board"],
    "NYSC": ["national youth service corps", "n.y.s.c.", "youth service"],
    "NNPC": ["nigerian national petroleum company", "n.n.p.c."],
    "NCC": ["nigerian communications commission", "n.c.c.", "telecom regulator"],
    "CAC": ["corporate affairs commission", "c.a.c.", "company registry"],
    "INEC": ["independent national electoral commission", "i.n.e.c.", "electoral commission"],
}

# ==========================================
# NORMALIZATION FUNCTIONS
# ==========================================

def normalize_text(text: str) -> str:
    """
    Apply Nigerian text normalization rules.
    
    1. Lowercase
    2. Remove punctuation except hyphens in compound names
    3. Collapse multiple spaces
    4. Strip leading/trailing whitespace
    """
    if not text:
        return ""
    
    text = text.lower().strip()
    
    # Replace common separators with space
    text = re.sub(r'[,;:\'\"()]', ' ', text)
    
    # Keep hyphens between words (compound names)
    text = re.sub(r'(?<=[a-z])-(?=[a-z])', '-', text)
    
    # Remove remaining punctuation
    text = re.sub(r'[^\w\s-]', '', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


# Multi-word honorifics to check first
MULTI_WORD_HONORIFICS = [
    "his excellency", "her excellency", "right honourable", "rt hon",
    "vice president", "deputy governor", "high chief", "air marshal",
    "air vice marshal", "rear admiral"
]

def strip_honorifics(name: str) -> str:
    """Remove honorifics and titles from a name."""
    name = name.lower()
    
    # First remove multi-word honorifics
    for honorific in MULTI_WORD_HONORIFICS:
        name = name.replace(honorific, '')
    
    # Then remove single-word honorifics
    tokens = name.split()
    filtered = []
    
    for token in tokens:
        clean_token = token.strip('.')
        if clean_token not in HONORIFICS:
            filtered.append(token)
    
    return ' '.join(filtered).strip()


def normalize_name(name: str) -> str:
    """Normalize a person name for matching."""
    name = normalize_text(name)
    name = strip_honorifics(name)
    return name


def normalize_place(place: str) -> str:
    """Normalize a place name for matching."""
    place = normalize_text(place)
    
    # Remove common suffixes
    place = re.sub(r'\s+(state|st|lga|local government)$', '', place)
    
    return place


# ==========================================
# MATCHING FUNCTIONS
# ==========================================

def similarity_ratio(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def token_overlap(a: str, b: str) -> float:
    """Calculate token-level overlap between two strings."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    
    if not tokens_a or not tokens_b:
        return 0.0
    
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    
    return len(intersection) / len(union)


def match_state(input_text: str) -> Optional[Tuple[str, float]]:
    """
    Match input to a Nigerian state.
    Returns (state_name, confidence) or None.
    """
    normalized = normalize_place(input_text)
    
    # Try exact match first
    for state in STATE_VARIATIONS:
        if normalized == state.lower():
            return (state, 1.0)
    
    # Try alias match
    for state, aliases in STATE_VARIATIONS.items():
        for alias in aliases:
            if normalized == alias.lower():
                return (state, 0.95)
    
    # Try fuzzy match
    best_match = None
    best_score = 0.0
    
    for state in STATE_VARIATIONS:
        score = similarity_ratio(normalized, state.lower())
        if score > best_score and score > 0.7:
            best_score = score
            best_match = state
    
    if best_match:
        return (best_match, best_score)
    
    return None


def match_party(input_text: str) -> Optional[Tuple[str, str, float]]:
    """
    Match input to a political party.
    Returns (acronym, full_name, confidence) or None.
    """
    normalized = normalize_text(input_text)
    
    # Try exact acronym match
    upper = normalized.upper().replace('.', '')
    if upper in POLITICAL_PARTIES:
        return (upper, POLITICAL_PARTIES[upper]["canonical"], 1.0)
    
    # Try alias match
    for acronym, data in POLITICAL_PARTIES.items():
        for alias in data["aliases"]:
            if normalized == alias.lower().replace('.', ''):
                return (acronym, data["canonical"], 0.95)
    
    # Try fuzzy match on full names
    best_match = None
    best_score = 0.0
    
    for acronym, data in POLITICAL_PARTIES.items():
        score = similarity_ratio(normalized, data["canonical"].lower())
        if score > best_score and score > 0.6:
            best_score = score
            best_match = (acronym, data["canonical"])
    
    if best_match:
        return (best_match[0], best_match[1], best_score)
    
    return None


def match_politician_name(input_name: str, candidates: List[Dict]) -> List[Tuple[Dict, float]]:
    """
    Match input name against a list of politician candidates.
    
    Each candidate should have: {"name": str, "id": any, ...}
    Returns list of (candidate, score) tuples sorted by score descending.
    """
    normalized_input = normalize_name(input_name)
    input_tokens = set(normalized_input.split())
    
    results = []
    
    for candidate in candidates:
        candidate_name = normalize_name(candidate.get("name", ""))
        candidate_tokens = set(candidate_name.split())
        
        # Calculate scores
        char_score = similarity_ratio(normalized_input, candidate_name)
        token_score = token_overlap(normalized_input, candidate_name)
        
        # Bonus for matching surname (usually last token)
        surname_bonus = 0.0
        if input_tokens and candidate_tokens:
            input_surname = normalized_input.split()[-1] if normalized_input.split() else ""
            cand_surname = candidate_name.split()[-1] if candidate_name.split() else ""
            if input_surname == cand_surname and len(input_surname) > 2:
                surname_bonus = 0.15
        
        # Combined score
        combined = (char_score * 0.5) + (token_score * 0.5) + surname_bonus
        combined = min(combined, 1.0)
        
        if combined > 0.4:
            results.append((candidate, combined))
    
    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    
    return results[:5]  # Return top 5


def match_lga(input_text: str, state: str, lga_list: List[str]) -> Optional[Tuple[str, float]]:
    """
    Match input to an LGA within a state.
    Returns (lga_name, confidence) or None.
    """
    normalized = normalize_place(input_text)
    
    # Try exact match first
    for lga in lga_list:
        if normalized == lga.lower():
            return (lga, 1.0)
    
    # Try fuzzy match
    best_match = None
    best_score = 0.0
    
    for lga in lga_list:
        # Try both character and token similarity
        char_score = similarity_ratio(normalized, lga.lower())
        token_score = token_overlap(normalized, lga.lower())
        
        score = max(char_score, token_score)
        
        if score > best_score and score > 0.6:
            best_score = score
            best_match = lga
    
    if best_match:
        return (best_match, best_score)
    
    return None


def needs_disambiguation(score: float, entity_type: str) -> bool:
    """
    Check if a match needs disambiguation based on confidence threshold.
    Different entity types have different thresholds.
    """
    thresholds = {
        "person": 0.85,
        "party": 0.80,
        "state": 0.75,
        "lga": 0.70,
        "organization": 0.80,
    }
    
    threshold = thresholds.get(entity_type, 0.80)
    return score < threshold


# ==========================================
# HIGH-LEVEL MATCHING API
# ==========================================

class NigerianMatcher:
    """
    High-level API for Nigerian entity matching.
    
    Usage:
        matcher = NigerianMatcher()
        result = matcher.match("Tinubu", entity_type="person", candidates=politicians)
    """
    
    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
    
    def match_any(self, input_text: str, entity_type: str, **kwargs) -> dict:
        """
        Match input against entities of a given type.
        
        Returns:
            {
                "matched": bool,
                "result": matched entity or None,
                "confidence": float,
                "needs_disambiguation": bool,
                "alternatives": list of other close matches
            }
        """
        if entity_type == "state":
            result = match_state(input_text)
            if result:
                return {
                    "matched": True,
                    "result": result[0],
                    "confidence": result[1],
                    "needs_disambiguation": needs_disambiguation(result[1], "state"),
                    "alternatives": []
                }
        
        elif entity_type == "party":
            result = match_party(input_text)
            if result:
                return {
                    "matched": True,
                    "result": {"acronym": result[0], "name": result[1]},
                    "confidence": result[2],
                    "needs_disambiguation": needs_disambiguation(result[2], "party"),
                    "alternatives": []
                }
        
        elif entity_type == "person":
            candidates = kwargs.get("candidates", [])
            results = match_politician_name(input_text, candidates)
            if results:
                top = results[0]
                return {
                    "matched": True,
                    "result": top[0],
                    "confidence": top[1],
                    "needs_disambiguation": needs_disambiguation(top[1], "person"),
                    "alternatives": [r[0] for r in results[1:3]]
                }
        
        elif entity_type == "lga":
            state = kwargs.get("state")
            lga_list = kwargs.get("lga_list", [])
            result = match_lga(input_text, state, lga_list)
            if result:
                return {
                    "matched": True,
                    "result": result[0],
                    "confidence": result[1],
                    "needs_disambiguation": needs_disambiguation(result[1], "lga"),
                    "alternatives": []
                }
        
        return {
            "matched": False,
            "result": None,
            "confidence": 0.0,
            "needs_disambiguation": False,
            "alternatives": []
        }
