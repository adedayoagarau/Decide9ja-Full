"""
Agentic Retrieval System for Decide9ja/Tade Chatbot.

Implements advanced retrieval patterns based on research from major AI labs:
- Manus AI: Tool grouping, context engineering
- Anthropic: Tool search, strict schemas
- OpenAI: Handoff patterns, mega-agent approach
- Google: Layered RAG architecture

Key Features:
1. Tool Groups - Organized tools with semantic routing
2. Pattern-matching Fast Path - Instant routing for common queries
3. Query Rewriting - Reformulate failed queries
4. Document Grading - LLM-scored relevance filtering
5. Multi-step Retrieval - Query decomposition for complex questions
6. Self-correction Loop - Retry with reflection on failure
7. Handoff Protocol - Tools can transfer to other tools

References:
- https://cookbook.openai.com/examples/orchestrating_agents
- https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns
- https://weaviate.io/blog/what-is-agentic-rag

Author: Decide9ja Team
"""
import os
import re
import json
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

import anthropic

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS & DATA CLASSES
# =============================================================================

class ToolGroup(Enum):
    """Tool groups for efficient routing."""
    POLITICIAN = "politician"       # DB lookups, position lookups
    NEWS = "news"                   # Web search, RSS, trending
    KNOWLEDGE = "knowledge"         # RAG, knowledge graph, documents
    ELECTION = "election"           # 2027 candidates, polls, compare
    COMMUNITY = "community"         # Issues, fact-check, gamification
    CONVERSATION = "conversation"   # Greetings, help, simple responses
    NONE = "none"                   # No tools needed


class RetrievalStatus(Enum):
    """Status of retrieval attempt."""
    SUCCESS = "success"
    PARTIAL = "partial"           # Got some results but incomplete
    FAILED = "failed"             # No results
    NEEDS_REWRITE = "needs_rewrite"
    NEEDS_DECOMPOSITION = "needs_decomposition"
    HANDOFF = "handoff"           # Transfer to another tool group


@dataclass
class GradedDocument:
    """A retrieved document with relevance score."""
    content: str
    source: str
    relevance_score: float  # 0-1
    metadata: Dict = field(default_factory=dict)


@dataclass
class RetrievalAttempt:
    """Record of a single retrieval attempt."""
    query: str
    tool_group: ToolGroup
    tools_used: List[str]
    documents: List[GradedDocument]
    status: RetrievalStatus
    error: Optional[str] = None
    rewrite_suggestion: Optional[str] = None


@dataclass
class AgenticResult:
    """Final result from agentic retrieval."""
    original_query: str
    final_query: str  # May be rewritten
    attempts: List[RetrievalAttempt]
    graded_context: str
    sources_used: List[str]
    confidence: float
    total_attempts: int
    success: bool


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

# Tool Group Definitions with descriptions for semantic routing
TOOL_GROUPS = {
    ToolGroup.POLITICIAN: {
        "description": "Information about politicians, government officials, their positions, parties, and biographical details",
        "keywords": ["who is", "governor", "senator", "president", "minister", "representative", "politician", "party", "APC", "PDP", "LP"],
        "tools": ["db_lookup", "position_lookup", "rep_lookup"]
    },
    ToolGroup.NEWS: {
        "description": "Current events, news, updates, recent happenings, trending topics in Nigerian politics",
        "keywords": ["news", "latest", "update", "recent", "happening", "today", "trending", "current"],
        "tools": ["web_search", "rss_search", "news_db"]
    },
    ToolGroup.KNOWLEDGE: {
        "description": "Historical information, policy explanations, educational content, background knowledge",
        "keywords": ["explain", "what is", "how does", "history", "policy", "law", "constitution", "budget", "FAAC"],
        "tools": ["rag_search", "knowledge_graph", "document_search"]
    },
    ToolGroup.ELECTION: {
        "description": "2027 elections, candidates, polls, comparisons, voting information",
        "keywords": ["2027", "election", "candidate", "vote", "poll", "compare", "follow", "running for"],
        "tools": ["candidate_tracker", "polling_system", "compare_candidates"]
    },
    ToolGroup.COMMUNITY: {
        "description": "Community issues, fact-checking, civic engagement, user reports, gamification",
        "keywords": ["report", "issue", "verify", "fact check", "points", "leaderboard", "subscribe"],
        "tools": ["issue_reporter", "fact_checker", "gamification"]
    },
    ToolGroup.CONVERSATION: {
        "description": "Greetings, help requests, simple conversational responses",
        "keywords": ["hi", "hello", "help", "thanks", "menu", "options"],
        "tools": ["greeting_handler", "help_handler", "template_response"]
    }
}


