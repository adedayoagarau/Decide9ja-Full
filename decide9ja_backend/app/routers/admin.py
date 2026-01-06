"""
Admin API Router
Endpoints for dashboard analytics, moderation, broadcasts, and fact-checks.
"""
import os
import json
import hashlib
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.services.analytics import (
    get_usage_stats,
    get_top_queries,
    get_unique_users,
    get_issue_analytics,
    generate_daily_report,
    generate_weekly_report,
)
from app.database import (
    SessionLocal, Politician, Issue, NewsArticle,
    BroadcastCampaign, BroadcastMessage, FactCheck, FactCheckRequest,
    CommunityIssue, CivicProfile, DigestSubscription, User
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# =====================
# Pydantic Models
# =====================

class BroadcastCreate(BaseModel):
    """Create a new broadcast campaign."""
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    category: str = Field(default="news")  # news, election, civic, alert
    message_content: str = Field(..., min_length=10, max_length=1600)
    message_title: Optional[str] = None
    cta_text: Optional[str] = None
    cta_options: Optional[List[str]] = None
    audience_criteria: Optional[dict] = None  # {states: [], lgas: [], interests: []}
    priority: str = Field(default="normal")  # breaking, high, normal, low
    scheduled_at: Optional[datetime] = None


class BroadcastUpdate(BaseModel):
    """Update a broadcast campaign."""
    name: Optional[str] = None
    description: Optional[str] = None
    message_content: Optional[str] = None
    audience_criteria: Optional[dict] = None
    status: Optional[str] = None  # draft, scheduled, paused, cancelled


class FactCheckCreate(BaseModel):
    """Create a fact-check result."""
    claim: str = Field(..., min_length=10)
    claimant: Optional[str] = None
    claim_date: Optional[datetime] = None
    verdict: str = Field(...)  # true, mostly_true, half_true, mostly_false, false, unverifiable
    explanation: str = Field(..., min_length=20)
    sources: List[dict] = []  # [{name, url}]
    category: Optional[str] = None
    is_viral: bool = False
    alert_level: str = "normal"


class FactCheckRequestUpdate(BaseModel):
    """Update a fact-check request status."""
    status: str  # processing, completed, rejected
    result_id: Optional[str] = None
    notes: Optional[str] = None


# =====================
# Analytics Endpoints
# =====================

@router.get("/stats")
async def get_stats(days: int = Query(7, ge=1, le=90)):
    """Get usage statistics for the past N days."""
    return get_usage_stats(days=days)


@router.get("/queries")
async def get_queries(days: int = Query(7, ge=1, le=90), limit: int = Query(20, ge=1, le=100)):
    """Get top queries for the past N days."""
    return {
        "period_days": days,
        "queries": get_top_queries(days=days, limit=limit)
    }


@router.get("/users")
async def get_users_estimate(days: int = Query(7, ge=1, le=90)):
    """Get estimated unique users for the past N days."""
    return {
        "period_days": days,
        "estimated_users": get_unique_users(days=days)
    }


@router.get("/issues/analytics")
async def get_issues_analytics():
    """Get issue tracking analytics."""
    return get_issue_analytics()


@router.get("/report/daily")
async def get_daily_report():
    """Generate daily analytics report."""
    return generate_daily_report()


@router.get("/report/weekly")
async def get_weekly_report():
    """Generate weekly analytics report."""
    return generate_weekly_report()


# =====================
# Overview Dashboard
# =====================

@router.get("/overview")
async def get_admin_overview():
    """Get comprehensive admin dashboard overview."""
    db = SessionLocal()
    try:
        # Quick counts
        politician_count = db.query(Politician).count()
        issue_count = db.query(Issue).filter(Issue.status == "active").count()
        severe_count = db.query(Issue).filter(
            Issue.status == "active",
            Issue.severity == "severe"
        ).count()
        news_count = db.query(NewsArticle).count()
        
        # Get usage stats
        usage = get_usage_stats(days=7)
        
        return {
            "counts": {
                "politicians": politician_count,
                "active_issues": issue_count,
                "severe_issues": severe_count,
                "news_articles": news_count,
            },
            "usage_7d": usage,
            "estimated_users_7d": get_unique_users(days=7),
        }
        
    finally:
        db.close()


# =====================
# Content Management
# =====================

@router.get("/politicians")
async def list_politicians(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    party: Optional[str] = None,
    state: Optional[str] = None,
):
    """List politicians for admin management."""
    db = SessionLocal()
    try:
        query = db.query(Politician)
        
        if party:
            query = query.filter(Politician.party == party)
        if state:
            query = query.filter(Politician.state == state)
        
        total = query.count()
        politicians = query.offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "politicians": [
                {
                    "slug": p.slug,
                    "name": p.name,
                    "party": p.party,
                    "position": p.position,
                    "state": p.state,
                }
                for p in politicians
            ]
        }
        
    finally:
        db.close()


