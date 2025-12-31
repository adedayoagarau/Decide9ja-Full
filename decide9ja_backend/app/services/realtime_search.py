"""
Real-time web search for current events and news.
Uses existing web_search service with enhanced query handling.
"""
import os
import logging
import aiohttp
from typing import Optional, List

logger = logging.getLogger(__name__)

# Keywords that indicate need for real-time information
REALTIME_KEYWORDS = [
    "today", "yesterday", "this week", "latest", "recent",
    "current", "now", "2024", "2025", "news", "update",
    "just", "happening", "announced", "breaking",
    "this month", "last week"
]


def needs_web_search(query: str) -> bool:
    """Determine if query needs real-time web search."""
    query_lower = query.lower()
    return any(kw in query_lower for kw in REALTIME_KEYWORDS)


async def search_web(query: str, num_results: int = 3) -> Optional[str]:
    """
    Search the web for current information using DuckDuckGo.
    Falls back to existing web_search service.
    """
    try:
        from app.services.web_search import WebSearchService
        
        search_service = WebSearchService()
        results = await search_service.search(f"{query} Nigeria news")
        
        if results:
            formatted = ["*Recent information from the web:*"]
            for i, result in enumerate(results[:num_results], 1):
                title = result.get("title", "")
                snippet = result.get("snippet", "")[:200]
                formatted.append(f"{i}. {title}: {snippet}")
            
            await search_service.close()
            return "\n".join(formatted)
        
        await search_service.close()
        return None
        
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return None


def format_web_results(results: List[dict]) -> str:
    """Format web search results for inclusion in context."""
    if not results:
        return ""
    
    formatted = ["*Recent web information:*"]
    for i, result in enumerate(results[:3], 1):
        title = result.get("title", "Unknown")
        snippet = result.get("snippet", "")[:150]
        source = result.get("source", "")
        formatted.append(f"• {title}: {snippet}")
    
    return "\n".join(formatted)
