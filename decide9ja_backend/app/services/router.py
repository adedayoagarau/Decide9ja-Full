"""
Decide9ja Smart Router
Handles Intent Classification and Data Retrieval Strategy.
"""
import re
from typing import List, Dict, Tuple, Optional
from enum import Enum

class Intent(Enum):
    GREETING = "greeting"
    REP_LOOKUP = "rep_lookup"
    POLITICIAN_INFO = "politician_info"
    POLITICIAN_RECORD = "politician_record"
    NEWS_QUERY = "news_query"
    ISSUE_REPORT = "issue_report"
    VOTER_REG = "voter_reg"
    FOLLOWUP = "followup"
    HELP = "help"
    RESET = "reset"
    CONFIRMATION = "confirmation"
    FALLBACK = "fallback"

class DataStrategy(Enum):
    RAG_ONLY = "rag"
    REALTIME_ONLY = "realtime"
    HYBRID = "hybrid"
    NO_DATA = "none"

# Constants moved from message_handler
NIGERIAN_STATES = {
    "abia", "adamawa", "akwa ibom", "anambra", "bauchi", "bayelsa", "benue",
    "borno", "cross river", "delta", "ebonyi", "edo", "ekiti", "enugu",
    "fct", "gombe", "imo", "jigawa", "kaduna", "kano", "katsina", "kebbi",
    "kogi", "kwara", "lagos", "nasarawa", "niger", "ogun", "ondo", "osun",
    "oyo", "plateau", "rivers", "sokoto", "taraba", "yobe", "zamfara",
    "abuja", "federal capital territory"
}