@router.get("/news")
async def list_news(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    processed: Optional[bool] = None,
):
    """List news articles for admin review."""
    db = SessionLocal()
    try:
        query = db.query(NewsArticle)
        
        if source:
            query = query.filter(NewsArticle.source == source)
        if processed is not None:
            query = query.filter(NewsArticle.is_processed == processed)
        
        total = query.count()
        articles = query.order_by(NewsArticle.scraped_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "articles": [
                {
                    "id": a.article_id,
                    "title": a.title,
                    "source": a.source_name,
                    "url": a.url,
                    "scraped_at": a.scraped_at.isoformat() if a.scraped_at else None,
                    "is_processed": a.is_processed,
                }
                for a in articles
            ]
        }
        
    finally:
        db.close()


# =====================
# System Health
# =====================

@router.get("/health")
async def admin_health_check():
    """Detailed health check for admin."""
    db = SessionLocal()
    try:
        from app.database import Document

        politicians = db.query(Politician).count()
        documents = db.query(Document).count()
        issues = db.query(Issue).count()
        news = db.query(NewsArticle).count()

        return {
            "status": "healthy",
            "database": {
                "politicians": politicians,
                "documents": documents,
                "issues": issues,
                "news_articles": news,
            },
            "services": {
                "rag": "ok",
                "llm": "ok" if os.getenv("ANTHROPIC_API_KEY") else "missing_key",
                "scheduler": "unknown",  # Would need to check scheduler health
            }
        }

    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
    finally:
        db.close()


# =====================
# BROADCAST MANAGEMENT
# =====================

