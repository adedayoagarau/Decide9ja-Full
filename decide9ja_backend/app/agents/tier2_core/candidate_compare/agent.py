"""
CandidateCompareAgent - Neutral side-by-side candidate comparison

Part of Tier 2 (Core Knowledge Agents) in the multi-agent architecture.
Provides unbiased, factual comparisons between political candidates.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any

from app.agents.base import LLMAgent, AgentInput, AgentOutput
from app.agents.registry import register_agent, registry
from .prompt import COMPARISON_SYSTEM_PROMPT, PARSE_COMPARISON_PROMPT, GENERATE_COMPARISON_PROMPT

logger = logging.getLogger(__name__)


@register_agent
class CandidateCompareAgent(LLMAgent):
    """
    Neutral side-by-side candidate comparison agent.

    Features:
    - Extracts candidate names and optional topic from user query
    - Fetches cached data for both candidates in parallel
    - Generates WhatsApp-formatted neutral comparison
    - Never endorses or shows preference

    Cost: Paid (uses LLM for comparison generation)
    """

    name = "candidate_compare"
    description = "Compare two political candidates neutrally"
    cost_type = "paid"

    # Valid comparison topics
    VALID_TOPICS = [
        "education",
        "healthcare",
        "security",
        "economy",
        "infrastructure",
        "agriculture",
        "corruption",
        "youth",
        "women",
        "technology",
        "environment",
    ]

    async def process(self, input: AgentInput) -> AgentOutput:
        """
        Process candidate comparison request.

        Flow:
        1. Parse request to extract candidate names and topic
        2. Fetch both candidates from cache in parallel
        3. Handle cache misses gracefully
        4. Generate neutral comparison
        """
        try:
            # Parse the comparison request
            parsed = await self._parse_comparison(input.message)

            candidate_a = parsed.get("candidate_a")
            candidate_b = parsed.get("candidate_b")
            topic = parsed.get("topic")

            # Validate we have two candidates
            if not candidate_a or not candidate_b:
                return AgentOutput(
                    success=False,
                    response_text=(
                        "Please name two candidates to compare.\n\n"
                        "*Examples:*\n"
                        "• Compare Tinubu and Obi\n"
                        "• Atiku vs Kwankwaso on education\n"
                        "• Difference between APC and PDP candidates"
                    ),
                    agent_name=self.name
                )

            # Check if comparing same person
            if self._normalize_name(candidate_a) == self._normalize_name(candidate_b):
                return AgentOutput(
                    success=False,
                    response_text="You're comparing the same person! Please name two different candidates.",
                    agent_name=self.name
                )

            # Get knowledge cache agent
            cache = registry.get("knowledge_cache")
            if not cache:
                logger.error("KnowledgeCacheAgent not found in registry")
                return AgentOutput(
                    success=False,
                    response_text="Comparison service temporarily unavailable.",
                    agent_name=self.name
                )

            # Parallel fetch from cache
            data_a, data_b = await asyncio.gather(
                cache.get_politician(candidate_a),
                cache.get_politician(candidate_b),
                return_exceptions=True
            )

            # Handle exceptions from parallel fetch
            if isinstance(data_a, Exception):
                logger.error(f"Error fetching {candidate_a}: {data_a}")
                data_a = None
            if isinstance(data_b, Exception):
                logger.error(f"Error fetching {candidate_b}: {data_b}")
                data_b = None

            # Handle cache misses
            missing = []
            if not data_a:
                missing.append(candidate_a)
            if not data_b:
                missing.append(candidate_b)

            if missing:
                # Record cache misses for research prioritization
                for name in missing:
                    try:
                        await cache.record_cache_miss(
                            query=input.message,
                            intent="candidate_compare",
                            entity=name
                        )
                    except Exception as e:
                        logger.warning(f"Failed to record cache miss: {e}")

                return AgentOutput(
                    success=False,
                    response_text=(
                        f"I'm still researching *{', '.join(missing)}*.\n\n"
                        "Try again in a few hours, or ask about someone else.\n\n"
                        "_Our research team is working on it!_"
                    ),
                    agent_name=self.name,
                    context={"missing_candidates": missing}
                )

            # Get promises for both candidates
            promises_a, promises_b = [], []
            try:
                if topic:
                    promises_a, promises_b = await asyncio.gather(
                        cache.get_promises(candidate_a, topic=topic),
                        cache.get_promises(candidate_b, topic=topic),
                        return_exceptions=True
                    )
                else:
                    promises_a, promises_b = await asyncio.gather(
                        cache.get_promises(candidate_a),
                        cache.get_promises(candidate_b),
                        return_exceptions=True
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch promises: {e}")

            # Handle promise fetch exceptions
            if isinstance(promises_a, Exception):
                promises_a = []
            if isinstance(promises_b, Exception):
                promises_b = []

            # Generate neutral comparison
            comparison = await self._generate_comparison(
                a={"profile": data_a.get("data", {}), "promises": promises_a[:5] if promises_a else []},
                b={"profile": data_b.get("data", {}), "promises": promises_b[:5] if promises_b else []},
                topic=topic
            )

            # Combine sources from both candidates
            sources = []
            if data_a and data_a.get("sources"):
                sources.extend(data_a["sources"][:2])
            if data_b and data_b.get("sources"):
                sources.extend(data_b["sources"][:2])

            return AgentOutput(
                success=True,
                response_text=comparison,
                sources=sources,
                agent_name=self.name,
                context={
                    "candidates": [candidate_a, candidate_b],
                    "topic": topic
                }
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return AgentOutput(
                success=False,
                response_text="I couldn't understand that comparison request. Try: 'Compare Tinubu and Obi'",
                agent_name=self.name
            )
        except Exception as e:
            logger.error(f"Comparison failed: {e}")
            return AgentOutput(
                success=False,
                response_text="Something went wrong with the comparison. Please try again.",
                agent_name=self.name
            )

    async def _parse_comparison(self, message: str) -> Dict[str, Any]:
        """
        Extract candidates and topic from message using LLM.

        Returns:
            Dict with candidate_a, candidate_b, topic (or None for each)
        """
        prompt = PARSE_COMPARISON_PROMPT.format(
            message=message,
            valid_topics=", ".join(self.VALID_TOPICS)
        )

        result = await self._call_llm(prompt, system_prompt=COMPARISON_SYSTEM_PROMPT)

        # Parse JSON response
        try:
            # Handle potential markdown code blocks
            result = result.strip()
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            result = result.strip()

            parsed = json.loads(result)

            # Validate topic if provided
            if parsed.get("topic") and parsed["topic"] not in self.VALID_TOPICS:
                parsed["topic"] = None

            return parsed
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse comparison request: {result}")
            return {"candidate_a": None, "candidate_b": None, "topic": None}

    async def _generate_comparison(
        self,
        a: Dict[str, Any],
        b: Dict[str, Any],
        topic: Optional[str]
    ) -> str:
        """
        Generate neutral WhatsApp-formatted comparison.

        Args:
            a: Dict with profile and promises for candidate A
            b: Dict with profile and promises for candidate B
            topic: Optional topic to focus comparison on
        """
        name_a = a["profile"].get("name", "Candidate A")
        name_b = b["profile"].get("name", "Candidate B")

        prompt = GENERATE_COMPARISON_PROMPT.format(
            name_a=name_a,
            party_a=a["profile"].get("party", "Unknown"),
            position_a=a["profile"].get("current_position", "Unknown"),
            promises_a=json.dumps(a["promises"][:3]) if a["promises"] else "No promises on record",
            bio_a=a["profile"].get("biography", "")[:500] if a["profile"].get("biography") else "",
            name_b=name_b,
            party_b=b["profile"].get("party", "Unknown"),
            position_b=b["profile"].get("current_position", "Unknown"),
            promises_b=json.dumps(b["promises"][:3]) if b["promises"] else "No promises on record",
            bio_b=b["profile"].get("biography", "")[:500] if b["profile"].get("biography") else "",
            topic_section=f"FOCUS ON: {topic.upper()}" if topic else "GENERAL COMPARISON",
            topic_title=f" on {topic.title()}" if topic else ""
        )

        return await self._call_llm(prompt, system_prompt=COMPARISON_SYSTEM_PROMPT)

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        return " ".join(name.lower().split())

    async def can_handle(self, input: AgentInput) -> bool:
        """Check if this agent can handle the input"""
        message = input.message.lower()

        comparison_keywords = [
            "compare", "vs", "versus", "difference between",
            "who is better", " or ", "vs."
        ]

        return any(kw in message for kw in comparison_keywords)
