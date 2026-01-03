"""
Claude Understanding Module

Uses Claude to semantically understand user queries and extract:
1. Intent - What the user wants to do
2. Entities - Key information (politician name, position, topic, etc.)
3. Retrieval Strategy - How to find the answer
"""
import json
import logging
import os
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import anthropic

logger = logging.getLogger(__name__)


class RetrievalStrategy(Enum):
    """How to retrieve information for a query."""
    DB_LOOKUP = "db_lookup"           # Look up politician by name in DB
    POSITION_LOOKUP = "position_lookup"   # Look up by position (president, governor)
    REP_LOOKUP = "rep_lookup"         # Look up user's representatives
    WEB_SEARCH = "web_search"         # Search web for news/current events
    RAG_SEARCH = "rag_search"         # Search document embeddings
    KNOWLEDGE_GRAPH = "knowledge_graph"   # Query Nigeria knowledge graph (history, economics, etc.)
    HYBRID = "hybrid"                 # Combine multiple sources
    NONE = "none"                     # No retrieval needed (greetings, help)
    ELECTION_SYSTEM = "election_system"   # Use 2027 election tracking system


class Intent(Enum):
    """User intent categories."""
    GREETING = "greeting"
    REP_LOOKUP = "rep_lookup"
    POLITICIAN_INFO = "politician_info"
    POLITICIAN_RECORD = "politician_record"
    NEWS_QUERY = "news_query"
    ISSUE_REPORT = "issue_report"
    VOTER_REGISTRATION = "voter_registration"
    HELP = "help"
    THANKS = "thanks"
    CONFIRMATION = "confirmation"
    CLARIFICATION = "clarification"
    FALLBACK = "fallback"
    # 2027 Election Intents
    FOLLOW_CANDIDATE = "follow_candidate"
    UNFOLLOW_CANDIDATE = "unfollow_candidate"
    MY_CANDIDATES = "my_candidates"
    COMPARE_CANDIDATES = "compare_candidates"
    CANDIDATE_SEARCH = "candidate_search"
    POLL_LIST = "poll_list"
    POLL_VOTE = "poll_vote"
    POLL_RESULTS = "poll_results"
    TRENDING_TOPICS = "trending_topics"
    ELECTION_INFO = "election_info"


@dataclass
class QueryUnderstanding:
    """Result of Claude's understanding of a user query."""
    intent: Intent
    entities: Dict
    retrieval_strategy: RetrievalStrategy
    confidence: float
    reasoning: str = ""
    

