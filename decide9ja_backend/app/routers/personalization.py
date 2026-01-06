"""
User Personalization API Router for Decide9ja.

Provides endpoints for:
- My Representatives lookup
- Saved politicians and issues
- User interests and preferences
- Personalized dashboard
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/me", tags=["personalization"])


# =============================================================================
# Request/Response Models
# =============================================================================

class SavePoliticianRequest(BaseModel):
    """Request to save/follow a politician."""
    phone_hash: str = Field(..., description="User's phone hash")
    politician_slug: str = Field(..., description="Politician slug to follow")
    notify_news: bool = Field(True, description="Notify on news mentions")
    notify_updates: bool = Field(True, description="Notify on status updates")


class SaveIssueRequest(BaseModel):
    """Request to save/track an issue."""
    phone_hash: str = Field(..., description="User's phone hash")
    issue_id: str = Field(..., description="Issue ID to track")
    notify_updates: bool = Field(True, description="Notify on updates")


class UpdateInterestsRequest(BaseModel):
    """Request to update user interests."""
    phone_hash: str = Field(..., description="User's phone hash")
    topics: Optional[List[str]] = Field(None, description="Topics of interest")
    domains: Optional[List[str]] = Field(None, description="Domains: power, roads, security, etc.")
    states: Optional[List[str]] = Field(None, description="States of interest")


class UpdatePreferencesRequest(BaseModel):
    """Request to update user preferences."""
    phone_hash: str = Field(..., description="User's phone hash")
    language: Optional[str] = Field(None, description="Preferred language")
    notification_frequency: Optional[str] = Field(None, description="instant, daily_digest, weekly")
    notification_channels: Optional[List[str]] = Field(None, description="whatsapp, sms, web_push")
    news_sources: Optional[List[str]] = Field(None, description="Preferred news sources")
    content_style: Optional[str] = Field(None, description="brief or detailed")
    accessibility_mode: Optional[bool] = Field(None, description="Enable accessibility features")


# =============================================================================
# My Representatives Endpoints
# =============================================================================

@router.get("/representatives")
async def get_my_representatives(
    state: str = Query(..., description="User's state"),
    lga: Optional[str] = Query(None, description="User's LGA (optional)")
) -> Dict[str, Any]:
    """
    Get all representatives for a user based on their location.

    Returns:
        - President
        - Senator (senatorial district)
        - House of Reps member (federal constituency)
        - Governor
        - State Assembly member (if LGA known)

    Example:
        GET /api/me/representatives?state=lagos&lga=ikeja
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    representatives = service.get_my_representatives(state, lga)

    return {
        "state": state,
        "lga": lga,
        "representatives": [r.__dict__ for r in representatives],
        "total": len(representatives)
    }


# =============================================================================
# Saved Politicians Endpoints
# =============================================================================

