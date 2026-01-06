"""
Bills & Voting Records API Router for Decide9ja.

Provides endpoints for:
- Browsing and searching bills
- Viewing bill details and voting history
- Politician voting records
- Voting statistics
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/bills", tags=["bills"])


# =============================================================================
# Request/Response Models
# =============================================================================

class BillCreateRequest(BaseModel):
    """Request to create a new bill."""
    title: str = Field(..., description="Full title of the bill")
    short_title: Optional[str] = Field(None, description="Short title for display")
    description: Optional[str] = Field(None, description="Bill description")
    bill_type: Optional[str] = Field(None, description="Type: executive, private_member, etc.")
    chamber: str = Field("house", description="Chamber: senate or house")
    sponsor_slug: Optional[str] = Field(None, description="Primary sponsor politician slug")
    sponsor_name: Optional[str] = Field(None, description="Primary sponsor name")
    category: Optional[str] = Field(None, description="Category: health, education, etc.")
    tags: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(None, description="Bill summary")
    full_text_url: Optional[str] = Field(None, description="URL to full bill text")


class BillStatusUpdateRequest(BaseModel):
    """Request to update bill status."""
    new_status: str = Field(..., description="New status")
    action_description: str = Field(..., description="Description of the action")
    ayes: Optional[int] = Field(None, description="Ayes count for vote results")
    nays: Optional[int] = Field(None, description="Nays count for vote results")
    abstentions: Optional[int] = Field(None, description="Abstentions count")


class VoteRecordRequest(BaseModel):
    """Request to record a vote."""
    politician_slug: str
    vote_cast: str = Field(..., description="Vote: aye, nay, abstain, absent")
    chamber: str
    bill_id: Optional[str] = None
    motion_title: Optional[str] = None
    vote_date: Optional[str] = None


class VotingSessionRequest(BaseModel):
    """Request to record a voting session."""
    chamber: str
    session_date: str
    bill_id: Optional[str] = None
    motion_title: Optional[str] = None
    vote_type: str = "motion"
    votes: List[VoteRecordRequest]


# =============================================================================
# Bill Endpoints
# =============================================================================

@router.get("")
async def list_bills(
    chamber: Optional[str] = Query(None, description="Filter by chamber: senate, house"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sponsor: Optional[str] = Query(None, description="Filter by sponsor slug"),
    search: Optional[str] = Query(None, description="Search term"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """
    List bills with optional filters.

    Examples:
        GET /api/bills
        GET /api/bills?chamber=senate&status=committee
        GET /api/bills?category=health&search=healthcare
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()
    result = service.get_bills(
        chamber=chamber,
        status=status,
        category=category,
        sponsor_slug=sponsor,
        search=search,
        limit=limit,
        offset=offset
    )

    return result


@router.get("/statistics")
async def get_bill_statistics() -> Dict[str, Any]:
    """
    Get overall bill statistics.

    Returns counts by status, chamber, and category.
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()
    return service.get_bill_statistics()


@router.get("/statuses")
async def get_bill_statuses() -> Dict[str, Any]:
    """
    Get valid bill statuses and their descriptions.
    """
    from app.services.voting_record_service import BILL_STATUS_ORDER, BILL_STATUS_DESCRIPTIONS

    return {
        "statuses": [
            {"status": s, "description": BILL_STATUS_DESCRIPTIONS.get(s, s)}
            for s in BILL_STATUS_ORDER
        ],
        "terminal_statuses": [
            {"status": "rejected", "description": BILL_STATUS_DESCRIPTIONS["rejected"]},
            {"status": "withdrawn", "description": BILL_STATUS_DESCRIPTIONS["withdrawn"]}
        ]
    }


@router.get("/{bill_id}")
async def get_bill(bill_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific bill.
    """
    from app.services.voting_record_service import VotingRecordService
    from dataclasses import asdict

    service = VotingRecordService()
    bill = service.get_bill(bill_id)

    if not bill:
        raise HTTPException(status_code=404, detail=f"Bill not found: {bill_id}")

    return asdict(bill)


