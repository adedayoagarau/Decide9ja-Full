# FIX 1: INTENT CLASSIFICATION
# File: app/services/intent_classifier.py
# 
# Problem: The word "issue" triggers issue-reporting flow even for news queries
# Solution: Check for news patterns BEFORE issue patterns

import re
from typing import Tuple, Optional
from enum import Enum

class Intent(Enum):
    GREETING = "greeting"
    REPRESENTATIVE_LOOKUP = "representative_lookup"
    POLITICIAN_INFO = "politician_info"
    POLITICIAN_RECORD = "politician_record"  # "what has X done?"
    NEWS_QUERY = "news_query"
    ISSUE_REPORT = "issue_report"
    ELECTION_INFO = "election_info"
    VOTER_REGISTRATION = "voter_registration"
    POLICY_QUESTION = "policy_question"
    CONTACT_LOOKUP = "contact_lookup"
    FOLLOWUP = "followup"
    CONFIRMATION = "confirmation"
    GENERAL_QUESTION = "general_question"
    UNKNOWN = "unknown"


def classify_intent(message: str, context: dict = None) -> Tuple[Intent, float, dict]:
    """
    Classify user intent from message.
    
    Returns:
        (intent, confidence, extracted_entities)
    """
    message_lower = message.lower().strip()
    entities = {}
    
    # === GREETING ===
    greeting_patterns = [
        r"^hi$", r"^hello$", r"^hey$", r"^good\s*(morning|afternoon|evening)",
        r"^howdy$", r"^greetings$", r"^sup$", r"^yo$"
    ]
    if any(re.match(p, message_lower) for p in greeting_patterns):
        return Intent.GREETING, 0.95, entities
    
    # === CONFIRMATION (yes/no responses) ===
    if message_lower in ["yes", "yeah", "yep", "sure", "ok", "okay", "no", "nope", "nah"]:
        return Intent.CONFIRMATION, 0.95, {"response": message_lower in ["yes", "yeah", "yep", "sure", "ok", "okay"]}
    
    # === VOTER REGISTRATION ===
    voter_patterns = [
        r"(how|where).*(register|vote|voting|pvc)",
        r"voter.*(registration|card)",
        r"(get|obtain).*(pvc|voter)",
        r"inec.*(registration|office)"
    ]
    if any(re.search(p, message_lower) for p in voter_patterns):
        return Intent.VOTER_REGISTRATION, 0.9, entities
    
    # === NEWS QUERY (check BEFORE issue patterns) ===
    # This is the key fix - "issue" in news context should not trigger issue reporting
    news_patterns = [
        r"update\s+on\s+.+",                    # "update on the wike issue"
        r"what.*(happening|going on)",          # "what's happening with"
        r"(latest|recent|trending|current).*(news|update|issue|development)",
        r"(wike|makinde|tinubu|obi|atiku).*vs",  # Political conflicts
        r".*vs.*(wike|makinde|tinubu|obi|atiku)",
        r"news\s+(about|on)",
        r"what.*(trending|happening)",
        r"(any|what).*(update|news)",
        r"tell me about.*(crisis|conflict|issue|problem|situation)",
        r"(pdp|apc|lp).*(crisis|issue|problem)",
        r".*issue\s+between",                   # "issue between X and Y"
        r"most important.*(policy|issue)",
    ]
    if any(re.search(p, message_lower) for p in news_patterns):
        return Intent.NEWS_QUERY, 0.85, entities
    
    # === FOLLOWUP QUESTIONS (context-dependent) ===
    # These need context to resolve
    followup_patterns = [
        r"^(what|how) about (him|her|them|that|this|it)\??$",
        r"^(tell me|what) more\??$",
        r"^(and|also|what about)\s",
        r"^the (recent|latest) (one|trip|news)",
        r"what (has|have|did) (he|she|they) done",
        r"what are (his|her|their) (policies|projects|achievements)",
        r"the (honorable|senator|governor|rep|minister)",  # References without name
    ]
    if any(re.search(p, message_lower) for p in followup_patterns):
        return Intent.FOLLOWUP, 0.8, entities
    
    # === POLITICIAN RECORD (what has X done) ===
    record_patterns = [
        r"what (has|have|did) .+ done",
        r"(achievements|projects|bills) (of|by)",
        r"(track record|performance) of",
        r".+ (achievements|accomplishments|projects)",
    ]
    if any(re.search(p, message_lower) for p in record_patterns):
        # Try to extract politician name
        name_match = re.search(r"what (?:has|have|did) (.+?) done", message_lower)
        if name_match:
            entities["politician_ref"] = name_match.group(1).strip()
        return Intent.POLITICIAN_RECORD, 0.85, entities
    
    # === REPRESENTATIVE LOOKUP ===
    rep_patterns = [
        r"who (is|are) my (rep|representative|senator|governor|legislator)",
        r"my (rep|representative|senator|governor)",
        r"who represents (me|us|my area)",
        r"(find|show|tell).*(my|our) (rep|representative)",
        r"(rep|representative|senator|governor) (for|of|in) .+",
    ]
    if any(re.search(p, message_lower) for p in rep_patterns):
        return Intent.REPRESENTATIVE_LOOKUP, 0.9, entities
    
    # === POLITICIAN INFO ===
    politician_patterns = [
        r"(who is|tell me about|info on) .+",
        r"(governor|senator|president|minister) of .+",
        r"(how many votes|election results) .+",
    ]
    if any(re.search(p, message_lower) for p in politician_patterns):
        # Extract name if present
        name_match = re.search(r"(?:who is|tell me about|info on) (.+)", message_lower)
        if name_match:
            entities["politician_query"] = name_match.group(1).strip()
        return Intent.POLITICIAN_INFO, 0.8, entities
    
    # === ELECTION INFO ===
    election_patterns = [
        r"(election|vote|voting) (results|data|count)",
        r"(who|which party) (won|win|winning)",
        r"2023.*(election|results)",
        r"2027.*(election|prediction)",
        r"(how many|total) votes",
    ]
    if any(re.search(p, message_lower) for p in election_patterns):
        return Intent.ELECTION_INFO, 0.85, entities
    
    # === POLICY QUESTION ===
    policy_patterns = [
        r"(policy|policies) (of|on|about)",
        r"what (is|are) .+ (policy|policies|stance)",
        r"(subsidy|tax|reform|bill)",
    ]
    if any(re.search(p, message_lower) for p in policy_patterns):
        return Intent.POLICY_QUESTION, 0.8, entities
    
    # === CONTACT LOOKUP ===
    contact_patterns = [
        r"(contact|phone|number|email|address) (of|for)",
        r"(how to|where to) (contact|reach|call)",
        r"(ministry|commissioner|office).*(contact|number|phone)",
    ]
    if any(re.search(p, message_lower) for p in contact_patterns):
        return Intent.CONTACT_LOOKUP, 0.85, entities
    
    # === ISSUE REPORT (check AFTER news patterns) ===
    # Only trigger if user explicitly wants to report
    issue_report_patterns = [
        r"(i want to|let me|help me) report",
        r"report (an?|this) (issue|problem)",
        r"(there is|there's) (a|an) (problem|issue) (in|at|near)",
        r"(bad|broken|damaged) (road|bridge|light|water)",
        r"no (light|water|electricity) (in|at)",
    ]
    if any(re.search(p, message_lower) for p in issue_report_patterns):
        return Intent.ISSUE_REPORT, 0.85, entities
    
    # === GENERAL QUESTION (fallback) ===
    if "?" in message or message_lower.startswith(("what", "who", "where", "when", "why", "how")):
        return Intent.GENERAL_QUESTION, 0.6, entities
    
    return Intent.UNKNOWN, 0.3, entities


