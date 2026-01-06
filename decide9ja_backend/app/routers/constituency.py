"""
Constituency & Community API Router for Decide9ja.

Provides endpoints for:
- Ward-level representatives and data
- Local government projects
- Community issue reporting and tracking
- Gamification and civic engagement
- Leaderboards

All responses are WhatsApp-compatible.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

router = APIRouter(prefix="/api/constituency", tags=["constituency"])


# =============================================================================
# Request/Response Models
# =============================================================================

class IssueCategoryEnum(str, Enum):
    ROADS = "roads"
    ELECTRICITY = "electricity"
    WATER = "water"
    SECURITY = "security"
    SANITATION = "sanitation"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    DRAINAGE = "drainage"
    STREETLIGHTS = "streetlights"
    OTHER = "other"


class ProjectCategoryEnum(str, Enum):
    ROADS = "roads"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    WATER = "water"
    ELECTRICITY = "electricity"
    HOUSING = "housing"
    AGRICULTURE = "agriculture"


class ReportIssueRequest(BaseModel):
    """Request to report a community issue."""
    title: str = Field(..., min_length=5, max_length=100)
    description: str = Field(..., min_length=10, max_length=500)
    category: IssueCategoryEnum
    state: str = Field(...)
    lga: str = Field(...)
    ward: Optional[str] = None
    address: Optional[str] = None
    reporter_hash: Optional[str] = None
    reporter_name: Optional[str] = None
    photo_urls: Optional[List[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class VoteRequest(BaseModel):
    """Request to vote on an issue."""
    issue_id: str
    voter_hash: str
    vote_type: str = Field("up", description="up or down")


class VerifyRequest(BaseModel):
    """Request to verify an issue."""
    issue_id: str
    verifier_hash: str
    is_verified: bool = True
    comment: Optional[str] = None
    photo_url: Optional[str] = None


class UpdateRequest(BaseModel):
    """Request to add update to an issue."""
    issue_id: str
    content: str = Field(..., min_length=5, max_length=500)
    author_hash: str
    author_name: Optional[str] = None
    photo_url: Optional[str] = None


class AwardPointsRequest(BaseModel):
    """Request to award points."""
    user_hash: str
    action: str
    description: Optional[str] = None


# =============================================================================
# Ward Representatives
# =============================================================================

@router.get("/representatives")
async def get_ward_representatives(
    state: str = Query(..., description="State name"),
    lga: str = Query(..., description="LGA name"),
    ward: Optional[str] = Query(None, description="Ward name")
) -> Dict[str, Any]:
    """Get ward-level representatives."""
    from app.services.constituency_service import get_constituency_service

    service = get_constituency_service()
    reps = service.get_ward_representatives(state, lga, ward)

    return {
        "representatives": [
            {
                "id": r.id,
                "name": r.name,
                "position": r.position,
                "ward": r.ward,
                "lga": r.lga,
                "party": r.party,
                "phone": r.phone,
                "email": r.email
            }
            for r in reps
        ],
        "count": len(reps),
        "location": {"state": state, "lga": lga, "ward": ward}
    }


@router.get("/representatives/whatsapp")
async def get_representatives_whatsapp(
    state: str = Query(...),
    lga: str = Query(...),
    ward: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get ward representatives formatted for WhatsApp."""
    from app.services.constituency_service import get_constituency_service

    service = get_constituency_service()
    reps = service.get_ward_representatives(state, lga, ward)
    location = f"{ward or lga}, {state}"

    return {
        "message": service.format_representatives_whatsapp(reps, location)
    }


# =============================================================================
# Local Projects
# =============================================================================

@router.get("/projects")
async def get_local_projects(
    state: str = Query(...),
    lga: str = Query(...),
    category: Optional[ProjectCategoryEnum] = Query(None),
    status: Optional[str] = Query(None, description="planned, in_progress, completed, delayed"),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """Get government projects in constituency."""
    from app.services.constituency_service import (
        get_constituency_service, ProjectCategory, ProjectStatus
    )

    service = get_constituency_service()

    cat = ProjectCategory(category.value) if category else None
    stat = ProjectStatus(status) if status else None

    projects = service.get_local_projects(state, lga, cat, stat, limit)

    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "category": p.category.value,
                "status": p.status.value,
                "location": p.location,
                "budget": p.budget,
                "percentage_complete": p.percentage_complete,
                "funding_source": p.funding_source,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "expected_completion": p.expected_completion.isoformat() if p.expected_completion else None
            }
            for p in projects
        ],
        "count": len(projects)
    }


