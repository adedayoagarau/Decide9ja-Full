"""
Notifications API Router for Decide9ja.

Provides endpoints for:
- Managing user subscriptions (follow/unfollow politicians, issues)
- Viewing notification history
- Notification preferences

All endpoints use user_hash for privacy (phone numbers never transmitted).
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import hashlib

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# =============================================================================
# Request/Response Models
# =============================================================================

class SubscribeRequest(BaseModel):
    """Request to subscribe to notifications."""
    phone_hash: str = Field(..., description="SHA256 hash of user's phone number")
    subscription_type: str = Field(..., description="Type: politician, issue, topic, state")
    target_id: str = Field(..., description="ID of target (politician slug, issue_id, etc.)")
    target_name: Optional[str] = Field(None, description="Human readable name")
    notify_news: bool = Field(True, description="Notify on news mentions")
    notify_updates: bool = Field(True, description="Notify on status updates")
    notify_daily_digest: bool = Field(False, description="Include in daily digest")


class UnsubscribeRequest(BaseModel):
    """Request to unsubscribe from notifications."""
    phone_hash: str = Field(..., description="SHA256 hash of user's phone number")
    subscription_type: Optional[str] = Field(None, description="Type to unsubscribe from")
    target_id: Optional[str] = Field(None, description="Specific target to unsubscribe from")
    subscription_id: Optional[int] = Field(None, description="Specific subscription ID")


class SubscriptionResponse(BaseModel):
    """Subscription details."""
    id: int
    type: str
    target_id: str
    target_name: Optional[str]
    notify_news: bool
    notify_updates: bool
    notify_daily_digest: bool
    created_at: Optional[str]


class NotificationResponse(BaseModel):
    """Notification details."""
    notification_id: str
    notification_type: str
    title: str
    body: str
    status: str
    created_at: str
    sent_at: Optional[str]
    reference_type: Optional[str]
    reference_id: Optional[str]


class QuickFollowRequest(BaseModel):
    """Quick follow request for chatbot integration."""
    phone_hash: str
    target_type: str  # politician or issue
    target_id: str


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/subscribe")
async def subscribe(request: SubscribeRequest):
    """
    Subscribe to notifications for a politician, issue, topic, or state.

    Example:
        POST /api/notifications/subscribe
        {
            "phone_hash": "abc123...",
            "subscription_type": "politician",
            "target_id": "bola-tinubu",
            "target_name": "Bola Tinubu",
            "notify_news": true,
            "notify_updates": true
        }
    """
    from app.services.notification_service import get_notification_service

    service = get_notification_service()

    result = service.subscribe(
        user_hash=request.phone_hash,
        subscription_type=request.subscription_type,
        target_id=request.target_id,
        target_name=request.target_name,
        notify_news=request.notify_news,
        notify_updates=request.notify_updates,
        notify_daily_digest=request.notify_daily_digest
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to subscribe"))

    return result


@router.post("/unsubscribe")
async def unsubscribe(request: UnsubscribeRequest):
    """
    Unsubscribe from notifications.

    Can unsubscribe by:
    - subscription_id (specific subscription)
    - subscription_type + target_id (specific target)
    - subscription_type only (all of that type)
    - None (all subscriptions)
    """
    from app.services.notification_service import get_notification_service

    service = get_notification_service()

    result = service.unsubscribe(
        user_hash=request.phone_hash,
        subscription_type=request.subscription_type,
        target_id=request.target_id,
        subscription_id=request.subscription_id
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to unsubscribe"))

    return result


@router.get("/subscriptions/{phone_hash}")
async def get_subscriptions(phone_hash: str) -> List[SubscriptionResponse]:
    """
    Get all active subscriptions for a user.

    Args:
        phone_hash: SHA256 hash of user's phone number
    """
    from app.services.notification_service import get_notification_service

    service = get_notification_service()
    subscriptions = service.get_subscriptions(phone_hash)

    return [SubscriptionResponse(**s) for s in subscriptions]


@router.get("/history/{phone_hash}")
async def get_notification_history(
    phone_hash: str,
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: pending, sent, failed")
) -> List[NotificationResponse]:
    """
    Get notification history for a user.

    Args:
        phone_hash: SHA256 hash of user's phone number
        limit: Maximum number of notifications to return
        status: Optional status filter
    """
    from app.database import SessionLocal, Notification

    db = SessionLocal()
    try:
        query = db.query(Notification).filter(
            Notification.user_hash == phone_hash
        )

        if status:
            query = query.filter(Notification.status == status)

        notifications = query.order_by(
            Notification.created_at.desc()
        ).limit(limit).all()

        return [
            NotificationResponse(
                notification_id=n.notification_id,
                notification_type=n.notification_type,
                title=n.title,
                body=n.body[:200] + "..." if len(n.body) > 200 else n.body,
                status=n.status,
                created_at=n.created_at.isoformat() if n.created_at else "",
                sent_at=n.sent_at.isoformat() if n.sent_at else None,
                reference_type=n.reference_type,
                reference_id=n.reference_id
            )
            for n in notifications
        ]
    finally:
        db.close()


@router.post("/quick-follow")
async def quick_follow(request: QuickFollowRequest):
    """
    Quick follow endpoint for chatbot integration.

    Simplified subscription for WhatsApp bot:
    - "Follow Tinubu" -> subscribe to politician
    - "Track power issue" -> subscribe to issue
    """
    from app.services.notification_service import get_notification_service
    from app.database import SessionLocal, Politician, Issue

    service = get_notification_service()
    db = SessionLocal()

    try:
        # Get target name
        target_name = request.target_id

        if request.target_type == "politician":
            politician = db.query(Politician).filter(
                Politician.slug == request.target_id
            ).first()
            if politician:
                target_name = politician.name

        elif request.target_type == "issue":
            issue = db.query(Issue).filter(
                Issue.issue_id == request.target_id
            ).first()
            if issue:
                target_name = issue.title

        result = service.subscribe(
            user_hash=request.phone_hash,
            subscription_type=request.target_type,
            target_id=request.target_id,
            target_name=target_name,
            notify_news=True,
            notify_updates=True,
            notify_daily_digest=False
        )

        if result.get("success"):
            return {
                "success": True,
                "message": f"✅ You're now following {target_name}. You'll be notified of important updates.",
                "target_name": target_name
            }
        else:
            return {
                "success": False,
                "message": f"Failed to follow {target_name}. Please try again.",
                "error": result.get("error")
            }

    finally:
        db.close()


@router.post("/quick-unfollow")
async def quick_unfollow(request: QuickFollowRequest):
    """
    Quick unfollow endpoint for chatbot integration.
    """
    from app.services.notification_service import get_notification_service

    service = get_notification_service()

    result = service.unsubscribe(
        user_hash=request.phone_hash,
        subscription_type=request.target_type,
        target_id=request.target_id
    )

    if result.get("success") and result.get("count", 0) > 0:
        return {
            "success": True,
            "message": f"✅ You've unfollowed this. You won't receive updates anymore."
        }
    else:
        return {
            "success": False,
            "message": "You weren't following this item."
        }


@router.get("/digest-preview/{phone_hash}")
async def get_digest_preview(phone_hash: str):
    """
    Preview what the daily digest would contain for a user.

    Useful for testing and showing users what they'll receive.
    """
    from app.services.notification_service import get_notification_service

    service = get_notification_service()
    digest = service.generate_daily_digest(phone_hash)

    if not digest:
        return {
            "has_content": False,
            "message": "No updates to report. Subscribe to politicians or issues to receive daily digests."
        }

    return {
        "has_content": True,
        "digest": digest
    }


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.get("/admin/stats")
async def get_notification_stats():
    """
    Get notification system statistics (admin only).
    """
    from app.database import SessionLocal, Notification, UserSubscription
    from datetime import timedelta

    db = SessionLocal()
    try:
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        # Notification stats
        total_notifications = db.query(Notification).count()
        pending = db.query(Notification).filter(Notification.status == "pending").count()
        sent_today = db.query(Notification).filter(
            Notification.status == "sent",
            Notification.sent_at >= day_ago
        ).count()
        failed = db.query(Notification).filter(Notification.status == "failed").count()

        # Subscription stats
        total_subscriptions = db.query(UserSubscription).filter(
            UserSubscription.is_active == True
        ).count()

        subscription_by_type = {}
        for row in db.query(
            UserSubscription.subscription_type,
        ).filter(UserSubscription.is_active == True).distinct().all():
            count = db.query(UserSubscription).filter(
                UserSubscription.subscription_type == row[0],
                UserSubscription.is_active == True
            ).count()
            subscription_by_type[row[0]] = count

        return {
            "notifications": {
                "total": total_notifications,
                "pending": pending,
                "sent_today": sent_today,
                "failed": failed
            },
            "subscriptions": {
                "total_active": total_subscriptions,
                "by_type": subscription_by_type
            },
            "timestamp": now.isoformat()
        }

    finally:
        db.close()


@router.post("/admin/trigger-digests")
async def trigger_daily_digests():
    """
    Manually trigger daily digest sending (admin only).

    Useful for testing or catching up after downtime.
    """
    from app.services.notification_service import get_notification_service

    service = get_notification_service()
    result = await service.send_all_daily_digests()

    return {
        "success": True,
        "result": result
    }


@router.post("/admin/process-queue")
async def process_notification_queue(batch_size: int = Query(50, ge=1, le=200)):
    """
    Process pending notifications in the queue (admin only).

    Normally called by scheduler, but can be triggered manually.
    """
    from app.services.notification_service import get_notification_service

    service = get_notification_service()
    result = await service.process_pending_notifications(batch_size)

    return {
        "success": True,
        "result": result
    }