@router.get("/broadcasts")
async def list_broadcasts(
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all broadcast campaigns."""
    db = SessionLocal()
    try:
        query = db.query(BroadcastCampaign)

        if status:
            query = query.filter(BroadcastCampaign.status == status)
        if category:
            query = query.filter(BroadcastCampaign.category == category)

        total = query.count()
        campaigns = query.order_by(BroadcastCampaign.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "campaigns": [
                {
                    "campaign_id": c.campaign_id,
                    "name": c.name,
                    "description": c.description,
                    "category": c.category,
                    "status": c.status,
                    "priority": c.priority,
                    "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
                    "stats": {
                        "total_recipients": c.total_recipients,
                        "sent": c.sent_count,
                        "delivered": c.delivered_count,
                        "read": c.read_count,
                        "replied": c.replied_count,
                        "failed": c.failed_count,
                    },
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in campaigns
            ]
        }
    finally:
        db.close()


@router.get("/broadcasts/{campaign_id}")
async def get_broadcast(campaign_id: str):
    """Get a specific broadcast campaign with details."""
    db = SessionLocal()
    try:
        campaign = db.query(BroadcastCampaign).filter(
            BroadcastCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Get message stats
        messages = db.query(BroadcastMessage).filter(
            BroadcastMessage.campaign_id == campaign_id
        ).all()

        message_stats = {
            "queued": sum(1 for m in messages if m.status == "queued"),
            "sent": sum(1 for m in messages if m.status == "sent"),
            "delivered": sum(1 for m in messages if m.status == "delivered"),
            "read": sum(1 for m in messages if m.status == "read"),
            "failed": sum(1 for m in messages if m.status == "failed"),
        }

        return {
            "campaign_id": campaign.campaign_id,
            "name": campaign.name,
            "description": campaign.description,
            "category": campaign.category,
            "message_content": campaign.message_content,
            "message_title": campaign.message_title,
            "cta_text": campaign.cta_text,
            "cta_options": json.loads(campaign.cta_options_json) if campaign.cta_options_json else None,
            "audience_criteria": json.loads(campaign.audience_criteria_json) if campaign.audience_criteria_json else None,
            "priority": campaign.priority,
            "status": campaign.status,
            "scheduled_at": campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
            "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
            "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
            "stats": {
                "total_recipients": campaign.total_recipients,
                "sent": campaign.sent_count,
                "delivered": campaign.delivered_count,
                "read": campaign.read_count,
                "replied": campaign.replied_count,
                "failed": campaign.failed_count,
            },
            "message_breakdown": message_stats,
            "created_by": campaign.created_by,
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        }
    finally:
        db.close()


@router.post("/broadcasts")
async def create_broadcast(data: BroadcastCreate):
    """Create a new broadcast campaign."""
    db = SessionLocal()
    try:
        import uuid
        campaign_id = f"BC{uuid.uuid4().hex[:12].upper()}"

        campaign = BroadcastCampaign(
            campaign_id=campaign_id,
            name=data.name,
            description=data.description,
            category=data.category,
            message_content=data.message_content,
            message_title=data.message_title,
            cta_text=data.cta_text,
            cta_options_json=json.dumps(data.cta_options) if data.cta_options else None,
            audience_criteria_json=json.dumps(data.audience_criteria) if data.audience_criteria else None,
            priority=data.priority,
            scheduled_at=data.scheduled_at,
            status="draft" if not data.scheduled_at else "scheduled",
        )

        db.add(campaign)
        db.commit()

        logger.info(f"Created broadcast campaign: {campaign_id}")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": campaign.status,
            "message": "Campaign created successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create broadcast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.put("/broadcasts/{campaign_id}")
async def update_broadcast(campaign_id: str, data: BroadcastUpdate):
    """Update a broadcast campaign."""
    db = SessionLocal()
    try:
        campaign = db.query(BroadcastCampaign).filter(
            BroadcastCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Only allow updates if draft or scheduled
        if campaign.status not in ["draft", "scheduled", "paused"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot update campaign with status: {campaign.status}"
            )

        if data.name:
            campaign.name = data.name
        if data.description is not None:
            campaign.description = data.description
        if data.message_content:
            campaign.message_content = data.message_content
        if data.audience_criteria is not None:
            campaign.audience_criteria_json = json.dumps(data.audience_criteria)
        if data.status:
            campaign.status = data.status

        db.commit()

        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": campaign.status,
            "message": "Campaign updated successfully"
        }
    finally:
        db.close()


@router.post("/broadcasts/{campaign_id}/schedule")
async def schedule_broadcast(campaign_id: str, scheduled_at: datetime = Body(...)):
    """Schedule a broadcast campaign for sending."""
    db = SessionLocal()
    try:
        campaign = db.query(BroadcastCampaign).filter(
            BroadcastCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if campaign.status not in ["draft", "paused"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot schedule campaign with status: {campaign.status}"
            )

        # Queue messages for recipients
        from app.services.broadcast_service import BroadcastService
        service = BroadcastService()

        # Get audience based on criteria
        audience_criteria = json.loads(campaign.audience_criteria_json) if campaign.audience_criteria_json else {}
        recipients = service._get_audience(audience_criteria, db)

        # Queue messages
        queued_count = 0
        for user_hash in recipients:
            import uuid
            msg = BroadcastMessage(
                message_id=f"BM{uuid.uuid4().hex[:12].upper()}",
                campaign_id=campaign_id,
                user_hash=user_hash,
                content=campaign.message_content,
                priority=campaign.priority,
                status="queued"
            )
            db.add(msg)
            queued_count += 1

        campaign.scheduled_at = scheduled_at
        campaign.status = "scheduled"
        campaign.total_recipients = queued_count

        db.commit()

        logger.info(f"Scheduled broadcast {campaign_id} for {scheduled_at} with {queued_count} recipients")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "scheduled_at": scheduled_at.isoformat(),
            "total_recipients": queued_count,
            "message": "Campaign scheduled successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to schedule broadcast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/broadcasts/{campaign_id}/send-now")
async def send_broadcast_now(campaign_id: str):
    """Send a broadcast campaign immediately."""
    db = SessionLocal()
    try:
        campaign = db.query(BroadcastCampaign).filter(
            BroadcastCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if campaign.status not in ["draft", "scheduled", "paused"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot send campaign with status: {campaign.status}"
            )

        # If no messages queued yet, queue them
        existing_messages = db.query(BroadcastMessage).filter(
            BroadcastMessage.campaign_id == campaign_id
        ).count()

        if existing_messages == 0:
            from app.services.broadcast_service import BroadcastService
            service = BroadcastService()

            audience_criteria = json.loads(campaign.audience_criteria_json) if campaign.audience_criteria_json else {}
            recipients = service._get_audience(audience_criteria, db)

            import uuid
            for user_hash in recipients:
                msg = BroadcastMessage(
                    message_id=f"BM{uuid.uuid4().hex[:12].upper()}",
                    campaign_id=campaign_id,
                    user_hash=user_hash,
                    content=campaign.message_content,
                    priority=campaign.priority,
                    status="queued"
                )
                db.add(msg)

            campaign.total_recipients = len(recipients)

        campaign.status = "sending"
        campaign.started_at = datetime.utcnow()
        campaign.scheduled_at = datetime.utcnow()

        db.commit()

        logger.info(f"Started immediate send for broadcast {campaign_id}")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": "sending",
            "total_recipients": campaign.total_recipients,
            "message": "Campaign sending started - messages will be delivered via scheduler"
        }
    finally:
        db.close()


@router.post("/broadcasts/{campaign_id}/pause")
async def pause_broadcast(campaign_id: str):
    """Pause a sending broadcast campaign."""
    db = SessionLocal()
    try:
        campaign = db.query(BroadcastCampaign).filter(
            BroadcastCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if campaign.status != "sending":
            raise HTTPException(
                status_code=400,
                detail=f"Can only pause campaigns that are sending"
            )

        campaign.status = "paused"
        db.commit()

        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": "paused",
            "message": "Campaign paused"
        }
    finally:
        db.close()


@router.post("/broadcasts/{campaign_id}/cancel")
async def cancel_broadcast(campaign_id: str):
    """Cancel a broadcast campaign."""
    db = SessionLocal()
    try:
        campaign = db.query(BroadcastCampaign).filter(
            BroadcastCampaign.campaign_id == campaign_id
        ).first()

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if campaign.status == "completed":
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel completed campaign"
            )

        campaign.status = "cancelled"

        # Cancel queued messages
        db.query(BroadcastMessage).filter(
            BroadcastMessage.campaign_id == campaign_id,
            BroadcastMessage.status == "queued"
        ).update({"status": "cancelled"})

        db.commit()

        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": "cancelled",
            "message": "Campaign cancelled"
        }
    finally:
        db.close()


# =====================
# FACT-CHECK MANAGEMENT
# =====================

@router.get("/fact-checks/requests")
async def list_fact_check_requests(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List fact-check requests from users."""
    db = SessionLocal()
    try:
        query = db.query(FactCheckRequest)

        if status:
            query = query.filter(FactCheckRequest.status == status)

        total = query.count()
        requests = query.order_by(FactCheckRequest.submitted_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "pending_count": db.query(FactCheckRequest).filter(FactCheckRequest.status == "pending").count(),
            "requests": [
                {
                    "request_id": r.request_id,
                    "claim": r.claim,
                    "user_hash": r.user_hash[:12] + "...",  # Truncate for privacy
                    "status": r.status,
                    "result_id": r.result_id,
                    "assigned_to": r.assigned_to,
                    "notes": r.notes,
                    "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                    "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                }
                for r in requests
            ]
        }
    finally:
        db.close()


@router.put("/fact-checks/requests/{request_id}")
async def update_fact_check_request(request_id: str, data: FactCheckRequestUpdate):
    """Update a fact-check request status."""
    db = SessionLocal()
    try:
        request = db.query(FactCheckRequest).filter(
            FactCheckRequest.request_id == request_id
        ).first()

        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        request.status = data.status
        if data.result_id:
            request.result_id = data.result_id
        if data.notes:
            request.notes = data.notes
        if data.status in ["completed", "rejected"]:
            request.processed_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "request_id": request_id,
            "status": request.status,
            "message": "Request updated"
        }
    finally:
        db.close()


