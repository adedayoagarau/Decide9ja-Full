# FIX 3: ONBOARDING PARSER
# File: app/services/onboarding.py
#
# Problem: Bot interprets user messages literally instead of extracting data
# Example: User says "My name is Ade" → Bot stores "My Name Is Ade" as the name
# Solution: Parse user responses to extract actual values

import re
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OnboardingStep(Enum):
    NOT_STARTED = 0
    ASK_NAME = 1
    ASK_STATE = 2
    ASK_LGA = 3
    ASK_VOTED = 4
    ASK_CONCERNS = 5
    COMPLETE = 6


@dataclass
class OnboardingState:
    step: OnboardingStep = OnboardingStep.NOT_STARTED
    name: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    voted_2023: Optional[bool] = None
    concerns: list = None
    
    def __post_init__(self):
        if self.concerns is None:
            self.concerns = []


# Nigerian states for validation
NIGERIAN_STATES = [
    "abia", "adamawa", "akwa ibom", "anambra", "bauchi", "bayelsa", "benue",
    "borno", "cross river", "delta", "ebonyi", "edo", "ekiti", "enugu",
    "fct", "gombe", "imo", "jigawa", "kaduna", "kano", "katsina", "kebbi",
    "kogi", "kwara", "lagos", "nasarawa", "niger", "ogun", "ondo", "osun",
    "oyo", "plateau", "rivers", "sokoto", "taraba", "yobe", "zamfara",
    "federal capital territory", "abuja"
]

# LGAs by state (abbreviated - add full list)
LGAS_BY_STATE = {
    "lagos": [
        "agege", "ajeromi-ifelodun", "alimosho", "amuwo-odofin", "apapa",
        "badagry", "epe", "eti-osa", "ibeju-lekki", "ifako-ijaiye",
        "ikeja", "ikorodu", "kosofe", "lagos island", "lagos mainland",
        "mushin", "ojo", "oshodi-isolo", "shomolu", "surulere"
    ],
    "oyo": [
        "afijio", "akinyele", "atiba", "atisbo", "egbeda", "ibadan north",
        "ibadan north-east", "ibadan north-west", "ibadan south-east",
        "ibadan south-west", "ibarapa central", "ibarapa east", "ibarapa north",
        "ido", "irepo", "iseyin", "itesiwaju", "iwajowa", "kajola", "lagelu",
        "ogbomosho north", "ogbomosho south", "ogo oluwa", "olorunsogo",
        "oluyole", "ona ara", "orelope", "ori ire", "oyo east", "oyo west",
        "saki east", "saki west", "surulere"
    ],
    "ogun": [
        "abeokuta north", "abeokuta south", "ado-odo/ota", "ewekoro",
        "ifo", "ijebu east", "ijebu north", "ijebu north east", "ijebu ode",
        "ikenne", "imeko afon", "ipokia", "obafemi owode", "odeda",
        "odogbolu", "ogun waterside", "remo north", "sagamu", "yewa north", "yewa south"
    ],
    # Add more states...
}