# =============================================================================
# PATTERN MATCHING (FAST PATH)
# =============================================================================

# Fast patterns for instant routing (bypasses LLM classification)
FAST_PATTERNS: List[Tuple[str, ToolGroup, str, Dict]] = [
    # Greetings - highest priority
    (r"^(hi|hello|hey|good\s*(morning|afternoon|evening))[\s!.,]*$", ToolGroup.CONVERSATION, "greeting", {}),
    (r"^(help|menu|options|what can you do)[\s?]*$", ToolGroup.CONVERSATION, "help", {}),
    (r"^(thanks?|thank you|ok|okay)[\s!.,]*$", ToolGroup.CONVERSATION, "thanks", {}),

    # Representative lookups - clear patterns
    (r"(my|who is my|who'?s my)\s*(senator|governor|rep|representative)", ToolGroup.POLITICIAN, "rep_lookup", {}),

    # Position lookups
    (r"who is (the )?(president|vice president|vp)", ToolGroup.POLITICIAN, "position_lookup", {"position": "president"}),
    (r"who is (the )?governor of (\w+)", ToolGroup.POLITICIAN, "position_lookup", {"position": "governor"}),

    # Election system - 2027
    (r"^follow\s+(.+)$", ToolGroup.ELECTION, "follow_candidate", {"candidate_name": 1}),
    (r"^unfollow\s+(.+)$", ToolGroup.ELECTION, "unfollow_candidate", {"candidate_name": 1}),
    (r"(my candidates|who am i following)", ToolGroup.ELECTION, "my_candidates", {}),
    (r"compare\s+(.+)\s+(and|vs|versus)\s+(.+)", ToolGroup.ELECTION, "compare_candidates", {}),
    (r"(who is running|candidates for|2027 candidates)", ToolGroup.ELECTION, "candidate_search", {}),
    (r"(show|list|any)\s*polls?", ToolGroup.ELECTION, "poll_list", {}),
    (r"poll results", ToolGroup.ELECTION, "poll_results", {}),

    # Community
    (r"(my points|check.*points|how many points)", ToolGroup.COMMUNITY, "my_points", {}),
    (r"leaderboard|rankings", ToolGroup.COMMUNITY, "leaderboard", {}),
    (r"^subscribe", ToolGroup.COMMUNITY, "subscribe", {}),
    (r"^unsubscribe", ToolGroup.COMMUNITY, "unsubscribe", {}),
    (r"(fact check|verify|is it true)", ToolGroup.COMMUNITY, "fact_check", {}),
    (r"report.*(issue|problem|pothole|road|light|water)", ToolGroup.COMMUNITY, "report_issue", {}),

    # News patterns
    (r"(latest|news|update|what'?s happening).*(about|on|with)?\s*(.+)?", ToolGroup.NEWS, "web_search", {}),
    (r"trending|what'?s hot", ToolGroup.NEWS, "trending", {}),
]


def fast_route(query: str) -> Optional[Tuple[ToolGroup, str, Dict]]:
    """
    Fast pattern-matching routing.
    Returns (tool_group, intent, entities) if matched, None otherwise.
    """
    query_lower = query.lower().strip()

    for pattern, tool_group, intent, entity_template in FAST_PATTERNS:
        match = re.search(pattern, query_lower, re.IGNORECASE)
        if match:
            # Extract entities from capture groups
            entities = {}
            for key, value in entity_template.items():
                if isinstance(value, int) and value <= len(match.groups()):
                    entities[key] = match.group(value)
                else:
                    entities[key] = value

            logger.info(f"Fast route matched: {intent} -> {tool_group.value}")
            return (tool_group, intent, entities)

    return None


