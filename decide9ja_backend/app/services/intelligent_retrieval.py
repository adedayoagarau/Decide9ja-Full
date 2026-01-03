"""
Intelligent Retrieval Orchestrator

Routes queries to appropriate data sources based on Claude's understanding.
Supports: DB lookup, position lookup, web search, RAG, and hybrid retrieval.
"""
import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from app.services.claude_understand import QueryUnderstanding, RetrievalStrategy, Intent

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Combined retrieval results from all sources."""
    politician: Optional[Dict] = None
    representatives: List[Dict] = field(default_factory=list)
    web_results: List[Dict] = field(default_factory=list)
    rag_context: str = ""
    knowledge_graph_results: List[Dict] = field(default_factory=list)
    knowledge_graph_context: str = ""
    sources_used: List[str] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None


async def intelligent_retrieve(
    understanding: QueryUnderstanding,
    user_state: Optional[str] = None,
    user_lga: Optional[str] = None
) -> RetrievalResult:
    """
    Route retrieval based on Claude's understanding.
    
    Args:
        understanding: The QueryUnderstanding from claude_understand
        user_state: User's Nigerian state
        user_lga: User's LGA
        
    Returns:
        RetrievalResult with data from relevant sources
    """
    result = RetrievalResult()
    strategy = understanding.retrieval_strategy
    entities = understanding.entities
    
    try:
        if strategy == RetrievalStrategy.NONE:
            # No retrieval needed (greetings, help, etc.)
            result.success = True
            return result
        
        if strategy == RetrievalStrategy.DB_LOOKUP:
            # Look up politician by name
            politician_name = entities.get("politician_name", "")
            if politician_name:
                result.politician = await _lookup_politician_by_name(politician_name)
                if result.politician:
                    result.sources_used.append("politicians_db")
                else:
                    # FALLBACK: If no DB result, try web search
                    logger.info(f"Politician lookup failed for '{politician_name}', trying web search fallback")
                    result.web_results = await _search_web(f"{politician_name} Nigeria politician")
                    if result.web_results:
                        result.sources_used.append("web_search_fallback")
        
        elif strategy == RetrievalStrategy.POSITION_LOOKUP:
            # Look up by position (president, governor, etc.)
            position = entities.get("position", "")
            state = entities.get("state", user_state)
            if position:
                result.politician = await _lookup_politician_by_position(position, state)
                if result.politician:
                    result.sources_used.append("politicians_db")
                else:
                    # FALLBACK: If no DB result, try web search
                    logger.info(f"Position lookup failed for '{position}', trying web search fallback")
                    search_query = f"{position} Nigeria"
                    if state:
                        search_query = f"{position} {state} Nigeria"
                    result.web_results = await _search_web(search_query)
                    if result.web_results:
                        result.sources_used.append("web_search_fallback")
        
        elif strategy == RetrievalStrategy.REP_LOOKUP:
            # Look up user's representatives
            if user_state and user_lga:
                result.representatives = await _lookup_representatives(user_state, user_lga)
                result.sources_used.append("lga_representatives")
        
        elif strategy == RetrievalStrategy.WEB_SEARCH:
            # Search web for news/current events
            topic = entities.get("topic", "")
            politician_name = entities.get("politician_name", "")
            search_query = topic or politician_name or "Nigeria politics"
            result.web_results = await _search_web(search_query)
            result.sources_used.append("web_search")
        
        elif strategy == RetrievalStrategy.RAG_SEARCH:
            # Search document embeddings
            topic = entities.get("topic", "")
            politician_name = entities.get("politician_name", "")
            result.rag_context = await _search_rag(topic or politician_name)
            result.sources_used.append("rag_documents")

        elif strategy == RetrievalStrategy.KNOWLEDGE_GRAPH:
            # Search Nigeria knowledge graph (history, economics, politics, etc.)
            topic = entities.get("topic", "")
            politician_name = entities.get("politician_name", "")
            query = topic or politician_name or understanding.interpreted_query
            kg_results = await _search_knowledge_graph(query)
            if kg_results:
                result.knowledge_graph_results = kg_results.get("results", [])
                result.knowledge_graph_context = kg_results.get("context", "")
                result.sources_used.append("nigeria_knowledge_graph")

        elif strategy == RetrievalStrategy.HYBRID:
            # Combine multiple sources
            topic = entities.get("topic", "")
            politician_name = entities.get("politician_name", "")
            
            # Try politician lookup
            if politician_name:
                result.politician = await _lookup_politician_by_name(politician_name)
                if result.politician:
                    result.sources_used.append("politicians_db")
            
            # Try position lookup
            position = entities.get("position")
            if position and not result.politician:
                result.politician = await _lookup_politician_by_position(
                    position, entities.get("state", user_state)
                )
                if result.politician:
                    result.sources_used.append("politicians_db")
            
            # Always try web search for hybrid
            search_query = topic or politician_name or "Nigeria"
            result.web_results = await _search_web(search_query)
            if result.web_results:
                result.sources_used.append("web_search")

            # Try RAG search
            result.rag_context = await _search_rag(topic or politician_name)
            if result.rag_context:
                result.sources_used.append("rag_documents")

            # Try knowledge graph for historical/economic data
            kg_query = topic or politician_name or understanding.interpreted_query
            kg_results = await _search_knowledge_graph(kg_query)
            if kg_results and kg_results.get("results"):
                result.knowledge_graph_results = kg_results.get("results", [])
                result.knowledge_graph_context = kg_results.get("context", "")
                result.sources_used.append("nigeria_knowledge_graph")

        result.success = bool(
            result.politician or
            result.representatives or
            result.web_results or
            result.rag_context or
            result.knowledge_graph_results or
            result.knowledge_graph_context
        )
        
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        result.error = str(e)
    
    return result


# === RETRIEVAL IMPLEMENTATIONS ===

async def _lookup_politician_by_name(name: str) -> Optional[Dict]:
    """Look up politician by name with fuzzy matching."""
    try:
        from app.database import get_db, Politician
        from app.services.fuzzy_match import fuzzy_find_politician
        
        db = next(get_db())
        
        # Try exact match first
        politician = db.query(Politician).filter(
            Politician.name.ilike(f"%{name}%")
        ).first()
        
        if politician:
            return {
                "id": politician.id,
                "name": politician.name,
                "party": politician.party,
                "position": politician.position,
                "state": politician.state,
                "bio": getattr(politician, 'bio', None)
            }
        
        # Try fuzzy match
        all_politicians = db.query(Politician).limit(300).all()
        politician_names = [p.name for p in all_politicians]
        
        match = fuzzy_find_politician(name, politician_names)
        if match:
            politician = db.query(Politician).filter(
                Politician.name == match
            ).first()
            if politician:
                return {
                    "id": politician.id,
                    "name": politician.name,
                    "party": politician.party,
                    "position": politician.position,
                    "state": politician.state,
                    "bio": getattr(politician, 'bio', None),
                    "fuzzy_match": True
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Politician lookup error: {e}")
        return None


async def _lookup_politician_by_position(position: str, state: Optional[str] = None) -> Optional[Dict]:
    """Look up politician by position (president, governor, etc.)."""
    try:
        from app.database import get_db, Politician
        from sqlalchemy import text
        
        db = next(get_db())
        
        # Normalize position
        position_lower = position.lower()
        
        if "president" in position_lower and "vice" not in position_lower:
            query_position = "President"
        elif "vice" in position_lower and "president" in position_lower:
            query_position = "Vice President"
        elif "governor" in position_lower:
            query_position = "Governor"
        elif "senator" in position_lower:
            query_position = "Senator"
        else:
            query_position = position.title()
        
        # Build query
        if query_position in ["President", "Vice President"]:
            # Federal positions - no state filter
            politician = db.query(Politician).filter(
                Politician.position == query_position
            ).first()
        elif state:
            # State-specific positions
            politician = db.query(Politician).filter(
                Politician.position == query_position,
                Politician.state.ilike(f"%{state}%")
            ).first()
        else:
            politician = None
        
        if politician:
            return {
                "id": politician.id,
                "name": politician.name,
                "party": politician.party,
                "position": politician.position,
                "state": politician.state,
                "bio": getattr(politician, 'bio', None)
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Position lookup error: {e}")
        return None


async def _lookup_representatives(user_state: str, user_lga: str) -> List[Dict]:
    """Look up user's representatives by state and LGA."""
    try:
        from sqlalchemy import create_engine, text
        
        engine = create_engine(os.getenv('DATABASE_URL'))
        
        with engine.connect() as conn:
            result = conn.execute(text('''
                SELECT 
                    state, lga,
                    governor_name, governor_party,
                    senator_name, senator_party,
                    house_rep_name, house_rep_party,
                    senatorial_district, federal_constituency
                FROM lga_representatives 
                WHERE LOWER(state) = :state AND LOWER(lga) = :lga
                LIMIT 1
            '''), {'state': user_state.lower(), 'lga': user_lga.lower()})
            
            row = result.fetchone()
            
            if row:
                reps = []
                
                if row[2]:  # governor_name
                    reps.append({
                        "position": "Governor",
                        "name": row[2],
                        "party": row[3] or "Unknown",
                        "area": row[0]  # state
                    })
                
                if row[4]:  # senator_name
                    reps.append({
                        "position": "Senator",
                        "name": row[4],
                        "party": row[5] or "Unknown",
                        "area": row[8]  # senatorial_district
                    })
                
                if row[6]:  # house_rep_name
                    reps.append({
                        "position": "House of Representatives",
                        "name": row[6],
                        "party": row[7] or "Unknown",
                        "area": row[9]  # federal_constituency
                    })
                
                return reps
        
        return []
        
    except Exception as e:
        logger.error(f"Rep lookup error: {e}")
        return []


