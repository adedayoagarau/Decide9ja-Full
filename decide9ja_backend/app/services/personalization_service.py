"""
User Personalization Service for Decide9ja.

Provides features for:
- My Representatives: Find politicians based on user's location
- Saved Politicians: Follow/unfollow politicians
- Saved Issues: Track specific issues
- User Interests: Topic preferences for personalized feeds
- User Preferences: Language, notification, display settings

Usage:
    from app.services.personalization_service import PersonalizationService

    service = PersonalizationService()
    reps = service.get_my_representatives("lagos", "ikeja")
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from app.database import (
    SessionLocal, User, Politician, UserSubscription,
    Issue, NewsArticle
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RepresentativeInfo:
    """Information about a user's representative."""
    slug: str
    name: str
    position: str
    party: Optional[str]
    state: Optional[str]
    constituency: Optional[str]
    level: str  # federal, state, local
    chamber: Optional[str]  # senate, house, state_assembly
    image_url: Optional[str] = None
    contact_info: Dict[str, str] = field(default_factory=dict)


@dataclass
class SavedPolitician:
    """A saved/followed politician."""
    slug: str
    name: str
    party: Optional[str]
    position: Optional[str]
    saved_at: str
    notify_news: bool = True
    notify_updates: bool = True


@dataclass
class SavedIssue:
    """A saved/tracked issue."""
    issue_id: str
    title: str
    domain: str
    status: str
    saved_at: str
    notify_updates: bool = True


@dataclass
class UserInterests:
    """User's topic interests."""
    topics: List[str]
    domains: List[str]  # power, roads, security, etc.
    states: List[str]  # States of interest beyond home state
    updated_at: str


@dataclass
class UserPreferences:
    """User's app preferences."""
    language: str = "en"
    notification_frequency: str = "instant"  # instant, daily_digest, weekly
    notification_channels: List[str] = field(default_factory=lambda: ["whatsapp"])
    news_sources: List[str] = field(default_factory=list)  # Preferred news sources
    content_style: str = "detailed"  # brief, detailed
    accessibility_mode: bool = False


@dataclass
class PersonalizedDashboard:
    """User's personalized dashboard data."""
    representatives: List[RepresentativeInfo]
    saved_politicians: List[SavedPolitician]
    saved_issues: List[SavedIssue]
    interests: UserInterests
    recent_activity: List[Dict]
    recommendations: List[Dict]


# =============================================================================
# Nigerian State/LGA to Constituency Mapping
# =============================================================================

# Mapping of states to their senatorial districts
SENATORIAL_DISTRICTS = {
    "lagos": {
        "lagos-west": ["alimosho", "agege", "ifako-ijaiye", "mushin", "oshodi-isolo"],
        "lagos-central": ["lagos-island", "lagos-mainland", "apapa", "surulere", "eti-osa"],
        "lagos-east": ["ikorodu", "epe", "ibeju-lekki", "shomolu", "kosofe"]
    },
    "kano": {
        "kano-central": ["kano-municipal", "dala", "nassarawa", "gwale", "fagge", "tarauni", "ungogo", "kumbotso"],
        "kano-north": ["dawakin-tofa", "bagwai", "gwarzo", "kabo", "makoda", "kunchi", "bichi", "tsanyawa", "shanono", "dambatta", "gezawa", "gabasawa", "minjibir", "tofa"],
        "kano-south": ["madobi", "karaye", "rogo", "kiru", "bebeji", "kura", "garun-mallam", "wudil", "garko", "albasu", "tudun-wada", "doguwa", "kibiya", "rano", "sumaila"]
    },
    # Add more states as needed
}

# Federal constituencies (simplified - in production would be comprehensive)
FEDERAL_CONSTITUENCIES = {
    "lagos": {
        "alimosho": "alimosho",
        "agege": "agege",
        "ifako-ijaiye": "ifako-ijaiye",
        "ikeja": "ikeja",
        "mushin": "mushin-i",
        "surulere": "surulere-i",
        "lagos-island": "lagos-island-i",
        "eti-osa": "eti-osa-i",
        "ikorodu": "ikorodu",
        "epe": "epe",
    },
    # Add more states as needed
}


# =============================================================================
# Service Class
# =============================================================================