# =============================================================================
# LLM-BASED ROUTING
# =============================================================================

async def llm_route_to_tool_group(
    query: str,
    user_context: Dict = None
) -> Tuple[ToolGroup, str, Dict, float]:
    """
    Use LLM to route query to appropriate tool group.
    Returns (tool_group, intent, entities, confidence).
    """
    user_context = user_context or {}

    prompt = f"""You are a router for Decide9ja, Nigeria's civic engagement platform.

Route this query to ONE tool group based on what the user needs:

TOOL GROUPS:
1. POLITICIAN - Info about politicians, positions, parties, bios
2. NEWS - Current events, latest updates, trending topics
3. KNOWLEDGE - Historical info, policy explanations, background
4. ELECTION - 2027 elections, candidates, polls, comparisons
5. COMMUNITY - Report issues, fact-check, civic points
6. CONVERSATION - Greetings, help, simple responses

USER CONTEXT:
State: {user_context.get('state', 'Unknown')}
Name: {user_context.get('name', 'Unknown')}

QUERY: "{query}"

Respond in JSON:
{{
    "tool_group": "POLITICIAN|NEWS|KNOWLEDGE|ELECTION|COMMUNITY|CONVERSATION",
    "intent": "specific_intent_name",
    "entities": {{"key": "extracted_value"}},
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Be decisive. Choose the MOST relevant group."""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        # Parse JSON
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.split("```")[0]

        data = json.loads(result_text)

        tool_group_str = data.get("tool_group", "CONVERSATION").upper()
        tool_group = getattr(ToolGroup, tool_group_str, ToolGroup.CONVERSATION)

        return (
            tool_group,
            data.get("intent", "unknown"),
            data.get("entities", {}),
            float(data.get("confidence", 0.5))
        )

    except Exception as e:
        logger.error(f"LLM routing error: {e}")
        return (ToolGroup.KNOWLEDGE, "fallback", {}, 0.3)


# =============================================================================
# QUERY ANALYSIS & DECOMPOSITION
# =============================================================================

async def analyze_query_complexity(query: str) -> Dict:
    """
    Analyze query to determine if it needs decomposition.
    Returns analysis with complexity score and sub-queries if needed.
    """
    # Simple heuristics first
    complexity_indicators = {
        "compare": 0.3,
        "and": 0.2,
        "vs": 0.3,
        "versus": 0.3,
        "difference between": 0.4,
        "both": 0.2,
        "all": 0.2,
        "multiple": 0.2,
    }

    complexity_score = 0
    for indicator, score in complexity_indicators.items():
        if indicator in query.lower():
            complexity_score += score

    # If potentially complex, use LLM to decompose
    if complexity_score >= 0.3:
        return await llm_decompose_query(query)

    return {
        "is_complex": False,
        "complexity_score": complexity_score,
        "sub_queries": [query],
        "strategy": "single"
    }


async def llm_decompose_query(query: str) -> Dict:
    """
    Use LLM to decompose complex query into sub-queries.
    """
    prompt = f"""Analyze this query and determine if it should be broken into sub-queries.

QUERY: "{query}"

If the query asks about multiple things (e.g., comparing politicians, multiple topics), break it down.
If it's a single focused question, keep it as-is.

Respond in JSON:
{{
    "is_complex": true|false,
    "complexity_score": 0.0-1.0,
    "sub_queries": ["query1", "query2"],
    "strategy": "single|parallel|sequential",
    "reasoning": "brief explanation"
}}

Examples:
- "Compare Tinubu and Obi" → ["Tinubu profile and policies", "Peter Obi profile and policies"]
- "What has Tinubu done?" → ["Tinubu achievements as president"] (single)
- "Who is the president and what's the latest news?" → ["Who is the president?", "Latest Nigerian politics news"]"""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()
        if "```" in result_text:
            result_text = result_text.split("```json")[-1].split("```")[0]

        return json.loads(result_text)

    except Exception as e:
        logger.error(f"Query decomposition error: {e}")
        return {
            "is_complex": False,
            "complexity_score": 0.3,
            "sub_queries": [query],
            "strategy": "single"
        }


