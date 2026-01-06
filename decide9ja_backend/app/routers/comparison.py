"""
Politician Comparison API Router for Decide9ja.

Provides endpoints for comparing politicians side-by-side:
- Basic profile information
- Party affiliations
- Committee memberships
- Issue stances
- News presence
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/compare", tags=["comparison"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CompareRequest(BaseModel):
    """Request to compare politicians."""
    slugs: List[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="List of politician slugs to compare (2-4)"
    )


class PoliticianSearchResult(BaseModel):
    """Search result for politician."""
    slug: str
    name: str
    party: Optional[str]
    position: Optional[str]
    state: Optional[str]


class SuggestedComparison(BaseModel):
    """Suggested comparison group."""
    title: str
    description: str
    slugs: List[str]
    category: str


# =============================================================================
# Endpoints
# =============================================================================

@router.get("")
async def compare_politicians(
    slugs: List[str] = Query(
        ...,
        min_length=2,
        max_length=4,
        description="Politician slugs to compare"
    )
) -> Dict[str, Any]:
    """
    Compare 2-4 politicians side-by-side.

    Example:
        GET /api/compare?slugs=bola-tinubu&slugs=peter-obi&slugs=atiku-abubakar

    Returns:
        - politicians: Profile data for each politician
        - issues: Issues associated with each politician
        - news_presence: News mention statistics
        - comparison_dimensions: Available comparison categories
        - party_colors: Color codes for each party
    """
    from app.services.politician_comparison import compare_politicians as do_compare

    try:
        result = do_compare(slugs)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate comparison: {str(e)}"
        )


@router.post("")
async def compare_politicians_post(request: CompareRequest) -> Dict[str, Any]:
    """
    Compare politicians (POST version for longer slug lists).

    Example:
        POST /api/compare
        {"slugs": ["bola-tinubu", "peter-obi", "atiku-abubakar"]}
    """
    from app.services.politician_comparison import compare_politicians as do_compare

    try:
        result = do_compare(request.slugs)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate comparison: {str(e)}"
        )


@router.get("/search")
async def search_for_comparison(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results")
) -> List[PoliticianSearchResult]:
    """
    Search for politicians to add to a comparison.

    Example:
        GET /api/compare/search?q=tinubu
    """
    from app.services.politician_comparison import search_politicians_for_comparison

    results = search_politicians_for_comparison(q, limit)
    return [PoliticianSearchResult(**r) for r in results]


@router.get("/suggestions")
async def get_suggestions() -> List[SuggestedComparison]:
    """
    Get suggested comparison groups.

    Returns pre-curated comparison suggestions like:
    - 2023 Presidential Candidates
    - Senate Leadership
    - South-West Governors
    """
    from app.services.politician_comparison import get_suggested_comparisons

    suggestions = get_suggested_comparisons()
    return [SuggestedComparison(**s) for s in suggestions]


@router.get("/politician/{slug}")
async def get_politician_profile(slug: str) -> Dict[str, Any]:
    """
    Get detailed comparison profile for a single politician.

    Useful for building comparison UI before committing to full comparison.
    """
    from app.services.politician_comparison import PoliticianComparisonService
    from dataclasses import asdict

    service = PoliticianComparisonService()
    profile = service.get_politician_profile(slug)

    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Politician not found: {slug}"
        )

    return asdict(profile)


@router.get("/dimensions")
async def get_comparison_dimensions() -> Dict[str, Any]:
    """
    Get available comparison dimensions with descriptions.

    Useful for explaining what each comparison category shows.
    """
    dimensions = {
        "basic_info": {
            "title": "Basic Information",
            "description": "Name, age, education, career background",
            "fields": ["name", "age", "education", "career_before_politics"]
        },
        "party": {
            "title": "Party Affiliation",
            "description": "Current party and party history",
            "fields": ["party", "party_full_name"]
        },
        "position": {
            "title": "Current Position",
            "description": "Current role, state, constituency",
            "fields": ["position", "state", "constituency", "term_start", "term_end"]
        },
        "committees": {
            "title": "Committee Memberships",
            "description": "Legislative committees they serve on",
            "fields": ["committee_memberships"]
        },
        "legislative_record": {
            "title": "Legislative Record",
            "description": "Bills sponsored, attendance rate",
            "fields": ["bills_sponsored", "attendance_rate"]
        },
        "scores": {
            "title": "Performance Scores",
            "description": "Promise fulfillment and transparency ratings",
            "fields": ["promise_score", "transparency_score"]
        },
        "issues": {
            "title": "Issue Involvement",
            "description": "Political issues they're associated with",
            "fields": ["issues"]
        },
        "news_presence": {
            "title": "News Presence",
            "description": "Media mentions and coverage analysis",
            "fields": ["total_mentions", "mentions_last_week", "top_topics"]
        }
    }

    return {
        "dimensions": dimensions,
        "timestamp": datetime.now().isoformat()
    }
