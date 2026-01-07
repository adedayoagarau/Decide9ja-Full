"""
Understanding Agent Prompt - Intent & Entity Extraction

Links to Source of Truth for:
- Entity definitions
- Nigerian politics knowledge (for entity recognition)
- Tools (for retrieval strategy selection)

This agent extracts intent, entities, and determines retrieval strategy.
"""

from typing import Dict, List, Optional
from app.services.prompts.source_of_truth import (
    get_sot_sections,
    SOTSection,
    build_agent_prompt,
    AgentPromptConfig
)


# =============================================================================
# UNDERSTANDING-SPECIFIC TASK DEFINITION
# =============================================================================

UNDERSTANDING_TASK = """
<task>
You are the Understanding Agent for Decide9ja. Your job is to:

1. CLASSIFY the user's intent
2. EXTRACT relevant entities (politicians, positions, states, topics)
3. DETERMINE the best retrieval strategy
4. IDENTIFY follow-up context needs

<input>
- User query (text)
- User context (state, LGA, name - if available)
- Conversation history (if available)
</input>

<processing_steps>
1. Read the query carefully
2. Identify the primary intent from the intent taxonomy
3. Extract all mentioned entities
4. Determine what data sources would best answer this query
5. Return structured JSON output
</processing_steps>
</task>
"""

UNDERSTANDING_OUTPUT = """
<output_format>
Return JSON with this exact schema:

```json
{
  "intent": "<intent_code>",
  "confidence": 0.0-1.0,
  "entities": {
    "politician_name": "<name or null>",
    "position": "<position or null>",
    "state": "<state or null>",
    "party": "<party or null>",
    "topic": "<topic or null>",
    "timeframe": "<timeframe or null>"
  },
  "retrieval_strategy": "<strategy_code>",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
```

<intent_taxonomy>
| Code | Description | Triggers |
|------|-------------|----------|
| GREETING | Hello, hi, good morning | Greetings, salutations |
| POLITICIAN_INFO | Who is X, tell me about Y | Politician name mentioned |
| POLITICIAN_RECORD | What has X done, X's record | Record, achievement, scandal |
| POSITION_LOOKUP | Who is the president/governor | Position mentioned |
| REPRESENTATIVE | Who is my senator/rep | "my" + position |
| NEWS_QUERY | Latest news, what's happening | news, latest, recent, update |
| EXPLANATION | Explain X, what is Y | explain, what is, how does |
| ELECTION_INFO | 2027 candidates, election | 2027, election, candidate |
| COMPARISON | Compare X and Y | compare, versus, vs, difference |
| ISSUE_REPORT | Report problem, submit | report, submit, complain |
| BUDGET_QUERY | Budget, allocation, FAAC | budget, allocation, spending |
| FOLLOWUP | Referring to previous context | pronouns without antecedent |
| HELP | How to use, what can you do | help, assist, how to |
| OUT_OF_SCOPE | Non-Nigerian politics | Weather, sports, etc. |
</intent_taxonomy>

<retrieval_strategies>
| Code | When to Use | Tools |
|------|-------------|-------|
| NONE | Greetings, help, out of scope | No retrieval needed |
| DB_LOOKUP | Politician by name | politician_lookup |
| POSITION_LOOKUP | Politician by position | politician_lookup (position) |
| REP_LOOKUP | User's representatives | representative_lookup |
| WEB_SEARCH | Current news, recent events | web_search |
| RAG_SEARCH | Historical, policies, explanations | knowledge_base |
| ELECTION_SYSTEM | 2027 election data | election_info |
| HYBRID | Complex queries needing multiple sources | Multiple tools |
</retrieval_strategies>
</output_format>
"""