@router.get("/projects/whatsapp")
async def get_projects_whatsapp(
    state: str = Query(...),
    lga: str = Query(...)
) -> Dict[str, Any]:
    """Get projects formatted for WhatsApp."""
    from app.services.constituency_service import get_constituency_service

    service = get_constituency_service()
    projects = service.get_local_projects(state, lga)
    location = f"{lga}, {state}"

    return {
        "message": service.format_projects_whatsapp(projects, location)
    }


@router.get("/projects/{project_id}")
async def get_project_detail(project_id: str) -> Dict[str, Any]:
    """Get single project details."""
    from app.services.constituency_service import get_constituency_service

    service = get_constituency_service()
    project = service.get_project_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "category": project.category.value,
            "status": project.status.value,
            "location": project.location,
            "ward": project.ward,
            "lga": project.lga,
            "state": project.state,
            "budget": project.budget,
            "contractor": project.contractor,
            "percentage_complete": project.percentage_complete,
            "funding_source": project.funding_source,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "expected_completion": project.expected_completion.isoformat() if project.expected_completion else None,
            "actual_completion": project.actual_completion.isoformat() if project.actual_completion else None,
            "issues_reported": project.issues_reported
        }
    }


@router.get("/projects/{project_id}/whatsapp")
async def get_project_whatsapp(project_id: str) -> Dict[str, Any]:
    """Get project detail formatted for WhatsApp."""
    from app.services.constituency_service import get_constituency_service

    service = get_constituency_service()
    project = service.get_project_by_id(project_id)

    if not project:
        return {"message": "Project not found."}

    return {
        "message": service.format_project_detail_whatsapp(project)
    }


# =============================================================================
# Community Issues
# =============================================================================

@router.post("/issues/report")
async def report_issue(request: ReportIssueRequest) -> Dict[str, Any]:
    """Report a new community issue."""
    from app.services.community_service import get_community_service, IssueCategory

    service = get_community_service()

    issue = service.report_issue(
        title=request.title,
        description=request.description,
        category=IssueCategory(request.category.value),
        state=request.state,
        lga=request.lga,
        ward=request.ward,
        address=request.address,
        reporter_hash=request.reporter_hash or "anonymous",
        reporter_name=request.reporter_name,
        photo_urls=request.photo_urls,
        latitude=request.latitude,
        longitude=request.longitude
    )

    return {
        "success": True,
        "issue_id": issue.id,
        "status": issue.status.value,
        "responsible_authority": issue.responsible_authority,
        "message": service.format_issue_reported_whatsapp(issue)
    }


@router.get("/issues")
async def get_local_issues(
    state: str = Query(...),
    lga: str = Query(...),
    category: Optional[IssueCategoryEnum] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """Get community issues in a location."""
    from app.services.community_service import get_community_service, IssueCategory, IssueStatus

    service = get_community_service()

    cat = IssueCategory(category.value) if category else None
    stat = IssueStatus(status) if status else None

    issues = service.get_local_issues(state, lga, cat, stat, limit)

    return {
        "issues": [
            {
                "id": i.id,
                "title": i.title,
                "category": i.category.value,
                "status": i.status.value,
                "upvotes": i.upvotes,
                "verification_count": i.verification_count,
                "created_at": i.created_at.isoformat()
            }
            for i in issues
        ],
        "count": len(issues)
    }


@router.get("/issues/whatsapp")
async def get_issues_whatsapp(
    state: str = Query(...),
    lga: str = Query(...)
) -> Dict[str, Any]:
    """Get issues formatted for WhatsApp."""
    from app.services.community_service import get_community_service

    service = get_community_service()
    issues = service.get_local_issues(state, lga)
    location = f"{lga}, {state}"

    return {
        "message": service.format_issues_list_whatsapp(issues, location)
    }


@router.get("/issues/trending")
async def get_trending_issues(
    state: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20)
) -> Dict[str, Any]:
    """Get trending community issues."""
    from app.services.community_service import get_community_service

    service = get_community_service()
    issues = service.get_trending_issues(state, limit)

    return {
        "trending": [
            {
                "id": i.id,
                "title": i.title,
                "lga": i.lga,
                "state": i.state,
                "category": i.category.value,
                "upvotes": i.upvotes
            }
            for i in issues
        ]
    }


