"""
Retrieval Orchestrator

Combines multiple data sources based on query intent:
- Database: Politicians, representatives, user data
- RAG: Historical records, bills, speeches, manifestos
- Web Search: Current news, recent events

Strategy Matrix:
    ┌─────────────────────┬──────────┬─────────┬────────────┐
    │ Intent              │ Database │ RAG     │ Web Search │
    ├─────────────────────┼──────────┼─────────┼────────────┤
    │ rep_lookup          │ PRIMARY  │ -       │ -          │
    │ politician_info     │ PRIMARY  │ ENRICH  │ FALLBACK   │
    │ politician_record   │ ENRICH   │ PRIMARY │ FALLBACK   │
    │ news_query          │ -        │ CONTEXT │ PRIMARY    │
    │ followup            │ CONTEXT  │ ENRICH  │ FALLBACK   │
    │ voter_registration  │ STATIC   │ -       │ -          │
    │ issue_report        │ -        │ -       │ -          │
    └─────────────────────┴──────────┴─────────┴────────────┘
"""
import asyncio
import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Combined retrieval results."""
    # Primary data
    politician: Optional[Dict] = None
    representatives: List[Dict] = field(default_factory=list)
    
    # Enrichment data  
    rag_context: str = ""
    web_results: List[Dict] = field(default_factory=list)
    news_results: List[Dict] = field(default_factory=list)
    
    # Metadata
    sources_used: List[str] = field(default_factory=list)
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)


class RetrievalStrategy(Enum):
    DATABASE_ONLY = "database_only"
    DATABASE_PLUS_RAG = "database_plus_rag"
    RAG_PRIMARY = "rag_primary"
    WEB_PRIMARY = "web_primary"
    HYBRID = "hybrid"


def get_strategy(intent) -> RetrievalStrategy:
    """Determine retrieval strategy based on intent."""
    from app.services.router import Intent
    
    strategy_map = {
        Intent.REP_LOOKUP: RetrievalStrategy.DATABASE_ONLY,
        Intent.POLITICIAN_INFO: RetrievalStrategy.DATABASE_PLUS_RAG,
        Intent.POLITICIAN_RECORD: RetrievalStrategy.RAG_PRIMARY,
        Intent.NEWS_QUERY: RetrievalStrategy.WEB_PRIMARY,
        Intent.FOLLOWUP: RetrievalStrategy.HYBRID,
        Intent.VOTER_REGISTRATION: RetrievalStrategy.DATABASE_ONLY,
        Intent.FALLBACK: RetrievalStrategy.HYBRID,
    }
    return strategy_map.get(intent, RetrievalStrategy.HYBRID)


async def retrieve(
    intent,
    query: str,
    user_state,
    entities: Dict = None
) -> RetrievalResult:
    """
    Main retrieval function. Orchestrates data fetching based on intent.
    
    Args:
        intent: Classified user intent
        query: User's message text
        user_state: Current conversation state
        entities: Extracted entities (politician name, topic, etc.)
    
    Returns:
        RetrievalResult with combined data from all sources
    """
    from app.services.router import Intent
    
    entities = entities or {}
    result = RetrievalResult()
    
    # === REPRESENTATIVE LOOKUP ===
    if intent == Intent.REP_LOOKUP:
        return await retrieve_representatives(user_state, result)
    
    # === POLITICIAN INFO ===
    if intent == Intent.POLITICIAN_INFO:
        return await retrieve_politician_info(query, user_state, entities, result)
    
    # === POLITICIAN RECORD ===
    if intent == Intent.POLITICIAN_RECORD:
        return await retrieve_politician_record(query, user_state, entities, result)
    
    # === NEWS QUERY ===
    if intent == Intent.NEWS_QUERY:
        return await retrieve_news(query, user_state, result)
    
    # === FOLLOWUP ===
    if intent == Intent.FOLLOWUP:
        return await retrieve_followup(query, user_state, entities, result)
    
    # === FALLBACK / HYBRID ===
    return await retrieve_hybrid(query, user_state, result)


async def retrieve_representatives(
    user_state, 
    result: RetrievalResult
) -> RetrievalResult:
    """Retrieve user's representatives from database."""
    from app.services.politician_lookup import get_representatives
    
    if not user_state.state:
        result.suggestions.append("I need to know your state to find your representatives.")
        return result
    
    reps = await get_representatives(user_state.state, user_state.lga)
    
    if reps:
        result.representatives = reps
        result.sources_used.append("database")
        result.confidence = 1.0
    else:
        result.suggestions.append(
            f"I don't have representative data for {user_state.lga}, {user_state.state} yet."
        )
    
    return result


