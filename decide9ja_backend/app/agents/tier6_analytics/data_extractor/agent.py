"""
DataExtractorAgent
==================
Extracts structured data from raw news article text using LLM.

This is the ONLY LLM-heavy agent in the research system.
Uses Claude to parse unstructured news into:
- Politician profiles
- Promises and their status
- Recent news summaries
- Controversies

Cost: MEDIUM (LLM calls, but batched and cached)
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from app.agents.base import (
    BaseAgent,
    LLMAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent
from app.agents.tier6_analytics.data_extractor.prompt import (
    POLITICIAN_EXTRACTION_PROMPT,
    PROMISE_STATUS_PROMPT,
    NEWS_SUMMARY_PROMPT
)

logger = logging.getLogger(__name__)


@register_agent
class DataExtractorAgent(LLMAgent):
    """Extracts structured data from raw text using LLM"""

    name = "data_extractor"
    description = "LLM-powered extraction of structured political data from news"
    tier = AgentTier.ANALYTICS
    cost_level = CostLevel.MEDIUM
    handled_intents = []  # Background agent

    # LLM settings
    max_tokens = 2000
    temperature = 0.1  # Low temperature for consistent extraction

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def can_handle(self, input: AgentInput) -> bool:
        return False  # Background agent

    async def handle(self, input: AgentInput) -> AgentOutput:
        """Not used directly - call extraction methods instead"""
        return self.fail("DataExtractor is a background agent", "NOT_USER_FACING")

    async def extract_politician_data(
        self,
        articles: List[Dict],
        politician_name: str
    ) -> Dict:
        """
        Extract structured politician data from articles.

        Args:
            articles: List of article dicts with 'content', 'source', 'date'
            politician_name: Name of politician to extract info about

        Returns:
            Structured dict with profile, promises, news, controversies
        """
        # Combine article content (limit to prevent token overflow)
        combined_text = self._combine_articles(articles, max_chars=8000)

        if not combined_text:
            logger.warning(f"No article content for {politician_name}")
            return self._empty_profile(politician_name)

        # Build the prompt
        prompt = POLITICIAN_EXTRACTION_PROMPT.format(
            politician_name=politician_name,
            articles=combined_text
        )

        try:
            # Call LLM
            result = await self.call_llm(prompt)

            # Parse JSON response
            data = self._parse_json_response(result)

            if data:
                # Add metadata
                data["extracted_at"] = datetime.utcnow().isoformat()
                data["source_count"] = len(articles)
                data["sources"] = [a.get("url") for a in articles[:5] if a.get("url")]
                return data

        except Exception as e:
            logger.error(f"LLM extraction failed for {politician_name}: {e}")

        return self._empty_profile(politician_name)

    async def extract_promise_status(
        self,
        promise: Dict,
        articles: List[Dict]
    ) -> Dict:
        """
        Check if a specific promise has been kept based on recent articles.

        Args:
            promise: Dict with 'promise_text', 'politician_name', 'date_made'
            articles: Recent articles to check against

        Returns:
            Dict with status, evidence, confidence
        """
        combined_text = self._combine_articles(articles, max_chars=4000)

        if not combined_text:
            return {
                "status": "unknown",
                "evidence": "No recent articles found to verify",
                "confidence": 0.0
            }

        prompt = PROMISE_STATUS_PROMPT.format(
            promise_text=promise.get("promise_text", ""),
            politician_name=promise.get("politician_name", ""),
            date_made=promise.get("date_made", "Unknown"),
            articles=combined_text
        )

        try:
            result = await self.call_llm(prompt)
            data = self._parse_json_response(result)

            if data:
                return {
                    "status": data.get("status", "unknown"),
                    "evidence": data.get("evidence", ""),
                    "source_url": data.get("source_url"),
                    "confidence": float(data.get("confidence", 0.5)),
                    "checked_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Promise status extraction failed: {e}")

        return {
            "status": "unknown",
            "evidence": "Extraction failed",
            "confidence": 0.0
        }

    async def extract_news_summary(
        self,
        articles: List[Dict],
        topic: Optional[str] = None
    ) -> List[Dict]:
        """
        Extract summarized news items from articles.

        Args:
            articles: List of article dicts
            topic: Optional topic filter

        Returns:
            List of summarized news items
        """
        combined_text = self._combine_articles(articles, max_chars=6000)

        if not combined_text:
            return []

        prompt = NEWS_SUMMARY_PROMPT.format(
            topic=topic or "Nigerian politics",
            articles=combined_text
        )

        try:
            result = await self.call_llm(prompt)
            data = self._parse_json_response(result)

            if data and isinstance(data.get("news_items"), list):
                return data["news_items"]

        except Exception as e:
            logger.error(f"News summary extraction failed: {e}")

        return []

    async def extract_entities_from_text(self, text: str) -> Dict:
        """
        Extract named entities (politicians, parties, locations) from text.

        Args:
            text: Raw text to extract from

        Returns:
            Dict with politicians, parties, states, topics mentioned
        """
        prompt = f"""Extract all named entities from this Nigerian political text.