def parse_name(message: str) -> Optional[str]:
    """
    Extract name from user message.
    
    Handles:
    - "My name is Ade"
    - "I'm Ade"
    - "Call me Ade"
    - "Ade"
    - "It's Adedayo"
    """
    message = message.strip()
    
    # Pattern matching for common name introductions
    patterns = [
        r"(?:my name is|i'm|i am|call me|it's|this is)\s+([A-Za-z]+)",
        r"^([A-Za-z]+)$",  # Just the name
        r"^([A-Za-z]+)[,!.]?\s*$",  # Name with punctuation
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Capitalize properly
            return name.capitalize()
    
    # If message is short (1-2 words) and looks like a name
    words = message.split()
    if len(words) <= 2:
        # Filter out common non-name words
        non_names = ["yes", "no", "ok", "okay", "sure", "hi", "hello", "hey"]
        if words[0].lower() not in non_names:
            return " ".join(w.capitalize() for w in words)
    
    return None


def parse_state(message: str) -> Optional[str]:
    """
    Extract Nigerian state from user message.
    
    Handles:
    - "Lagos"
    - "I'm from Lagos state"
    - "I live in Oyo"
    - "Lagos State"
    - "I'm originally from Ogun but live in Oyo" (returns residence)
    """
    message_lower = message.lower().strip()
    
    # Handle "I'm from X but live in Y" pattern - prefer residence
    live_match = re.search(r"(?:live|stay|reside|based|living)\s+(?:in|at)\s+(\w+(?:\s+\w+)?)", message_lower)
    if live_match:
        potential_state = live_match.group(1).replace(" state", "").strip()
        if potential_state in NIGERIAN_STATES:
            return potential_state.title()
    
    # Handle "I'm from X" pattern
    from_match = re.search(r"(?:from|in)\s+(\w+(?:\s+\w+)?)", message_lower)
    if from_match:
        potential_state = from_match.group(1).replace(" state", "").strip()
        if potential_state in NIGERIAN_STATES:
            return potential_state.title()
    
    # Direct state mention
    for state in NIGERIAN_STATES:
        if state in message_lower:
            return state.title()
    
    # Check if message is just the state name
    cleaned = message_lower.replace(" state", "").strip()
    if cleaned in NIGERIAN_STATES:
        return cleaned.title()
    
    return None


def parse_lga(message: str, state: str = None) -> Optional[str]:
    """
    Extract LGA from user message.
    
    Handles:
    - "Alimosho"
    - "Alimosho LGA"
    - "I'm in Ibadan South West"
    - "Ijebu North local government"
    """
    message_lower = message.lower().strip()
    
    # Remove common suffixes
    cleaned = re.sub(r"\s*(lga|local\s*government(\s*area)?|lg)\s*$", "", message_lower, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    
    # Handle "I'm in X" pattern
    location_match = re.search(r"(?:in|at|from)\s+(.+?)(?:\s+(?:lga|local|lg))?$", cleaned)
    if location_match:
        cleaned = location_match.group(1).strip()
    
    # If state is known, validate against that state's LGAs
    if state:
        state_lower = state.lower()
        if state_lower in LGAS_BY_STATE:
            state_lgas = LGAS_BY_STATE[state_lower]
            
            # Exact match
            if cleaned in state_lgas:
                return cleaned.title()
            
            # Partial match (e.g., "ibadan south" matches "ibadan south-west")
            for lga in state_lgas:
                if cleaned in lga or lga in cleaned:
                    return lga.title()
    
    # Return cleaned input as-is if we can't validate
    # (better to store something than nothing)
    if len(cleaned) > 1:
        return cleaned.title()
    
    return None


def parse_voted_response(message: str) -> Optional[bool]:
    """
    Parse yes/no response for voting question.
    
    Handles:
    - "Yes" / "No"
    - "1" / "2" / "3"
    - "I voted" / "I didn't vote"
    - "Yeah" / "Nope"
    """
    message_lower = message.lower().strip()
    
    # Number responses (from menu)
    if message_lower in ["1", "yes", "yeah", "yep", "sure", "i voted", "i did"]:
        return True
    if message_lower in ["2", "no", "nope", "nah", "didn't vote", "i didn't", "did not"]:
        return False
    if message_lower in ["3", "prefer not to say", "skip", "rather not"]:
        return None  # Explicitly skipped
    
    # Check for positive/negative words
    if any(word in message_lower for word in ["yes", "voted", "did"]):
        return True
    if any(word in message_lower for word in ["no", "didn't", "did not", "never"]):
        return False
    
    return None


def parse_concerns(message: str) -> list:
    """
    Extract governance concerns from user message.
    
    Returns list of concern categories.
    """
    message_lower = message.lower()
    
    concern_keywords = {
        "roads": ["road", "pothole", "highway", "expressway", "street"],
        "security": ["security", "insecurity", "crime", "kidnap", "bandit", "terrorism", "safety"],
        "education": ["education", "school", "university", "teacher", "student"],
        "healthcare": ["health", "hospital", "doctor", "medical", "medicine"],
        "economy": ["economy", "price", "inflation", "job", "employment", "naira", "dollar"],
        "electricity": ["electricity", "power", "nepa", "phcn", "light", "generator"],
        "water": ["water", "pipe", "borehole"],
        "corruption": ["corruption", "corrupt", "bribe", "steal"],
        "tax": ["tax", "taxation", "vat"],
    }
    
    found_concerns = []
    for concern, keywords in concern_keywords.items():
        if any(kw in message_lower for kw in keywords):
            found_concerns.append(concern)
    
    # If nothing matched, store the raw input as a custom concern
    if not found_concerns and len(message) > 2:
        found_concerns.append(message.strip().lower())
    
    return found_concerns


class OnboardingManager:
    """
    Manages the onboarding flow for a user.
    """
    
    def __init__(self, state: OnboardingState = None):
        self.state = state or OnboardingState()
    
    def get_current_prompt(self) -> str:
        """Get the prompt for the current onboarding step."""
        prompts = {
            OnboardingStep.NOT_STARTED: "Welcome to Decide9ja! 🇳🇬\n\nI help Nigerians stay informed about their representatives and government.\n\nFirst, what should I call you?",
            OnboardingStep.ASK_NAME: "What should I call you?",
            OnboardingStep.ASK_STATE: "Nice to meet you, {name}! 👋\n\nWhat state are you in?",
            OnboardingStep.ASK_LGA: "Got it, {state}! Which Local Government Area (LGA)?",
            OnboardingStep.ASK_VOTED: "Thanks! Did you vote in the 2023 elections?\n\n1️⃣ Yes\n2️⃣ No\n3️⃣ Prefer not to say",
            OnboardingStep.ASK_CONCERNS: "One last question — what's your biggest concern about governance in Nigeria right now?\n\nFor example: roads, security, education, healthcare, economy...",
            OnboardingStep.COMPLETE: "Thanks for sharing, {name}! I've noted your concerns.\n\nHere's what I can help you with:\n\n📍 *Your Representatives*\nAsk \"Who is my senator?\" or \"Who is my governor?\"\n\n📝 *Report Issues*\nSay \"I want to report an issue\"\n\n🔍 *Political Info*\nAsk about any politician, party, or policy\n\nWhat would you like to know first?"
        }
        
        prompt = prompts.get(self.state.step, "")
        return prompt.format(
            name=self.state.name or "friend",
            state=self.state.state or "your state",
            lga=self.state.lga or "your area"
        )
    
    def process_response(self, message: str) -> Tuple[bool, str]:
        """
        Process user response for current onboarding step.
        
        Returns:
            (should_continue, response_message)
            - should_continue: True if onboarding continues, False if complete
        """
        current_step = self.state.step
        
        if current_step == OnboardingStep.NOT_STARTED:
            # First message - treat as name or start onboarding
            name = parse_name(message)
            if name:
                self.state.name = name
                self.state.step = OnboardingStep.ASK_STATE
                return True, self.get_current_prompt()
            else:
                self.state.step = OnboardingStep.ASK_NAME
                return True, self.get_current_prompt()
        
        elif current_step == OnboardingStep.ASK_NAME:
            name = parse_name(message)
            if name:
                self.state.name = name
                self.state.step = OnboardingStep.ASK_STATE
                return True, self.get_current_prompt()
            else:
                return True, "I didn't catch your name. What should I call you?"
        
        elif current_step == OnboardingStep.ASK_STATE:
            state = parse_state(message)
            if state:
                self.state.state = state
                self.state.step = OnboardingStep.ASK_LGA
                return True, self.get_current_prompt()
            else:
                return True, "I couldn't identify that state. Please enter a Nigerian state (e.g., Lagos, Kano, Rivers):"
        
        elif current_step == OnboardingStep.ASK_LGA:
            lga = parse_lga(message, self.state.state)
            if lga:
                self.state.lga = lga
                self.state.step = OnboardingStep.ASK_VOTED
                return True, self.get_current_prompt()
            else:
                return True, f"Please enter your Local Government Area in {self.state.state}:"
        
        elif current_step == OnboardingStep.ASK_VOTED:
            voted = parse_voted_response(message)
            self.state.voted_2023 = voted  # Can be True, False, or None (skipped)
            self.state.step = OnboardingStep.ASK_CONCERNS
            return True, self.get_current_prompt()
        
        elif current_step == OnboardingStep.ASK_CONCERNS:
            concerns = parse_concerns(message)
            self.state.concerns = concerns
            self.state.step = OnboardingStep.COMPLETE
            
            # Format concerns for response
            concerns_str = ", ".join(concerns) if concerns else "your concerns"
            
            return False, f"Thanks for sharing, {self.state.name}! I've noted that *{concerns_str}* matter to you.\n\nHere's what I can help you with:\n\n📍 *Your Representatives*\nAsk \"Who is my senator?\" or \"Who is my governor?\"\n\n📝 *Report Issues*\nSay \"I want to report an issue\"\n\n🔍 *Political Info*\nAsk about any politician, party, or policy\n\nWhat would you like to know first?"
        
        # If already complete
        return False, ""
    
    def is_complete(self) -> bool:
        """Check if onboarding is complete."""
        return self.state.step == OnboardingStep.COMPLETE
    
    def skip_onboarding(self):
        """Skip remaining onboarding steps."""
        self.state.step = OnboardingStep.COMPLETE
    
    def get_profile_dict(self) -> dict:
        """Get user profile as dictionary."""
        return {
            "name": self.state.name,
            "state": self.state.state,
            "lga": self.state.lga,
            "voted_2023": self.state.voted_2023,
            "concerns": self.state.concerns,
        }


# === TEST ===
if __name__ == "__main__":
    print("=== ONBOARDING PARSER TESTS ===\n")
    
    # Test name parsing
    name_tests = [
        ("My name is Ade", "Ade"),
        ("I'm Chidi", "Chidi"),
        ("Call me Ngozi", "Ngozi"),
        ("Ade", "Ade"),
        ("My name is Ade. Please save that", "Ade"),
        ("Adedayo", "Adedayo"),
    ]
    
    print("NAME PARSING:")
    for input_text, expected in name_tests:
        result = parse_name(input_text)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_text}' → '{result}' (expected: '{expected}')")
    
    # Test state parsing
    print("\nSTATE PARSING:")
    state_tests = [
        ("Lagos", "Lagos"),
        ("I'm from Ogun state", "Ogun"),
        ("I live in Oyo", "Oyo"),
        ("I'm originally from Ogun state but I live in oyo state", "Oyo"),  # Should prefer residence
        ("Rivers State", "Rivers"),
    ]
    
    for input_text, expected in state_tests:
        result = parse_state(input_text)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_text}' → '{result}' (expected: '{expected}')")
    
    # Test LGA parsing
    print("\nLGA PARSING:")
    lga_tests = [
        ("Alimosho", "lagos", "Alimosho"),
        ("Ibadan South West", "oyo", "Ibadan South-West"),
        ("Ijebu North LGA", "ogun", "Ijebu North"),
        ("Oluyole", "oyo", "Oluyole"),
        ("I'm in Oluyole local government", "oyo", "Oluyole"),
    ]
    
    for input_text, state, expected in lga_tests:
        result = parse_lga(input_text, state)
        status = "✅" if result and expected.lower() in result.lower() else "❌"
        print(f"  {status} '{input_text}' ({state}) → '{result}' (expected: '{expected}')")
    
    # Test full onboarding flow
    print("\n=== FULL ONBOARDING FLOW ===\n")
    
    manager = OnboardingManager()
    
    # Simulate conversation
    test_inputs = [
        "Hi",  # First message
        "My name is Ade",  # Name
        "I'm originally from Ogun state but I live in oyo state",  # State
        "Oluyole",  # LGA
        "Yes",  # Voted
        "The tax issue. And insecurity.",  # Concerns
    ]
    
    for user_input in test_inputs:
        print(f"User: {user_input}")
        should_continue, response = manager.process_response(user_input)
        print(f"Bot: {response[:100]}..." if len(response) > 100 else f"Bot: {response}")
        print()
        
        if not should_continue:
            break
    
    print("Final profile:", manager.get_profile_dict())