UNDERSTANDING_EXAMPLES = """
<examples>

<example>
USER: "Who is Tinubu?"
OUTPUT:
{
  "intent": "POLITICIAN_INFO",
  "confidence": 0.95,
  "entities": {
    "politician_name": "Tinubu",
    "position": null,
    "state": null,
    "party": null,
    "topic": null,
    "timeframe": null
  },
  "retrieval_strategy": "DB_LOOKUP",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
</example>

<example>
USER: "Who is the governor of Lagos?"
OUTPUT:
{
  "intent": "POSITION_LOOKUP",
  "confidence": 0.95,
  "entities": {
    "politician_name": null,
    "position": "governor",
    "state": "Lagos",
    "party": null,
    "topic": null,
    "timeframe": null
  },
  "retrieval_strategy": "POSITION_LOOKUP",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
</example>

<example>
USER: "Who is my senator?"
USER_CONTEXT: {state: "Lagos", lga: "Ikeja"}
OUTPUT:
{
  "intent": "REPRESENTATIVE",
  "confidence": 0.95,
  "entities": {
    "politician_name": null,
    "position": "senator",
    "state": "Lagos",
    "party": null,
    "topic": null,
    "timeframe": null
  },
  "retrieval_strategy": "REP_LOOKUP",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
</example>

<example>
USER: "Who is my senator?"
USER_CONTEXT: {state: null, lga: null}
OUTPUT:
{
  "intent": "REPRESENTATIVE",
  "confidence": 0.7,
  "entities": {
    "politician_name": null,
    "position": "senator",
    "state": null,
    "party": null,
    "topic": null,
    "timeframe": null
  },
  "retrieval_strategy": "REP_LOOKUP",
  "requires_clarification": true,
  "clarification_question": "To find your senator, I need to know your location. Which state and LGA do you live in?",
  "is_followup": false,
  "followup_context": null
}
</example>

<example>
USER: "What's the latest news on the tax reform?"
OUTPUT:
{
  "intent": "NEWS_QUERY",
  "confidence": 0.9,
  "entities": {
    "politician_name": null,
    "position": null,
    "state": null,
    "party": null,
    "topic": "tax reform",
    "timeframe": "latest"
  },
  "retrieval_strategy": "WEB_SEARCH",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
</example>

<example>
USER: "Explain how VAT sharing works"
OUTPUT:
{
  "intent": "EXPLANATION",
  "confidence": 0.9,
  "entities": {
    "politician_name": null,
    "position": null,
    "state": null,
    "party": null,
    "topic": "VAT sharing formula",
    "timeframe": null
  },
  "retrieval_strategy": "RAG_SEARCH",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
</example>

<example>
USER: "What about his party?"
PREVIOUS: Discussed Tinubu
OUTPUT:
{
  "intent": "FOLLOWUP",
  "confidence": 0.85,
  "entities": {
    "politician_name": null,
    "position": null,
    "state": null,
    "party": null,
    "topic": "party affiliation",
    "timeframe": null
  },
  "retrieval_strategy": "DB_LOOKUP",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": true,
  "followup_context": "User asking about previously discussed politician's party"
}
</example>

<example>
USER: "Who is running for president in 2027?"
OUTPUT:
{
  "intent": "ELECTION_INFO",
  "confidence": 0.95,
  "entities": {
    "politician_name": null,
    "position": "president",
    "state": null,
    "party": null,
    "topic": "2027 presidential candidates",
    "timeframe": "2027"
  },
  "retrieval_strategy": "ELECTION_SYSTEM",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
</example>

<example>
USER: "Compare Tinubu and Atiku"
OUTPUT:
{
  "intent": "COMPARISON",
  "confidence": 0.9,
  "entities": {
    "politician_name": "Tinubu, Atiku",
    "position": null,
    "state": null,
    "party": null,
    "topic": "politician comparison",
    "timeframe": null
  },
  "retrieval_strategy": "HYBRID",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
</example>

<example>
USER: "What's the weather like?"
OUTPUT:
{
  "intent": "OUT_OF_SCOPE",
  "confidence": 0.95,
  "entities": {
    "politician_name": null,
    "position": null,
    "state": null,
    "party": null,
    "topic": "weather",
    "timeframe": null
  },
  "retrieval_strategy": "NONE",
  "requires_clarification": false,
  "clarification_question": null,
  "is_followup": false,
  "followup_context": null
}
</example>

</examples>
"""


# =============================================================================
# BUILD UNDERSTANDING PROMPT
# =============================================================================

def build_understanding_prompt(
    query: str,
    user_context: Dict = None,
    conversation_history: str = None
) -> str:
    """
    Build the complete Understanding Agent prompt.

    Args:
        query: User's query to analyze
        user_context: User's state, LGA, name
        conversation_history: Recent conversation for followup detection

    Returns:
        Complete prompt string
    """
    user_context = user_context or {}

    config = AgentPromptConfig(
        agent_name="Understanding Agent",
        agent_role="Intent Classification & Entity Extraction",
        sot_sections=[
            SOTSection.ENTITIES,
            SOTSection.POLITICS,  # For entity recognition
        ],
        task_specific=UNDERSTANDING_TASK,
        output_format=UNDERSTANDING_OUTPUT,
        examples=UNDERSTANDING_EXAMPLES
    )

    base_prompt = build_agent_prompt(config)

    # Add the actual query
    query_section = f"""
<query_to_analyze>
USER QUERY: "{query}"

USER CONTEXT:
- State: {user_context.get('state', 'Unknown')}
- LGA: {user_context.get('lga', 'Unknown')}
- Name: {user_context.get('name', 'Unknown')}
"""

    if conversation_history:
        query_section += f"""
RECENT CONVERSATION:
{conversation_history}
"""

    query_section += """
</query_to_analyze>

INSTRUCTIONS:
Analyze the query and return ONLY the JSON output. No explanation needed.
"""

    return base_prompt + query_section