@router.get("/fact-checks")
async def list_fact_checks(
    verdict: Optional[str] = None,
    category: Optional[str] = None,
    is_viral: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all fact-checks."""
    db = SessionLocal()
    try:
        query = db.query(FactCheck)

        if verdict:
            query = query.filter(FactCheck.verdict == verdict)
        if category:
            query = query.filter(FactCheck.category == category)
        if is_viral is not None:
            query = query.filter(FactCheck.is_viral == is_viral)

        total = query.count()
        fact_checks = query.order_by(FactCheck.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "fact_checks": [
                {
                    "fact_check_id": fc.fact_check_id,
                    "claim": fc.claim[:200] + "..." if len(fc.claim) > 200 else fc.claim,
                    "claimant": fc.claimant,
                    "verdict": fc.verdict,
                    "category": fc.category,
                    "is_viral": fc.is_viral,
                    "alert_level": fc.alert_level,
                    "times_queried": fc.times_queried,
                    "created_at": fc.created_at.isoformat() if fc.created_at else None,
                }
                for fc in fact_checks
            ]
        }
    finally:
        db.close()


@router.get("/fact-checks/{fact_check_id}")
async def get_fact_check(fact_check_id: str):
    """Get a specific fact-check with full details."""
    db = SessionLocal()
    try:
        fc = db.query(FactCheck).filter(
            FactCheck.fact_check_id == fact_check_id
        ).first()

        if not fc:
            raise HTTPException(status_code=404, detail="Fact-check not found")

        return {
            "fact_check_id": fc.fact_check_id,
            "claim": fc.claim,
            "claimant": fc.claimant,
            "claim_date": fc.claim_date.isoformat() if fc.claim_date else None,
            "claim_context": fc.claim_context,
            "verdict": fc.verdict,
            "explanation": fc.explanation,
            "sources": json.loads(fc.sources_json) if fc.sources_json else [],
            "category": fc.category,
            "tags": json.loads(fc.tags_json) if fc.tags_json else [],
            "is_viral": fc.is_viral,
            "alert_level": fc.alert_level,
            "times_queried": fc.times_queried,
            "checked_by": fc.checked_by,
            "verified": fc.verified,
            "created_at": fc.created_at.isoformat() if fc.created_at else None,
            "updated_at": fc.updated_at.isoformat() if fc.updated_at else None,
        }
    finally:
        db.close()


@router.post("/fact-checks")
async def create_fact_check(data: FactCheckCreate):
    """Create a new fact-check."""
    db = SessionLocal()
    try:
        import uuid
        fact_check_id = f"FC{uuid.uuid4().hex[:12].upper()}"
        claim_hash = hashlib.sha256(data.claim.lower().encode()).hexdigest()

        # Check for duplicate
        existing = db.query(FactCheck).filter(FactCheck.claim_hash == claim_hash).first()
        if existing:
            return {
                "success": False,
                "error": "duplicate",
                "existing_id": existing.fact_check_id,
                "message": "A fact-check for this claim already exists"
            }

        fc = FactCheck(
            fact_check_id=fact_check_id,
            claim=data.claim,
            claim_hash=claim_hash,
            claimant=data.claimant,
            claim_date=data.claim_date,
            verdict=data.verdict,
            explanation=data.explanation,
            sources_json=json.dumps(data.sources) if data.sources else None,
            category=data.category,
            is_viral=data.is_viral,
            alert_level=data.alert_level,
            verified=True,
        )

        db.add(fc)
        db.commit()

        logger.info(f"Created fact-check: {fact_check_id} - verdict: {data.verdict}")

        return {
            "success": True,
            "fact_check_id": fact_check_id,
            "verdict": data.verdict,
            "message": "Fact-check created successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create fact-check: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.put("/fact-checks/{fact_check_id}")
async def update_fact_check(fact_check_id: str, data: FactCheckCreate):
    """Update an existing fact-check."""
    db = SessionLocal()
    try:
        fc = db.query(FactCheck).filter(
            FactCheck.fact_check_id == fact_check_id
        ).first()

        if not fc:
            raise HTTPException(status_code=404, detail="Fact-check not found")

        fc.claim = data.claim
        fc.claimant = data.claimant
        fc.claim_date = data.claim_date
        fc.verdict = data.verdict
        fc.explanation = data.explanation
        fc.sources_json = json.dumps(data.sources) if data.sources else None
        fc.category = data.category
        fc.is_viral = data.is_viral
        fc.alert_level = data.alert_level

        db.commit()

        return {
            "success": True,
            "fact_check_id": fact_check_id,
            "message": "Fact-check updated"
        }
    finally:
        db.close()


# =====================
# COMMUNITY MANAGEMENT
# =====================

@router.get("/community/issues")
async def list_community_issues(
    status: Optional[str] = None,
    category: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List community-reported issues for moderation."""
    db = SessionLocal()
    try:
        query = db.query(CommunityIssue)

        if status:
            query = query.filter(CommunityIssue.status == status)
        if category:
            query = query.filter(CommunityIssue.category == category)
        if state:
            query = query.filter(CommunityIssue.state == state)

        total = query.count()
        issues = query.order_by(CommunityIssue.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "pending_count": db.query(CommunityIssue).filter(CommunityIssue.status == "reported").count(),
            "issues": [
                {
                    "issue_id": i.issue_id,
                    "title": i.title,
                    "category": i.category,
                    "state": i.state,
                    "lga": i.lga,
                    "status": i.status,
                    "upvotes": i.upvotes,
                    "verification_count": i.verification_count,
                    "reporter_hash": i.reporter_hash[:12] + "...",
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
                for i in issues
            ]
        }
    finally:
        db.close()


@router.put("/community/issues/{issue_id}/status")
async def update_community_issue_status(
    issue_id: str,
    status: str = Body(...),
    official_response: Optional[str] = Body(None),
):
    """Update status of a community issue (moderation)."""
    db = SessionLocal()
    try:
        issue = db.query(CommunityIssue).filter(
            CommunityIssue.issue_id == issue_id
        ).first()

        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        valid_statuses = ["reported", "verified", "acknowledged", "in_progress", "resolved", "closed", "rejected"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

        issue.status = status
        if official_response:
            issue.official_response = official_response
        if status == "resolved":
            issue.resolved_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "issue_id": issue_id,
            "status": status,
            "message": "Issue status updated"
        }
    finally:
        db.close()


# =====================
# ENHANCED ANALYTICS
# =====================

@router.get("/analytics/broadcasts")
async def get_broadcast_analytics(days: int = Query(30, ge=1, le=90)):
    """Get broadcast analytics and performance metrics."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        campaigns = db.query(BroadcastCampaign).filter(
            BroadcastCampaign.created_at >= cutoff
        ).all()

        total_sent = sum(c.sent_count or 0 for c in campaigns)
        total_delivered = sum(c.delivered_count or 0 for c in campaigns)
        total_read = sum(c.read_count or 0 for c in campaigns)
        total_replied = sum(c.replied_count or 0 for c in campaigns)

        return {
            "period_days": days,
            "total_campaigns": len(campaigns),
            "campaigns_by_status": {
                "draft": sum(1 for c in campaigns if c.status == "draft"),
                "scheduled": sum(1 for c in campaigns if c.status == "scheduled"),
                "sending": sum(1 for c in campaigns if c.status == "sending"),
                "completed": sum(1 for c in campaigns if c.status == "completed"),
                "paused": sum(1 for c in campaigns if c.status == "paused"),
                "cancelled": sum(1 for c in campaigns if c.status == "cancelled"),
            },
            "message_stats": {
                "total_sent": total_sent,
                "total_delivered": total_delivered,
                "total_read": total_read,
                "total_replied": total_replied,
                "delivery_rate": round(total_delivered / total_sent * 100, 1) if total_sent > 0 else 0,
                "read_rate": round(total_read / total_delivered * 100, 1) if total_delivered > 0 else 0,
                "reply_rate": round(total_replied / total_delivered * 100, 1) if total_delivered > 0 else 0,
            },
            "by_category": {
                cat: sum(c.sent_count or 0 for c in campaigns if c.category == cat)
                for cat in ["news", "election", "civic", "alert", "digest"]
            }
        }
    finally:
        db.close()


@router.get("/analytics/fact-checks")
async def get_fact_check_analytics(days: int = Query(30, ge=1, le=90)):
    """Get fact-check analytics."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        fact_checks = db.query(FactCheck).filter(
            FactCheck.created_at >= cutoff
        ).all()

        requests = db.query(FactCheckRequest).filter(
            FactCheckRequest.submitted_at >= cutoff
        ).all()

        return {
            "period_days": days,
            "total_fact_checks": len(fact_checks),
            "total_requests": len(requests),
            "pending_requests": sum(1 for r in requests if r.status == "pending"),
            "verdicts": {
                "true": sum(1 for fc in fact_checks if fc.verdict == "true"),
                "mostly_true": sum(1 for fc in fact_checks if fc.verdict == "mostly_true"),
                "half_true": sum(1 for fc in fact_checks if fc.verdict == "half_true"),
                "mostly_false": sum(1 for fc in fact_checks if fc.verdict == "mostly_false"),
                "false": sum(1 for fc in fact_checks if fc.verdict == "false"),
                "unverifiable": sum(1 for fc in fact_checks if fc.verdict == "unverifiable"),
            },
            "viral_claims": sum(1 for fc in fact_checks if fc.is_viral),
            "total_queries": sum(fc.times_queried or 0 for fc in fact_checks),
            "most_queried": [
                {"claim": fc.claim[:100], "times_queried": fc.times_queried}
                for fc in sorted(fact_checks, key=lambda x: x.times_queried or 0, reverse=True)[:5]
            ]
        }
    finally:
        db.close()


@router.get("/analytics/community")
async def get_community_analytics(days: int = Query(30, ge=1, le=90)):
    """Get community engagement analytics."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        issues = db.query(CommunityIssue).filter(
            CommunityIssue.created_at >= cutoff
        ).all()

        profiles = db.query(CivicProfile).all()

        return {
            "period_days": days,
            "community_issues": {
                "total_reported": len(issues),
                "by_status": {
                    "reported": sum(1 for i in issues if i.status == "reported"),
                    "verified": sum(1 for i in issues if i.status == "verified"),
                    "acknowledged": sum(1 for i in issues if i.status == "acknowledged"),
                    "in_progress": sum(1 for i in issues if i.status == "in_progress"),
                    "resolved": sum(1 for i in issues if i.status == "resolved"),
                },
                "by_category": {
                    cat: sum(1 for i in issues if i.category == cat)
                    for cat in ["roads", "electricity", "water", "security", "sanitation", "education", "health"]
                },
                "total_upvotes": sum(i.upvotes or 0 for i in issues),
            },
            "civic_profiles": {
                "total_users": len(profiles),
                "total_points_awarded": sum(p.total_points or 0 for p in profiles),
                "active_streaks": sum(1 for p in profiles if (p.current_streak or 0) > 0),
                "level_distribution": {
                    f"level_{i}": sum(1 for p in profiles if p.level == i)
                    for i in range(1, 11)
                }
            }
        }
    finally:
        db.close()


@router.get("/analytics/users")
async def get_user_analytics(days: int = Query(30, ge=1, le=90)):
    """Get user engagement analytics."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        users = db.query(User).all()
        active_users = db.query(User).filter(User.last_interaction >= cutoff).count()
        onboarded_users = db.query(User).filter(User.onboarding_completed == True).count()

        digest_subs = db.query(DigestSubscription).filter(DigestSubscription.is_active == True).count()

        # State distribution
        state_counts = {}
        for u in users:
            if u.state:
                state_counts[u.state] = state_counts.get(u.state, 0) + 1

        top_states = sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "period_days": days,
            "total_users": len(users),
            "active_users": active_users,
            "onboarded_users": onboarded_users,
            "onboarding_rate": round(onboarded_users / len(users) * 100, 1) if users else 0,
            "digest_subscribers": digest_subs,
            "top_states": [{"state": s, "count": c} for s, c in top_states],
        }
    finally:
        db.close()
