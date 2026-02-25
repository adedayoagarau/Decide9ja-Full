"""
Intent classification and routing.

PRIORITY ORDER (matters!):
1. Commands (reset, help)
2. Greetings
3. Confirmations (yes/no when in confirming state)
4. Voter registration
5. NEWS_QUERY ← BEFORE issue (prevents "issue" keyword confusion)
6. Followup (pronouns, "more", "what about")
7. Politician record
8. Rep lookup
9. Politician info
10. Issue report
11. Fallback
"""
import re
import logging
from enum import Enum
from typing import Tuple, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class Intent(Enum):
    """All possible user intents."""
    COMMAND = "command"
    PRIVACY_DELETE = "privacy_delete"  # User wants to delete their data
    GREETING = "greeting"
    CONFIRMATION = "confirmation"
    VOTER_REGISTRATION = "voter_registration"
    NEWS_QUERY = "news_query"
    FOLLOWUP = "followup"
    POLITICIAN_RECORD = "politician_record"
    REP_LOOKUP = "rep_lookup"
    POLITICIAN_INFO = "politician_info"
    ISSUE_REPORT = "issue_report"
    HELP = "help"
    THANKS = "thanks"
    FALLBACK = "fallback"


# Backward compatibility for message_handler_v2
class DataStrategy(Enum):
    """Data retrieval strategy (backward compat)."""
    RAG_ONLY = "rag_only"
    RAG_PLUS_REALTIME = "rag_plus_realtime"
    REALTIME_ONLY = "realtime_only"
    DATABASE_LOOKUP = "database_lookup"
    NO_DATA = "no_data"


@dataclass
class ClassificationResult:
    """Result of intent classification."""
    intent: Intent
    confidence: float
    entities: Dict


