"""
Election 2027 Analytics API
============================

REST API endpoints for:
1. Poll results and trends
2. Candidate analytics (sentiment, mentions)
3. Regional breakdowns
4. Trending topics
5. Exportable data for infographics

These endpoints power the public-facing analytics dashboard
and provide data for infographic generation.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/election", tags=["Election Analytics"])


# === RESPONSE MODELS ===

class CandidateAnalytics(BaseModel):
    """Analytics for a single candidate."""
    id: str
    name: str
    party: str
    position: str
    sentiment_score: float
    sentiment_label: str  # positive, negative, neutral
    mention_count_7d: int
    mention_count_30d: int
    trending: bool
    poll_average: Optional[float] = None


class PollResultSummary(BaseModel):
    """Summary of poll results."""
    poll_id: str
    title: str
    total_responses: int
    results: Dict[str, float]  # option_id -> percentage
    leading: str
    leading_percentage: float
    last_updated: datetime


class RegionalBreakdown(BaseModel):
    """Regional breakdown of poll results."""
    region: str
    results: Dict[str, float]
    sample_size: int


class TrendingTopic(BaseModel):
    """A trending political topic."""
    topic: str
    category: str
    mention_count: int
    sentiment: str
    related_entities: List[str]
    sample_headlines: List[str]


class DashboardSummary(BaseModel):
    """Summary data for the main dashboard."""
    total_poll_responses: int
    active_polls: int
    candidates_tracked: int
    trending_topics: List[str]
    top_candidate: str
    latest_poll_update: datetime


# === ENDPOINTS ===

@router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard_summary():
    """
    Get summary data for the main analytics dashboard.

    Returns:
        High-level metrics for the election tracking system.
    """
    from app.services.election_2027.polling_system import get_polling_system
    from app.services.election_2027.candidate_tracker import get_candidate_tracker
    from app.services.content_context_engine import get_content_engine

    ps = get_polling_system()
    tracker = get_candidate_tracker()
    engine = get_content_engine()

    # Calculate totals
    total_responses = sum(len([r for r in ps.responses.values() if r["poll_id"] == poll.id])
                          for poll in ps.get_active_polls())

    active_polls = len(ps.get_active_polls())
    candidates_tracked = len(tracker.candidates)

    # Get trending topics
    trending = engine.get_trending_today()
    trending_names = [t["name"] for t in trending[:5]]

    # Find top candidate by sentiment
    top_candidate = max(
        tracker.candidates.values(),
        key=lambda c: c.sentiment_score
    )

    return DashboardSummary(
        total_poll_responses=total_responses,
        active_polls=active_polls,
        candidates_tracked=candidates_tracked,
        trending_topics=trending_names,
        top_candidate=top_candidate.name,
        latest_poll_update=datetime.now()
    )


@router.get("/polls", response_model=List[PollResultSummary])
async def get_poll_results(
    poll_type: Optional[str] = Query(None, description="Filter by poll type: voting_intention, approval, issue"),
    position: Optional[str] = Query(None, description="Filter by position: president, governor"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get poll results with optional filters.

    Args:
        poll_type: Filter by type of poll
        position: Filter by position being polled
        limit: Maximum number of polls to return

    Returns:
        List of poll results with percentages.
    """
    from app.services.election_2027.polling_system import get_polling_system

    ps = get_polling_system()
    polls = ps.get_active_polls()

    # Apply filters
    if poll_type:
        polls = [p for p in polls if p.poll_type == poll_type]
    if position:
        polls = [p for p in polls if p.position == position]

    results = []
    for poll in polls[:limit]:
        poll_result = ps.compute_results(poll.id)
        if poll_result:
            # Find leading option
            leading_id = max(poll_result.results, key=poll_result.results.get)
            leading_pct = poll_result.results[leading_id]
            leading_name = next(
                (o.text for o in poll.options if o.id == leading_id),
                leading_id
            )

            results.append(PollResultSummary(
                poll_id=poll.id,
                title=poll.title,
                total_responses=poll_result.total_responses,
                results=poll_result.results,
                leading=leading_name,
                leading_percentage=leading_pct,
                last_updated=poll_result.last_updated
            ))

    return results


@router.get("/polls/{poll_id}")
async def get_poll_detail(poll_id: str):
    """
    Get detailed results for a specific poll.

    Args:
        poll_id: The poll ID

    Returns:
        Detailed poll results including regional breakdown.
    """
    from app.services.election_2027.polling_system import get_polling_system

    ps = get_polling_system()
    poll = ps.get_poll(poll_id)

    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    result = ps.compute_results(poll_id)

    return {
        "poll": {
            "id": poll.id,
            "title": poll.title,
            "question": poll.question,
            "poll_type": poll.poll_type,
            "options": [{"id": o.id, "text": o.text, "emoji": o.emoji} for o in poll.options],
            "target_level": poll.target_level,
            "is_active": poll.is_active
        },
        "results": {
            "total_responses": result.total_responses if result else 0,
            "percentages": result.results if result else {},
            "by_state": result.results_by_state if result else {}
        },
        "formatted": ps.format_results_for_whatsapp(poll_id)
    }