# =============================================================================
# DOCUMENT GRADING
# =============================================================================

async def grade_documents(
    query: str,
    documents: List[Dict],
    threshold: float = 0.4
) -> List[GradedDocument]:
    """
    Grade retrieved documents for relevance using LLM.
    Filters out documents below threshold.
    """
    if not documents:
        return []

    # Format documents for grading
    doc_texts = []
    for i, doc in enumerate(documents[:10]):  # Limit to 10 docs
        content = doc.get("content", doc.get("summary", doc.get("title", "")))[:300]
        doc_texts.append(f"[{i}] {content}")

    docs_formatted = "\n".join(doc_texts)

    prompt = f"""Grade these documents for relevance to the query.

QUERY: "{query}"

DOCUMENTS:
{docs_formatted}

For each document, rate relevance 0.0-1.0:
- 0.0-0.3: Not relevant
- 0.4-0.6: Somewhat relevant
- 0.7-1.0: Highly relevant

Respond in JSON:
{{
    "grades": [
        {{"index": 0, "score": 0.8, "reason": "directly answers question"}},
        {{"index": 1, "score": 0.3, "reason": "tangentially related"}}
    ]
}}"""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()
        if "```" in result_text:
            result_text = result_text.split("```json")[-1].split("```")[0]

        data = json.loads(result_text)

        # Build graded documents
        graded = []
        for grade in data.get("grades", []):
            idx = grade.get("index", 0)
            score = float(grade.get("score", 0))

            if score >= threshold and idx < len(documents):
                doc = documents[idx]
                graded.append(GradedDocument(
                    content=doc.get("content", doc.get("summary", doc.get("title", ""))),
                    source=doc.get("source", "unknown"),
                    relevance_score=score,
                    metadata=doc
                ))

        # Sort by relevance
        graded.sort(key=lambda x: x.relevance_score, reverse=True)
        return graded

    except Exception as e:
        logger.error(f"Document grading error: {e}")
        # Fallback: return all documents with default score
        return [
            GradedDocument(
                content=doc.get("content", doc.get("summary", "")),
                source=doc.get("source", "unknown"),
                relevance_score=0.5,
                metadata=doc
            )
            for doc in documents[:5]
        ]


# =============================================================================
# QUERY REWRITING
# =============================================================================

async def rewrite_query(
    original_query: str,
    failed_attempt: RetrievalAttempt,
    user_context: Dict = None
) -> str:
    """
    Rewrite query based on failed retrieval attempt.
    """
    user_context = user_context or {}

    prompt = f"""The following query didn't retrieve good results. Rewrite it to be more specific.

ORIGINAL QUERY: "{original_query}"

WHAT WE TRIED:
- Tool group: {failed_attempt.tool_group.value}
- Tools used: {', '.join(failed_attempt.tools_used)}
- Status: {failed_attempt.status.value}
{f'- Error: {failed_attempt.error}' if failed_attempt.error else ''}

USER CONTEXT:
State: {user_context.get('state', 'Unknown')}

REWRITING STRATEGIES:
1. Add "Nigeria" if missing
2. Use full names instead of nicknames
3. Add relevant timeframe (e.g., "2024", "recent")
4. Be more specific about what's being asked
5. Include relevant keywords

Respond with ONLY the rewritten query, nothing else."""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        rewritten = response.content[0].text.strip()
        # Remove quotes if present
        rewritten = rewritten.strip('"\'')

        logger.info(f"Query rewritten: '{original_query}' -> '{rewritten}'")
        return rewritten

    except Exception as e:
        logger.error(f"Query rewrite error: {e}")
        # Simple fallback: add "Nigeria" if not present
        if "nigeria" not in original_query.lower():
            return f"{original_query} Nigeria"
        return original_query


# =============================================================================
# TOOL EXECUTORS
# =============================================================================