# Pattern definitions with priority (higher = checked first)
PATTERNS = [
    # 1. COMMANDS - highest priority
    {
        "intent": Intent.COMMAND,
        "patterns": [
            r"^(reset|restart|start over|menu|cancel|stop)$",
        ],
        "priority": 100,
    },
    
    # 1.5 PRIVACY COMMANDS - very high priority
    {
        "intent": Intent.PRIVACY_DELETE,
        "patterns": [
            r"\b(delete|remove|erase)\s+(my|all)\s*data\b",
            r"\bforget\s+(me|my\s*data)\b",
            r"\bdelete\s+(my|the)?\s*account\b",
            r"\bprivacy\s+delete\b",
        ],
        "priority": 99,
    },
    
    # 2. HELP
    {
        "intent": Intent.HELP,
        "patterns": [
            r"^(help|options|what can you do|how do you work)(\?)?$",
        ],
        "priority": 98,
    },
    
    # 3. THANKS
    {
        "intent": Intent.THANKS,
        "patterns": [
            r"^(thanks|thank you|thank u|ty|cheers|appreciated)(\s|!|\.)?",
        ],
        "priority": 96,
    },
    
    # 4. GREETINGS
    {
        "intent": Intent.GREETING,
        "patterns": [
            r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|greetings|howdy|yo|sup|what'?s\s*up)(\s|!|\?|$)",
        ],
        "priority": 95,
    },
    
    # 5. CONFIRMATIONS - Must be EXACT single-word responses
    {
        "intent": Intent.CONFIRMATION,
        "patterns": [
            # Exact word only (no additional text)
            r"^(yes|yeah|yep|yup|sure|ok|okay|nope|nah|correct|confirm|wrong)(\s*[!?.]*)$",
            r"^(y|n|1|2)$",  # Single character confirmations
            r"^no\s*[!?.]*$",  # "no" alone (not "no electricity...")
        ],
        "priority": 90,
    },
    
    # 6. VOTER REGISTRATION
    {
        "intent": Intent.VOTER_REGISTRATION,
        "patterns": [
            r"\b(register|registration|vote|voter|pvc|inec|polling)\b.*\b(vote|how|where|get)\b",
            r"\b(how|where|can)\b.*(register|vote|pvc|polling)",
            r"\b(pvc|voter'?s?\s*card)\b",
            r"\bget\s+(my\s+)?pvc\b",
        ],
        "priority": 85,
    },
    
    # 7. NEWS QUERY - BEFORE issue report
    {
        "intent": Intent.NEWS_QUERY,
        "patterns": [
            r"\b(news|update|latest|recent|happening|trending|current)\b",
            r"\bwhat'?s\s*(happening|going\s*on|the\s*(latest|news|update))\b",
            r"\b(today|yesterday|this\s*week)\b.*\b(news|happen|said|announce)\b",
            r"\bissue\b.*\b(wike|makinde|tinubu|obi|atiku|sanwo)\b",  # "issue" with politician = news
            r"\b(wike|makinde|tinubu|obi|atiku|sanwo)\b.*\bissue\b",  # politician + "issue" = news
            r"\b(tax|bill|budget|policy|law|naira|dollar|fuel|subsidy)\b",
        ],
        "priority": 80,
    },
    
    # 8. FOLLOWUP
    {
        "intent": Intent.FOLLOWUP,
        "patterns": [
            r"^(what\s*about|how\s*about|and|also)\s",
            r"^(more|continue|go\s*on|tell\s*me\s*more)",
            r"^(his|her|their|the)\s+(bills?|record|projects?|votes?|achievement)",
            r"^(yes|yeah|sure),?\s*(tell\s*me|more|what)",
            r"\bwhat\s+(has|have|did)\s+(he|she|they)\b",
        ],
        "priority": 75,
    },
    
    # 9. POLITICIAN RECORD
    {
        "intent": Intent.POLITICIAN_RECORD,
        "patterns": [
            r"\b(done|achieved|accomplish|record|bills?|projects?|performance)\b",
            r"\b(what|how)\s*(has|have|did)\s+\w+\s+(done|achieved|accomplish)",
            r"\btrack\s*record\b",
            r"\bsponsor(ed)?\s+(bills?|motion)",
        ],
        "priority": 70,
    },
    
    # 10. REP LOOKUP
    {
        "intent": Intent.REP_LOOKUP,
        "patterns": [
            r"\b(my|our)\s+(senator|representative|rep|governor|councillor|chairman)",
            r"\bwho\s+(is|are)\s+(my|our)\b",
            r"\brepresent(s|ing|ative)?\s+(me|us|my)\b",
            r"\bmy\s+(lga|state|constituency)\s+(rep|representative|senator)",
        ],
        "priority": 65,
    },
    
    # 11. POLITICIAN INFO
    {
        "intent": Intent.POLITICIAN_INFO,
        "patterns": [
            r"\bwho\s+is\s+(?!my|our)\w+",  # "who is X" but not "who is my"
            r"\btell\s+me\s+about\s+\w+",
            r"\b(governor|senator|president|minister)\s+of\s+\w+",
            r"\b(tinubu|atiku|obi|makinde|sanwo|wike|fubara|shettima)\b",  # Common politician names
        ],
        "priority": 60,
    },
    
    # 12. ISSUE REPORT - lower priority
    {
        "intent": Intent.ISSUE_REPORT,
        "patterns": [
            r"\breport\s+(a\s+)?(bad\s+road|pothole|issue|problem)",
            r"\b(bad|damaged|broken)\s+(road|bridge|drain|pipe)",
            r"\b(no|lack\s+of)\s+(water|electricity|light|power)",
            r"\bi\s+want\s+to\s+report\b",
            r"\bproblem\s+(with|in)\s+(my|our|the)\s+(area|street|community)",
            r"\bthere'?s?\s+(a\s+)?(pothole|bad\s+road|flooding|blocked\s+drain)",
            r"\bpothole\s+(on|at|in)\b",
            r"\bno\s+(electricity|water|light|power)\s+(for|in)\b",
        ],
        "priority": 50,
    },
]