async def retrieve_politician_info(
    query: str,
    user_state,
    entities: Dict,
    result: RetrievalResult
) -> RetrievalResult:
    """
    Retrieve politician info with fuzzy matching.
    Strategy: Database (primary) + RAG (enrich) + Web (fallback)
    """
    from app.services.politician_lookup import find_politician
    
    politician_query = entities.get("politician_query", query)
    
    # Step 1: Database lookup with fuzzy matching
    match = await find_politician(politician_query, user_state)
    
    if match.politician:
        result.politician = match.politician
        result.sources_used.append("database")
        result.confidence = match.confidence
        
        if match.suggestion:
            result.suggestions.append(match.suggestion)
        
        # Step 2: Enrich with RAG if we have a match
        if match.match_type != "web":
            try:
                rag_context = await rag_search(
                    query=f"{match.politician['name']} biography background",
                    filters={"politician_id": match.politician.get("id")}
                )
                if rag_context:
                    result.rag_context = rag_context
                    result.sources_used.append("rag")
            except Exception as e:
                logger.warning(f"RAG enrichment failed: {e}")
    
    elif match.candidates:
        # Multiple matches - let user choose
        result.suggestions.append("I found several people who might match:")
        for c in match.candidates[:5]:
            result.suggestions.append(f"• {c['name']} ({c.get('position', 'Unknown position')})")
        result.confidence = 0.5
    
    else:
        # Step 3: Web search fallback
        web_results = await search_web_async(f"{politician_query} Nigeria politician", max_results=3)
        if web_results:
            result.web_results = web_results
            result.sources_used.append("web_search")
            result.confidence = 0.6
        else:
            result.suggestions.append(f"I couldn't find information about '{politician_query}'.")
            result.confidence = 0.0
    
    return result


async def retrieve_politician_record(
    query: str,
    user_state,
    entities: Dict,
    result: RetrievalResult
) -> RetrievalResult:
    """
    Retrieve politician's record (bills, projects, etc.)
    Strategy: RAG (primary) + Database (context) + Web (recent)
    """
    from app.services.politician_lookup import find_politician
    
    # Determine which politician
    politician_id = None
    politician_name = None
    
    # Check if we have active context
    if user_state.active_politician_id:
        politician_id = user_state.active_politician_id
        politician_name = user_state.active_politician_name
    else:
        # Try to extract from query
        match = await find_politician(query, user_state)
        if match.politician:
            politician_id = match.politician.get("id")
            politician_name = match.politician.get("name")
            result.politician = match.politician
            result.sources_used.append("database")
    
    if not politician_id:
        result.suggestions.append("Which politician are you asking about?")
        return result
    
    # Parallel fetch: RAG + Web
    try:
        rag_result, web_result = await asyncio.gather(
            rag_search(
                query=f"{politician_name} bills motions projects achievements record",
                filters={"politician_id": politician_id}
            ),
            search_news_async(f"{politician_name} latest news achievements", max_results=3),
            return_exceptions=True
        )
        
        if isinstance(rag_result, str) and rag_result:
            result.rag_context = rag_result
            result.sources_used.append("rag")
            result.confidence = 0.8
        
        if isinstance(web_result, list) and web_result:
            result.news_results = web_result
            result.sources_used.append("web_news")
    except Exception as e:
        logger.warning(f"Parallel fetch failed: {e}")
    
    if not result.rag_context and not result.news_results:
        result.suggestions.append(f"I don't have detailed records for {politician_name} yet.")
        result.confidence = 0.3
    
    return result


async def retrieve_news(
    query: str,
    user_state,
    result: RetrievalResult
) -> RetrievalResult:
    """
    Retrieve current news.
    Strategy: Web (primary) + RAG (background context)
    """
    try:
        # Parallel fetch
        web_result, rag_result = await asyncio.gather(
            search_news_async(query, max_results=5),
            rag_search(query, filters={"type": "news"}),
            return_exceptions=True
        )
        
        if isinstance(web_result, list) and web_result:
            result.news_results = web_result
            result.sources_used.append("web_news")
            result.confidence = 0.9
        
        if isinstance(rag_result, str) and rag_result:
            result.rag_context = rag_result
            result.sources_used.append("rag")
    except Exception as e:
        logger.warning(f"News retrieval failed: {e}")
    
    if not result.news_results:
        result.suggestions.append("I couldn't find recent news on that topic.")
        result.confidence = 0.3
    
    return result


