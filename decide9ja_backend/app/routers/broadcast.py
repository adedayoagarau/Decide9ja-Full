"""
Broadcast & Proactive Messaging API Router for Decide9ja.

Provides endpoints for:
- Campaign management (create, schedule, send)
- Audience targeting
- News digests (subscribe, configure)
- Fact-checking claims
- Breaking news alerts

All messages are WhatsApp-compatible.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

router = APIRouter(prefix="/api/broadcast", tags=["broadcast"])


# =============================================================================
# Request/Response Models
# =============================================================================

class AudienceTypeEnum(str, Enum):
    ALL = "all"
    STATE = "state"
    LGA = "lga"
    SENATORIAL = "senatorial"
    INTERESTS = "interests"
    FOLLOWED_POLITICIAN = "followed_politician"
    CUSTOM = "custom"


class PriorityEnum(str, Enum):
    BREAKING = "breaking"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class AudienceCriteriaRequest(BaseModel):
    """Audience targeting criteria."""
    audience_type: AudienceTypeEnum = Field(AudienceTypeEnum.ALL)
    states: Optional[List[str]] = Field(None, description="Target states")
    lgas: Optional[List[str]] = Field(None, description="Target LGAs")
    senatorial_districts: Optional[List[str]] = Field(None)
    interests: Optional[List[str]] = Field(None, description="User interests to target")
    followed_politicians: Optional[List[str]] = Field(None, description="Politicians' slugs")
    exclude_states: Optional[List[str]] = Field(None)
    exclude_users: Optional[List[str]] = Field(None, description="User hashes to exclude")
    custom_user_hashes: Optional[List[str]] = Field(None, description="Specific users")
    last_active_within_days: Optional[int] = Field(None, ge=1, le=365)


class CreateCampaignRequest(BaseModel):
    """Request to create a broadcast campaign."""
    name: str = Field(..., min_length=3, max_length=100)
    content: str = Field(..., min_length=10, max_length=1000, description="Message content. Use {name}, {state}, {lga} for personalization.")
    audience: AudienceCriteriaRequest
    priority: PriorityEnum = Field(PriorityEnum.NORMAL)
    scheduled_at: Optional[datetime] = Field(None, description="When to send (UTC)")
    category: str = Field("general", description="news, election, civic, alert")
    cta_text: Optional[str] = Field(None, description="Call to action text")
    cta_options: Optional[List[str]] = Field(None, description="Reply options")


class ScheduleCampaignRequest(BaseModel):
    """Request to schedule a campaign."""
    scheduled_at: datetime
    send_window_start: int = Field(8, ge=0, le=23, description="Start hour (WAT)")
    send_window_end: int = Field(20, ge=0, le=23, description="End hour (WAT)")


class BreakingNewsRequest(BaseModel):
    """Request to send breaking news."""
    headline: str = Field(..., min_length=10, max_length=200)
    content: str = Field(..., min_length=20, max_length=500)
    source: str = Field(..., description="News source")
    audience: Optional[AudienceCriteriaRequest] = Field(None)


class SendDirectRequest(BaseModel):
    """Request to send direct message to a user."""
    user_hash: str = Field(...)
    content: str = Field(..., min_length=5, max_length=1000)
    category: str = Field("direct")


# =============================================================================
# Campaign Endpoints
# =============================================================================

@router.post("/campaigns")
async def create_campaign(request: CreateCampaignRequest) -> Dict[str, Any]:
    """
    Create a new broadcast campaign.

    Campaigns can be scheduled for later or saved as drafts.
    Use personalization placeholders: {name}, {state}, {lga}
    """
    from app.services.broadcast_service import (
        get_broadcast_service, AudienceCriteria, AudienceType, MessagePriority
    )

    service = get_broadcast_service()

    # Build audience criteria
    audience = AudienceCriteria(
        audience_type=AudienceType(request.audience.audience_type.value),
        states=request.audience.states or [],
        lgas=request.audience.lgas or [],
        senatorial_districts=request.audience.senatorial_districts or [],
        interests=request.audience.interests or [],
        followed_politicians=request.audience.followed_politicians or [],
        exclude_states=request.audience.exclude_states or [],
        exclude_users=request.audience.exclude_users or [],
        custom_user_hashes=request.audience.custom_user_hashes or [],
        last_active_within_days=request.audience.last_active_within_days
    )

    campaign = service.create_campaign(
        name=request.name,
        content=request.content,
        audience=audience,
        priority=MessagePriority(request.priority.value),
        scheduled_at=request.scheduled_at,
        category=request.category,
        cta_text=request.cta_text,
        cta_options=request.cta_options
    )

    # Get audience count
    audience_count = service.get_audience_count(audience)

    return {
        "campaign_id": campaign.id,
        "name": campaign.name,
        "status": campaign.status.value,
        "estimated_recipients": audience_count,
        "scheduled_at": campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
        "created_at": campaign.created_at.isoformat()
    }


@router.get("/campaigns")
async def list_campaigns(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100)
) -> Dict[str, Any]:
    """List broadcast campaigns."""
    from app.services.broadcast_service import get_broadcast_service, CampaignStatus

    service = get_broadcast_service()

    status_filter = CampaignStatus(status) if status else None
    campaigns = service.list_campaigns(status=status_filter, limit=limit)

    return {
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status.value,
                "total_recipients": c.total_recipients,
                "sent_count": c.sent_count,
                "delivered_count": c.delivered_count,
                "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
                "created_at": c.created_at.isoformat()
            }
            for c in campaigns
        ],
        "total": len(campaigns)
    }


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str) -> Dict[str, Any]:
    """Get campaign details and statistics."""
    from app.services.broadcast_service import get_broadcast_service

    service = get_broadcast_service()
    stats = service.get_campaign_stats(campaign_id)

    if not stats:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return stats


@router.post("/campaigns/{campaign_id}/schedule")
async def schedule_campaign(
    campaign_id: str,
    request: ScheduleCampaignRequest
) -> Dict[str, Any]:
    """Schedule a draft campaign for sending."""
    from app.services.broadcast_service import get_broadcast_service

    service = get_broadcast_service()

    success = service.schedule_campaign(
        campaign_id=campaign_id,
        scheduled_at=request.scheduled_at,
        send_window_start=request.send_window_start,
        send_window_end=request.send_window_end
    )

    if not success:
        raise HTTPException(status_code=400, detail="Could not schedule campaign")

    return {
        "success": True,
        "campaign_id": campaign_id,
        "scheduled_at": request.scheduled_at.isoformat()
    }


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(
    campaign_id: str,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Execute a campaign - start sending messages.

    Messages are queued and sent asynchronously.
    """
    from app.services.broadcast_service import get_broadcast_service

    service = get_broadcast_service()
    result = service.send_campaign(campaign_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str) -> Dict[str, Any]:
    """Pause an active campaign."""
    from app.services.broadcast_service import get_broadcast_service

    service = get_broadcast_service()

    if not service.pause_campaign(campaign_id):
        raise HTTPException(status_code=400, detail="Could not pause campaign")

    return {"success": True, "campaign_id": campaign_id, "status": "paused"}