# Claude prompt for understanding queries
UNDERSTANDING_PROMPT = """You are classifying queries for Decide9ja, Nigeria's non-partisan civic engagement platform. Users ask about politics, government, policies, elections, and civic issues.

USER CONTEXT:
- State: {user_state} | LGA: {user_lga} | Name: {user_name} | Previous Topic: {active_topic}

QUERY: "{query}"

Return JSON with: intent, entities, retrieval_strategy, confidence (0-1), reasoning

=== MULTI-SHOT EXAMPLES ===

QUERY: "Who is the president of Nigeria?"
→ {{"intent": "politician_info", "entities": {{"position": "president"}}, "retrieval_strategy": "position_lookup", "confidence": 0.95, "reasoning": "Position-based lookup for president"}}

QUERY: "What's the latest on Peter Obi?"
→ {{"intent": "news_query", "entities": {{"politician_name": "Peter Obi", "topic": "Peter Obi latest news"}}, "retrieval_strategy": "web_search", "confidence": 0.95, "reasoning": "Wants current news about Peter Obi"}}

QUERY: "Who is my senator?"
→ {{"intent": "rep_lookup", "entities": {{}}, "retrieval_strategy": "rep_lookup", "confidence": 0.95, "reasoning": "Asking about their own representative"}}

QUERY: "Who represents Ikeja?"
→ {{"intent": "rep_lookup", "entities": {{"lga": "Ikeja", "state": "Lagos"}}, "retrieval_strategy": "rep_lookup", "confidence": 0.9, "reasoning": "Asking about representatives for specific LGA"}}

QUERY: "Who is the senator for Ogun West?"
→ {{"intent": "politician_info", "entities": {{"position": "senator", "district": "Ogun West", "state": "Ogun"}}, "retrieval_strategy": "position_lookup", "confidence": 0.9, "reasoning": "Asking about senator for specific district"}}

QUERY: "Show me representatives for Alimosho, Lagos"
→ {{"intent": "rep_lookup", "entities": {{"lga": "Alimosho", "state": "Lagos"}}, "retrieval_strategy": "rep_lookup", "confidence": 0.95, "reasoning": "Explicit LGA and state for rep lookup"}}

QUERY: "Tell me more about the governor" (after seeing representatives)
→ {{"intent": "politician_record", "entities": {{"position": "governor", "is_followup": true}}, "retrieval_strategy": "hybrid", "confidence": 0.9, "reasoning": "Follow-up about a rep just shown"}}

QUERY: "What has the senator done?" (after seeing representatives)
→ {{"intent": "politician_record", "entities": {{"position": "senator", "is_followup": true}}, "retrieval_strategy": "hybrid", "confidence": 0.9, "reasoning": "Follow-up about senator from previous response"}}

QUERY: "What bills has he sponsored?" (Previous Topic: Peter Obi)
→ {{"intent": "politician_record", "entities": {{"is_followup": true, "record_type": "bills"}}, "retrieval_strategy": "hybrid", "confidence": 0.9, "reasoning": "Follow-up about bills, resolves to active topic"}}

QUERY: "What about his education policies?" (Previous Topic: Tinubu)
→ {{"intent": "politician_record", "entities": {{"is_followup": true, "topic": "education policies"}}, "retrieval_strategy": "hybrid", "confidence": 0.9, "reasoning": "Follow-up about topic, resolves to active politician"}}

QUERY: "Any recent news about him?" (Previous Topic: Wike)
→ {{"intent": "news_query", "entities": {{"is_followup": true}}, "retrieval_strategy": "web_search", "confidence": 0.9, "reasoning": "Follow-up news request about active politician"}}

QUERY: "What has Tinubu done since becoming president?"
→ {{"intent": "politician_record", "entities": {{"politician_name": "Tinubu", "topic": "achievements as president"}}, "retrieval_strategy": "hybrid", "confidence": 0.9, "reasoning": "Wants record/achievements, needs DB + web"}}

QUERY: "Explain the tax reform bill controversy"
→ {{"intent": "news_query", "entities": {{"topic": "tax reform bill Nigeria"}}, "retrieval_strategy": "web_search", "confidence": 0.9, "reasoning": "Policy explanation needs current context"}}

QUERY: "Is Wike still fighting with Fubara?"
→ {{"intent": "news_query", "entities": {{"politician_name": "Wike", "topic": "Wike Fubara conflict"}}, "retrieval_strategy": "web_search", "confidence": 0.95, "reasoning": "Current events question about political conflict"}}

QUERY: "How do I get my PVC?"
→ {{"intent": "voter_registration", "entities": {{}}, "retrieval_strategy": "rag_search", "confidence": 0.95, "reasoning": "Voter registration question"}}

QUERY: "Tell me about Atiku Abubakar"
→ {{"intent": "politician_info", "entities": {{"politician_name": "Atiku Abubakar"}}, "retrieval_strategy": "db_lookup", "confidence": 0.95, "reasoning": "Biographical info request"}}

QUERY: "What's APC's position on fuel subsidy?"
→ {{"intent": "news_query", "entities": {{"topic": "APC fuel subsidy policy Nigeria"}}, "retrieval_strategy": "hybrid", "confidence": 0.85, "reasoning": "Policy question needs web search"}}

QUERY: "There's a big pothole on my street"
→ {{"intent": "issue_report", "entities": {{"issue_type": "pothole"}}, "retrieval_strategy": "none", "confidence": 0.9, "reasoning": "User wants to report infrastructure issue"}}

QUERY: "Compare Obi and Tinubu's education policies"
→ {{"intent": "news_query", "entities": {{"politician_name": "Peter Obi, Tinubu", "topic": "education policy comparison"}}, "retrieval_strategy": "hybrid", "confidence": 0.85, "reasoning": "Policy comparison needs multiple sources"}}

QUERY: "When is the next election?"
→ {{"intent": "news_query", "entities": {{"topic": "Nigeria next election date"}}, "retrieval_strategy": "web_search", "confidence": 0.9, "reasoning": "Election information query"}}

QUERY: "I heard the governor was impeached - is that true?"
→ {{"intent": "news_query", "entities": {{"position": "governor", "topic": "governor impeachment Nigeria"}}, "retrieval_strategy": "web_search", "confidence": 0.95, "reasoning": "Verifying current news/rumor"}}

QUERY: "Hi"
→ {{"intent": "greeting", "entities": {{}}, "retrieval_strategy": "none", "confidence": 1.0, "reasoning": "Simple greeting"}}

QUERY: "help"
→ {{"intent": "help", "entities": {{}}, "retrieval_strategy": "none", "confidence": 1.0, "reasoning": "Explicit help request"}}

QUERY: "What do you think about Tinubu?"
→ {{"intent": "news_query", "entities": {{"politician_name": "Tinubu", "topic": "Tinubu public opinion analysis"}}, "retrieval_strategy": "hybrid", "confidence": 0.8, "reasoning": "Opinion/analysis question - provide neutral facts"}}

QUERY: "Why is Nigeria's economy struggling?"
→ {{"intent": "news_query", "entities": {{"topic": "Nigeria economy analysis 2024"}}, "retrieval_strategy": "web_search", "confidence": 0.85, "reasoning": "Economic analysis question"}}

QUERY: "Who are the senators from Lagos?"
→ {{"intent": "politician_info", "entities": {{"position": "senator", "state": "Lagos"}}, "retrieval_strategy": "db_lookup", "confidence": 0.9, "reasoning": "State-specific politician query"}}

=== 2027 ELECTION EXAMPLES ===

QUERY: "Follow Tinubu"
→ {{"intent": "follow_candidate", "entities": {{"candidate_name": "Tinubu"}}, "retrieval_strategy": "election_system", "confidence": 0.95, "reasoning": "User wants to follow a candidate"}}

QUERY: "Unfollow Peter Obi"
→ {{"intent": "unfollow_candidate", "entities": {{"candidate_name": "Peter Obi"}}, "retrieval_strategy": "election_system", "confidence": 0.95, "reasoning": "User wants to stop following a candidate"}}

QUERY: "My candidates" / "Who am I following?"
→ {{"intent": "my_candidates", "entities": {{}}, "retrieval_strategy": "election_system", "confidence": 0.95, "reasoning": "User wants to see followed candidates"}}

QUERY: "Compare Tinubu and Obi" / "Compare candidates"
→ {{"intent": "compare_candidates", "entities": {{"candidates": ["Tinubu", "Obi"]}}, "retrieval_strategy": "election_system", "confidence": 0.9, "reasoning": "Candidate comparison request"}}

QUERY: "Who is running for president in 2027?"
→ {{"intent": "candidate_search", "entities": {{"position": "president"}}, "retrieval_strategy": "election_system", "confidence": 0.9, "reasoning": "Searching for 2027 candidates"}}

QUERY: "Show me polls" / "Current polls" / "Any polls?"
→ {{"intent": "poll_list", "entities": {{}}, "retrieval_strategy": "election_system", "confidence": 0.95, "reasoning": "User wants to see available polls"}}

QUERY: "Vote in poll" / "I want to vote"
→ {{"intent": "poll_vote", "entities": {{}}, "retrieval_strategy": "election_system", "confidence": 0.9, "reasoning": "User wants to participate in poll"}}

QUERY: "Poll results" / "Who is winning?"
→ {{"intent": "poll_results", "entities": {{}}, "retrieval_strategy": "election_system", "confidence": 0.9, "reasoning": "User wants to see poll results"}}

QUERY: "What's trending?" / "Trending topics" / "Hot in politics"
→ {{"intent": "trending_topics", "entities": {{}}, "retrieval_strategy": "election_system", "confidence": 0.9, "reasoning": "User wants trending political topics"}}

QUERY: "When is the 2027 election?" / "INEC updates"
→ {{"intent": "election_info", "entities": {{}}, "retrieval_strategy": "election_system", "confidence": 0.9, "reasoning": "General 2027 election information"}}

=== CLASSIFICATION RULES ===
1. "latest", "news", "update", "happening", "recent", "heard" → news_query + web_search
2. "who is" + position (president, governor) → politician_info + position_lookup
3. "who is" + name → politician_info + db_lookup
4. "my senator", "my governor", "represents me" → rep_lookup
5. Policy questions, comparisons, analysis → news_query + hybrid
6. "what has X done", achievements, record → politician_record + hybrid
7. Only "help", "options", "what can you do" → help
8. Only greetings → greeting
9. "follow" + candidate name → follow_candidate + election_system
10. "unfollow" + candidate name → unfollow_candidate + election_system
11. "my candidates", "who am I following" → my_candidates + election_system
12. "compare" + candidate names → compare_candidates + election_system
13. "who is running", "2027 candidates" → candidate_search + election_system
14. "polls", "vote in poll" → poll_list or poll_vote + election_system
15. "poll results", "who is winning" → poll_results + election_system
16. "trending", "what's hot" → trending_topics + election_system

Now classify this query: "{query}"
Return ONLY valid JSON."""


