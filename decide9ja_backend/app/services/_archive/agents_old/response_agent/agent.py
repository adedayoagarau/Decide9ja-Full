"""
Response Agent Implementation

Handles complex queries requiring retrieval and generation:
- POLITICIAN_INFO, POLITICIAN_RECORD
- REP_LOOKUP
- NEWS_QUERY
- General fallback queries
"""
import os
import logging
from typing import Set, Optional

from app.services.agents.base import BaseAgent
from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability,
    HandoffReason
)
from app.services.agents.response_agent.prompt import get_response_prompt_with_context
from app.services.templates import get_template

logger = logging.getLogger(__name__)


class ResponseAgent(BaseAgent):
    """
    General-purpose response agent for complex queries.

    Handles queries requiring:
    - Database retrieval (politicians, representatives)
    - Web search (news, current events)
    - RAG (knowledge base documents)
    - Claude generation with context
    """

    name = "response"
    capabilities = [AgentCapability.RESPONSE_GENERATION, AgentCapability.RETRIEVAL]
    handled_intents: Set[str] = {
        "politician_info",
        "politician_record",
        "rep_lookup",
        "news_query",
        "clarification",
        "fallback",
    }

    # Use slightly larger token limit for complex responses
    max_tokens = 600

    def get_system_prompt(self) -> str:
        """Return the response-focused system prompt."""
        return get_response_prompt_with_context()

    async def can_handle(self, message: AgentMessage) -> bool:
        """Response agent is the fallback - handles anything."""
        return True

    async def handle(self, message: AgentMessage) -> AgentResult:
        """Handle complex queries with retrieval and generation."""
        intent = message.intent.lower() if message.intent else "fallback"
        ctx = message.user_context

        try:
            # Get retrieval strategy from metadata
            strategy = message.metadata.get("retrieval_strategy", "hybrid")

            # Perform retrieval
            retrieval_result, agentic_result = await self._retrieve(message, strategy)

            # Generate response with context
            response = await self._generate_response(
                message, retrieval_result, agentic_result
            )

            return self.success(response)

        except Exception as e:
            logger.exception(f"[ResponseAgent] Error handling {intent}: {e}")
            # Use smart fallback
            return await self._smart_fallback(message)

    async def _retrieve(self, message: AgentMessage, strategy: str):
        """Perform retrieval based on strategy."""
        from app.services.claude_understand import (
            QueryUnderstanding,
            Intent,
            RetrievalStrategy
        )
        from app.services.intelligent_retrieval import intelligent_retrieve
        from app.services.agentic_retrieval import agentic_retrieve

        ctx = message.user_context

        # Build understanding object for legacy retrieval
        intent_map = {
            "politician_info": Intent.POLITICIAN_INFO,
            "politician_record": Intent.POLITICIAN_RECORD,
            "rep_lookup": Intent.REP_LOOKUP,
            "news_query": Intent.NEWS_QUERY,
        }
        strategy_map = {
            "db_lookup": RetrievalStrategy.DB_LOOKUP,
            "position_lookup": RetrievalStrategy.POSITION_LOOKUP,
            "rep_lookup": RetrievalStrategy.REP_LOOKUP,
            "web_search": RetrievalStrategy.WEB_SEARCH,
            "rag_search": RetrievalStrategy.RAG_SEARCH,
            "hybrid": RetrievalStrategy.HYBRID,
            "none": RetrievalStrategy.NONE,
        }

        understanding = QueryUnderstanding(
            intent=intent_map.get(message.intent, Intent.FALLBACK),
            entities=message.entities,
            retrieval_strategy=strategy_map.get(strategy, RetrievalStrategy.HYBRID),
            confidence=message.confidence
        )

        # Run agentic retrieval
        user_context_dict = {
            "state": ctx.state,
            "lga": ctx.lga,
            "name": ctx.first_name or ctx.name,
            "phone": ctx.phone
        }
        agentic_result = await agentic_retrieve(message.query, user_context_dict)

        # Run legacy retrieval for fallback
        retrieval_result = await intelligent_retrieve(
            understanding=understanding,
            user_state=ctx.state,
            user_lga=ctx.lga
        )

        return retrieval_result, agentic_result

    async def _generate_response(
        self,
        message: AgentMessage,
        retrieval_result,
        agentic_result
    ) -> str:
        """Generate response using Claude with retrieved context."""
        from app.services.intelligent_retrieval import format_retrieval_for_context
        from app.services.agentic_retrieval import RetrievalStatus
        from app.services.output_guard import guard_output

        ctx = message.user_context

        # Format context from retrieval
        legacy_context = format_retrieval_for_context(retrieval_result)

        # Prefer agentic context if successful
        agentic_success = agentic_result and agentic_result.status in [
            RetrievalStatus.SUCCESS, RetrievalStatus.PARTIAL
        ]

        if agentic_success and agentic_result.graded_context:
            context = f"""RETRIEVED INFORMATION:
{agentic_result.graded_context}

ADDITIONAL CONTEXT:
{legacy_context}"""
        else:
            context = legacy_context

        # Build the prompt
        system_prompt = get_response_prompt_with_context(
            user_state=ctx.state,
            user_lga=ctx.lga,
            user_name=ctx.first_name or ctx.name
        )

        user_prompt = f"""QUERY: {message.query}

{context}

Please provide a helpful response based on the retrieved information. If the information is insufficient, acknowledge what you don't know and offer alternatives."""

        try:
            # Call Claude
            response = await self.call_claude(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=self.max_tokens
            )

            # Apply output guardrails
            return await guard_output(response, context=message.query)

        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            raise

    async def _smart_fallback(self, message: AgentMessage) -> AgentResult:
        """Smart fallback when main processing fails."""
        from app.services.nigerian_politics import analyze_query_for_hot_issues

        ctx = message.user_context

        # Check if it's a hot issue we know about
        hot_issue = analyze_query_for_hot_issues(message.query)
        if hot_issue:
            issue_ctx = hot_issue['context']
            if isinstance(issue_ctx, dict):
                result = f"Regarding {hot_issue['issue'].replace('_', ' ')}:\n\n"
                if 'status' in issue_ctx:
                    result += f"Status: {issue_ctx['status']}\n"
                if 'impact' in issue_ctx:
                    result += f"Impact: {issue_ctx['impact']}\n"
                if 'sentiment' in issue_ctx:
                    result += f"Public sentiment: {issue_ctx['sentiment']}\n"
                result += "\nWant more current details?"
                return self.success(result)

        # Try web search as last resort
        try:
            from app.services.realtime import fetch_web_search
            web_results = fetch_web_search(message.query, limit=3)
            if web_results:
                result = "Here's what I found online:\n\n"
                for item in web_results[:3]:
                    result += f"• {item.get('title', 'News')}\n"
                result += "\nWant more details on any of these?"
                return self.success(result)
        except Exception as e:
            logger.error(f"Fallback web search failed: {e}")

        # Final fallback
        response = get_template("no_info_found", query=message.query)
        return self.success(response)
