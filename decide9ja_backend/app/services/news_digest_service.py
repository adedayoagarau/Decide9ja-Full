"""
News Digest Service for Decide9ja.

Generates personalized news digests for WhatsApp delivery:
- Daily morning briefings
- Weekly summaries
- Breaking news alerts
- Topic-specific updates

All content is WhatsApp-optimized (plain text, limited length).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

class DigestFrequency(str, Enum):
    """Digest delivery frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    BREAKING = "breaking"  # Immediate for important news


class ContentCategory(str, Enum):
    """News content categories."""
    POLITICS = "politics"
    ECONOMY = "economy"
    SECURITY = "security"
    EDUCATION = "education"
    HEALTH = "health"
    INFRASTRUCTURE = "infrastructure"
    ELECTION = "election"
    GOVERNANCE = "governance"


@dataclass
class NewsItem:
    """A news item for digest."""
    id: str
    title: str
    summary: str
    source: str
    url: str
    category: str
    published_at: datetime
    states_mentioned: List[str] = field(default_factory=list)
    politicians_mentioned: List[str] = field(default_factory=list)
    importance_score: float = 0.5  # 0-1


@dataclass
class DigestPreferences:
    """User preferences for digests."""
    user_hash: str
    enabled: bool = True
    frequency: DigestFrequency = DigestFrequency.DAILY
    send_time: str = "07:00"  # HH:MM in WAT
    categories: List[str] = field(default_factory=lambda: ["politics", "economy", "security"])
    states_of_interest: List[str] = field(default_factory=list)
    politicians_followed: List[str] = field(default_factory=list)
    max_items: int = 5
    include_polls: bool = True
    include_election_updates: bool = True
    language: str = "en"


@dataclass
class GeneratedDigest:
    """A generated digest ready for sending."""
    id: str
    user_hash: str
    frequency: DigestFrequency
    content: str  # WhatsApp-ready message
    items_count: int
    generated_at: datetime
    personalized: bool = True


# =============================================================================
# News Digest Service
# =============================================================================