async def claude_understand(
    query: str,
    user_state: Optional[str] = None,
    user_lga: Optional[str] = None,
    user_name: Optional[str] = None,
    active_topic: Optional[str] = None
) -> QueryUnderstanding:
    """
    Use Claude to semantically understand a user query.
    
    Args:
        query: The user's message
        user_state: User's Nigerian state (for context)
        user_lga: User's LGA (for context)
        user_name: User's name (for personalization)
        active_topic: Current conversation topic (for follow-ups)
    
    Returns:
        QueryUnderstanding with intent, entities, and retrieval strategy
    """
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Format the prompt
        prompt = UNDERSTANDING_PROMPT.format(
            user_state=user_state or "Unknown",
            user_lga=user_lga or "Unknown",
            user_name=user_name or "Unknown",
            active_topic=active_topic or "None",
            query=query
        )
        
        # Call Claude
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Fast and cheap for classification
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON response
        response_text = response.content[0].text.strip()
        
        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        data = json.loads(response_text)
        
        # Convert to QueryUnderstanding
        return QueryUnderstanding(
            intent=_parse_intent(data.get("intent", "fallback")),
            entities=data.get("entities", {}),
            retrieval_strategy=_parse_strategy(data.get("retrieval_strategy", "none")),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", "")
        )
        
    except json.JSONDecodeError as e:
        logger.warning(f"Claude returned invalid JSON: {e}")
        return _fallback_understanding(query)
        
    except Exception as e:
        logger.error(f"Claude understanding error: {e}")
        return _fallback_understanding(query)