class Router:
    def __init__(self):
        pass

    def classify_intent(self, text: str, context: object = None) -> Tuple[Intent, float, Dict]:
        """
        Classify user intent. Returns (intent, confidence, entities).
        """
        text_lower = text.lower().strip()
        entities = {}
        
        # === COMMANDS ===
        if text_lower in ["reset", "start over", "/reset"]:
            return Intent.RESET, 1.0, entities
        
        if text_lower in ["help", "menu", "/help", "what can you do"]:
            return Intent.HELP, 1.0, entities
        
        # === GREETINGS ===
        if text_lower in ["hi", "hello", "hey", "hi there", "hello there", "start", "/start"] or \
           text_lower.startswith(("good morning", "good afternoon", "good evening", "hi ", "hello ", "hey ")):
            return Intent.GREETING, 0.95, entities
        
        # === CONFIRMATIONS ===
        if text_lower in ["yes", "yeah", "yep", "no", "nope", "ok", "okay", "sure", "1", "2", "3"]:
            entities["is_yes"] = text_lower in ["yes", "yeah", "yep", "ok", "okay", "sure", "1"]
            return Intent.CONFIRMATION, 0.9, entities
        
        # === VOTER REGISTRATION ===
        if re.search(r"(register|vote|voting|pvc|inec).*(how|where|get)", text_lower) or \
           re.search(r"(how|where).*(register|vote|pvc)", text_lower):
            return Intent.VOTER_REG, 0.9, entities
        
        # === NEWS QUERY ===
        news_patterns = [
            r"update on",
            r"what.*(happening|going on)",
            r"(latest|recent|trending|current).*(news|issue|development)",
            r"news (about|on)",
            r".*\s+vs\s+.*",
            r".*(crisis|conflict)\s+(in|between|with)",
            r"tell me about the .* (issue|situation|crisis)",
            r"most important.*(policy|issue)",
            r"what is happening with",
        ]
        
        political_context = ["wike", "makinde", "tinubu", "obi", "atiku", "pdp", "apc", 
                            "lp", "nnpp", "senate", "house", "governor", "minister", "power", "grid"]
        
        if any(re.search(p, text_lower) for p in news_patterns):
            return Intent.NEWS_QUERY, 0.85, entities
        
        if "issue" in text_lower and any(ctx in text_lower for ctx in political_context):
            return Intent.NEWS_QUERY, 0.8, entities
        
        # === FOLLOWUP ===
        followup_indicators = [
            r"^what (has|have|did|does) (he|she|they)",
            r"^(his|her|their) (record|bills|policies|achievements)",
            r"^(the|that) (honorable|senator|governor|rep|minister)",
            r"^tell me more",
            r"^more (about|on|details)",
            r"^what about (him|her|them)",
        ]
        
        if any(re.match(p, text_lower) for p in followup_indicators):
            return Intent.FOLLOWUP, 0.85, entities
        
        # Short message with pronouns
        if context and getattr(context, 'politician', None) and not context.is_stale():
            pronouns = ["he", "him", "his", "she", "her", "they", "them", "their"]
            if len(text_lower.split()) <= 6 and any(p in text_lower.split() for p in pronouns):
                entities["resolved_politician"] = context.politician
                return Intent.FOLLOWUP, 0.8, entities
        
        # === POLITICIAN RECORD ===
        record_patterns = [
            r"what (has|have|did) (.+?) done",
            r"(.+?)('s|s') (record|achievements|bills|projects)",
            r"(achievements|projects|bills) (of|by) (.+)",
        ]
        
        for pattern in record_patterns:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                for g in groups:
                    if g and g not in ["has", "have", "did", "'s", "s'", "of", "by", 
                                       "record", "achievements", "bills", "projects"]:
                        entities["politician_query"] = g.strip()
                        break
                return Intent.POLITICIAN_RECORD, 0.85, entities
        
        # === REPRESENTATIVE LOOKUP ===
        if re.search(r"(who|find|show).*(my|our).*(rep|representative|senator|governor)", text_lower) or \
           re.search(r"(my|our) (rep|representative|senator|governor)", text_lower) or \
           re.search(r"who represents (me|us|my area)", text_lower):
            return Intent.REP_LOOKUP, 0.9, entities
        
        # === POLITICIAN INFO ===
        info_patterns = [
            r"who is (.+)",
            r"tell me about (.+)",
            r"(governor|senator|president|minister) of (.+)",
        ]
        
        for pattern in info_patterns:
            match = re.search(pattern, text_lower)
            if match:
                entities["politician_query"] = match.group(1).strip()
                return Intent.POLITICIAN_INFO, 0.8, entities
        
        # === ISSUE REPORT ===
        issue_patterns = [
            r"(report|document).*(issue|problem|pothole|flood|damage)",
            r"(bad|broken|damaged) (road|bridge|light|pipe)",
            r"(no|lack of) (light|power|water|electricity)",
            r"(pothole|flood|erosion|leak)",
            r"there('s| is) (a|an) (problem|issue|crater)",
        ]
        
        if any(re.search(p, text_lower) for p in issue_patterns):
            return Intent.ISSUE_REPORT, 0.85, entities
        
        # === FALLBACK ===
        return Intent.FALLBACK, 0.3, entities

    def decide_data_strategy(self, intent: Intent, text: str) -> DataStrategy:
        """
        Decide whether to use RAG, Realtime, or Hybrid based on intent and query.
        """
        if intent == Intent.NEWS_QUERY:
            return DataStrategy.HYBRID
            
        if intent in [Intent.POLITICIAN_INFO, Intent.POLITICIAN_RECORD]:
            # If query asks for "latest" or "current", verify with realtime
            if any(w in text.lower() for w in ["latest", "current", "news", "today", "now"]):
                return DataStrategy.HYBRID
            return DataStrategy.RAG_ONLY
            
        if intent == Intent.REP_LOOKUP:
            return DataStrategy.RAG_ONLY
            
        if intent == Intent.FALLBACK:
            # Check for realtime keywords
            rt_keywords = ["news", "latest", "price", "cost", "happening", "breaking"]
            if any(k in text.lower() for k in rt_keywords):
                return DataStrategy.REALTIME_ONLY
            # Check if likely general knowledge -> RAG
            return DataStrategy.RAG_ONLY
            
        return DataStrategy.NO_DATA

# Singleton
router = Router()