class PersonalizationService:
    """
    Service for user personalization features.
    """

    def __init__(self):
        pass

    # =========================================================================
    # My Representatives
    # =========================================================================

    def get_my_representatives(
        self,
        state: str,
        lga: Optional[str] = None
    ) -> List[RepresentativeInfo]:
        """
        Get all representatives for a user based on their location.

        Returns:
            - President
            - Senator (senatorial district)
            - House of Reps member (federal constituency)
            - Governor
            - State Assembly member (if LGA known)
        """
        db = SessionLocal()
        try:
            representatives = []
            state_lower = state.lower().replace(" ", "-")

            # 1. President (always included)
            president = db.query(Politician).filter(
                Politician.position == "President"
            ).first()
            if president:
                representatives.append(self._politician_to_rep(president, "federal", None))

            # 2. Senator for the state
            # Try to find by senatorial district if LGA is known
            senator = db.query(Politician).filter(
                Politician.position == "Senator",
                Politician.state.ilike(f"%{state}%")
            ).first()
            if senator:
                representatives.append(self._politician_to_rep(senator, "federal", "senate"))

            # 3. House of Reps member
            house_member = db.query(Politician).filter(
                Politician.position == "House Member",
                Politician.state.ilike(f"%{state}%")
            ).first()
            if house_member:
                representatives.append(self._politician_to_rep(house_member, "federal", "house"))

            # 4. Governor
            governor = db.query(Politician).filter(
                Politician.position == "Governor",
                Politician.state.ilike(f"%{state}%")
            ).first()
            if governor:
                representatives.append(self._politician_to_rep(governor, "state", None))

            # 5. State Assembly member (if LGA known)
            if lga:
                assembly_member = db.query(Politician).filter(
                    Politician.position.ilike("%Assembly%"),
                    Politician.state.ilike(f"%{state}%"),
                    Politician.constituency.ilike(f"%{lga}%")
                ).first()
                if assembly_member:
                    representatives.append(
                        self._politician_to_rep(assembly_member, "state", "state_assembly")
                    )

            return representatives

        finally:
            db.close()

    def _politician_to_rep(
        self,
        politician: Politician,
        level: str,
        chamber: Optional[str]
    ) -> RepresentativeInfo:
        """Convert Politician model to RepresentativeInfo."""
        data = {}
        if politician.data_json:
            try:
                data = json.loads(politician.data_json)
            except:
                pass

        return RepresentativeInfo(
            slug=politician.slug,
            name=politician.name,
            position=politician.position or "Unknown",
            party=politician.party,
            state=politician.state,
            constituency=politician.constituency,
            level=level,
            chamber=chamber,
            image_url=data.get("image_url"),
            contact_info=data.get("contact", {})
        )

    # =========================================================================
    # Saved Politicians
    # =========================================================================

    def save_politician(
        self,
        user_hash: str,
        politician_slug: str,
        notify_news: bool = True,
        notify_updates: bool = True
    ) -> Dict[str, Any]:
        """
        Save/follow a politician.
        """
        db = SessionLocal()
        try:
            # Get politician info
            politician = db.query(Politician).filter(
                Politician.slug == politician_slug
            ).first()

            if not politician:
                return {"success": False, "error": "Politician not found"}

            # Check if already saved
            existing = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.subscription_type == "politician",
                UserSubscription.target_id == politician_slug,
                UserSubscription.is_active == True
            ).first()

            if existing:
                return {"success": True, "message": "Already following", "new": False}

            # Create subscription
            subscription = UserSubscription(
                user_hash=user_hash,
                subscription_type="politician",
                target_id=politician_slug,
                target_name=politician.name,
                notify_news=notify_news,
                notify_updates=notify_updates,
                is_active=True
            )
            db.add(subscription)
            db.commit()

            return {
                "success": True,
                "message": f"Now following {politician.name}",
                "new": True
            }

        except Exception as e:
            logger.error(f"Failed to save politician: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def unsave_politician(self, user_hash: str, politician_slug: str) -> Dict[str, Any]:
        """
        Unsave/unfollow a politician.
        """
        db = SessionLocal()
        try:
            subscription = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.subscription_type == "politician",
                UserSubscription.target_id == politician_slug,
                UserSubscription.is_active == True
            ).first()

            if not subscription:
                return {"success": False, "error": "Not following this politician"}

            subscription.is_active = False
            db.commit()

            return {"success": True, "message": "Unfollowed successfully"}

        except Exception as e:
            logger.error(f"Failed to unsave politician: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def get_saved_politicians(self, user_hash: str) -> List[SavedPolitician]:
        """
        Get all saved politicians for a user.
        """
        db = SessionLocal()
        try:
            subscriptions = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.subscription_type == "politician",
                UserSubscription.is_active == True
            ).all()

            saved = []
            for sub in subscriptions:
                politician = db.query(Politician).filter(
                    Politician.slug == sub.target_id
                ).first()

                if politician:
                    saved.append(SavedPolitician(
                        slug=politician.slug,
                        name=politician.name,
                        party=politician.party,
                        position=politician.position,
                        saved_at=sub.created_at.isoformat() if sub.created_at else "",
                        notify_news=sub.notify_news,
                        notify_updates=sub.notify_updates
                    ))

            return saved

        finally:
            db.close()

    # =========================================================================
    # Saved Issues
    # =========================================================================

    def save_issue(
        self,
        user_hash: str,
        issue_id: str,
        notify_updates: bool = True
    ) -> Dict[str, Any]:
        """
        Save/track an issue.
        """
        db = SessionLocal()
        try:
            # Get issue info
            issue = db.query(Issue).filter(Issue.issue_id == issue_id).first()

            if not issue:
                return {"success": False, "error": "Issue not found"}

            # Check if already saved
            existing = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.subscription_type == "issue",
                UserSubscription.target_id == issue_id,
                UserSubscription.is_active == True
            ).first()

            if existing:
                return {"success": True, "message": "Already tracking", "new": False}

            # Create subscription
            subscription = UserSubscription(
                user_hash=user_hash,
                subscription_type="issue",
                target_id=issue_id,
                target_name=issue.title,
                notify_updates=notify_updates,
                is_active=True
            )
            db.add(subscription)
            db.commit()

            return {
                "success": True,
                "message": f"Now tracking: {issue.title}",
                "new": True
            }

        except Exception as e:
            logger.error(f"Failed to save issue: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def get_saved_issues(self, user_hash: str) -> List[SavedIssue]:
        """
        Get all saved issues for a user.
        """
        db = SessionLocal()
        try:
            subscriptions = db.query(UserSubscription).filter(
                UserSubscription.user_hash == user_hash,
                UserSubscription.subscription_type == "issue",
                UserSubscription.is_active == True
            ).all()

            saved = []
            for sub in subscriptions:
                issue = db.query(Issue).filter(
                    Issue.issue_id == sub.target_id
                ).first()

                if issue:
                    saved.append(SavedIssue(
                        issue_id=issue.issue_id,
                        title=issue.title,
                        domain=issue.domain,
                        status=issue.status,
                        saved_at=sub.created_at.isoformat() if sub.created_at else "",
                        notify_updates=sub.notify_updates
                    ))

            return saved

        finally:
            db.close()

    # =========================================================================
    # User Interests
    # =========================================================================

    def update_interests(
        self,
        user_hash: str,
        topics: Optional[List[str]] = None,
        domains: Optional[List[str]] = None,
        states: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update user's topic interests.
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if not user:
                return {"success": False, "error": "User not found"}

            # Parse existing preferences
            prefs = {}
            if user.preferences_json:
                try:
                    prefs = json.loads(user.preferences_json)
                except:
                    pass

            # Update interests
            interests = prefs.get("interests", {})
            if topics is not None:
                interests["topics"] = topics
            if domains is not None:
                interests["domains"] = domains
            if states is not None:
                interests["states"] = states
            interests["updated_at"] = datetime.now().isoformat()

            prefs["interests"] = interests
            user.preferences_json = json.dumps(prefs)
            db.commit()

            return {
                "success": True,
                "interests": interests
            }

        except Exception as e:
            logger.error(f"Failed to update interests: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def get_interests(self, user_hash: str) -> UserInterests:
        """
        Get user's topic interests.
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if not user:
                return UserInterests(
                    topics=[],
                    domains=[],
                    states=[],
                    updated_at=""
                )

            prefs = {}
            if user.preferences_json:
                try:
                    prefs = json.loads(user.preferences_json)
                except:
                    pass

            interests = prefs.get("interests", {})

            return UserInterests(
                topics=interests.get("topics", []),
                domains=interests.get("domains", []),
                states=interests.get("states", []),
                updated_at=interests.get("updated_at", "")
            )

        finally:
            db.close()

    # =========================================================================
    # User Preferences
    # =========================================================================

    def update_preferences(
        self,
        user_hash: str,
        language: Optional[str] = None,
        notification_frequency: Optional[str] = None,
        notification_channels: Optional[List[str]] = None,
        news_sources: Optional[List[str]] = None,
        content_style: Optional[str] = None,
        accessibility_mode: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update user's app preferences.
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            if not user:
                return {"success": False, "error": "User not found"}

            # Parse existing preferences
            prefs = {}
            if user.preferences_json:
                try:
                    prefs = json.loads(user.preferences_json)
                except:
                    pass

            # Update preferences
            if language is not None:
                prefs["language"] = language
            if notification_frequency is not None:
                prefs["notification_frequency"] = notification_frequency
            if notification_channels is not None:
                prefs["notification_channels"] = notification_channels
            if news_sources is not None:
                prefs["news_sources"] = news_sources
            if content_style is not None:
                prefs["content_style"] = content_style
            if accessibility_mode is not None:
                prefs["accessibility_mode"] = accessibility_mode

            user.preferences_json = json.dumps(prefs)
            db.commit()

            return {
                "success": True,
                "preferences": prefs
            }

        except Exception as e:
            logger.error(f"Failed to update preferences: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def get_preferences(self, user_hash: str) -> UserPreferences:
        """
        Get user's app preferences.
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            prefs = {}
            if user and user.preferences_json:
                try:
                    prefs = json.loads(user.preferences_json)
                except:
                    pass

            return UserPreferences(
                language=prefs.get("language", "en"),
                notification_frequency=prefs.get("notification_frequency", "instant"),
                notification_channels=prefs.get("notification_channels", ["whatsapp"]),
                news_sources=prefs.get("news_sources", []),
                content_style=prefs.get("content_style", "detailed"),
                accessibility_mode=prefs.get("accessibility_mode", False)
            )

        finally:
            db.close()

    # =========================================================================
    # Personalized Dashboard
    # =========================================================================

    def get_dashboard(self, user_hash: str) -> Dict[str, Any]:
        """
        Get personalized dashboard data for a user.
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone_hash == user_hash).first()

            # Get representatives
            representatives = []
            if user and user.state:
                representatives = self.get_my_representatives(user.state, user.lga)

            # Get saved politicians
            saved_politicians = self.get_saved_politicians(user_hash)

            # Get saved issues
            saved_issues = self.get_saved_issues(user_hash)

            # Get interests
            interests = self.get_interests(user_hash)

            # Get recent activity (news about saved politicians/issues)
            recent_activity = self._get_recent_activity(user_hash, db)

            # Get recommendations
            recommendations = self._get_recommendations(user_hash, db)

            return {
                "user": {
                    "name": user.name if user else None,
                    "state": user.state if user else None,
                    "lga": user.lga if user else None,
                    "onboarding_completed": user.onboarding_completed if user else False
                },
                "representatives": [r.__dict__ for r in representatives],
                "saved_politicians": [p.__dict__ for p in saved_politicians],
                "saved_issues": [i.__dict__ for i in saved_issues],
                "interests": interests.__dict__,
                "recent_activity": recent_activity,
                "recommendations": recommendations
            }

        finally:
            db.close()

    def _get_recent_activity(self, user_hash: str, db) -> List[Dict]:
        """Get recent news/activity for saved politicians and issues."""
        # Get saved politician slugs
        politician_subs = db.query(UserSubscription).filter(
            UserSubscription.user_hash == user_hash,
            UserSubscription.subscription_type == "politician",
            UserSubscription.is_active == True
        ).all()

        activity = []
        for sub in politician_subs[:5]:  # Limit to 5 politicians
            articles = db.query(NewsArticle).filter(
                NewsArticle.politicians_json.contains(sub.target_id)
            ).order_by(NewsArticle.scraped_at.desc()).limit(3).all()

            for article in articles:
                activity.append({
                    "type": "news",
                    "politician_slug": sub.target_id,
                    "politician_name": sub.target_name,
                    "title": article.title,
                    "source": article.source_name,
                    "url": article.url,
                    "date": article.scraped_at.isoformat() if article.scraped_at else ""
                })

        # Sort by date and limit
        activity.sort(key=lambda x: x.get("date", ""), reverse=True)
        return activity[:10]

    def _get_recommendations(self, user_hash: str, db) -> List[Dict]:
        """Get personalized recommendations based on interests."""
        user = db.query(User).filter(User.phone_hash == user_hash).first()
        recommendations = []

        if user:
            prefs = {}
            if user.preferences_json:
                try:
                    prefs = json.loads(user.preferences_json)
                except:
                    pass

            interests = prefs.get("interests", {})
            domains = interests.get("domains", [])

            # Recommend issues in user's domains of interest
            for domain in domains[:3]:
                issues = db.query(Issue).filter(
                    Issue.domain == domain,
                    Issue.status == "active"
                ).order_by(Issue.last_updated.desc()).limit(2).all()

                for issue in issues:
                    recommendations.append({
                        "type": "issue",
                        "reason": f"Based on your interest in {domain}",
                        "item": {
                            "issue_id": issue.issue_id,
                            "title": issue.title,
                            "domain": issue.domain,
                            "status": issue.status
                        }
                    })

        return recommendations[:5]


# =============================================================================
# Helper Functions
# =============================================================================

def get_personalization_service() -> PersonalizationService:
    """Get singleton personalization service instance."""
    return PersonalizationService()
