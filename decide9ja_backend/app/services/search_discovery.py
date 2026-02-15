"""
Search & Discovery Service for Decide9ja.

Provides:
1. Smart Suggestions - context-aware query suggestions
2. Trending Queries - what people are asking about
3. Topic Pages - curated pages for major topics
4. Advanced Filters - filter by state, party, date, type

Usage:
    from app.services.search_discovery import SearchDiscoveryService

    service = SearchDiscoveryService()
    suggestions = service.get_smart_suggestions("tinubu")
    trending = service.get_trending_queries()
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import hashlib

from app.database import (
    SessionLocal, Politician, NewsArticle, Issue,
    Interaction, Document
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SearchSuggestion:
    """A search suggestion."""
    text: str
    type: str  # politician, issue, topic, query
    relevance: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendingQuery:
    """A trending search query."""
    query: str
    count: int
    trend: str  # rising, stable, falling
    category: str
    related_entities: List[str] = field(default_factory=list)


@dataclass
class TopicPage:
    """A curated topic page."""
    slug: str
    title: str
    description: str
    category: str
    key_points: List[str]
    related_politicians: List[str]
    related_issues: List[str]
    recent_news: List[Dict]
    faqs: List[Dict]
    updated_at: str


@dataclass
class SearchResult:
    """A search result."""
    id: str
    type: str  # politician, issue, news, bill
    title: str
    snippet: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchFilters:
    """Search filters."""
    states: Optional[List[str]] = None
    parties: Optional[List[str]] = None
    types: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    domains: Optional[List[str]] = None


# =============================================================================
# Topic Pages Content
# =============================================================================

TOPIC_PAGES = {
    "fuel-subsidy": TopicPage(
        slug="fuel-subsidy",
        title="Fuel Subsidy Removal",
        description="Everything about Nigeria's fuel subsidy removal and its impact",
        category="economy",
        key_points=[
            "Fuel subsidy was removed on May 29, 2023",
            "Petrol prices increased from around ₦185 to over ₦500",
            "The government says savings will fund infrastructure and social programs",
            "Palliatives including cash transfers are being distributed",
            "Transport costs and general inflation have increased"
        ],
        related_politicians=["bola-tinubu", "wale-edun"],
        related_issues=["inflation-2023", "transport-costs"],
        recent_news=[],  # Populated dynamically
        faqs=[
            {"q": "Why was fuel subsidy removed?", "a": "The government said subsidy was unsustainable, costing trillions yearly, and benefiting smugglers more than Nigerians."},
            {"q": "What palliatives are available?", "a": "Cash transfers, CNG conversion programs, transport subsidies, and student loans."},
            {"q": "Will subsidy return?", "a": "The government has said no, but has promised to stabilize prices."}
        ],
        updated_at=datetime.now().isoformat()
    ),
    "security-situation": TopicPage(
        slug="security-situation",
        title="Security Situation in Nigeria",
        description="Overview of Nigeria's security challenges and government response",
        category="security",
        key_points=[
            "Multiple security challenges: Boko Haram, banditry, kidnapping",
            "Government has increased military operations in the North",
            "Community policing and state security outfits established",
            "Defense budget has increased significantly",
            "Some states have implemented ransom bans"
        ],
        related_politicians=["bola-tinubu", "nuhu-ribadu"],
        related_issues=["banditry-northwest", "kidnapping-highways"],
        recent_news=[],
        faqs=[
            {"q": "Is Nigeria safe?", "a": "Security varies by region. Some areas are peaceful while others face challenges."},
            {"q": "What is the government doing?", "a": "Military operations, community policing, addressing root causes like poverty."},
            {"q": "Are kidnappings increasing?", "a": "Statistics vary, but high-profile cases continue to make headlines."}
        ],
        updated_at=datetime.now().isoformat()
    ),
    "naira-exchange-rate": TopicPage(
        slug="naira-exchange-rate",
        title="Naira and Exchange Rate",
        description="Understanding Nigeria's currency situation and forex policies",
        category="economy",
        key_points=[
            "Naira was floated in June 2023, leading to significant depreciation",
            "Multiple exchange rates were unified into one market-determined rate",
            "CBN has implemented various measures to stabilize the Naira",
            "Diaspora remittances remain an important forex source",
            "Oil revenue still key to foreign exchange earnings"
        ],
        related_politicians=["bola-tinubu", "olayemi-cardoso"],
        related_issues=["forex-scarcity", "inflation-2023"],
        recent_news=[],
        faqs=[
            {"q": "Why did the Naira fall?", "a": "The float removed the artificial rate, revealing the true market value."},
            {"q": "Will the Naira recover?", "a": "Experts differ. Some expect stabilization, others predict further depreciation."},
            {"q": "How does this affect me?", "a": "Import prices rise, affecting food, electronics, and many goods."}
        ],
        updated_at=datetime.now().isoformat()
    ),
    "2027-elections": TopicPage(
        slug="2027-elections",
        title="2027 General Elections",
        description="Everything about Nigeria's upcoming 2027 elections",
        category="elections",
        key_points=[
            "Presidential election scheduled for February 2027",
            "Governorship elections in most states same day",
            "National Assembly elections two weeks before",
            "INEC voter registration ongoing",
            "Major parties gearing up for primaries"
        ],
        related_politicians=["bola-tinubu", "atiku-abubakar", "peter-obi"],
        related_issues=[],
        recent_news=[],
        faqs=[
            {"q": "When is the election?", "a": "Presidential and governorship: February 25, 2027. NASS: February 11, 2027."},
            {"q": "How do I register to vote?", "a": "Visit INEC's CVR portal or nearest INEC office with valid ID."},
            {"q": "Who can run for President?", "a": "Nigerian citizen, 40+ years old, member of a registered party, with required educational qualifications."}
        ],
        updated_at=datetime.now().isoformat()
    ),
    "power-crisis": TopicPage(
        slug="power-crisis",
        title="Nigeria's Power Crisis",
        description="Understanding Nigeria's electricity challenges and solutions",
        category="infrastructure",
        key_points=[
            "Nigeria generates about 4,000-5,000 MW for 200+ million people",
            "Transmission and distribution losses are significant",
            "Renewable energy (solar) adoption is growing",
            "DisCos have been privatized, GenCos partly",
            "Tariff reforms ongoing to attract investment"
        ],
        related_politicians=["bola-tinubu", "adebayo-adelabu"],
        related_issues=["grid-collapse-2024", "tariff-increase"],
        recent_news=[],
        faqs=[
            {"q": "Why is there no constant light?", "a": "Insufficient generation, poor transmission, distribution losses, and vandalism."},
            {"q": "Will it improve?", "a": "Investments are ongoing, but significant improvement will take years."},
            {"q": "What about solar?", "a": "Growing option for homes and businesses, with financing schemes available."}
        ],
        updated_at=datetime.now().isoformat()
    ),
}


# =============================================================================
# Service Class
# =============================================================================

class SearchDiscoveryService:
    """
    Service for search and discovery features.
    """

    def __init__(self):
        self.topic_pages = TOPIC_PAGES
        self._query_log: List[Dict] = []  # In production, use database

    # =========================================================================
    # Smart Suggestions
    # =========================================================================

    def get_smart_suggestions(
        self,
        partial_query: str,
        user_context: Optional[Dict] = None,
        limit: int = 10
    ) -> List[SearchSuggestion]:
        """
        Get smart suggestions based on partial query and context.
        """
        suggestions = []
        query_lower = partial_query.lower().strip()

        if len(query_lower) < 2:
            return self._get_popular_suggestions(limit)

        db = SessionLocal()
        try:
            # 1. Match politicians
            politicians = db.query(Politician).filter(
                Politician.name.ilike(f"%{query_lower}%")
            ).limit(5).all()

            for pol in politicians:
                suggestions.append(SearchSuggestion(
                    text=pol.name,
                    type="politician",
                    relevance=0.9,
                    metadata={
                        "slug": pol.slug,
                        "party": pol.party,
                        "position": pol.position
                    }
                ))

            # 2. Match issues
            issues = db.query(Issue).filter(
                Issue.title.ilike(f"%{query_lower}%")
            ).limit(3).all()

            for issue in issues:
                suggestions.append(SearchSuggestion(
                    text=issue.title,
                    type="issue",
                    relevance=0.85,
                    metadata={
                        "issue_id": issue.issue_id,
                        "domain": issue.domain,
                        "status": issue.status
                    }
                ))

            # 3. Match topic pages
            for slug, topic in self.topic_pages.items():
                if query_lower in topic.title.lower() or query_lower in topic.description.lower():
                    suggestions.append(SearchSuggestion(
                        text=topic.title,
                        type="topic",
                        relevance=0.8,
                        metadata={"slug": slug, "category": topic.category}
                    ))

            # 4. Add query completions
            completions = self._get_query_completions(query_lower)
            for comp, count in completions[:5]:
                suggestions.append(SearchSuggestion(
                    text=comp,
                    type="query",
                    relevance=min(0.7, count / 100),
                    metadata={"search_count": count}
                ))

            # Sort by relevance and deduplicate
            suggestions.sort(key=lambda s: s.relevance, reverse=True)
            seen = set()
            unique = []
            for s in suggestions:
                if s.text.lower() not in seen:
                    seen.add(s.text.lower())
                    unique.append(s)

            return unique[:limit]

        finally:
            db.close()

    def _get_popular_suggestions(self, limit: int) -> List[SearchSuggestion]:
        """Get popular/default suggestions."""
        defaults = [
            SearchSuggestion("Bola Tinubu", "politician", 0.9, {"slug": "bola-tinubu"}),
            SearchSuggestion("Peter Obi", "politician", 0.85, {"slug": "peter-obi"}),
            SearchSuggestion("Fuel Subsidy", "topic", 0.8, {"slug": "fuel-subsidy"}),
            SearchSuggestion("2027 Elections", "topic", 0.8, {"slug": "2027-elections"}),
            SearchSuggestion("What's happening in Naira?", "query", 0.7, {}),
            SearchSuggestion("Security situation", "topic", 0.7, {"slug": "security-situation"}),
        ]
        return defaults[:limit]

    def _get_query_completions(self, partial: str) -> List[Tuple[str, int]]:
        """Get query completions based on search history."""
        # In production, this would query interaction logs
        common_queries = [
            ("who is the president", 100),
            ("what is fuel subsidy", 80),
            ("when is 2027 election", 75),
            ("naira exchange rate", 70),
            ("power outage today", 65),
            ("national assembly news", 60),
            ("lagos governor", 55),
            ("budget 2024", 50),
        ]

        matches = []
        for query, count in common_queries:
            if partial.lower() in query.lower():
                matches.append((query, count))

        return matches

    # =========================================================================
    # Trending Queries
    # =========================================================================

    def get_trending_queries(
        self,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[TrendingQuery]:
        """
        Get trending search queries.
        """
        db = SessionLocal()
        try:
            # Get recent interactions
            since = datetime.now() - timedelta(days=1)
            interactions = db.query(Interaction).filter(
                Interaction.created_at >= since
            ).all()

            # Count queries
            query_counts = Counter()
            for interaction in interactions:
                if interaction.query:
                    # Normalize query
                    normalized = self._normalize_query(interaction.query)
                    if normalized:
                        query_counts[normalized] += 1

            # Build trending list
            trending = []
            for query, count in query_counts.most_common(limit * 2):
                cat = self._categorize_query(query)

                if category and cat != category:
                    continue

                trending.append(TrendingQuery(
                    query=query,
                    count=count,
                    trend="rising" if count > 10 else "stable",
                    category=cat,
                    related_entities=self._extract_entities(query)
                ))

            return trending[:limit]

        finally:
            db.close()

    def _normalize_query(self, query: str) -> Optional[str]:
        """Normalize a query for counting."""
        if not query:
            return None

        # Remove special characters, lowercase
        normalized = re.sub(r'[^\w\s]', '', query.lower().strip())

        # Remove very short queries
        if len(normalized) < 5:
            return None

        return normalized

    def _categorize_query(self, query: str) -> str:
        """Categorize a query."""
        query_lower = query.lower()

        if any(w in query_lower for w in ["president", "senator", "governor", "minister"]):
            return "politicians"
        elif any(w in query_lower for w in ["election", "vote", "inec", "2027"]):
            return "elections"
        elif any(w in query_lower for w in ["budget", "naira", "economy", "subsidy", "tax"]):
            return "economy"
        elif any(w in query_lower for w in ["security", "bandit", "kidnap", "boko"]):
            return "security"
        elif any(w in query_lower for w in ["power", "nepa", "light", "electricity"]):
            return "infrastructure"
        else:
            return "general"

    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities from a query."""
        # Simple keyword extraction
        entities = []

        # Check for politician names
        politician_keywords = ["tinubu", "obi", "atiku", "buhari", "kwankwaso"]
        for kw in politician_keywords:
            if kw in query.lower():
                entities.append(kw.title())

        # Check for parties
        party_keywords = ["apc", "pdp", "lp", "nnpp"]
        for kw in party_keywords:
            if kw in query.lower():
                entities.append(kw.upper())

        return entities

    # =========================================================================
    # Topic Pages
    # =========================================================================

    def get_topic_page(self, slug: str) -> Optional[TopicPage]:
        """
        Get a topic page with latest data.
        """
        topic = self.topic_pages.get(slug)
        if not topic:
            return None

        # Populate recent news
        db = SessionLocal()
        try:
            news = db.query(NewsArticle).filter(
                NewsArticle.topics_json.contains(slug.replace("-", " "))
            ).order_by(NewsArticle.scraped_at.desc()).limit(5).all()

            topic.recent_news = [
                {
                    "title": n.title,
                    "source": n.source_name,
                    "date": n.scraped_at.isoformat() if n.scraped_at else None,
                    "url": n.url
                }
                for n in news
            ]

            topic.updated_at = datetime.now().isoformat()
            return topic

        finally:
            db.close()

    def get_all_topic_pages(self) -> List[Dict[str, Any]]:
        """
        Get list of all available topic pages.
        """
        return [
            {
                "slug": slug,
                "title": topic.title,
                "description": topic.description,
                "category": topic.category
            }
            for slug, topic in self.topic_pages.items()
        ]

    # =========================================================================
    # Advanced Search
    # =========================================================================

    def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Advanced search with filters.
        """
        db = SessionLocal()
        try:
            results = []
            query_lower = query.lower().strip()

            # Search politicians
            pol_query = db.query(Politician)
            if filters and filters.parties:
                pol_query = pol_query.filter(Politician.party.in_(filters.parties))
            if filters and filters.states:
                pol_query = pol_query.filter(Politician.state.in_(filters.states))

            politicians = pol_query.filter(
                Politician.name.ilike(f"%{query_lower}%")
            ).limit(10).all()

            for pol in politicians:
                results.append(SearchResult(
                    id=pol.slug,
                    type="politician",
                    title=pol.name,
                    snippet=f"{pol.position or 'Politician'} - {pol.party or 'Unknown party'}",
                    score=0.9,
                    metadata={
                        "slug": pol.slug,
                        "party": pol.party,
                        "state": pol.state,
                        "position": pol.position
                    }
                ))

            # Search issues
            issue_query = db.query(Issue)
            if filters and filters.states:
                for state in filters.states:
                    issue_query = issue_query.filter(Issue.states_json.contains(state))
            if filters and filters.domains:
                issue_query = issue_query.filter(Issue.domain.in_(filters.domains))

            issues = issue_query.filter(
                Issue.title.ilike(f"%{query_lower}%")
            ).limit(10).all()

            for issue in issues:
                results.append(SearchResult(
                    id=issue.issue_id,
                    type="issue",
                    title=issue.title,
                    snippet=issue.summary or f"{issue.domain.title()} issue - {issue.status}",
                    score=0.85,
                    metadata={
                        "issue_id": issue.issue_id,
                        "domain": issue.domain,
                        "status": issue.status,
                        "severity": issue.severity
                    }
                ))

            # Search news
            news_query = db.query(NewsArticle)
            if filters and filters.date_from:
                news_query = news_query.filter(NewsArticle.scraped_at >= filters.date_from)
            if filters and filters.date_to:
                news_query = news_query.filter(NewsArticle.scraped_at <= filters.date_to)

            news = news_query.filter(
                (NewsArticle.title.ilike(f"%{query_lower}%")) |
                (NewsArticle.excerpt.ilike(f"%{query_lower}%"))
            ).order_by(NewsArticle.scraped_at.desc()).limit(10).all()

            for article in news:
                results.append(SearchResult(
                    id=article.article_id,
                    type="news",
                    title=article.title,
                    snippet=article.excerpt or article.title,
                    score=0.8,
                    metadata={
                        "source": article.source_name,
                        "url": article.url,
                        "date": article.scraped_at.isoformat() if article.scraped_at else None
                    }
                ))

            # --- SEARCH CATALOG ARCHIVE ---
            # Include catalog if no specific type filter or "archive" is in types
            include_archive = True
            if filters and filters.types and "archive" not in filters.types and "news" not in filters.types:
                include_archive = False
            
            if include_archive:
                try:
                    from app.services.catalog_search import get_catalog_service
                    catalog_service = get_catalog_service()
                    if catalog_service.is_available:
                        # Convert datetime filters to year integers if present
                        year_from = filters.date_from.year if filters and filters.date_from else None
                        year_to = filters.date_to.year if filters and filters.date_to else None
                        
                        cat_results = catalog_service.search(
                            query=query,
                            limit=10,
                            year_from=year_from,
                            year_to=year_to
                        )
                        
                        for i, article in enumerate(cat_results.articles):
                            # Score slightly lower than fresh news unless high rank
                            score = 0.75 - (i * 0.02) 
                            
                            results.append(SearchResult(
                                id=article.id,
                                type="archive",
                                title=article.title,
                                snippet=article.snippet,
                                score=score,
                                metadata={
                                    "source": article.source_id,
                                    "date": article.published_date,
                                    "topics": article.topics,
                                    "relevance": article.relevance_rank
                                }
                            ))
                except Exception as e:
                    logger.error(f"Error searching catalog in unified search: {e}")

            # --- SEARCH BUDGETS ---
            include_budgets = True
            if filters and filters.types and "budget" not in filters.types:
                include_budgets = False
            
            if include_budgets:
                try:
                    from app.services.budget_search import get_budget_service
                    budget_service = get_budget_service()
                    if budget_service.is_available:
                        # Extract year filter if present
                        year = filters.date_from.year if filters and filters.date_from else None
                        
                        # Extract jurisdiction from state filter?
                        # If states filter is present, we can use it as jurisdiction filter
                        # But budget service takes single strings for now.
                        # Maybe iteration? Or simple broad search.
                        jurisdiction = None
                        if filters and filters.states:
                             # Just take the first one or ignore for now to avoid complexity
                             # Ideally we'd loop or support lists in budget service
                             jurisdiction = filters.states[0]

                        bud_results = budget_service.search(
                            query=query,
                            limit=5, # Keep it light
                            year=year,
                            jurisdiction=jurisdiction
                        )

                        for item in bud_results.items:
                            results.append(SearchResult(
                                id=f"budget-{item.id}",
                                type="budget",
                                title=f"{item.jurisdiction} Budget: {item.project}",
                                snippet=f"{item.mda} - ₦{item.amount:,.2f}",
                                score=0.82, # High relevance for specific searches
                                metadata={
                                    "year": item.year,
                                    "jurisdiction": item.jurisdiction,
                                    "amount": item.amount,
                                    "mda": item.mda
                                }
                            ))
                except Exception as e:
                    logger.error(f"Error searching budgets: {e}")

            # Sort by score
            results.sort(key=lambda r: r.score, reverse=True)

            # Log the search
            self._log_search(query, len(results))

            return {
                "query": query,
                "results": [
                    {
                        "id": r.id,
                        "type": r.type,
                        "title": r.title,
                        "snippet": r.snippet,
                        "score": r.score,
                        "metadata": r.metadata
                    }
                    for r in results[:limit]
                ],
                "total": len(results),
                "filters_applied": bool(filters)
            }

        finally:
            db.close()

    def _log_search(self, query: str, result_count: int):
        """Log a search for trending analysis."""
        self._query_log.append({
            "query": query,
            "result_count": result_count,
            "timestamp": datetime.now().isoformat()
        })

    # =========================================================================
    # Filter Options
    # =========================================================================

    def get_filter_options(self) -> Dict[str, List[str]]:
        """
        Get available filter options.
        """
        db = SessionLocal()
        try:
            # Get unique parties
            parties = db.query(Politician.party).distinct().all()
            parties = [p[0] for p in parties if p[0]]

            # Get unique states
            states = db.query(Politician.state).distinct().all()
            states = [s[0] for s in states if s[0]]
            states.sort()

            # Get domains
            domains = db.query(Issue.domain).distinct().all()
            domains = [d[0] for d in domains if d[0]]

            return {
                "parties": parties,
                "states": states,
                "domains": domains,
                "types": ["politician", "issue", "news", "bill", "archive", "budget"],
                "categories": ["economy", "security", "infrastructure", "governance", "elections"]
            }

        finally:
            db.close()


# =============================================================================
# Helper Functions
# =============================================================================

def get_search_service() -> SearchDiscoveryService:
    """Get singleton search service instance."""
    return SearchDiscoveryService()