def _parse_intent(intent_str: str) -> Intent:
    """Parse intent string to Intent enum."""
    intent_map = {
        "greeting": Intent.GREETING,
        "rep_lookup": Intent.REP_LOOKUP,
        "politician_info": Intent.POLITICIAN_INFO,
        "politician_record": Intent.POLITICIAN_RECORD,
        "news_query": Intent.NEWS_QUERY,
        "issue_report": Intent.ISSUE_REPORT,
        "voter_registration": Intent.VOTER_REGISTRATION,
        "help": Intent.HELP,
        "thanks": Intent.THANKS,
        "confirmation": Intent.CONFIRMATION,
        "clarification": Intent.CLARIFICATION,
        # 2027 Election intents
        "follow_candidate": Intent.FOLLOW_CANDIDATE,
        "unfollow_candidate": Intent.UNFOLLOW_CANDIDATE,
        "my_candidates": Intent.MY_CANDIDATES,
        "compare_candidates": Intent.COMPARE_CANDIDATES,
        "candidate_search": Intent.CANDIDATE_SEARCH,
        "poll_list": Intent.POLL_LIST,
        "poll_vote": Intent.POLL_VOTE,
        "poll_results": Intent.POLL_RESULTS,
        "trending_topics": Intent.TRENDING_TOPICS,
        "election_info": Intent.ELECTION_INFO,
    }
    return intent_map.get(intent_str.lower(), Intent.FALLBACK)


def _parse_strategy(strategy_str: str) -> RetrievalStrategy:
    """Parse strategy string to RetrievalStrategy enum."""
    strategy_map = {
        "db_lookup": RetrievalStrategy.DB_LOOKUP,
        "position_lookup": RetrievalStrategy.POSITION_LOOKUP,
        "rep_lookup": RetrievalStrategy.REP_LOOKUP,
        "web_search": RetrievalStrategy.WEB_SEARCH,
        "rag_search": RetrievalStrategy.RAG_SEARCH,
        "hybrid": RetrievalStrategy.HYBRID,
        "none": RetrievalStrategy.NONE,
        "election_system": RetrievalStrategy.ELECTION_SYSTEM,
    }
    return strategy_map.get(strategy_str.lower(), RetrievalStrategy.NONE)


def _fallback_understanding(query: str) -> QueryUnderstanding:
    """Fallback understanding when Claude fails."""
    # Simple keyword-based fallback
    query_lower = query.lower()
    
    if any(w in query_lower for w in ["hi", "hello", "hey", "good"]):
        return QueryUnderstanding(
            intent=Intent.GREETING,
            entities={},
            retrieval_strategy=RetrievalStrategy.NONE,
            confidence=0.6
        )
    
    if any(w in query_lower for w in ["my senator", "my governor", "my rep", "represent me"]):
        return QueryUnderstanding(
            intent=Intent.REP_LOOKUP,
            entities={},
            retrieval_strategy=RetrievalStrategy.REP_LOOKUP,
            confidence=0.6
        )
    
    if any(w in query_lower for w in ["news", "latest", "update", "happening"]):
        return QueryUnderstanding(
            intent=Intent.NEWS_QUERY,
            entities={"topic": query},
            retrieval_strategy=RetrievalStrategy.WEB_SEARCH,
            confidence=0.5
        )
    
    # Default fallback
    return QueryUnderstanding(
        intent=Intent.FALLBACK,
        entities={},
        retrieval_strategy=RetrievalStrategy.HYBRID,
        confidence=0.3
    )


# Synchronous wrapper for non-async contexts
def understand_sync(
    query: str,
    user_state: Optional[str] = None,
    user_lga: Optional[str] = None,
    user_name: Optional[str] = None,
    active_topic: Optional[str] = None
) -> QueryUnderstanding:
    """Synchronous version of claude_understand."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        claude_understand(query, user_state, user_lga, user_name, active_topic)
    )
