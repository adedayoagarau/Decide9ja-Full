"""
FactCheckAgent
==============
Verifies political claims by searching reputable news sources and official records.
Uses Tavily/Google Search via ResearchOrchestrator tools or direct web search.

Cost: MEDIUM (Requires LLM for synthesis + Search API)
"""

import logging
from typing import Dict, Any, List

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel,
    LLMAgent
)
from app.agents.registry import register_agent
from app.agents.tier1_entry.classifier import Intent

logger = logging.getLogger(__name__)


@register_agent
class FactCheckAgent(LLMAgent):
    name = "fact_check"
    description = "Verifies political claims and statements"
    tier = AgentTier.CORE
    cost_level = CostLevel.MEDIUM
    handled_intents = [Intent.FACT_CHECK]

    system_prompt = """You are a neutral, non-partisan political fact-checker for Decide9ja.
Your goal is to verify claims about Nigerian politics, politicians, and government activities.

PROTOCOL:
1. Identify the core claim(s) in the user's input.
2. If the claim is subjective (e.g., "Tinubu is a bad president"), explain that it's a matter of opinion but provide relevant context/metrics.
3. If the claim is factual (e.g., "Tinubu promised X"), verify it against your knowledge base or search results.
4. Rate the claim: TRUE, FALSE, MISLEADING, or UNVERIFIED.
5. Provide evidence/sources for your rating.
6. Use neutral, objective language. Avoid taking sides.

OUTPUT FORMAT:
- **Verdict**: [TRUE/FALSE/MISLEADING/UNVERIFIED]
- **Analysis**: Brief explanation of the facts.
- **Evidence**: List specific quotes, dates, or documents.
- **Sources**: Citations.
"""

    async def can_handle(self, input: AgentInput) -> bool:
        return input.intent == Intent.FACT_CHECK

    async def process_with_llm(self, input: AgentInput) -> str:
        """
        Process fact-check request.
        TODO: Integrate actual Web Search tool (Tavily/SerpAPI) here.
        For now, relies on LLM internal knowledge + RAG context if available.
        """
        # If we had search results in context, we'd add them here
        context_str = ""
        if input.context and "search_results" in input.context:
            context_str = f"\nSEARCH RESULTS:\n{input.context['search_results']}\n"

        user_prompt = f"""Verify this claim/query regarding Nigerian politics:
"{input.raw_text}"

{context_str}

Provide a fact-check analysis based on available information.
"""
        return await self.call_llm(user_prompt)

    async def handle(self, input: AgentInput) -> AgentOutput:
        # In a real implementation, we would trigger a web search first
        # For now, we'll just use the LLM
        return await super().handle(input)
