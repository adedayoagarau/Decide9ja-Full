"""
Onboarding flow handler.
Collects: first_name → last_name → state → LGA (minimum required)
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
        0: Initial greeting, ask for first name
        1: Got first name, ask for last name
        2: Got last name, ask for state
        3: Got state, ask for LGA
        4: Got LGA, complete onboarding
    """
    text = text.strip()

    # STEP 0: Initial greeting, ask for first name
    if state.flow_step == 0:
        # Check if this is just a greeting (not a name or question)
        text_lower = text.lower().strip()
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yo", "sup", "start"}
        is_greeting = text_lower in greetings or text_lower.startswith(("hi ", "hello ", "hey "))

        if is_greeting:
            # User is greeting, show welcome and ask for name
            state.greeted = True
            return TEMPLATES["welcome_new"]

        # Try to extract first name (in case they gave their name directly)
        first_name = extract_first_name(text)

        if first_name:
            # They gave their name, proceed
            state.first_name = first_name
            state.greeted = True
            state.flow_step = 1
            return get_template("ask_last_name", first_name=first_name)
        else:
            # They said something else (question, statement, etc.)
            # Acknowledge it and ask for their name
            if not state.greeted:
                state.greeted = True
                # Store their original message so we can reference it later
                state.pending_query = text
                return TEMPLATES["welcome_with_acknowledgment"]
            else:
                return TEMPLATES["didnt_catch_first_name"]

    # STEP 1: Waiting for last name (first name captured)
    if state.flow_step == 1 and state.first_name and not state.last_name:
        last_name = extract_last_name(text)

        if last_name:
            state.last_name = last_name
            state.name = f"{state.first_name} {state.last_name}"  # Set full name
            state.flow_step = 2
            return get_template("ask_state", first_name=state.first_name)
        else:
            return TEMPLATES["didnt_catch_last_name"]

    # Edge case: Step 1 but no first name yet
    if state.flow_step == 1 and not state.first_name:
        first_name = extract_first_name(text)
        if first_name:
            state.first_name = first_name
            return get_template("ask_last_name", first_name=first_name)
        else:
            return TEMPLATES["didnt_catch_first_name"]

    # STEP 2: Waiting for state (names captured)
    if state.flow_step == 2 and state.first_name and not state.state:
        extracted_state = extract_nigerian_state(text)

        if extracted_state:
            state.state = extracted_state
            state.flow_step = 3
            return get_template("ask_lga", state=extracted_state)
        else:
            return TEMPLATES["didnt_recognize_state"]

    # STEP 3: Waiting for LGA (names and state captured)
    if state.flow_step == 3 and state.state and not state.lga:
        extracted_lga = extract_lga(text, state.state)

        if extracted_lga:
            state.lga = extracted_lga
            state.flow_step = 4
            state.flow = ConversationFlow.IDLE  # Onboarding complete

            return get_template("onboarding_complete",
                first_name=state.first_name,
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


def normalize_apostrophes(text: str) -> str:
    """
    Normalize various apostrophe/quote characters to standard ASCII apostrophe.
    Handles smart quotes, curly quotes, and other Unicode variants.
    """
    # Map of various apostrophe-like characters to standard apostrophe
    apostrophe_variants = [
        '\u2019',  # RIGHT SINGLE QUOTATION MARK (')
        '\u2018',  # LEFT SINGLE QUOTATION MARK (')
        '\u02BC',  # MODIFIER LETTER APOSTROPHE (ʼ)
        '\u02BB',  # MODIFIER LETTER TURNED COMMA (ʻ)
        '\u0060',  # GRAVE ACCENT (`)
        '\u00B4',  # ACUTE ACCENT (´)
        '\u2032',  # PRIME (′)
    ]

    for char in apostrophe_variants:
        text = text.replace(char, "'")

    return text


def extract_first_name(text: str) -> Optional[str]:
    """
    Extract first name from user input.
    Handles: "John", "My name is John", "I'm John", "Call me John", etc.
    Only extracts the FIRST word as the first name.
    """
    text = text.strip()

    # Normalize apostrophes FIRST (handles smart quotes from WhatsApp, etc.)
    text = normalize_apostrophes(text)

    # Skip if it's just a greeting
    greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yo", "sup"}
    if text.lower() in greetings:
        return None

    # Remove common prefixes (case-insensitive matching)
    prefixes = [
        "my name is ", "my first name is ", "i'm ", "i am ", "call me ", "it's ", "its ",
        "this is ", "the name is ", "name is ", "i go by ", "they call me ", "first name is "
    ]

    text_lower = text.lower()
    for prefix in prefixes:
        if text_lower.startswith(prefix):
            text = text[len(prefix):]
            break

    # Remove trailing pleasantries
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

    # If they gave full name, take only first word
    words = text.split()
    if words:
        first_name = words[0]
    else:
        return None

    # Validate: first name should be 2-30 chars, mostly letters
    if len(first_name) < 2 or len(first_name) > 30:
        return None

    if not any(c.isalpha() for c in first_name):
        return None

    # Capitalize properly
    return first_name.title()


def extract_last_name(text: str) -> Optional[str]:
    """
    Extract last name/surname from user input.
    Handles: "Agarau", "My surname is Agarau", "Last name is Agarau", etc.
    """
    text = text.strip()

    # Normalize apostrophes
    text = normalize_apostrophes(text)

    # Remove common prefixes
    prefixes = [
        "my surname is ", "my last name is ", "surname is ", "last name is ",
        "family name is ", "it's ", "its ", "i am ", "i'm "
    ]

    text_lower = text.lower()
    for prefix in prefixes:
        if text_lower.startswith(prefix):
            text = text[len(prefix):]
            break

    # Clean up
    text = text.strip().strip(".,!?")

    # If they gave multiple words, take only first (the surname)
    words = text.split()
    if words:
        last_name = words[0]
    else:
        return None

    # Validate: last name should be 2-30 chars, mostly letters
    if len(last_name) < 2 or len(last_name) > 30:
        return None

    if not any(c.isalpha() for c in last_name):
        return None

    # Capitalize properly
    return last_name.title()


def extract_name(text: str) -> Optional[str]:
    """
    Extract full name from user input (legacy function).
    Handles: "John", "My name is John", "I'm John", "Call me John", etc.
    """
    text = text.strip()

    # Normalize apostrophes FIRST (handles smart quotes from WhatsApp, etc.)
    text = normalize_apostrophes(text)

    # Skip if it's just a greeting
    greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yo", "sup"}
    if text.lower() in greetings:
        return None

    # Remove common prefixes (case-insensitive matching)
    prefixes = [
        "my name is ", "i'm ", "i am ", "call me ", "it's ", "its ",
        "this is ", "the name is ", "name is ", "i go by ", "they call me "
    ]

    text_lower = text.lower()
    for prefix in prefixes:
        if text_lower.startswith(prefix):
            # Extract just the name part (everything after the prefix)
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