@router.get("/politicians/{phone_hash}")
async def get_saved_politicians(phone_hash: str) -> Dict[str, Any]:
    """
    Get all saved/followed politicians for a user.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    politicians = service.get_saved_politicians(phone_hash)

    return {
        "politicians": [p.__dict__ for p in politicians],
        "total": len(politicians)
    }


@router.post("/politicians/save")
async def save_politician(request: SavePoliticianRequest) -> Dict[str, Any]:
    """
    Save/follow a politician.

    User will receive notifications about this politician.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    result = service.save_politician(
        user_hash=request.phone_hash,
        politician_slug=request.politician_slug,
        notify_news=request.notify_news,
        notify_updates=request.notify_updates
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/politicians/unsave")
async def unsave_politician(
    phone_hash: str = Query(...),
    politician_slug: str = Query(...)
) -> Dict[str, Any]:
    """
    Unsave/unfollow a politician.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    result = service.unsave_politician(phone_hash, politician_slug)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


# =============================================================================
# Saved Issues Endpoints
# =============================================================================

@router.get("/issues/{phone_hash}")
async def get_saved_issues(phone_hash: str) -> Dict[str, Any]:
    """
    Get all saved/tracked issues for a user.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    issues = service.get_saved_issues(phone_hash)

    return {
        "issues": [i.__dict__ for i in issues],
        "total": len(issues)
    }


@router.post("/issues/save")
async def save_issue(request: SaveIssueRequest) -> Dict[str, Any]:
    """
    Save/track an issue.

    User will receive notifications about this issue.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    result = service.save_issue(
        user_hash=request.phone_hash,
        issue_id=request.issue_id,
        notify_updates=request.notify_updates
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/issues/unsave")
async def unsave_issue(
    phone_hash: str = Query(...),
    issue_id: str = Query(...)
) -> Dict[str, Any]:
    """
    Unsave/untrack an issue.
    """
    from app.services.personalization_service import PersonalizationService
    from app.database import SessionLocal, UserSubscription

    db = SessionLocal()
    try:
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_hash == phone_hash,
            UserSubscription.subscription_type == "issue",
            UserSubscription.target_id == issue_id,
            UserSubscription.is_active == True
        ).first()

        if not subscription:
            raise HTTPException(status_code=400, detail="Not tracking this issue")

        subscription.is_active = False
        db.commit()

        return {"success": True, "message": "Issue untracked"}

    finally:
        db.close()


# =============================================================================
# Interests Endpoints
# =============================================================================

@router.get("/interests/{phone_hash}")
async def get_interests(phone_hash: str) -> Dict[str, Any]:
    """
    Get user's topic interests.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    interests = service.get_interests(phone_hash)

    return interests.__dict__


@router.put("/interests")
async def update_interests(request: UpdateInterestsRequest) -> Dict[str, Any]:
    """
    Update user's topic interests.

    These interests are used for personalized content recommendations.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    result = service.update_interests(
        user_hash=request.phone_hash,
        topics=request.topics,
        domains=request.domains,
        states=request.states
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/domains")
async def get_available_domains() -> Dict[str, Any]:
    """
    Get available domains/categories for interests.
    """
    domains = [
        {"id": "power", "name": "Power & Electricity", "description": "Power outages, grid issues, tariffs"},
        {"id": "roads", "name": "Roads & Infrastructure", "description": "Road conditions, construction, traffic"},
        {"id": "security", "name": "Security", "description": "Safety, crime, policing"},
        {"id": "health", "name": "Healthcare", "description": "Hospitals, health policies, disease outbreaks"},
        {"id": "education", "name": "Education", "description": "Schools, universities, ASUU, education policies"},
        {"id": "water", "name": "Water & Sanitation", "description": "Water supply, sanitation, environmental issues"},
        {"id": "economy", "name": "Economy & Finance", "description": "Inflation, exchange rates, economic policies"},
        {"id": "governance", "name": "Governance", "description": "Government operations, corruption, accountability"},
        {"id": "agriculture", "name": "Agriculture", "description": "Farming, food security, agricultural policies"},
        {"id": "technology", "name": "Technology", "description": "Digital economy, tech policies, internet"},
    ]

    return {"domains": domains}


# =============================================================================
# Preferences Endpoints
# =============================================================================

@router.get("/preferences/{phone_hash}")
async def get_preferences(phone_hash: str) -> Dict[str, Any]:
    """
    Get user's app preferences.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    preferences = service.get_preferences(phone_hash)

    return preferences.__dict__


@router.put("/preferences")
async def update_preferences(request: UpdatePreferencesRequest) -> Dict[str, Any]:
    """
    Update user's app preferences.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    result = service.update_preferences(
        user_hash=request.phone_hash,
        language=request.language,
        notification_frequency=request.notification_frequency,
        notification_channels=request.notification_channels,
        news_sources=request.news_sources,
        content_style=request.content_style,
        accessibility_mode=request.accessibility_mode
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


# =============================================================================
# Dashboard Endpoint
# =============================================================================

@router.get("/dashboard/{phone_hash}")
async def get_dashboard(phone_hash: str) -> Dict[str, Any]:
    """
    Get personalized dashboard for a user.

    Returns:
        - User info
        - My representatives (based on location)
        - Saved politicians
        - Saved issues
        - Interests
        - Recent activity (news about saved items)
        - Recommendations

    This is the main endpoint for building a personalized home screen.
    """
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    dashboard = service.get_dashboard(phone_hash)

    return dashboard


# =============================================================================
# Onboarding Status
# =============================================================================

@router.get("/onboarding/{phone_hash}")
async def get_onboarding_status(phone_hash: str) -> Dict[str, Any]:
    """
    Check user's onboarding status and what's missing.
    """
    from app.database import SessionLocal, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_hash == phone_hash).first()

        if not user:
            return {
                "completed": False,
                "missing": ["registration", "location", "interests"],
                "next_step": "registration"
            }

        missing = []
        if not user.state:
            missing.append("location")
        if not user.preferences_json or "interests" not in user.preferences_json:
            missing.append("interests")

        return {
            "completed": user.onboarding_completed,
            "missing": missing,
            "next_step": missing[0] if missing else None,
            "user": {
                "name": user.name,
                "state": user.state,
                "lga": user.lga
            }
        }

    finally:
        db.close()


@router.post("/onboarding/complete/{phone_hash}")
async def mark_onboarding_complete(phone_hash: str) -> Dict[str, Any]:
    """
    Mark user's onboarding as complete.
    """
    from app.database import SessionLocal, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_hash == phone_hash).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.onboarding_completed = True
        db.commit()

        return {"success": True, "message": "Onboarding marked complete"}

    finally:
        db.close()