def classify_intent(text: str, state=None) -> Tuple[Intent, float, Dict]:
    """
    Classify user intent based on message text and conversation state.
    
    Args:
        text: User's message
        state: Optional UserState for context-aware classification
    
    Returns:
        Tuple of (Intent, confidence, extracted_entities)
    """
    text_lower = text.lower().strip()
    entities = {}
    
    # Sort patterns by priority (descending)
    sorted_patterns = sorted(PATTERNS, key=lambda x: x["priority"], reverse=True)
    
    # Check each pattern in priority order
    for pattern_group in sorted_patterns:
        for pattern in pattern_group["patterns"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                intent = pattern_group["intent"]
                
                # Extract entities based on intent
                if intent == Intent.POLITICIAN_INFO:
                    entities["politician_query"] = extract_politician_query(text)
                elif intent == Intent.NEWS_QUERY:
                    entities["news_query"] = text
                elif intent == Intent.ISSUE_REPORT:
                    entities["issue_type"] = extract_issue_type(text)
                
                confidence = min(0.95, pattern_group["priority"] / 100)
                logger.debug(f"Classified '{text[:50]}...' as {intent.value} (conf={confidence})")
                return intent, confidence, entities
    
    # Fallback
    logger.debug(f"No pattern matched for '{text[:50]}...', using FALLBACK")
    return Intent.FALLBACK, 0.3, {}


def extract_politician_query(text: str) -> str:
    """Extract politician name or position from query."""
    # Remove common prefixes
    prefixes = ["who is", "tell me about", "what about", "info on", "information on", "about"]
    text_lower = text.lower()
    
    for prefix in prefixes:
        if text_lower.startswith(prefix):
            return text[len(prefix):].strip()
    
    return text


def extract_issue_type(text: str) -> Optional[str]:
    """Extract issue category from text."""
    issue_keywords = {
        "road": "road_damage",
        "pothole": "road_damage",
        "bridge": "infrastructure",
        "drain": "drainage",
        "drainage": "drainage",
        "flood": "drainage",
        "water": "water_supply",
        "electricity": "electricity",
        "light": "electricity",
        "power": "electricity",
        "nepa": "electricity",
        "waste": "sanitation",
        "garbage": "sanitation",
        "refuse": "sanitation",
        "security": "security",
        "crime": "security",
        "robbery": "security",
    }
    
    text_lower = text.lower()
    for keyword, category in issue_keywords.items():
        if keyword in text_lower:
            return category
    
    return "general"


def is_greeting(text: str) -> bool:
    """Check if text is a greeting."""
    greetings = {
        "hi", "hello", "hey", "good morning", "good afternoon", 
        "good evening", "greetings", "sup", "whatsup", "what's up",
        "howdy", "hiya", "yo", "hola"
    }
    text_lower = text.lower().strip()
    return text_lower in greetings or any(text_lower.startswith(g) for g in greetings)


# ==========================================
# BACKWARD COMPATIBILITY LAYER
# ==========================================

class Router:
    """
    Router class for backward compatibility with message_handler_v2.
    Wraps the functional classify_intent and adds decide_data_strategy.
    """
    
    def classify_intent(self, text: str, context=None) -> Tuple[Intent, float, Dict]:
        """Classify user intent."""
        return classify_intent(text, context)
    
    def decide_data_strategy(self, intent: Intent, text: str = "") -> DataStrategy:
        """Decide which data strategy to use for this intent."""
        strategy_map = {
            Intent.GREETING: DataStrategy.NO_DATA,
            Intent.HELP: DataStrategy.NO_DATA,
            Intent.THANKS: DataStrategy.NO_DATA,
            Intent.COMMAND: DataStrategy.NO_DATA,
            Intent.CONFIRMATION: DataStrategy.NO_DATA,
            Intent.REP_LOOKUP: DataStrategy.DATABASE_LOOKUP,
            Intent.POLITICIAN_INFO: DataStrategy.RAG_ONLY,
            Intent.POLITICIAN_RECORD: DataStrategy.RAG_ONLY,
            Intent.NEWS_QUERY: DataStrategy.RAG_PLUS_REALTIME,
            Intent.VOTER_REGISTRATION: DataStrategy.NO_DATA,
            Intent.ISSUE_REPORT: DataStrategy.NO_DATA,
            Intent.FOLLOWUP: DataStrategy.RAG_ONLY,
            Intent.FALLBACK: DataStrategy.RAG_PLUS_REALTIME,
        }
        return strategy_map.get(intent, DataStrategy.RAG_PLUS_REALTIME)


# Singleton for backward compatibility
router = Router()