# =============================================================================
# FAST PATTERN-BASED UNDERSTANDING (Bypass LLM for simple cases)
# =============================================================================

INTENT_PATTERNS = {
    "GREETING": [
        r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|greetings)[\s!.,?]*$",
        r"^(how\s*(are\s*you|do\s*you\s*do))[\s!.,?]*$",
    ],
    "HELP": [
        r"^(help|what\s*can\s*you\s*do|how\s*do\s*(i|you)|assist)[\s!.,?]*$",
        r"^(/help|/start|/menu)[\s!.,?]*$",
    ],
    "POLITICIAN_INFO": [
        r"who\s+is\s+([A-Z][a-z]+(\s+[A-Z][a-z]+)*)",
        r"tell\s+me\s+about\s+([A-Z][a-z]+)",
    ],
    "POSITION_LOOKUP": [
        r"who\s+is\s+the\s+(president|governor|senator|minister)",
        r"(president|governor|senator)\s+of\s+(\w+)",
    ],
    "REPRESENTATIVE": [
        r"(my|our)\s+(senator|governor|representative|rep)",
        r"who\s+represents\s+me",
    ],
    "NEWS_QUERY": [
        r"(latest|recent|news|update|what'?s\s+happening)",
        r"trending",
    ],
}


def fast_pattern_match(query: str) -> Optional[Dict]:
    """
    Fast pattern matching for simple queries.
    Returns None if no pattern matches (use LLM instead).
    """
    import re

    query_lower = query.lower().strip()

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                # Found a match - extract basic entities
                entities = _extract_entities_from_pattern(query, intent)
                return {
                    "intent": intent,
                    "confidence": 0.8,  # Pattern match confidence
                    "entities": entities,
                    "retrieval_strategy": _get_strategy_for_intent(intent),
                    "requires_clarification": False,
                    "is_followup": False,
                    "matched_by": "pattern"
                }

    return None  # No pattern matched, use LLM


def _extract_entities_from_pattern(query: str, intent: str) -> Dict:
    """Extract entities based on intent type."""
    import re

    entities = {
        "politician_name": None,
        "position": None,
        "state": None,
        "party": None,
        "topic": None,
        "timeframe": None
    }

    if intent == "POLITICIAN_INFO":
        # Extract capitalized names
        words = query.split()
        names = [w for w in words if w[0].isupper() and len(w) > 2]
        if names:
            entities["politician_name"] = " ".join(names[:2])

    elif intent == "POSITION_LOOKUP":
        positions = ["president", "governor", "senator", "minister", "rep"]
        for pos in positions:
            if pos in query.lower():
                entities["position"] = pos
                break

        # Extract state
        nigerian_states = ["lagos", "kano", "rivers", "oyo", "kaduna", "abuja", "fct"]
        for state in nigerian_states:
            if state in query.lower():
                entities["state"] = state.title()
                break

    elif intent == "REPRESENTATIVE":
        positions = ["senator", "governor", "representative", "rep"]
        for pos in positions:
            if pos in query.lower():
                entities["position"] = pos
                break

    elif intent == "NEWS_QUERY":
        # Extract topic (everything after trigger words)
        topic_match = re.search(r"(news|latest|update)\s+(on|about)?\s*(.+)", query.lower())
        if topic_match:
            entities["topic"] = topic_match.group(3).strip()

    return entities


def _get_strategy_for_intent(intent: str) -> str:
    """Map intent to retrieval strategy."""
    strategy_map = {
        "GREETING": "NONE",
        "HELP": "NONE",
        "POLITICIAN_INFO": "DB_LOOKUP",
        "POSITION_LOOKUP": "POSITION_LOOKUP",
        "REPRESENTATIVE": "REP_LOOKUP",
        "NEWS_QUERY": "WEB_SEARCH",
        "EXPLANATION": "RAG_SEARCH",
        "ELECTION_INFO": "ELECTION_SYSTEM",
        "COMPARISON": "HYBRID",
        "FOLLOWUP": "DB_LOOKUP",
        "OUT_OF_SCOPE": "NONE",
    }
    return strategy_map.get(intent, "HYBRID")