@router.post("/campaigns/{campaign_id}/cancel")
async def cancel_campaign(campaign_id: str) -> Dict[str, Any]:
    """Cancel a campaign."""
    from app.services.broadcast_service import get_broadcast_service

    service = get_broadcast_service()

    if not service.cancel_campaign(campaign_id):
        raise HTTPException(status_code=400, detail="Could not cancel campaign")

    return {"success": True, "campaign_id": campaign_id, "status": "cancelled"}


# =============================================================================
# Breaking News & Direct Messages
# =============================================================================

@router.post("/breaking-news")
async def send_breaking_news(
    request: BreakingNewsRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Send immediate breaking news alert.

    Delivers with highest priority to all users or targeted audience.
    """
    from app.services.broadcast_service import get_broadcast_service, AudienceCriteria, AudienceType

    service = get_broadcast_service()

    audience = None
    if request.audience:
        audience = AudienceCriteria(
            audience_type=AudienceType(request.audience.audience_type.value),
            states=request.audience.states or [],
            lgas=request.audience.lgas or []
        )

    content = f"""⚠️ BREAKING: {request.headline}

{request.content}

Source: {request.source}

Reply "more" for details."""

    result = service.send_breaking_news(
        content=content,
        title=request.headline,
        audience=audience,
        source_url=None
    )

    return result


@router.post("/send-direct")
async def send_direct_message(request: SendDirectRequest) -> Dict[str, Any]:
    """Send a direct message to a specific user."""
    from app.services.broadcast_service import get_broadcast_service

    service = get_broadcast_service()

    result = service.send_to_user(
        user_hash=request.user_hash,
        content=request.content,
        category=request.category
    )

    return result


# =============================================================================
# Audience Estimation
# =============================================================================

@router.post("/audience/estimate")
async def estimate_audience(criteria: AudienceCriteriaRequest) -> Dict[str, Any]:
    """
    Get estimated recipient count for audience criteria.

    Use this to preview campaign reach before creating.
    """
    from app.services.broadcast_service import get_broadcast_service, AudienceCriteria, AudienceType

    service = get_broadcast_service()

    audience = AudienceCriteria(
        audience_type=AudienceType(criteria.audience_type.value),
        states=criteria.states or [],
        lgas=criteria.lgas or [],
        senatorial_districts=criteria.senatorial_districts or [],
        interests=criteria.interests or [],
        followed_politicians=criteria.followed_politicians or [],
        exclude_states=criteria.exclude_states or [],
        last_active_within_days=criteria.last_active_within_days
    )

    count = service.get_audience_count(audience)

    return {
        "estimated_recipients": count,
        "criteria": criteria.dict()
    }


# =============================================================================
# Queue & Delivery Status
# =============================================================================

@router.get("/queue/stats")
async def get_queue_stats() -> Dict[str, Any]:
    """Get message queue statistics."""
    from app.services.broadcast_service import get_broadcast_service

    service = get_broadcast_service()
    return service.get_queue_stats()


@router.get("/queue/pending")
async def get_pending_messages(
    limit: int = Query(100, ge=1, le=500)
) -> Dict[str, Any]:
    """Get pending messages from queue."""
    from app.services.broadcast_service import get_broadcast_service

    service = get_broadcast_service()
    messages = service.get_pending_messages(limit=limit)

    return {
        "messages": messages,
        "count": len(messages)
    }


# =============================================================================
# News Digest Endpoints
# =============================================================================

class DigestSubscribeRequest(BaseModel):
    """Request to subscribe to digest."""
    user_hash: str
    frequency: str = Field("daily", description="daily, weekly")
    send_time: Optional[str] = Field("07:00", description="HH:MM in WAT")


class DigestPreferencesRequest(BaseModel):
    """Request to update digest preferences."""
    user_hash: str
    enabled: Optional[bool] = None
    frequency: Optional[str] = None
    send_time: Optional[str] = None
    categories: Optional[List[str]] = None
    states_of_interest: Optional[List[str]] = None
    max_items: Optional[int] = Field(None, ge=1, le=10)
    include_polls: Optional[bool] = None
    language: Optional[str] = None


@router.post("/digest/subscribe")
async def subscribe_to_digest(request: DigestSubscribeRequest) -> Dict[str, Any]:
    """Subscribe user to news digest."""
    from app.services.news_digest_service import get_news_digest_service

    service = get_news_digest_service()
    result = service.subscribe_to_digest(request.user_hash, request.frequency)

    if request.send_time:
        service.update_preferences(request.user_hash, send_time=request.send_time)

    return result


@router.post("/digest/unsubscribe")
async def unsubscribe_from_digest(user_hash: str = Query(...)) -> Dict[str, Any]:
    """Unsubscribe user from news digest."""
    from app.services.news_digest_service import get_news_digest_service

    service = get_news_digest_service()
    return service.unsubscribe_from_digest(user_hash)


@router.get("/digest/preferences/{user_hash}")
async def get_digest_preferences(user_hash: str) -> Dict[str, Any]:
    """Get user's digest preferences."""
    from app.services.news_digest_service import get_news_digest_service

    service = get_news_digest_service()
    prefs = service.get_preferences(user_hash)

    return {
        "user_hash": prefs.user_hash,
        "enabled": prefs.enabled,
        "frequency": prefs.frequency.value,
        "send_time": prefs.send_time,
        "categories": prefs.categories,
        "states_of_interest": prefs.states_of_interest,
        "max_items": prefs.max_items,
        "include_polls": prefs.include_polls,
        "language": prefs.language
    }


@router.put("/digest/preferences")
async def update_digest_preferences(request: DigestPreferencesRequest) -> Dict[str, Any]:
    """Update user's digest preferences."""
    from app.services.news_digest_service import get_news_digest_service

    service = get_news_digest_service()

    prefs = service.update_preferences(
        user_hash=request.user_hash,
        enabled=request.enabled,
        frequency=request.frequency,
        send_time=request.send_time,
        categories=request.categories,
        states_of_interest=request.states_of_interest,
        max_items=request.max_items,
        include_polls=request.include_polls,
        language=request.language
    )

    return {
        "success": True,
        "preferences": {
            "enabled": prefs.enabled,
            "frequency": prefs.frequency.value,
            "send_time": prefs.send_time
        }
    }


@router.get("/digest/preview/{user_hash}")
async def preview_digest(
    user_hash: str,
    frequency: str = Query("daily", description="daily or weekly")
) -> Dict[str, Any]:
    """
    Preview what a user's digest would look like.

    Useful for testing personalization.
    """
    from app.services.news_digest_service import get_news_digest_service, DigestFrequency

    service = get_news_digest_service()

    # Get user context from database
    user_context = _get_user_context(user_hash)

    if frequency == "weekly":
        digest = service.generate_weekly_digest(user_hash, user_context)
    else:
        digest = service.generate_daily_digest(user_hash, user_context)

    return {
        "id": digest.id,
        "frequency": digest.frequency.value,
        "content": digest.content,
        "items_count": digest.items_count,
        "personalized": digest.personalized
    }


def _get_user_context(user_hash: str) -> Optional[Dict]:
    """Get user context from database."""
    import os
    from sqlalchemy import create_engine, text

    try:
        engine = create_engine(os.getenv('DATABASE_URL'))

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name, state, lga, preferences_json
                FROM users WHERE phone_hash = :hash
            """), {"hash": user_hash})

            row = result.fetchone()
            if row:
                return {
                    "name": row[0],
                    "state": row[1],
                    "lga": row[2],
                    "preferences": row[3] or {}
                }
    except Exception:
        pass

    return None


# =============================================================================
# Fact-Check Endpoints
# =============================================================================

class FactCheckRequest(BaseModel):
    """Request to check a claim."""
    claim: str = Field(..., min_length=10, max_length=500)
    user_hash: Optional[str] = None


class AddFactCheckRequest(BaseModel):
    """Request to add a fact-check (admin)."""
    claim: str = Field(..., min_length=10)
    verdict: str = Field(..., description="true, mostly_true, half_true, mostly_false, false, unverifiable")
    explanation: str = Field(..., min_length=20)
    sources: List[Dict] = Field(..., description="List of source objects with name, url, credibility")
    category: str = Field("politician")
    claimant: Optional[str] = None
    is_viral: bool = False
    alert_level: str = Field("normal", description="normal, elevated, critical")


@router.post("/fact-check")
async def check_claim(request: FactCheckRequest) -> Dict[str, Any]:
    """
    Check a claim and get verdict.

    Returns verdict with explanation and sources.
    If claim is new, queues it for manual review.
    """
    from app.services.fact_check_service import get_fact_check_service

    service = get_fact_check_service()
    result = service.check_claim(request.claim, request.user_hash)

    return result


@router.get("/fact-check/whatsapp")
async def check_claim_whatsapp(
    claim: str = Query(..., min_length=10),
    user_hash: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check a claim and get WhatsApp-formatted response.

    Use this endpoint for WhatsApp bot integration.
    """
    from app.services.fact_check_service import get_fact_check_service

    service = get_fact_check_service()
    result = service.check_claim(claim, user_hash)
    whatsapp_message = service.format_whatsapp_response(result)

    return {
        "verdict": result.get("verdict"),
        "message": whatsapp_message
    }


@router.get("/fact-check/viral")
async def get_viral_claims(
    limit: int = Query(5, ge=1, le=20)
) -> Dict[str, Any]:
    """Get currently viral claims being checked."""
    from app.services.fact_check_service import get_fact_check_service

    service = get_fact_check_service()
    claims = service.get_viral_claims(limit)

    return {
        "viral_claims": claims,
        "count": len(claims)
    }


@router.get("/fact-check/alert")
async def get_misinformation_alert() -> Dict[str, Any]:
    """
    Get current misinformation alert if any.

    Returns an alert message for critical viral misinformation.
    """
    from app.services.fact_check_service import get_fact_check_service

    service = get_fact_check_service()
    alert = service.get_misinformation_alert()

    return {
        "has_alert": alert is not None,
        "message": alert
    }


@router.get("/fact-check/stats")
async def get_fact_check_stats() -> Dict[str, Any]:
    """Get fact-checking statistics."""
    from app.services.fact_check_service import get_fact_check_service

    service = get_fact_check_service()
    return service.get_stats()


@router.post("/fact-check/add")
async def add_fact_check(request: AddFactCheckRequest) -> Dict[str, Any]:
    """
    Add a new fact-check (admin only).

    Use this to add verified fact-checks to the database.
    """
    from app.services.fact_check_service import get_fact_check_service, Verdict, ClaimCategory

    service = get_fact_check_service()

    fc = service.add_fact_check(
        claim=request.claim,
        verdict=Verdict(request.verdict),
        explanation=request.explanation,
        sources=request.sources,
        category=ClaimCategory(request.category),
        claimant=request.claimant,
        is_viral=request.is_viral,
        alert_level=request.alert_level
    )

    return {
        "success": True,
        "fact_check_id": fc.id,
        "verdict": fc.verdict.value
    }


@router.get("/fact-check/pending")
async def get_pending_fact_checks(
    limit: int = Query(50, ge=1, le=100)
) -> Dict[str, Any]:
    """Get pending fact-check requests for review."""
    from app.services.fact_check_service import get_fact_check_service

    service = get_fact_check_service()
    pending = service.get_pending_requests(limit)

    return {
        "pending": [
            {
                "id": r.id,
                "claim": r.claim,
                "user_hash": r.user_hash[:8] + "...",
                "submitted_at": r.submitted_at.isoformat()
            }
            for r in pending
        ],
        "count": len(pending)
    }
