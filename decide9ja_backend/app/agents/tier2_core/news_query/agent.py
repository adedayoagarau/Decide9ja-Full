"""
NewsQueryAgent
==============
Handles news queries about Nigerian politics.

Uses web search for current news, caches results.
Cost: CHEAP (web search + optional LLM summarization)

Handles:
- "Latest news about Tinubu"
- "What's happening with the tax bill?"
- "Political news today"
- "News about Lagos"
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent
from app.agents.tier1_entry.classifier import Intent

logger = logging.getLogger(__name__)


@register_agent
class NewsQueryAgent(BaseAgent):
    name = "news_query"
    description = "Search and summarize Nigerian political news"
    tier = AgentTier.CORE
    cost_level = CostLevel.CHEAP  # Web search costs
    handled_intents = [
        Intent.NEWS_QUERY,
        Intent.TRENDING,
        Intent.POLITICIAN_NEWS,
    ]

    # Nigerian news sources (trusted)
    TRUSTED_SOURCES = [
        "punchng.com",
        "premiumtimesng.com",
        "thecable.ng",
        "vanguardngr.com",
        "guardian.ng",
        "dailytrust.com",
        "channelstv.com",
        "arise.tv",
    ]

    # Topics for categorization
    TOPIC_KEYWORDS = {
        "economy": ["naira", "dollar", "inflation", "budget", "tax", "fuel", "subsidy"],
        "security": ["bandit", "kidnap", "boko haram", "terrorism", "police", "army"],
        "politics": ["election", "senate", "house", "governor", "minister", "apc", "pdp"],
        "education": ["asuu", "university", "school", "jamb", "waec"],
        "health": ["hospital", "doctor", "health", "disease"],
    }

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent in self.handled_intents

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        # Check cache first
        cached = await self._check_cache(input)
        if cached:
            return self._tag_analytics(input, cached)

        # Extract search query
        search_query = self._build_search_query(input)

        # Try to get news
        news_results = await self._search_news(search_query)

        if news_results:
            output = self._format_news_response(input, news_results, search_query)
        else:
            # Fallback to trending topics
            output = self._format_trending_fallback(input)

        # Cache successful results
        if output.success:
            await self._save_cache(input, output, ttl=1800)  # 30 min cache

        return self._tag_analytics(input, output)

    def _build_search_query(self, input: AgentInput) -> str:
        """Build search query from user input"""
        base_query = input.raw_text.lower()

        # Remove common prefixes
        for prefix in ["news about", "latest news", "what's happening with",
                       "tell me about", "news on", "update on"]:
            if base_query.startswith(prefix):
                base_query = base_query[len(prefix):].strip()

        # Add Nigeria context if not present
        if "nigeria" not in base_query:
            base_query = f"Nigeria {base_query}"

        # Add politician name if detected
        politician = input.entities.get("politician")
        if politician and politician.lower() not in base_query:
            base_query = f"{politician} {base_query}"

        # Add "news" if not present
        if "news" not in base_query:
            base_query = f"{base_query} news"

        return base_query.strip()

    async def _search_news(self, query: str) -> List[Dict]:
        """Search for news articles"""
        results = []

        # Try database first (cached news)
        if self.db:
            try:
                db_results = await self._search_cached_news(query)
                if db_results:
                    results.extend(db_results)
            except Exception as e:
                logger.error(f"Database news search failed: {e}")

        # If not enough results, try web search
        if len(results) < 3:
            try:
                web_results = await self._web_search(query)
                results.extend(web_results)
            except Exception as e:
                logger.error(f"Web search failed: {e}")

        # Deduplicate by title
        seen_titles = set()
        unique_results = []
        for r in results:
            title_key = r.get("title", "").lower()[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_results.append(r)

        return unique_results[:5]  # Max 5 results

    async def _search_cached_news(self, query: str) -> List[Dict]:
        """Search cached news in database"""
        # Implement based on your news table schema
        # Example for MongoDB:
        # return await self.db.news.find(
        #     {"$text": {"$search": query}},
        #     {"score": {"$meta": "textScore"}}
        # ).sort([("score", {"$meta": "textScore"})]).limit(5).to_list(5)
        return []

    async def _web_search(self, query: str) -> List[Dict]:
        """Perform web search for news"""
        # This would integrate with your web search service
        # For now, return empty - implement with your search provider

        # Example integration:
        # from app.services.realtime import fetch_web_search
        # results = fetch_web_search(query, limit=5)
        # return [{"title": r["title"], "summary": r["snippet"],
        #          "source": r["source"], "url": r["url"]} for r in results]

        return []

    def _format_news_response(self, input: AgentInput, news: List[Dict], query: str) -> AgentOutput:
        """Format news results for user"""
        
        # Orchestrator Tool Mode: Return raw JSON
        if input.context and input.context.get("tool_mode"):
            return AgentOutput(
                success=True,
                response_text="Data retrieved via tool.",
                data={"news": news, "query": query},
                cost_level=CostLevel.FREE
            )

        if not news:
            return self._format_trending_fallback(input)

        # Detect topic for analytics
        topic = self._detect_topic(query)

        response_parts = [f"📰 *Latest News: {query.replace('Nigeria ', '').title()}*\n"]

        for i, article in enumerate(news[:5], 1):
            title = article.get("title", "Untitled")
            summary = article.get("summary", article.get("snippet", ""))
            source = article.get("source", "News")
            url = article.get("url", "")

            # Truncate summary
            if len(summary) > 150:
                summary = summary[:147] + "..."

            response_parts.append(f"\n*{i}. {title}*")
            if summary:
                response_parts.append(f"   {summary}")
            response_parts.append(f"   _— {source}_")

        response_parts.append("\n\n_Say a number for more details, or ask about another topic._")

        return AgentOutput(
            success=True,
            response_text="".join(response_parts),
            data={"news": news, "query": query},
            sources=[a.get("source", "News") for a in news[:3]],
            cost_level=CostLevel.CHEAP,
            analytics_tags={
                "topic": "news",
                "subtopic": topic,
                "results_count": len(news)
            }
        )

    def _format_trending_fallback(self, input: AgentInput) -> AgentOutput:
        """Fallback when no specific news found"""
        
        # Orchestrator Tool Mode: Return raw JSON fallback
        if input.context and input.context.get("tool_mode"):
            return AgentOutput(
                success=False,
                response_text="No news found.",
                data={"error": "no news found"},
                cost_level=CostLevel.FREE
            )

        # Static trending topics (update regularly)
        trending = [
            {"topic": "2027 Elections", "summary": "Campaign preparations and party primaries"},
            {"topic": "Economy", "summary": "Naira exchange rates and inflation updates"},
            {"topic": "Security", "summary": "Latest on security operations nationwide"},
            {"topic": "Governance", "summary": "Policy announcements and cabinet activities"},
        ]

        response = """📰 *Trending in Nigerian Politics*

"""
        for t in trending:
            response += f"🔥 *{t['topic']}*\n   {t['summary']}\n\n"

        response += """_Ask about any topic for latest news:_
• "News about Tinubu"
• "Latest on the economy"
• "Security news"
• "Education updates\""""

        return AgentOutput(
            success=True,
            response_text=response,
            buttons=[
                {"text": "Economy News", "callback": "news:economy"},
                {"text": "Political News", "callback": "news:politics"},
                {"text": "Security News", "callback": "news:security"},
            ],
            cost_level=CostLevel.FREE,
            analytics_tags={"topic": "news", "subtopic": "trending_fallback"}
        )

    def _detect_topic(self, text: str) -> str:
        """Detect topic category from text"""
        text_lower = text.lower()

        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return topic

        return "general"

    def _is_trusted_source(self, source: str) -> bool:
        """Check if source is in trusted list"""
        source_lower = source.lower()
        return any(trusted in source_lower for trusted in self.TRUSTED_SOURCES)
