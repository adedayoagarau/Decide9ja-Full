"""
Catalog API Router — Newspaper Archive Search

Provides REST endpoints for searching the 80K+ newspaper archive catalog.
This is the single source of truth for all newspaper/press content in Decide9ja.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


class CatalogSearchResponse(BaseModel):
    """Response model for catalog search."""
    query: str
    total_matches: int
    results: List[Dict[str, Any]]
    search_time_ms: float


@router.get("/search")
async def search_catalog(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    year_from: Optional[int] = Query(None, description="Filter by start year"),
    year_to: Optional[int] = Query(None, description="Filter by end year"),
    source: Optional[str] = Query(None, description="Filter by newspaper source ID"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    entity: Optional[str] = Query(None, description="Filter by entity"),
) -> Dict[str, Any]:
    """
    Search the newspaper archive catalog (80K+ documents, 1941-2026).
    
    Uses FTS5 full-text search for fast, ranked results.
    """
    from app.services.catalog_search import get_catalog_service

    service = get_catalog_service()
    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Catalog database not available"
        )

    result = service.search(
        query=q,
        limit=limit,
        year_from=year_from,
        year_to=year_to,
        source_id=source,
        topic=topic,
        entity=entity,
    )

    return {
        "query": result.query,
        "total_matches": result.total_matches,
        "search_time_ms": round(result.search_time_ms, 1),
        "results": [
            {
                "id": a.id,
                "title": a.title,
                "snippet": a.snippet,
                "published_date": a.published_date,
                "source_type": a.source_type,
                "source_id": a.source_id,
                "topics": a.topics,
                "entities": a.entities,
                "relevance_rank": a.relevance_rank,
            }
            for a in result.articles
        ],
    }


@router.get("/facets")
async def get_catalog_facets(
    q: Optional[str] = Query(None, description="Filter facets by query"),
) -> Dict[str, Any]:
    """
    Get faceted counts for catalog search.
    Returns counts for topics, sources, and years.
    """
    from app.services.catalog_search import get_catalog_service

    service = get_catalog_service()
    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Catalog database not available"
        )

    return service.get_facets(query=q)


@router.get("/stats")
async def catalog_stats() -> Dict[str, Any]:
    """
    Get catalog database statistics.
    
    Returns document count, date range, topic/entity counts.
    """
    from app.services.catalog_search import get_catalog_service

    service = get_catalog_service()
    if not service.is_available:
        return {"available": False, "message": "Catalog database not connected"}

    return service.get_stats()


@router.get("/politician/{name}")
async def search_politician_articles(
    name: str,
    limit: int = Query(10, ge=1, le=50),
    year: Optional[int] = Query(None, description="Filter by year"),
) -> Dict[str, Any]:
    """
    Search catalog for articles about a specific politician.
    """
    from app.services.catalog_search import get_catalog_service

    service = get_catalog_service()
    if not service.is_available:
        raise HTTPException(status_code=503, detail="Catalog not available")

    result = service.search_by_politician(name, limit=limit, year=year)

    return {
        "politician": name,
        "total_matches": result.total_matches,
        "search_time_ms": round(result.search_time_ms, 1),
        "results": [a.to_dict() for a in result.articles],
    }