async def _search_web(query: str, limit: int = 3) -> List[Dict]:
    """Search web for news/current events."""
    logger.info(f"Starting web search for: {query}")
    
    try:
        from app.services.realtime import fetch_web_search, fetch_rss_news
        
        # Try web search (fetch_web_search already adds "Nigeria")
        logger.info(f"Calling fetch_web_search with query: {query}")
        web_results = fetch_web_search(query, limit=limit)
        logger.info(f"Web search returned {len(web_results)} results")
        
        # Also try RSS for Nigerian news
        logger.info(f"Calling fetch_rss_news with topic: {query}")
        rss_results = fetch_rss_news(topic=query, limit=limit)
        logger.info(f"RSS search returned {len(rss_results)} results")
        
        # Combine and deduplicate
        seen_titles = set()
        combined = []
        
        for r in web_results + rss_results:
            title = r.get('title', '')[:50]
            if title not in seen_titles:
                seen_titles.add(title)
                combined.append(r)
        
        logger.info(f"Total combined results: {len(combined)}")
        return combined[:limit]
        
    except Exception as e:
        logger.error(f"Web search error: {e}", exc_info=True)
        return []


async def _search_rag(query: str, limit: int = 3) -> str:
    """Search RAG documents for relevant context."""
    try:
        from app.services.rag import RAGService
        from app.database import get_db

        # Get database session (required by RAGService)
        db = next(get_db())
        rag = RAGService(db)

        # Use the correct method: retrieve() returns (context_str, sources_list)
        context, sources = rag.retrieve(query, top_k=limit)

        # Return the formatted context if we got results
        if context and not context.startswith("NO"):
            return context

        return ""

    except Exception as e:
        logger.error(f"RAG search error: {e}")
        return ""