async def execute_politician_tools(
    query: str,
    intent: str,
    entities: Dict,
    user_context: Dict = None
) -> List[Dict]:
    """Execute politician-related tools."""
    from app.services.intelligent_retrieval import (
        _lookup_politician_by_name,
        _lookup_politician_by_position,
        _lookup_representatives
    )

    results = []
    user_context = user_context or {}

    try:
        if intent == "rep_lookup":
            state = user_context.get("state")
            lga = user_context.get("lga")
            if state and lga:
                reps = await _lookup_representatives(state, lga)
                for rep in reps:
                    results.append({
                        "content": f"{rep['position']}: {rep['name']} ({rep['party']}) - {rep.get('area', '')}",
                        "source": "lga_representatives",
                        "type": "representative",
                        "data": rep
                    })

        elif intent == "position_lookup":
            position = entities.get("position", "")
            state = entities.get("state", user_context.get("state"))
            politician = await _lookup_politician_by_position(position, state)
            if politician:
                results.append({
                    "content": f"{politician['name']} is the {politician['position']}. Party: {politician.get('party', 'Unknown')}. {politician.get('bio', '')}",
                    "source": "politicians_db",
                    "type": "politician",
                    "data": politician
                })

        elif intent in ["db_lookup", "politician_info"]:
            name = entities.get("politician_name", query)
            politician = await _lookup_politician_by_name(name)
            if politician:
                results.append({
                    "content": f"{politician['name']} - {politician['position']}. Party: {politician.get('party', 'Unknown')}. {politician.get('bio', '')}",
                    "source": "politicians_db",
                    "type": "politician",
                    "data": politician
                })

    except Exception as e:
        logger.error(f"Politician tools error: {e}")

    return results


async def execute_news_tools(
    query: str,
    intent: str,
    entities: Dict,
    user_context: Dict = None
) -> List[Dict]:
    """Execute news-related tools."""
    from app.services.intelligent_retrieval import _search_web

    results = []

    try:
        # Add Nigeria context if not present
        search_query = query
        if "nigeria" not in query.lower():
            search_query = f"{query} Nigeria"

        web_results = await _search_web(search_query, limit=5)

        for item in web_results:
            results.append({
                "content": f"{item.get('title', '')}\n{item.get('summary', '')[:300]}",
                "source": item.get("source", "web_search"),
                "type": "news",
                "url": item.get("url", ""),
                "data": item
            })

    except Exception as e:
        logger.error(f"News tools error: {e}")

    return results


async def execute_knowledge_tools(
    query: str,
    intent: str,
    entities: Dict,
    user_context: Dict = None
) -> List[Dict]:
    """Execute knowledge/RAG tools."""
    from app.services.intelligent_retrieval import _search_rag

    results = []

    try:
        rag_context = await _search_rag(query, limit=5)

        if rag_context:
            results.append({
                "content": rag_context,
                "source": "rag_documents",
                "type": "knowledge",
                "data": {}
            })

    except Exception as e:
        logger.error(f"Knowledge tools error: {e}")

    return results


async def execute_election_tools(
    query: str,
    intent: str,
    entities: Dict,
    user_context: Dict = None
) -> List[Dict]:
    """Execute election-related tools."""
    from app.services.election_2027.candidate_tracker import (
        get_candidate_tracker,
        get_candidate
    )

    results = []

    try:
        tracker = get_candidate_tracker()

        if intent == "candidate_search":
            candidates = tracker.get_presidential_candidates()
            for c in candidates:
                results.append({
                    "content": f"{c.name} ({c.party}) - {'Incumbent' if c.is_incumbent else 'Challenger'}",
                    "source": "candidate_tracker",
                    "type": "candidate",
                    "data": {"name": c.name, "party": c.party}
                })

        elif intent in ["follow_candidate", "politician_info"]:
            name = entities.get("candidate_name", query)
            candidate = get_candidate(name)
            if candidate:
                results.append({
                    "content": f"{candidate.name} - {candidate.party}. {candidate.bio or ''}",
                    "source": "candidate_tracker",
                    "type": "candidate",
                    "data": {"name": candidate.name, "party": candidate.party}
                })

    except Exception as e:
        logger.error(f"Election tools error: {e}")

    return results


