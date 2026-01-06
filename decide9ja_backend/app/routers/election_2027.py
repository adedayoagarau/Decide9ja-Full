"""
Election 2027 Enhanced Features API Router for Decide9ja.

Provides endpoints for:
- Candidate Matcher (quiz-based candidate matching)
- Debate Tracker (upcoming/past debates, summaries)
- Poll Aggregator (weighted polling averages)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/election/2027", tags=["election-2027"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CandidateMatchRequest(BaseModel):
    """Request to match user with candidates."""
    stances: Dict[str, str] = Field(
        ...,
        description="Dict of issue_id -> position_id from quiz"
    )
    position: str = Field(
        "president",
        description="Position to match for: president, governor"
    )


class AddDebateSummaryRequest(BaseModel):
    """Request to add summary to a debate."""
    summary: str = Field(..., description="Debate summary text")
    key_moments: Optional[List[Dict]] = Field(None, description="Key moments with timestamps")
    fact_checks: Optional[List[Dict]] = Field(None, description="Fact check results")


class AddPollRequest(BaseModel):
    """Request to add an external poll."""
    source_id: str = Field(..., description="Polling source ID")
    title: str = Field(..., description="Poll title")
    position: str = Field(..., description="Position: president, governor")
    state: Optional[str] = Field(None, description="State for state-level polls")
    date_conducted: str = Field(..., description="Date poll was conducted (ISO format)")
    sample_size: int = Field(..., gt=0)
    margin_of_error: float = Field(3.0, ge=0)
    results: Dict[str, float] = Field(..., description="candidate_slug -> percentage")
    methodology: Optional[str] = Field(None)
    url: Optional[str] = Field(None)


# =============================================================================
# Candidate Matcher Endpoints
# =============================================================================

@router.get("/matcher/quiz")
async def get_matcher_quiz() -> Dict[str, Any]:
    """
    Get the candidate matching quiz questions.

    Returns list of issues with position options for user to answer.
    """
    from app.services.election_2027.enhanced_features import get_candidate_matcher

    matcher = get_candidate_matcher()
    questions = matcher.get_quiz_questions()

    return {
        "title": "Find Your Candidate Match",
        "description": "Answer these questions to see which 2027 candidates align with your views",
        "questions": questions,
        "total_questions": len(questions)
    }


@router.post("/matcher/match")
async def match_candidates(request: CandidateMatchRequest) -> Dict[str, Any]:
    """
    Match user with candidates based on their issue stances.

    Returns ranked list of candidates with match percentages.
    """
    from app.services.election_2027.enhanced_features import get_candidate_matcher

    matcher = get_candidate_matcher()
    matches = matcher.match_user(request.stances, request.position)

    return {
        "position": request.position,
        "matches": [
            {
                "rank": i + 1,
                "slug": m.slug,
                "name": m.name,
                "party": m.party,
                "match_percentage": m.match_percentage,
                "matching_issues": len(m.matching_issues),
                "differing_issues": len(m.differing_issues),
                "key_agreements": m.key_agreements,
                "key_disagreements": m.key_disagreements
            }
            for i, m in enumerate(matches)
        ],
        "total_candidates": len(matches),
        "issues_evaluated": len(request.stances)
    }


@router.get("/matcher/candidate/{slug}/stances")
async def get_candidate_stances(slug: str) -> Dict[str, Any]:
    """
    Get a specific candidate's stance on all issues.
    """
    from app.services.election_2027.enhanced_features import get_candidate_matcher

    matcher = get_candidate_matcher()
    card = matcher.get_candidate_stance_card(slug)

    if not card["stances"]:
        raise HTTPException(
            status_code=404,
            detail=f"No stance information for candidate: {slug}"
        )

    return card


# =============================================================================
# Debate Tracker Endpoints
# =============================================================================

@router.get("/debates/upcoming")
async def get_upcoming_debates(
    position: Optional[str] = Query(None, description="Filter by position"),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get upcoming election debates.
    """
    from app.services.election_2027.enhanced_features import get_debate_tracker

    tracker = get_debate_tracker()
    debates = tracker.get_upcoming_debates(position, limit)

    return {
        "upcoming": debates,
        "total": len(debates)
    }