@router.get("/issues/trending/whatsapp")
async def get_trending_whatsapp(
    state: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get trending issues formatted for WhatsApp."""
    from app.services.community_service import get_community_service

    service = get_community_service()
    issues = service.get_trending_issues(state)
    area = state or "Nigeria"

    return {
        "message": service.format_trending_whatsapp(issues, area)
    }


@router.get("/issues/{issue_id}")
async def get_issue_detail(issue_id: str) -> Dict[str, Any]:
    """Get single issue details."""
    from app.services.community_service import get_community_service

    service = get_community_service()
    issue = service.get_issue(issue_id)

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    updates = service.get_issue_updates(issue_id)

    return {
        "issue": {
            "id": issue.id,
            "title": issue.title,
            "description": issue.description,
            "category": issue.category.value,
            "status": issue.status.value,
            "ward": issue.ward,
            "lga": issue.lga,
            "state": issue.state,
            "address": issue.address,
            "upvotes": issue.upvotes,
            "downvotes": issue.downvotes,
            "verification_count": issue.verification_count,
            "responsible_authority": issue.responsible_authority,
            "official_response": issue.official_response,
            "created_at": issue.created_at.isoformat(),
            "photo_urls": issue.photo_urls
        },
        "updates": [
            {
                "id": u.id,
                "type": u.update_type.value,
                "content": u.content,
                "is_official": u.is_official,
                "created_at": u.created_at.isoformat()
            }
            for u in updates
        ]
    }


@router.get("/issues/{issue_id}/whatsapp")
async def get_issue_whatsapp(issue_id: str) -> Dict[str, Any]:
    """Get issue detail formatted for WhatsApp."""
    from app.services.community_service import get_community_service

    service = get_community_service()
    issue = service.get_issue(issue_id)

    if not issue:
        return {"message": f"Issue #{issue_id} not found."}

    return {
        "message": service.format_issue_detail_whatsapp(issue)
    }


@router.post("/issues/vote")
async def vote_on_issue(request: VoteRequest) -> Dict[str, Any]:
    """Vote on a community issue."""
    from app.services.community_service import get_community_service

    service = get_community_service()
    result = service.vote_issue(
        issue_id=request.issue_id,
        voter_hash=request.voter_hash,
        vote_type=request.vote_type
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/issues/verify")
async def verify_issue(request: VerifyRequest) -> Dict[str, Any]:
    """Verify that an issue exists."""
    from app.services.community_service import get_community_service

    service = get_community_service()
    result = service.verify_issue(
        issue_id=request.issue_id,
        verifier_hash=request.verifier_hash,
        is_verified=request.is_verified,
        comment=request.comment,
        photo_url=request.photo_url
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/issues/update")
async def add_issue_update(request: UpdateRequest) -> Dict[str, Any]:
    """Add an update to an issue."""
    from app.services.community_service import get_community_service, UpdateType

    service = get_community_service()
    result = service.add_update(
        issue_id=request.issue_id,
        content=request.content,
        author_hash=request.author_hash,
        author_name=request.author_name,
        update_type=UpdateType.COMMENT,
        photo_url=request.photo_url
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/issues/stats")
async def get_community_stats(
    state: Optional[str] = Query(None),
    lga: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get community reporting statistics."""
    from app.services.community_service import get_community_service

    service = get_community_service()
    return service.get_stats(state, lga)


# =============================================================================
# Gamification
# =============================================================================

@router.get("/profile/{user_hash}")
async def get_civic_profile(user_hash: str) -> Dict[str, Any]:
    """Get user's civic engagement profile."""
    from app.services.gamification_service import get_gamification_service, BADGES

    service = get_gamification_service()
    profile = service.get_profile(user_hash)

    return {
        "profile": {
            "user_hash": profile.user_hash[:8] + "...",
            "display_name": profile.display_name,
            "level": profile.level,
            "title": profile.title,
            "total_points": profile.total_points,
            "points_this_week": profile.points_this_week,
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "badges": [
                {
                    "id": b,
                    "name": BADGES[b].name,
                    "emoji": BADGES[b].emoji
                }
                for b in profile.badges if b in BADGES
            ],
            "badges_count": len(profile.badges),
            "state": profile.state,
            "lga": profile.lga
        }
    }


@router.get("/profile/{user_hash}/whatsapp")
async def get_profile_whatsapp(user_hash: str) -> Dict[str, Any]:
    """Get civic profile formatted for WhatsApp."""
    from app.services.gamification_service import get_gamification_service

    service = get_gamification_service()
    return {
        "message": service.format_profile_whatsapp(user_hash)
    }


@router.get("/profile/{user_hash}/badges")
async def get_user_badges(user_hash: str) -> Dict[str, Any]:
    """Get user's badges."""
    from app.services.gamification_service import get_gamification_service, BADGES

    service = get_gamification_service()
    profile = service.get_profile(user_hash)

    earned = []
    available = []

    for badge_id, badge in BADGES.items():
        badge_info = {
            "id": badge_id,
            "name": badge.name,
            "description": badge.description,
            "emoji": badge.emoji,
            "category": badge.category.value
        }

        if badge_id in profile.badges:
            earned.append(badge_info)
        elif not badge.is_secret:
            available.append(badge_info)

    return {
        "earned": earned,
        "available": available,
        "total_earned": len(earned),
        "total_available": len(BADGES)
    }


@router.get("/profile/{user_hash}/badges/whatsapp")
async def get_badges_whatsapp(user_hash: str) -> Dict[str, Any]:
    """Get badges formatted for WhatsApp."""
    from app.services.gamification_service import get_gamification_service

    service = get_gamification_service()
    return {
        "message": service.format_badges_whatsapp(user_hash)
    }


@router.post("/points/award")
async def award_points(request: AwardPointsRequest) -> Dict[str, Any]:
    """Award points for civic action."""
    from app.services.gamification_service import get_gamification_service, CivicAction

    service = get_gamification_service()

    try:
        action = CivicAction(request.action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    result = service.award_points(
        user_hash=request.user_hash,
        action=action,
        description=request.description
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/leaderboard")
async def get_leaderboard(
    state: Optional[str] = Query(None),
    lga: Optional[str] = Query(None),
    period: str = Query("all_time", description="all_time, monthly, weekly"),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """Get civic engagement leaderboard."""
    from app.services.gamification_service import get_gamification_service

    service = get_gamification_service()
    leaderboard = service.get_leaderboard(state, lga, period, limit)

    return {
        "leaderboard": leaderboard,
        "period": period,
        "location": lga or state or "Nigeria"
    }


@router.get("/leaderboard/whatsapp")
async def get_leaderboard_whatsapp(
    state: Optional[str] = Query(None),
    lga: Optional[str] = Query(None),
    period: str = Query("all_time")
) -> Dict[str, Any]:
    """Get leaderboard formatted for WhatsApp."""
    from app.services.gamification_service import get_gamification_service

    service = get_gamification_service()
    leaderboard = service.get_leaderboard(state, lga, period)
    location = lga or state or "Nigeria"

    return {
        "message": service.format_leaderboard_whatsapp(leaderboard, location, period)
    }


@router.get("/leaderboard/rank/{user_hash}")
async def get_user_rank(
    user_hash: str,
    state: Optional[str] = Query(None),
    lga: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get user's rank on leaderboard."""
    from app.services.gamification_service import get_gamification_service

    service = get_gamification_service()
    return service.get_user_rank(user_hash, state, lga)


@router.get("/gamification/stats")
async def get_gamification_stats() -> Dict[str, Any]:
    """Get gamification statistics."""
    from app.services.gamification_service import get_gamification_service

    service = get_gamification_service()
    return service.get_stats()