@router.get("/polls/{poll_id}/regional")
async def get_poll_regional_breakdown(poll_id: str):
    """
    Get regional breakdown of poll results.

    Args:
        poll_id: The poll ID

    Returns:
        Results broken down by Nigerian geopolitical zones.
    """
    from app.services.election_2027.polling_system import get_polling_system

    ps = get_polling_system()
    result = ps.compute_results(poll_id)

    if not result:
        raise HTTPException(status_code=404, detail="Poll results not found")

    # Map states to geopolitical zones
    ZONES = {
        "North-West": ["Kaduna", "Kano", "Katsina", "Kebbi", "Sokoto", "Zamfara", "Jigawa"],
        "North-East": ["Adamawa", "Bauchi", "Borno", "Gombe", "Taraba", "Yobe"],
        "North-Central": ["Benue", "Kogi", "Kwara", "Nasarawa", "Niger", "Plateau", "FCT"],
        "South-West": ["Ekiti", "Lagos", "Ogun", "Ondo", "Osun", "Oyo"],
        "South-East": ["Abia", "Anambra", "Ebonyi", "Enugu", "Imo"],
        "South-South": ["Akwa Ibom", "Bayelsa", "Cross River", "Delta", "Edo", "Rivers"]
    }

    # Aggregate by zone
    zone_results = {}
    for zone, states in ZONES.items():
        zone_data = {}
        sample_size = 0
        for state in states:
            if state in result.results_by_state:
                state_data = result.results_by_state[state]
                for opt_id, pct in state_data.items():
                    zone_data[opt_id] = zone_data.get(opt_id, 0) + pct
                sample_size += 1

        if sample_size > 0:
            # Average the percentages
            zone_results[zone] = {
                "results": {k: round(v / sample_size, 1) for k, v in zone_data.items()},
                "sample_size": sample_size
            }

    return {
        "poll_id": poll_id,
        "zones": zone_results,
        "states": result.results_by_state
    }