async def _search_knowledge_graph(query: str, limit: int = 5) -> Optional[Dict]:
    """Search Nigeria knowledge graph for historical, political, economic data."""
    try:
        from app.services.nigeria_knowledge.query_engine import get_query_engine

        engine = get_query_engine()

        # Check if engine loaded successfully
        if not engine.loaded:
            logger.warning("Knowledge graph not loaded")
            return None

        # Query the knowledge graph
        result = engine.query_natural_language(query)

        if result.get("results"):
            return {
                "results": result.get("results", [])[:limit],
                "context": result.get("context", ""),
                "query_type": result.get("query_type", "general"),
                "sources": result.get("sources", ["knowledge_graph"])
            }

        return None

    except Exception as e:
        logger.error(f"Knowledge graph search error: {e}")
        return None


def format_retrieval_for_context(result: RetrievalResult) -> str:
    """Format retrieval results as context for Claude response generation."""
    parts = []
    
    if result.politician:
        p = result.politician
        parts.append(f"""POLITICIAN INFORMATION:
Name: {p.get('name')}
Position: {p.get('position')}
Party: {p.get('party', 'Unknown')}
State: {p.get('state', 'Federal')}
Bio: {p.get('bio', 'No biography available.')}""")
    
    if result.representatives:
        reps_text = "USER'S REPRESENTATIVES:\n"
        for rep in result.representatives:
            reps_text += f"• {rep['position']}: {rep['name']} ({rep['party']}) - {rep.get('area', '')}\n"
        parts.append(reps_text)
    
    if result.web_results:
        news_text = "RECENT NEWS:\n"
        for news in result.web_results[:3]:
            news_text += f"• {news.get('title', 'No title')}\n  {news.get('summary', '')[:200]}\n"
        parts.append(news_text)
    
    if result.rag_context:
        parts.append(f"BACKGROUND INFORMATION:\n{result.rag_context}")

    if result.knowledge_graph_context:
        parts.append(f"NIGERIA KNOWLEDGE BASE:\n{result.knowledge_graph_context}")
    elif result.knowledge_graph_results:
        # Format knowledge graph results if no pre-formatted context
        kg_text = "NIGERIA KNOWLEDGE BASE:\n"
        for item in result.knowledge_graph_results[:5]:
            name = item.get("name", "")
            item_type = item.get("type", "").replace("_", " ").title()
            if name:
                kg_text += f"• {name}"
                if item_type:
                    kg_text += f" [{item_type}]"
                description = item.get("description", item.get("content", ""))
                if description:
                    kg_text += f"\n  {description[:200]}..."
                kg_text += "\n"
        parts.append(kg_text)

    return "\n\n---\n\n".join(parts) if parts else "No relevant information found."