@router.get("/debates/past")
async def get_past_debates(
    position: Optional[str] = Query(None, description="Filter by position"),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get past debates with summaries and analysis.
    """
    from app.services.election_2027.enhanced_features import get_debate_tracker

    tracker = get_debate_tracker()
    debates = tracker.get_past_debates(position, limit)

    return {
        "past": debates,
        "total": len(debates)
    }


@router.get("/debates/calendar")
async def get_debate_calendar(
    year: int = Query(2027, ge=2024, le=2030)
) -> Dict[str, Any]:
    """
    Get debate calendar organized by month.
    """
    from app.services.election_2027.enhanced_features import get_debate_tracker

    tracker = get_debate_tracker()
    calendar = tracker.get_debate_calendar(year)

    return {
        "year": year,
        "calendar": calendar
    }


@router.get("/debates/{debate_id}")
async def get_debate_detail(debate_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific debate.

    Includes summary, key moments, and fact checks if available.
    """
    from app.services.election_2027.enhanced_features import get_debate_tracker

    tracker = get_debate_tracker()
    debate = tracker.get_debate(debate_id)

    if not debate:
        raise HTTPException(status_code=404, detail=f"Debate not found: {debate_id}")

    return debate


@router.post("/debates/{debate_id}/summary")
async def add_debate_summary(
    debate_id: str,
    request: AddDebateSummaryRequest
) -> Dict[str, Any]:
    """
    Add summary and analysis to a completed debate (admin only).
    """
    from app.services.election_2027.enhanced_features import get_debate_tracker

    tracker = get_debate_tracker()
    success = tracker.add_debate_summary(
        debate_id=debate_id,
        summary=request.summary,
        key_moments=request.key_moments,
        fact_checks=request.fact_checks
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Debate not found: {debate_id}")

    return {
        "success": True,
        "debate_id": debate_id,
        "message": "Summary added successfully"
    }


# =============================================================================
# Poll Aggregator Endpoints
# =============================================================================

@router.get("/polls/average")
async def get_polling_average(
    position: str = Query("president", description="Position: president, governor"),
    state: Optional[str] = Query(None, description="State for state-level polls"),
    days: int = Query(30, ge=7, le=180, description="Days to include")
) -> Dict[str, Any]:
    """
    Get weighted polling average from multiple sources.

    Weights are based on:
    - Recency (30%)
    - Sample size (20%)
    - Methodology quality (20%)
    - Source credibility (30%)
    """
    from app.services.election_2027.enhanced_features import get_poll_aggregator

    aggregator = get_poll_aggregator()
    result = aggregator.get_polling_average(position, state, days)

    return result


@router.get("/polls/trend/{candidate_slug}")
async def get_candidate_polling_trend(
    candidate_slug: str,
    position: str = Query("president"),
    days: int = Query(90, ge=30, le=365)
) -> Dict[str, Any]:
    """
    Get polling trend for a specific candidate over time.
    """
    from app.services.election_2027.enhanced_features import get_poll_aggregator

    aggregator = get_poll_aggregator()
    trend = aggregator.get_trend(candidate_slug, position, days)

    return {
        "candidate_slug": candidate_slug,
        "position": position,
        "period_days": days,
        "data_points": trend,
        "count": len(trend)
    }


@router.get("/polls/sources")
async def get_polling_sources() -> Dict[str, Any]:
    """
    Get information about polling sources and their credibility ratings.
    """
    from app.services.election_2027.enhanced_features import get_poll_aggregator

    aggregator = get_poll_aggregator()
    sources = aggregator.get_sources()

    return {
        "sources": sources,
        "methodology_ranking": [
            {"method": "face_to_face", "quality": "Highest", "score": 1.0},
            {"method": "mixed", "quality": "High", "score": 0.9},
            {"method": "telephone", "quality": "Medium", "score": 0.8},
            {"method": "online", "quality": "Lower", "score": 0.6}
        ]
    }


@router.post("/polls/add")
async def add_external_poll(request: AddPollRequest) -> Dict[str, Any]:
    """
    Add an external poll to the aggregator (admin only).
    """
    from app.services.election_2027.enhanced_features import get_poll_aggregator

    aggregator = get_poll_aggregator()

    try:
        poll_id = aggregator.add_poll(request.dict())
        return {
            "success": True,
            "poll_id": poll_id,
            "message": "Poll added to aggregator"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Combined Election Dashboard
# =============================================================================

@router.get("/dashboard")
async def get_election_dashboard() -> Dict[str, Any]:
    """
    Get combined election 2027 dashboard data.

    Includes polling averages, upcoming debates, and trending topics.
    """
    from app.services.election_2027.enhanced_features import (
        get_poll_aggregator,
        get_debate_tracker
    )

    aggregator = get_poll_aggregator()
    debate_tracker = get_debate_tracker()

    # Get polling average
    polling = aggregator.get_polling_average("president", None, 30)

    # Get upcoming debates
    debates = debate_tracker.get_upcoming_debates(limit=3)

    return {
        "polling_average": {
            "position": "president",
            "results": polling.get("results", [])[:5],
            "polls_included": polling.get("polls_included", 0),
            "margin_of_error": polling.get("average_margin_of_error")
        },
        "upcoming_debates": debates,
        "countdown": {
            "election_date": "2027-02-25",
            "days_remaining": (datetime(2027, 2, 25) - datetime.now()).days
        },
        "last_updated": datetime.now().isoformat()
    }