# Tool group executor mapping
TOOL_EXECUTORS = {
    ToolGroup.POLITICIAN: execute_politician_tools,
    ToolGroup.NEWS: execute_news_tools,
    ToolGroup.KNOWLEDGE: execute_knowledge_tools,
    ToolGroup.ELECTION: execute_election_tools,
}


# =============================================================================
# SELF-CORRECTION LOOP
# =============================================================================

async def retrieval_with_self_correction(
    query: str,
    tool_group: ToolGroup,
    intent: str,
    entities: Dict,
    user_context: Dict = None,
    max_attempts: int = 3
) -> RetrievalAttempt:
    """
    Execute retrieval with self-correction loop.

    Pattern:
    1. Execute tools
    2. Grade results
    3. If insufficient, reflect and rewrite
    4. Retry with rewritten query
    5. Max 3 attempts
    """
    user_context = user_context or {}
    current_query = query
    attempts = []

    for attempt_num in range(max_attempts):
        logger.info(f"Retrieval attempt {attempt_num + 1}/{max_attempts}: {current_query}")

        # Execute appropriate tools
        executor = TOOL_EXECUTORS.get(tool_group)
        if not executor:
            # Fallback to knowledge tools
            executor = execute_knowledge_tools

        raw_results = await executor(current_query, intent, entities, user_context)

        # Grade the results
        graded_docs = await grade_documents(current_query, raw_results)

        # Determine status
        if graded_docs and any(d.relevance_score >= 0.6 for d in graded_docs):
            status = RetrievalStatus.SUCCESS
        elif graded_docs:
            status = RetrievalStatus.PARTIAL
        else:
            status = RetrievalStatus.FAILED

        attempt = RetrievalAttempt(
            query=current_query,
            tool_group=tool_group,
            tools_used=[tool_group.value],
            documents=graded_docs,
            status=status
        )
        attempts.append(attempt)

        # If successful or partial with good docs, we're done
        if status == RetrievalStatus.SUCCESS:
            logger.info(f"Retrieval succeeded on attempt {attempt_num + 1}")
            return attempt

        # If failed and we have more attempts, rewrite query
        if attempt_num < max_attempts - 1:
            # Check if we should try a different tool group (handoff)
            if status == RetrievalStatus.FAILED and attempt_num == 0:
                # Try news if politician failed, or vice versa
                if tool_group == ToolGroup.POLITICIAN:
                    logger.info("Handing off from POLITICIAN to NEWS")
                    tool_group = ToolGroup.NEWS
                elif tool_group == ToolGroup.NEWS:
                    logger.info("Handing off from NEWS to KNOWLEDGE")
                    tool_group = ToolGroup.KNOWLEDGE

            # Rewrite query for next attempt
            current_query = await rewrite_query(query, attempt, user_context)

    # Return last attempt
    return attempts[-1] if attempts else RetrievalAttempt(
        query=query,
        tool_group=tool_group,
        tools_used=[],
        documents=[],
        status=RetrievalStatus.FAILED,
        error="Max attempts reached"
    )


# =============================================================================
# MAIN AGENTIC RETRIEVAL
# =============================================================================

