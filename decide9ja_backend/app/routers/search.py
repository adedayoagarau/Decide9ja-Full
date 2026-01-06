"""
Search & Discovery API Router for Decide9ja.

Provides endpoints for:
- Smart Suggestions
- Trending Queries
- Topic Pages
- Advanced Search with Filters
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/search", tags=["search"])


# =============================================================================
# Request/Response Models
# =============================================================================

class SearchRequest(BaseModel):
    """Advanced search request."""
    query: str = Field(..., min_length=2)
    states: Optional[List[str]] = None
    parties: Optional[List[str]] = None
    types: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)


# =============================================================================
# Suggestions Endpoints
# =============================================================================

@router.get("/suggestions")
async def get_suggestions(
    q: str = Query(..., min_length=1, description="Partial query"),
    limit: int = Query(10, ge=1, le=20)
) -> Dict[str, Any]:
    """
    Get smart search suggestions based on partial query.

    Returns suggestions for:
    - Politicians matching the query
    - Issues matching the query
    - Topic pages matching the query
    - Previous search queries
    """
    from app.services.search_discovery import SearchDiscoveryService

    service = SearchDiscoveryService()
    suggestions = service.get_smart_suggestions(q, limit=limit)

    return {
        "query": q,
        "suggestions": [
            {
                "text": s.text,
                "type": s.type,
                "relevance": s.relevance,
                "metadata": s.metadata
            }
            for s in suggestions
        ]
    }


# =============================================================================
# Trending Endpoints
# =============================================================================

@router.get("/trending")
async def get_trending(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get trending search queries.

    Shows what people are currently searching for.
    """
    from app.services.search_discovery import SearchDiscoveryService

    service = SearchDiscoveryService()
    trending = service.get_trending_queries(category=category, limit=limit)

    return {
        "trending": [
            {
                "query": t.query,
                "count": t.count,
                "trend": t.trend,
                "category": t.category,
                "related_entities": t.related_entities
            }
            for t in trending
        ],
        "categories": ["politicians", "elections", "economy", "security", "infrastructure", "general"]
    }


# =============================================================================
# Topic Pages Endpoints
# =============================================================================

@router.get("/topics")
async def list_topics() -> Dict[str, Any]:
    """
    Get list of all available topic pages.
    """
    from app.services.search_discovery import SearchDiscoveryService

    service = SearchDiscoveryService()
    topics = service.get_all_topic_pages()

    # Group by category
    by_category = {}
    for topic in topics:
        cat = topic["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(topic)

    return {
        "topics": topics,
        "by_category": by_category
    }


@router.get("/topics/{slug}")
async def get_topic(slug: str) -> Dict[str, Any]:
    """
    Get a specific topic page with latest data.

    Topic pages provide curated information on major topics like
    fuel subsidy, security situation, naira exchange rate, etc.
    """
    from app.services.search_discovery import SearchDiscoveryService
    from dataclasses import asdict

    service = SearchDiscoveryService()
    topic = service.get_topic_page(slug)

    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic not found: {slug}")

    return asdict(topic)


# =============================================================================
# Search Endpoints
# =============================================================================

@router.get("")
async def search_get(
    q: str = Query(..., min_length=2, description="Search query"),
    states: Optional[str] = Query(None, description="Comma-separated states"),
    parties: Optional[str] = Query(None, description="Comma-separated parties"),
    types: Optional[str] = Query(None, description="Comma-separated types"),
    domains: Optional[str] = Query(None, description="Comma-separated domains"),
    date_from: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Search across politicians, issues, and news.

    Supports filtering by state, party, type, domain, and date range.
    """
    from app.services.search_discovery import SearchDiscoveryService, SearchFilters

    service = SearchDiscoveryService()

    # Parse filters
    filters = SearchFilters(
        states=states.split(",") if states else None,
        parties=parties.split(",") if parties else None,
        types=types.split(",") if types else None,
        domains=domains.split(",") if domains else None,
        date_from=datetime.fromisoformat(date_from) if date_from else None,
        date_to=datetime.fromisoformat(date_to) if date_to else None
    )

    results = service.search(q, filters, limit)
    return results


@router.post("")
async def search_post(request: SearchRequest) -> Dict[str, Any]:
    """
    Advanced search with filters (POST version).

    Allows more complex filter combinations.
    """
    from app.services.search_discovery import SearchDiscoveryService, SearchFilters

    service = SearchDiscoveryService()

    filters = SearchFilters(
        states=request.states,
        parties=request.parties,
        types=request.types,
        domains=request.domains,
        date_from=datetime.fromisoformat(request.date_from) if request.date_from else None,
        date_to=datetime.fromisoformat(request.date_to) if request.date_to else None
    )

    results = service.search(request.query, filters, request.limit)
    return results


# =============================================================================
# Filter Options Endpoint
# =============================================================================

@router.get("/filters")
async def get_filter_options() -> Dict[str, Any]:
    """
    Get available filter options for search.

    Returns lists of:
    - Parties
    - States
    - Domains
    - Types
    """
    from app.services.search_discovery import SearchDiscoveryService

    service = SearchDiscoveryService()
    options = service.get_filter_options()

    return {"filters": options}
