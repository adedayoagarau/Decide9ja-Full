"""
Onboarding flow handler.
Collects: name → state → LGA (minimum required)
"""
import logging
from typing import Optional

from app.models.state import UserState, ConversationFlow
from app.services.templates import get_template, TEMPLATES

logger = logging.getLogger(__name__)

# Nigerian states for validation
NIGERIAN_STATES = {
    "abia", "adamawa", "akwa ibom", "anambra", "bauchi", "bayelsa",
    "benue", "borno", "cross river", "delta", "ebonyi", "edo",
    "ekiti", "enugu", "gombe", "imo", "jigawa", "kaduna", "kano",
    "katsina", "kebbi", "kogi", "kwara", "lagos", "nasarawa",
    "niger", "ogun", "ondo", "osun", "oyo", "plateau", "rivers",
    "sokoto", "taraba", "yobe", "zamfara", "fct", "abuja"
}


async def handle_onboarding(state: UserState, text: str) -> str:
    """
    Handle onboarding flow steps.
    
    Steps:
        0: Initial greeting, ask for name
        1: Got name, ask for state
        2: Got state, ask for LGA
        3: Got LGA, complete onboarding
    """
    text = text.strip()
    
    # STEP 0: Initial greeting
    if state.flow_step == 0:
        # Check if they already included their name
        name = extract_name(text)
        
        if not state.greeted:
            state.greeted = True
            
            if name:
                state.name = name
                state.flow_step = 1
                return get_template("ask_state", name=name)
            else:
                return TEMPLATES["welcome_new"]
        else:
            # Already greeted, they sent another message
            if name:
                state.name = name
                state.flow_step = 1
                return get_template("ask_state", name=name)
            else:
                return TEMPLATES["didnt_catch_name"]
    
    # STEP 1: Waiting for state (name already captured)
    if state.flow_step == 1 and state.name and not state.state:
        extracted_state = extract_nigerian_state(text)
        
        if extracted_state:
            state.state = extracted_state
            state.flow_step = 2
            return get_template("ask_lga", state=extracted_state)
        else:
            return TEMPLATES["didnt_recognize_state"]
    
    # Edge case: Step 1 but no name yet
    if state.flow_step == 1 and not state.name:
        name = extract_name(text)
        if name:
            state.name = name
            return get_template("ask_state", name=name)
        else:
            return TEMPLATES["didnt_catch_name"]
    
    # STEP 2: Waiting for LGA (name and state captured)
    if state.flow_step == 2 and state.state and not state.lga:
        extracted_lga = extract_lga(text, state.state)
        
        if extracted_lga:
            state.lga = extracted_lga
            state.flow_step = 3
            state.flow = ConversationFlow.IDLE  # Onboarding complete
            
            return get_template("onboarding_complete",
                lga=state.lga,
                state=state.state
            )
        else:
            return get_template("didnt_recognize_lga", state=state.state)
    
    # Onboarding already complete
    if state.is_onboarding_complete():
        state.flow = ConversationFlow.IDLE
        return "You're all set. What can I help you with?"
    
    # Something went wrong, restart
    state.flow_step = 0
    state.greeted = False
    return TEMPLATES["welcome_new"]


def extract_name(text: str) -> Optional[str]:
    """
    Extract name from user input.
    Handles: "John", "My name is John", "I'm John", "Call me John", etc.
    """
    text = text.strip()
    
    # Skip if it's just a greeting
    greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yo", "sup"}
    if text.lower() in greetings:
        return None
    
    # Remove common prefixes
    prefixes = [
        "my name is ", "i'm ", "i am ", "call me ", "it's ", "its ",
        "this is ", "the name is ", "name is ", "i go by ", "they call me "
    ]
    
    text_lower = text.lower()
    for prefix in prefixes:
        if text_lower.startswith(prefix):
            text = text[len(prefix):]
            break
    
    # Remove trailing pleasantries (extended list)
    suffixes = [
        ", nice to meet you", ", how are you", ", hope you are well",
        ", i hope you are well", ". how are you", ". nice to meet you",
        ", thanks", ". thanks", ". thank you", ", thank you",
        ". pleased to meet you", ", pleased to meet you",
        ". cheers", ", cheers", "!", "."
    ]
    
    text_lower = text.lower()
    for suffix in suffixes:
        if text_lower.endswith(suffix):
            text = text[:-len(suffix)]
            break
    
    # Clean up
    text = text.strip().strip(".,!?")
    
    # Validate: name should be 2-50 chars, mostly letters
    if len(text) < 2 or len(text) > 50:
        return None
    
    if not any(c.isalpha() for c in text):
        return None
    
    # Capitalize properly
    return text.title()


def extract_nigerian_state(text: str) -> Optional[str]:
    """Extract Nigerian state name from text."""
    text_lower = text.lower().strip()
    
    # Direct match
    for state in NIGERIAN_STATES:
        if state in text_lower:
            if state == "fct" or state == "abuja":
                return "FCT"
            return state.title()
    
    # Handle "Rivers State" format
    if "rivers" in text_lower:
        return "Rivers"
    if "cross" in text_lower and "river" in text_lower:
        return "Cross River"
    if "akwa" in text_lower and "ibom" in text_lower:
        return "Akwa Ibom"
    
    return None


def extract_lga(text: str, state: str) -> Optional[str]:
    """
    Extract LGA name from text for a given state.
    Uses fuzzy matching against known LGAs in the database.
    """
    import os
    from rapidfuzz import fuzz, process
    
    text_clean = text.strip().lower()
    
    # Remove common prefixes (conversational text)
    prefixes = [
        "i believe i'm from ", "i believe i am from ", "i'm from ",
        "i am from ", "i live in ", "i stay in ", "it's ", "its ",
        "my lga is ", "i'm in ", "from "
    ]
    for prefix in prefixes:
        if text_clean.startswith(prefix):
            text_clean = text_clean[len(prefix):]
            break
    
    # Remove common suffixes
    suffixes = [
        " local government", " lga", " local govt", " lg", 
        " local government area", " area"
    ]
    for suffix in suffixes:
        if text_clean.endswith(suffix):
            text_clean = text_clean[:-len(suffix)]
            break
    
    text_clean = text_clean.strip()
    
    # Get known LGAs for this state from database
    try:
        from sqlalchemy import create_engine, text as sql_text
        engine = create_engine(os.getenv('DATABASE_URL'))
        
        with engine.connect() as conn:
            result = conn.execute(sql_text('''
                SELECT DISTINCT lga FROM lga_representatives 
                WHERE LOWER(state) = :state
            '''), {'state': state.lower()})
            known_lgas = [row[0] for row in result]
        
        if not known_lgas:
            # No LGAs in DB for this state, return cleaned input
            return text_clean.title() if text_clean else None
        
        # Fuzzy match against known LGAs
        match = process.extractOne(
            text_clean, 
            known_lgas, 
            scorer=fuzz.token_set_ratio,
            score_cutoff=60
        )
        
        if match:
            return match[0]  # Return the matched LGA name
        
        # No good match - return cleaned input as fallback
        return text_clean.title() if len(text_clean) >= 2 else None
        
    except Exception as e:
        logger.warning(f"LGA extraction error: {e}")
        # Fallback: return cleaned input
        if len(text_clean) >= 2 and any(c.isalpha() for c in text_clean):
            return text_clean.title()
        return None