async def agentic_retrieve(
    query: str,
    user_context: Dict = None
) -> AgenticResult:
    """
    Main entry point for agentic retrieval.

    Flow:
    1. Try fast pattern matching
    2. If no match, use LLM routing
    3. Analyze query complexity (decompose if needed)
    4. Execute retrieval with self-correction
    5. Grade and merge results
    6. Return formatted context
    """
    user_context = user_context or {}
    all_attempts = []

    # Step 1: Fast pattern matching
    fast_result = fast_route(query)

    if fast_result:
        tool_group, intent, entities = fast_result
        confidence = 0.95  # High confidence for pattern match
    else:
        # Step 2: LLM routing
        tool_group, intent, entities, confidence = await llm_route_to_tool_group(
            query, user_context
        )

    logger.info(f"Routed to {tool_group.value} with intent={intent}, confidence={confidence}")

    # Step 3: Check if we need the conversation handler (no retrieval)
    if tool_group == ToolGroup.CONVERSATION:
        return AgenticResult(
            original_query=query,
            final_query=query,
            attempts=[],
            graded_context="",
            sources_used=[],
            confidence=confidence,
            total_attempts=0,
            success=True
        )

    # Step 4: Analyze complexity
    complexity = await analyze_query_complexity(query)

    if complexity.get("is_complex") and complexity.get("strategy") == "parallel":
        # Execute sub-queries in parallel
        sub_queries = complexity.get("sub_queries", [query])
        tasks = [
            retrieval_with_self_correction(
                sq, tool_group, intent, entities, user_context
            )
            for sq in sub_queries
        ]
        sub_results = await asyncio.gather(*tasks)

        # Merge results
        all_docs = []
        for result in sub_results:
            all_attempts.append(result)
            all_docs.extend(result.documents)

        # Re-grade merged documents
        final_docs = await grade_documents(query, [
            {"content": d.content, "source": d.source}
            for d in all_docs
        ])

    else:
        # Single query retrieval
        result = await retrieval_with_self_correction(
            query, tool_group, intent, entities, user_context
        )
        all_attempts.append(result)
        final_docs = result.documents

    # Step 5: Format final context
    graded_context = format_graded_context(final_docs)
    sources_used = list(set(d.source for d in final_docs))

    success = bool(final_docs) and any(d.relevance_score >= 0.4 for d in final_docs)

    return AgenticResult(
        original_query=query,
        final_query=all_attempts[-1].query if all_attempts else query,
        attempts=all_attempts,
        graded_context=graded_context,
        sources_used=sources_used,
        confidence=confidence,
        total_attempts=len(all_attempts),
        success=success
    )


def format_graded_context(documents: List[GradedDocument]) -> str:
    """Format graded documents into context string."""
    if not documents:
        return "No relevant information found."

    parts = []
    for i, doc in enumerate(documents[:5]):  # Top 5 documents
        relevance_label = "HIGH" if doc.relevance_score >= 0.7 else "MEDIUM" if doc.relevance_score >= 0.5 else "LOW"
        parts.append(f"[{doc.source.upper()}] ({relevance_label} relevance)\n{doc.content}")

    return "\n\n---\n\n".join(parts)


# =============================================================================
# HANDOFF PROTOCOL
# =============================================================================

class ToolHandoff:
    """Represents a handoff from one tool to another."""

    def __init__(self, from_tool: str, to_tool: str, reason: str, context: Dict = None):
        self.from_tool = from_tool
        self.to_tool = to_tool
        self.reason = reason
        self.context = context or {}
        self.timestamp = datetime.utcnow()


def transfer_to_news(context: Dict = None) -> ToolHandoff:
    """Transfer conversation to news tools."""
    return ToolHandoff("current", "news", "Query requires current events", context)


def transfer_to_politician(context: Dict = None) -> ToolHandoff:
    """Transfer conversation to politician tools."""
    return ToolHandoff("current", "politician", "Query about specific politician", context)


def transfer_to_knowledge(context: Dict = None) -> ToolHandoff:
    """Transfer conversation to knowledge/RAG tools."""
    return ToolHandoff("current", "knowledge", "Query requires background information", context)


def transfer_to_election(context: Dict = None) -> ToolHandoff:
    """Transfer conversation to election tools."""
    return ToolHandoff("current", "election", "Query about 2027 elections", context)


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

async def get_agentic_context(
    query: str,
    user_state: str = None,
    user_lga: str = None,
    user_name: str = None
) -> Tuple[str, List[str], bool]:
    """
    Helper function to get agentic retrieval context.
    Returns (context_string, sources_used, success).
    """
    user_context = {
        "state": user_state,
        "lga": user_lga,
        "name": user_name
    }

    result = await agentic_retrieve(query, user_context)

    return (
        result.graded_context,
        result.sources_used,
        result.success
    )