@router.get("/{bill_id}/votes")
async def get_bill_votes(bill_id: str) -> Dict[str, Any]:
    """
    Get all votes cast on a specific bill.
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()

    # Verify bill exists
    bill = service.get_bill(bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail=f"Bill not found: {bill_id}")

    votes = service.get_bill_votes(bill_id)

    return {
        "bill_id": bill_id,
        "bill_title": bill.title,
        "votes": votes,
        "total": len(votes)
    }


@router.post("")
async def create_bill(request: BillCreateRequest) -> Dict[str, Any]:
    """
    Create a new bill record (admin only).
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()
    bill_id = service.create_bill(request.dict())

    if not bill_id:
        raise HTTPException(status_code=500, detail="Failed to create bill")

    return {
        "success": True,
        "bill_id": bill_id,
        "message": f"Bill created: {bill_id}"
    }


@router.put("/{bill_id}/status")
async def update_bill_status(bill_id: str, request: BillStatusUpdateRequest) -> Dict[str, Any]:
    """
    Update bill status (admin only).

    Adds an entry to the bill timeline.
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()

    vote_result = None
    if request.ayes is not None:
        vote_result = {
            "ayes": request.ayes,
            "nays": request.nays,
            "abstentions": request.abstentions
        }

    success = service.update_bill_status(
        bill_id=bill_id,
        new_status=request.new_status,
        action_description=request.action_description,
        vote_result=vote_result
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Bill not found: {bill_id}")

    return {
        "success": True,
        "bill_id": bill_id,
        "new_status": request.new_status
    }


# =============================================================================
# Voting Record Endpoints
# =============================================================================

@router.get("/voting/statistics")
async def get_voting_statistics() -> Dict[str, Any]:
    """
    Get overall voting statistics.
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()
    return service.get_voting_statistics()


@router.get("/voting/sessions")
async def get_voting_sessions(
    chamber: Optional[str] = Query(None, description="Filter by chamber"),
    bill_id: Optional[str] = Query(None, description="Filter by bill"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get voting sessions with filters.
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    sessions = service.get_voting_sessions(
        chamber=chamber,
        bill_id=bill_id,
        start_date=start,
        end_date=end,
        limit=limit
    )

    return {
        "sessions": sessions,
        "total": len(sessions)
    }


@router.post("/voting/sessions")
async def record_voting_session(request: VotingSessionRequest) -> Dict[str, Any]:
    """
    Record a complete voting session with individual votes (admin only).
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()

    session_date = datetime.fromisoformat(request.session_date)
    votes = [
        {
            "politician_slug": v.politician_slug,
            "vote_cast": v.vote_cast,
            "party": None  # Will be looked up
        }
        for v in request.votes
    ]

    session_id = service.record_voting_session(
        chamber=request.chamber,
        session_date=session_date,
        bill_id=request.bill_id,
        motion_title=request.motion_title,
        vote_type=request.vote_type,
        votes=votes
    )

    if not session_id:
        raise HTTPException(status_code=500, detail="Failed to record voting session")

    return {
        "success": True,
        "session_id": session_id
    }


# =============================================================================
# Politician Voting Record Endpoints
# =============================================================================

@router.get("/politician/{slug}/record")
async def get_politician_voting_record(slug: str) -> Dict[str, Any]:
    """
    Get comprehensive voting record for a politician.

    Includes:
    - Overall statistics (attendance, participation, party loyalty)
    - Vote breakdown (ayes, nays, abstentions, absent)
    - Bills sponsored
    - Recent votes
    - Notable votes
    """
    from app.services.voting_record_service import VotingRecordService
    from dataclasses import asdict

    service = VotingRecordService()
    record = service.get_politician_voting_record(slug)

    if not record:
        raise HTTPException(status_code=404, detail=f"Politician not found: {slug}")

    return asdict(record)


@router.get("/politician/{slug}/bills")
async def get_politician_bills(
    slug: str,
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get bills sponsored by a politician.
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()
    result = service.get_bills(sponsor_slug=slug, limit=limit)

    return {
        "politician_slug": slug,
        "bills": result.get("bills", []),
        "total": result.get("total", 0)
    }


@router.post("/politician/{slug}/recalculate")
async def recalculate_voting_record(slug: str) -> Dict[str, Any]:
    """
    Recalculate aggregate voting statistics for a politician (admin only).
    """
    from app.services.voting_record_service import VotingRecordService

    service = VotingRecordService()
    success = service.recalculate_voting_record(slug)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"No voting records found for: {slug}"
        )

    return {
        "success": True,
        "politician_slug": slug,
        "message": "Voting record recalculated"
    }