async def retrieve_followup(
    query: str,
    user_state,
    entities: Dict,
    result: RetrievalResult
) -> RetrievalResult:
    """
    Retrieve context for followup questions.
    Uses active_politician and active_topic from state.
    """
    # Resolve pronouns using active context
    resolved_query = resolve_pronouns(query, user_state)
    
    # Determine what they're asking about
    if user_state.active_politician_id:
        # They're asking about a politician
        return await retrieve_politician_record(
            resolved_query, user_state, entities, result
        )
    
    elif getattr(user_state, 'active_topic', None):
        # They're asking about a topic
        return await retrieve_news(resolved_query, user_state, result)
    
    else:
        # No context - ask for clarification
        result.suggestions.append("Who or what are you asking about?")
        return result


async def retrieve_hybrid(
    query: str,
    user_state,
    result: RetrievalResult
) -> RetrievalResult:
    """
    Hybrid retrieval for unclear intents.
    Tries all sources in parallel.
    """
    from app.services.politician_lookup import find_politician
    
    try:
        # Run retrievals in parallel
        pol_result, rag_result, web_result = await asyncio.gather(
            find_politician(query, user_state),
            rag_search(query),
            search_web_async(query + " Nigeria", max_results=3),
            return_exceptions=True
        )
        
        # Collect results from politician lookup
        from app.services.politician_lookup import PoliticianMatch
        if isinstance(pol_result, PoliticianMatch) and pol_result.politician:
            result.politician = pol_result.politician
            result.sources_used.append("database")
            if pol_result.suggestion:
                result.suggestions.append(pol_result.suggestion)
        
        # Collect RAG results  
        if isinstance(rag_result, str) and rag_result:
            result.rag_context = rag_result
            result.sources_used.append("rag")
        
        # Collect web results
        if isinstance(web_result, list) and web_result:
            result.web_results = web_result
            result.sources_used.append("web_search")
        
        # Set confidence based on what we found
        if result.politician:
            result.confidence = 0.8
        elif result.rag_context:
            result.confidence = 0.7
        elif result.web_results:
            result.confidence = 0.6
        else:
            result.confidence = 0.2
            
    except Exception as e:
        logger.error(f"Hybrid retrieval failed: {e}")
        result.confidence = 0.1
    
    return result


def resolve_pronouns(text: str, user_state) -> str:
    """Replace pronouns with the active politician's name."""
    if not getattr(user_state, 'active_politician_name', None):
        return text
    
    name = user_state.active_politician_name
    
    replacements = [
        (r'\b(he|him)\b', name),
        (r'\b(she|her)\b', name),
        (r'\bthey\b', name),
        (r'\bthem\b', name),
        (r'\bhis\b', f"{name}'s"),
        (r'\bher\b', f"{name}'s"),
        (r'\btheir\b', f"{name}'s"),
    ]
    
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


# === HELPER FUNCTIONS FOR RAG AND WEB SEARCH ===

async def rag_search(query: str, filters: Dict = None) -> str:
    """
    Semantic search using existing RAG service.
    """
    try:
        from app.database import get_db
        from app.services.rag import RAGService
        
        db = next(get_db())
        rag = RAGService(db)
        
        context, sources = rag.retrieve(query=query, top_k=3, filters=filters)
        
        if context and not context.startswith("NO"):
            return context
        return ""
    except Exception as e:
        logger.warning(f"RAG search failed: {e}")
        return ""


async def search_web_async(query: str, max_results: int = 3) -> List[Dict]:
    """
    Async web search using DuckDuckGo.
    """
    try:
        from app.services.realtime import fetch_web_search
        
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: fetch_web_search(query, limit=max_results)
        )
        return results
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return []


async def search_news_async(query: str, max_results: int = 5) -> List[Dict]:
    """
    Async news search combining RSS and web.
    """
    try:
        from app.services.realtime import fetch_rss_news, fetch_web_search
        
        loop = asyncio.get_event_loop()
        
        rss_results = await loop.run_in_executor(
            None,
            lambda: fetch_rss_news(topic=query, limit=max_results // 2)
        )
        
        web_results = await loop.run_in_executor(
            None,
            lambda: fetch_web_search(f"{query} news", limit=max_results // 2)
        )
        
        return rss_results + web_results
    except Exception as e:
        logger.warning(f"News search failed: {e}")
        return []
