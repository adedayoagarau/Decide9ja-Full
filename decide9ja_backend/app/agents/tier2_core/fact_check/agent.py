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
        Searches news database + web for evidence, then uses LLM to synthesize verdict.
        """
        # Gather evidence from multiple sources
        evidence_parts = []

        # 1. Search news database
        try:
            from app.database import SessionLocal, NewsArticle
            from sqlalchemy import or_, desc

            db = SessionLocal()
            try:
                # Extract key terms from the claim
                claim = input.raw_text.lower()
                keywords = [w for w in claim.split() if len(w) > 3][:5]
                if keywords:
                    filters = []
                    for kw in keywords:
                        filters.append(NewsArticle.title.ilike(f"%{kw}%"))
                        filters.append(NewsArticle.excerpt.ilike(f"%{kw}%"))

                    articles = db.query(NewsArticle).filter(
                        or_(*filters)
                    ).order_by(desc(NewsArticle.published_date)).limit(5).all()

                    if articles:
                        evidence_parts.append("NEWS DATABASE EVIDENCE:")
                        for a in articles:
                            date_str = a.published_date.strftime("%Y-%m-%d") if a.published_date else "Unknown date"
                            evidence_parts.append(
                                f"- [{date_str}] {a.title} ({a.source_name or a.source}): {(a.excerpt or '')[:200]}"
                            )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"News DB search for fact-check failed: {e}")

        # 2. Search web for current information
        try:
            from app.services.realtime import fetch_web_search
            import asyncio

            loop = asyncio.get_running_loop()
            web_results = await loop.run_in_executor(
                None,
                lambda: fetch_web_search(f"Nigeria {input.raw_text} fact check", limit=5)
            )
            if web_results:
                evidence_parts.append("\nWEB SEARCH EVIDENCE:")
                for r in web_results[:5]:
                    evidence_parts.append(
                        f"- {r.get('title', '')}: {r.get('snippet', r.get('description', ''))[:200]}"
                    )
        except Exception as e:
            logger.debug(f"Web search for fact-check failed: {e}")

        # 3. Check RAG documents
        try:
            from app.services.enhanced_rag import get_enhanced_rag_service
            from app.database import SessionLocal as SL
            db2 = SL()
            try:
                rag = get_enhanced_rag_service(db2)
                import asyncio
                loop = asyncio.get_running_loop()
                context, _ = await loop.run_in_executor(
                    None,
                    lambda: rag.retrieve(input.raw_text)
                )
                if context and len(context) > 50:
                    evidence_parts.append(f"\nKNOWLEDGE BASE:\n{context[:1000]}")
            finally:
                db2.close()
        except Exception as e:
            logger.debug(f"RAG search for fact-check failed: {e}")

        # Build context string
        if evidence_parts:
            context_str = "\n".join(evidence_parts)
        else:
            context_str = "(No external evidence found — rely on training knowledge with caution)"

        user_prompt = f"""Verify this claim/query regarding Nigerian politics:
"{input.raw_text}"

EVIDENCE GATHERED:
{context_str}

Based on the evidence above, provide a fact-check analysis. Be honest about what the evidence supports and what remains unverified.
"""
        return await self.call_llm(user_prompt)

    async def handle(self, input: AgentInput) -> AgentOutput:
        return await super().handle(input)
