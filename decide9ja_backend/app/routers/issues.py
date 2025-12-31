"""
Issues API Router
Public and admin endpoints for issue tracking.
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.issue_pipeline import (
    list_issues,
    get_issue_with_events,
    get_issues_for_politician,
)
from app.database import SessionLocal, Issue, Politician

router = APIRouter(prefix="/api/issues", tags=["issues"])


class IssueResponse(BaseModel):
    issue_id: str
    title: str
    domain: str
    severity: str
    status: str
    location: Optional[str] = None
    event_count: Optional[int] = 0
    confidence: Optional[float] = 0.5
    verified: bool = False
    last_updated: Optional[str] = None


class IssueDetailResponse(BaseModel):
    issue_id: str
    title: str
    domain: str
    severity: str
    status: str
    location: Optional[str] = None
    states: List[str] = []
    summary: Optional[str] = None
    confidence: Optional[float] = 0.5
    verified: bool = False
    event_count: Optional[int] = 0
    first_reported: Optional[str] = None
    last_updated: Optional[str] = None
    events: List[dict] = []
    politicians: List[dict] = []


@router.get("", response_model=List[IssueResponse])
async def get_issues(
    domain: Optional[str] = Query(None, description="Filter by domain (power, roads, security, etc.)"),
    state: Optional[str] = Query(None, description="Filter by affected state"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, moderate, severe)"),
    status: str = Query("active", description="Filter by status (active, resolved, archived)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List issues with optional filters.
    
    Returns active issues by default, sorted by last update.
    """
    issues = list_issues(
        domain=domain,
        state=state,
        severity=severity,
        status=status,
        limit=limit,
        offset=offset,
    )
    return issues


@router.get("/domains")
async def get_issue_domains():
    """Get list of issue domains with counts."""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        domain_counts = db.query(
            Issue.domain,
            func.count(Issue.id).label("count")
        ).filter(
            Issue.status == "active"
        ).group_by(Issue.domain).all()
        
        return {
            "domains": [
                {"domain": d[0], "count": d[1]}
                for d in domain_counts
            ]
        }
    finally:
        db.close()


@router.get("/trending", response_model=List[IssueResponse])
async def get_trending_issues(limit: int = Query(5, ge=1, le=20)):
    """
    Get trending issues - most recently updated severe/moderate issues.
    """
    issues = list_issues(
        status="active",
        limit=limit,
    )
    
    # Sort by severity then update time
    severity_order = {"severe": 0, "moderate": 1, "low": 2}
    issues.sort(key=lambda x: (severity_order.get(x["severity"], 2), x.get("last_updated") or ""))
    
    return issues[:limit]


@router.get("/{issue_id}", response_model=IssueDetailResponse)
async def get_issue_detail(issue_id: str):
    """
    Get full issue details including timeline and linked politicians.
    """
    issue = get_issue_with_events(issue_id)
    
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    return issue


@router.get("/politician/{politician_slug}")
async def get_politician_issues(politician_slug: str):
    """
    Get all issues linked to a specific politician.
    """
    # Verify politician exists
    db = SessionLocal()
    try:
        pol = db.query(Politician).filter(Politician.slug == politician_slug).first()
        if not pol:
            raise HTTPException(status_code=404, detail="Politician not found")
    finally:
        db.close()
    
    issues = get_issues_for_politician(politician_slug)
    return {"politician": politician_slug, "issues": issues}


# =====================
# Admin Endpoints
# =====================

admin_router = APIRouter(prefix="/api/admin/issues", tags=["admin"])


class VerifyRequest(BaseModel):
    verified: bool = True


@admin_router.post("/{issue_id}/verify")
async def verify_issue(issue_id: str, request: VerifyRequest):
    """
    Mark an issue as verified (admin only).
    """
    db = SessionLocal()
    try:
        issue = db.query(Issue).filter(Issue.issue_id == issue_id).first()
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        issue.verified = request.verified
        db.commit()
        
        return {"status": "ok", "issue_id": issue_id, "verified": request.verified}
    finally:
        db.close()


class StatusRequest(BaseModel):
    status: str  # active, resolved, archived


@admin_router.post("/{issue_id}/status")
async def update_issue_status(issue_id: str, request: StatusRequest):
    """
    Update issue status (admin only).
    """
    if request.status not in ["active", "resolved", "archived"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    db = SessionLocal()
    try:
        issue = db.query(Issue).filter(Issue.issue_id == issue_id).first()
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        issue.status = request.status
        db.commit()
        
        return {"status": "ok", "issue_id": issue_id, "new_status": request.status}
    finally:
        db.close()


@admin_router.get("/pending")
async def get_pending_issues(limit: int = 50):
    """
    Get unverified issues for review.
    """
    issues = list_issues(status="active", limit=limit)
    unverified = [i for i in issues if not i.get("verified")]
    
    return {
        "count": len(unverified),
        "issues": unverified
    }