@router.get("/candidates", response_model=List[CandidateAnalytics])
async def get_candidate_analytics(
    position: Optional[str] = Query(None, description="Filter by position"),
    party: Optional[str] = Query(None, description="Filter by party"),
    state: Optional[str] = Query(None, description="Filter by state (for governors)"),
    sort_by: str = Query("sentiment", description="Sort by: sentiment, mentions, name"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get analytics for candidates.

    Args:
        position: Filter by position (president, governor, senator)
        party: Filter by party (APC, PDP, LP, NNPP)
        state: Filter by state
        sort_by: Sort field
        limit: Maximum results

    Returns:
        List of candidates with analytics data.
    """
    from app.services.election_2027.candidate_tracker import get_candidate_tracker

    tracker = get_candidate_tracker()
    candidates = list(tracker.candidates.values())

    # Apply filters
    if position:
        candidates = [c for c in candidates if c.position_sought == position]
    if party:
        candidates = [c for c in candidates if c.party.upper() == party.upper()]
    if state:
        candidates = [c for c in candidates if c.state and c.state.lower() == state.lower()]

    # Sort
    if sort_by == "sentiment":
        candidates.sort(key=lambda c: c.sentiment_score, reverse=True)
    elif sort_by == "mentions":
        candidates.sort(key=lambda c: c.mention_count_7d, reverse=True)
    elif sort_by == "name":
        candidates.sort(key=lambda c: c.name)

    # Convert to response model
    results = []
    for c in candidates[:limit]:
        sentiment_label = "positive" if c.sentiment_score > 0.1 else "negative" if c.sentiment_score < -0.1 else "neutral"
        results.append(CandidateAnalytics(
            id=c.id,
            name=c.name,
            party=c.party,
            position=c.position_sought,
            sentiment_score=c.sentiment_score,
            sentiment_label=sentiment_label,
            mention_count_7d=c.mention_count_7d,
            mention_count_30d=c.mention_count_7d * 4,  # Placeholder
            trending=c.trending,
            poll_average=None  # Would calculate from polls
        ))

    return results


@router.get("/candidates/{candidate_id}")
async def get_candidate_detail(candidate_id: str):
    """
    Get detailed analytics for a specific candidate.

    Args:
        candidate_id: The candidate ID/slug

    Returns:
        Comprehensive candidate profile with analytics.
    """
    from app.services.election_2027.candidate_tracker import get_candidate

    candidate = get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "profile": {
            "id": candidate.id,
            "name": candidate.name,
            "party": candidate.party,
            "party_full": candidate.party_full,
            "position_sought": candidate.position_sought,
            "state": candidate.state,
            "bio": candidate.bio_short,
            "age": candidate.age,
            "state_of_origin": candidate.state_of_origin,
            "is_incumbent": candidate.is_incumbent,
            "campaign_slogan": candidate.campaign_slogan,
            "twitter": candidate.twitter
        },
        "politics": {
            "previous_positions": candidate.previous_positions,
            "key_policies": candidate.key_policies
        },
        "analytics": {
            "sentiment_score": candidate.sentiment_score,
            "sentiment_trend": "up" if candidate.sentiment_score > 0 else "down",
            "mention_count_7d": candidate.mention_count_7d,
            "trending": candidate.trending,
            "latest_news": candidate.latest_news[:5]
        }
    }


@router.get("/trending", response_model=List[TrendingTopic])
async def get_trending_topics(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get trending political topics.

    Args:
        category: Filter by category (economy, security, election, etc.)
        limit: Maximum topics to return

    Returns:
        List of trending topics with metadata.
    """
    from app.services.content_context_engine import get_content_engine

    engine = get_content_engine()
    trending = engine.get_trending_today()

    # Apply category filter
    if category:
        trending = [t for t in trending if t.get("category", "").lower() == category.lower()]

    results = []
    for t in trending[:limit]:
        results.append(TrendingTopic(
            topic=t.get("name", "Unknown"),
            category=t.get("category", "general"),
            mention_count=0,  # Would come from news analysis
            sentiment=t.get("sentiment", "neutral"),
            related_entities=[],
            sample_headlines=[]
        ))

    return results


@router.get("/export/infographic")
async def export_for_infographic(
    data_type: str = Query(..., description="Data type: poll_results, candidate_comparison, trending"),
    poll_id: Optional[str] = Query(None),
    candidate_ids: Optional[str] = Query(None, description="Comma-separated candidate IDs")
):
    """
    Export data formatted for infographic generation.

    Args:
        data_type: Type of data to export
        poll_id: Poll ID (for poll_results)
        candidate_ids: Candidate IDs (for comparison)

    Returns:
        Data formatted for infographic tools (Canva, Datawrapper, etc.)
    """
    from app.services.election_2027.polling_system import get_polling_system
    from app.services.election_2027.candidate_tracker import get_candidate_tracker

    if data_type == "poll_results":
        if not poll_id:
            raise HTTPException(status_code=400, detail="poll_id required for poll_results")

        ps = get_polling_system()
        poll = ps.get_poll(poll_id)
        result = ps.compute_results(poll_id)

        if not poll or not result:
            raise HTTPException(status_code=404, detail="Poll not found")

        # Format for charts
        return {
            "type": "pie_chart",
            "title": poll.title,
            "subtitle": f"{result.total_responses:,} responses",
            "data": [
                {
                    "label": next((o.text for o in poll.options if o.id == opt_id), opt_id),
                    "value": pct,
                    "color": _get_party_color(opt_id)
                }
                for opt_id, pct in sorted(result.results.items(), key=lambda x: x[1], reverse=True)
            ],
            "source": "Decide9ja Poll",
            "date": datetime.now().strftime("%B %d, %Y")
        }

    elif data_type == "candidate_comparison":
        if not candidate_ids:
            raise HTTPException(status_code=400, detail="candidate_ids required for comparison")

        ids = [c.strip() for c in candidate_ids.split(",")]
        tracker = get_candidate_tracker()

        candidates = []
        for cid in ids:
            c = tracker.get_candidate(cid)
            if c:
                candidates.append({
                    "name": c.name,
                    "party": c.party,
                    "sentiment": c.sentiment_score,
                    "mentions": c.mention_count_7d,
                    "color": _get_party_color(c.party)
                })

        return {
            "type": "bar_chart",
            "title": "Candidate Comparison",
            "metrics": ["sentiment", "mentions"],
            "data": candidates,
            "source": "Decide9ja Analytics",
            "date": datetime.now().strftime("%B %d, %Y")
        }

    elif data_type == "trending":
        from app.services.content_context_engine import get_content_engine
        engine = get_content_engine()
        trending = engine.get_trending_today()

        return {
            "type": "list",
            "title": "Trending in Nigerian Politics",
            "data": [{"rank": i + 1, "topic": t["name"]} for i, t in enumerate(trending[:10])],
            "source": "Decide9ja",
            "date": datetime.now().strftime("%B %d, %Y")
        }

    raise HTTPException(status_code=400, detail="Invalid data_type")


def _get_party_color(party_or_id: str) -> str:
    """Get color for party visualization."""
    colors = {
        "APC": "#00A86B",  # Green
        "PDP": "#DC143C",  # Red
        "LP": "#FFD700",   # Yellow/Gold
        "NNPP": "#4169E1", # Blue
        "tinubu": "#00A86B",
        "atiku": "#DC143C",
        "obi": "#FFD700",
        "kwankwaso": "#4169E1",
    }
    return colors.get(party_or_id.upper() if isinstance(party_or_id, str) else party_or_id, "#808080")


# === INCLUDE IN MAIN APP ===
# Add to main.py: app.include_router(election_analytics.router)