def resolve_followup_intent(message: str, context: dict) -> Tuple[Intent, dict]:
    """
    Resolve a followup question using conversation context.
    
    Context should contain:
    - active_politician: Currently discussed politician
    - active_topic: Current topic (e.g., "policies", "record", "election")
    - last_intent: Previous intent
    """
    message_lower = message.lower().strip()
    entities = {}
    
    active_politician = context.get("active_politician")
    active_topic = context.get("active_topic")
    
    # If there's an active politician and user asks about "him/her/them/the honorable"
    if active_politician:
        # Check for record/achievement questions
        if any(kw in message_lower for kw in ["done", "achievement", "project", "bill", "record"]):
            entities["politician_name"] = active_politician
            return Intent.POLITICIAN_RECORD, entities
        
        # Check for policy questions
        if any(kw in message_lower for kw in ["policy", "policies", "stance", "position"]):
            entities["politician_name"] = active_politician
            return Intent.POLICY_QUESTION, entities
        
        # Check for election/vote questions
        if any(kw in message_lower for kw in ["vote", "votes", "election", "won", "win"]):
            entities["politician_name"] = active_politician
            return Intent.ELECTION_INFO, entities
        
        # General followup about the politician
        if any(kw in message_lower for kw in ["him", "her", "them", "the honorable", "the senator", "the governor"]):
            entities["politician_name"] = active_politician
            return Intent.POLITICIAN_INFO, entities
    
    # Default to general question
    return Intent.GENERAL_QUESTION, entities


# === TEST CASES ===
if __name__ == "__main__":
    test_cases = [
        # Should be NEWS_QUERY, not ISSUE_REPORT
        ("What's the update on the wike vs Seyi Makinde issue", Intent.NEWS_QUERY),
        ("What's the most important policy trending in Nigeria rn?", Intent.NEWS_QUERY),
        ("Any update on the PDP crisis", Intent.NEWS_QUERY),
        ("What's happening with the tax bill issue", Intent.NEWS_QUERY),
        
        # Should be ISSUE_REPORT
        ("I want to report an issue", Intent.ISSUE_REPORT),
        ("There's a bad road in my area", Intent.ISSUE_REPORT),
        ("Report broken street light", Intent.ISSUE_REPORT),
        
        # Should be FOLLOWUP
        ("What has he done?", Intent.FOLLOWUP),
        ("The honorable's achievements", Intent.FOLLOWUP),
        ("What are his policies?", Intent.FOLLOWUP),
        
        # Should be REPRESENTATIVE_LOOKUP
        ("Who is my senator?", Intent.REPRESENTATIVE_LOOKUP),
        ("Who represents me?", Intent.REPRESENTATIVE_LOOKUP),
        
        # Should be VOTER_REGISTRATION
        ("How do I register to vote", Intent.VOTER_REGISTRATION),
        
        # Should be GREETING
        ("Hi", Intent.GREETING),
        ("Hello", Intent.GREETING),
    ]
    
    print("=== INTENT CLASSIFICATION TESTS ===\n")
    passed = 0
    failed = 0
    
    for message, expected in test_cases:
        intent, confidence, entities = classify_intent(message)
        status = "✅" if intent == expected else "❌"
        if intent == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status} '{message}'")
        print(f"   Expected: {expected.value}, Got: {intent.value} ({confidence:.0%})")
        print()
    
    print(f"\n=== RESULTS: {passed}/{passed+failed} passed ===")