class NewsDigestService:
    """
    Service for generating and managing news digests.

    Features:
    - Personalized content selection based on user interests
    - State/LGA-specific news prioritization
    - Followed politician updates
    - WhatsApp-optimized formatting
    - Multiple frequency options
    """

    def __init__(self):
        self._user_preferences: Dict[str, DigestPreferences] = {}
        self._news_cache: List[NewsItem] = []
        self._last_cache_update: Optional[datetime] = None

    # -------------------------------------------------------------------------
    # User Preferences
    # -------------------------------------------------------------------------

    def get_preferences(self, user_hash: str) -> DigestPreferences:
        """Get user's digest preferences."""
        if user_hash not in self._user_preferences:
            # Create default preferences
            self._user_preferences[user_hash] = DigestPreferences(user_hash=user_hash)
        return self._user_preferences[user_hash]

    def update_preferences(
        self,
        user_hash: str,
        enabled: Optional[bool] = None,
        frequency: Optional[str] = None,
        send_time: Optional[str] = None,
        categories: Optional[List[str]] = None,
        states_of_interest: Optional[List[str]] = None,
        max_items: Optional[int] = None,
        include_polls: Optional[bool] = None,
        language: Optional[str] = None
    ) -> DigestPreferences:
        """Update user's digest preferences."""
        prefs = self.get_preferences(user_hash)

        if enabled is not None:
            prefs.enabled = enabled
        if frequency is not None:
            prefs.frequency = DigestFrequency(frequency)
        if send_time is not None:
            prefs.send_time = send_time
        if categories is not None:
            prefs.categories = categories
        if states_of_interest is not None:
            prefs.states_of_interest = states_of_interest
        if max_items is not None:
            prefs.max_items = max_items
        if include_polls is not None:
            prefs.include_polls = include_polls
        if language is not None:
            prefs.language = language

        return prefs

    def subscribe_to_digest(self, user_hash: str, frequency: str = "daily") -> Dict:
        """Subscribe user to digest."""
        prefs = self.get_preferences(user_hash)
        prefs.enabled = True
        prefs.frequency = DigestFrequency(frequency)

        return {
            "success": True,
            "message": f"Subscribed to {frequency} digest",
            "send_time": prefs.send_time
        }

    def unsubscribe_from_digest(self, user_hash: str) -> Dict:
        """Unsubscribe user from digest."""
        prefs = self.get_preferences(user_hash)
        prefs.enabled = False

        return {
            "success": True,
            "message": "Unsubscribed from digest"
        }

    # -------------------------------------------------------------------------
    # News Fetching
    # -------------------------------------------------------------------------

    def _fetch_recent_news(self, hours: int = 24) -> List[NewsItem]:
        """Fetch recent news from database."""
        import os
        from sqlalchemy import create_engine, text

        try:
            engine = create_engine(os.getenv('DATABASE_URL'))

            with engine.connect() as conn:
                query = text("""
                    SELECT id, title, summary, source, url,
                           topics, related_state, mentioned_candidates,
                           published_at, sentiment_score
                    FROM news_items
                    WHERE published_at >= NOW() - INTERVAL :hours HOUR
                    AND is_relevant = true
                    ORDER BY published_at DESC
                    LIMIT 100
                """)

                result = conn.execute(query, {"hours": hours})

                news_items = []
                for row in result:
                    row_dict = dict(row._mapping)
                    topics = row_dict.get("topics") or []
                    category = topics[0] if topics else "politics"

                    news_items.append(NewsItem(
                        id=str(row_dict["id"]),
                        title=row_dict["title"],
                        summary=row_dict.get("summary") or row_dict["title"],
                        source=row_dict["source"],
                        url=row_dict["url"],
                        category=category,
                        published_at=row_dict["published_at"],
                        states_mentioned=[row_dict["related_state"]] if row_dict.get("related_state") else [],
                        politicians_mentioned=row_dict.get("mentioned_candidates") or [],
                        importance_score=0.5 + (row_dict.get("sentiment_score") or 0) * 0.5
                    ))

                return news_items

        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []

    def _get_cached_news(self, max_age_hours: int = 1) -> List[NewsItem]:
        """Get news from cache, refreshing if stale."""
        now = datetime.utcnow()

        if (self._last_cache_update is None or
            now - self._last_cache_update > timedelta(hours=max_age_hours)):
            self._news_cache = self._fetch_recent_news(hours=24)
            self._last_cache_update = now

        return self._news_cache

    # -------------------------------------------------------------------------
    # Digest Generation
    # -------------------------------------------------------------------------

    def generate_daily_digest(
        self,
        user_hash: str,
        user_context: Optional[Dict] = None
    ) -> GeneratedDigest:
        """
        Generate personalized daily digest for a user.

        Args:
            user_hash: User identifier
            user_context: Optional context (name, state, lga, interests)

        Returns:
            GeneratedDigest with WhatsApp-ready content
        """
        prefs = self.get_preferences(user_hash)
        news = self._get_cached_news()

        # Personalize news selection
        selected = self._select_news_for_user(news, prefs, user_context)

        # Generate content
        content = self._format_daily_digest(selected, user_context, prefs)

        return GeneratedDigest(
            id=f"digest_{user_hash}_{datetime.utcnow().strftime('%Y%m%d')}",
            user_hash=user_hash,
            frequency=DigestFrequency.DAILY,
            content=content,
            items_count=len(selected),
            generated_at=datetime.utcnow(),
            personalized=bool(user_context)
        )

    def generate_weekly_digest(
        self,
        user_hash: str,
        user_context: Optional[Dict] = None
    ) -> GeneratedDigest:
        """Generate weekly summary digest."""
        prefs = self.get_preferences(user_hash)

        # Get news from the past week
        news = self._fetch_recent_news(hours=168)  # 7 days

        # Select top stories
        selected = self._select_news_for_user(news, prefs, user_context, max_items=10)

        # Generate content
        content = self._format_weekly_digest(selected, user_context, prefs)

        return GeneratedDigest(
            id=f"weekly_{user_hash}_{datetime.utcnow().strftime('%Y%m%d')}",
            user_hash=user_hash,
            frequency=DigestFrequency.WEEKLY,
            content=content,
            items_count=len(selected),
            generated_at=datetime.utcnow(),
            personalized=bool(user_context)
        )

    def generate_breaking_alert(
        self,
        headline: str,
        summary: str,
        source: str,
        category: str = "politics"
    ) -> str:
        """
        Generate breaking news alert message.

        Args:
            headline: News headline
            summary: Brief summary (max 200 chars)
            source: News source
            category: News category

        Returns:
            WhatsApp-ready message
        """
        emoji_map = {
            "politics": "🏛️",
            "economy": "💰",
            "security": "🚨",
            "election": "🗳️",
            "health": "🏥",
            "education": "📚"
        }
        emoji = emoji_map.get(category, "📢")

        return f"""⚠️ BREAKING NEWS

{emoji} {headline}

{summary[:200]}

Source: {source}

Reply "more" for details.
— Tade"""

    # -------------------------------------------------------------------------
    # News Selection
    # -------------------------------------------------------------------------

    def _select_news_for_user(
        self,
        news: List[NewsItem],
        prefs: DigestPreferences,
        user_context: Optional[Dict],
        max_items: Optional[int] = None
    ) -> List[NewsItem]:
        """Select and rank news items for a user."""
        if not news:
            return []

        max_items = max_items or prefs.max_items

        # Score each item for this user
        scored = []
        for item in news:
            score = self._calculate_relevance_score(item, prefs, user_context)
            scored.append((item, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Take top items
        return [item for item, score in scored[:max_items]]

    def _calculate_relevance_score(
        self,
        item: NewsItem,
        prefs: DigestPreferences,
        user_context: Optional[Dict]
    ) -> float:
        """Calculate relevance score for a news item."""
        score = item.importance_score

        # Category match
        if item.category in prefs.categories:
            score += 0.3

        # State relevance
        user_state = None
        if user_context:
            user_state = user_context.get("state", "").lower()
        elif prefs.states_of_interest:
            user_state = prefs.states_of_interest[0].lower()

        if user_state:
            for state in item.states_mentioned:
                if state.lower() == user_state:
                    score += 0.4
                    break

        # Followed politicians
        if prefs.politicians_followed:
            for pol in item.politicians_mentioned:
                if pol in prefs.politicians_followed:
                    score += 0.5
                    break

        # Recency bonus
        hours_old = (datetime.utcnow() - item.published_at).total_seconds() / 3600
        if hours_old < 6:
            score += 0.2
        elif hours_old < 12:
            score += 0.1

        return min(score, 2.0)  # Cap at 2.0

    # -------------------------------------------------------------------------
    # Content Formatting
    # -------------------------------------------------------------------------

    def _format_daily_digest(
        self,
        items: List[NewsItem],
        user_context: Optional[Dict],
        prefs: DigestPreferences
    ) -> str:
        """Format daily digest for WhatsApp."""
        # Greeting
        name = user_context.get("name", "") if user_context else ""
        greeting = f"Good morning, {name}!" if name else "Good morning!"

        # Date
        today = datetime.now().strftime("%A, %B %d")

        # Headlines
        if not items:
            headlines = "No major news today. Check back tomorrow!"
        else:
            headlines = "\n".join([f"• {item.title}" for item in items])

        # Build message
        message = f"""{greeting}

📰 *Daily Briefing* — {today}

{headlines}"""

        # Add sources
        if items:
            sources = list(set([item.source for item in items[:3]]))
            message += f"\n\nSources: {', '.join(sources)}"

        # Add CTA
        message += "\n\nReply with a number for details, or \"off\" to unsubscribe.\n— Tade"

        return message

    def _format_weekly_digest(
        self,
        items: List[NewsItem],
        user_context: Optional[Dict],
        prefs: DigestPreferences
    ) -> str:
        """Format weekly summary for WhatsApp."""
        name = user_context.get("name", "") if user_context else ""
        greeting = f"Hi {name}!" if name else "Hi!"

        # Date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}"

        # Categorize items
        by_category: Dict[str, List[NewsItem]] = {}
        for item in items:
            cat = item.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)

        # Build sections
        sections = []
        category_emojis = {
            "politics": "🏛️",
            "economy": "💰",
            "security": "🚨",
            "election": "🗳️",
            "health": "🏥",
            "education": "📚",
            "infrastructure": "🛣️"
        }

        for cat, cat_items in list(by_category.items())[:4]:
            emoji = category_emojis.get(cat, "📌")
            section = f"{emoji} *{cat.title()}*:\n"
            section += "\n".join([f"  • {item.title}" for item in cat_items[:3]])
            sections.append(section)

        content = "\n\n".join(sections) if sections else "Quiet week — no major updates."

        message = f"""{greeting}

📊 *Weekly Summary* ({date_range})

{content}

Reply "details" for more on any topic.
— Tade"""

        return message

    # -------------------------------------------------------------------------
    # Batch Generation
    # -------------------------------------------------------------------------

    def get_users_for_digest(
        self,
        frequency: DigestFrequency,
        send_time: str
    ) -> List[str]:
        """Get users who should receive digest at this time."""
        users = []
        for user_hash, prefs in self._user_preferences.items():
            if (prefs.enabled and
                prefs.frequency == frequency and
                prefs.send_time == send_time):
                users.append(user_hash)
        return users

    def generate_batch_digests(
        self,
        frequency: DigestFrequency,
        user_hashes: List[str]
    ) -> List[GeneratedDigest]:
        """Generate digests for multiple users."""
        digests = []

        for user_hash in user_hashes:
            try:
                if frequency == DigestFrequency.DAILY:
                    digest = self.generate_daily_digest(user_hash)
                elif frequency == DigestFrequency.WEEKLY:
                    digest = self.generate_weekly_digest(user_hash)
                else:
                    continue

                digests.append(digest)
            except Exception as e:
                logger.error(f"Error generating digest for {user_hash}: {e}")

        return digests


# =============================================================================
# Singleton Instance
# =============================================================================

_news_digest_service: Optional[NewsDigestService] = None


def get_news_digest_service() -> NewsDigestService:
    """Get singleton news digest service instance."""
    global _news_digest_service
    if _news_digest_service is None:
        _news_digest_service = NewsDigestService()
    return _news_digest_service