TEXT:
{text[:3000]}

Return JSON:
{{
    "politicians": ["List of politician names mentioned"],
    "parties": ["Political parties mentioned (APC, PDP, LP, etc.)"],
    "states": ["Nigerian states mentioned"],
    "organizations": ["Government bodies, agencies mentioned"],
    "topics": ["Main topics discussed (education, security, economy, etc.)"]
}}

Only include entities explicitly mentioned. Return empty lists if none found."""

        try:
            result = await self.call_llm(prompt)
            return self._parse_json_response(result) or {
                "politicians": [],
                "parties": [],
                "states": [],
                "organizations": [],
                "topics": []
            }
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {
                "politicians": [],
                "parties": [],
                "states": [],
                "organizations": [],
                "topics": []
            }

    def _combine_articles(self, articles: List[Dict], max_chars: int = 8000) -> str:
        """Combine article content with source attribution"""
        parts = []
        total_chars = 0

        for article in articles:
            content = article.get("content", "")
            if not content:
                continue

            # Limit each article
            content = content[:2000]

            source = article.get("source_name") or article.get("source", "Unknown")
            date = article.get("date") or article.get("date_raw", "Unknown date")

            article_text = f"[Source: {source}, Date: {date}]\n{content}\n"

            if total_chars + len(article_text) > max_chars:
                break

            parts.append(article_text)
            total_chars += len(article_text)

        return "\n---\n".join(parts)

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown code blocks"""
        if not response:
            return None

        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            # Find the end of the code block
            lines = response.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]  # Remove opening ```json or ```
            if lines[-1] == "```":
                lines = lines[:-1]  # Remove closing ```
            response = "\n".join(lines)

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")

            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass

            return None

    def _empty_profile(self, name: str) -> Dict:
        """Return empty profile structure"""
        return {
            "name": name,
            "party": None,
            "current_position": None,
            "state_of_origin": None,
            "age": None,
            "education": [],
            "career_history": [],
            "promises": [],
            "recent_news": [],
            "controversies": [],
            "social_media": {},
            "contact": {},
            "extracted_at": datetime.utcnow().isoformat(),
            "source_count": 0,
            "sources": []
        }

    async def call_llm(self, user_prompt: str, context: Dict = None) -> str:
        """Call the LLM with extraction-optimized settings"""
        if not self.llm:
            # Fallback: try to import and use anthropic directly
            try:
                import os
                import anthropic

                client = anthropic.Anthropic(
                    api_key=os.getenv("ANTHROPIC_API_KEY")
                )

                message = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )

                return message.content[0].text

            except Exception as e:
                logger.error(f"Direct Anthropic call failed: {e}")
                raise ValueError("LLM client not configured and direct call failed")

        # Use configured LLM client
        messages = [
            {"role": "user", "content": user_prompt}
        ]

        response = await self.llm.chat(
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )

        return response.content

    def stats(self) -> Dict:
        """Return extractor statistics"""
        base_stats = super().stats()
        base_stats.update({
            "cost_level": "MEDIUM",
            "uses_llm": True
        })
        return base_stats
