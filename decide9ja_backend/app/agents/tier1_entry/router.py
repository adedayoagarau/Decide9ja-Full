"""
RouterAgent
===========
Routes classified intents to specialist agents.

NO LLM CALLS - pure rules-based routing.
Cost: FREE
"""

import logging

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent, registry
from app.agents.tier1_entry.classifier import Intent

logger = logging.getLogger(__name__)


@register_agent
class RouterAgent(BaseAgent):
    name = "router"
    description = "Routes intents to specialist agents"
    tier = AgentTier.ENTRY
    cost_level = CostLevel.FREE
    handled_intents = ["__all__"]

    # Intent to agent mapping
    ROUTING_TABLE = {
        # Simple responses (handled by templates, no specialist needed)
        Intent.GREETING: "response_composer",
        Intent.HELP: "response_composer",
        Intent.THANKS: "response_composer",
        Intent.GOODBYE: "response_composer",

        # Representation
        Intent.REP_LOOKUP: "rep_lookup",
        Intent.POLITICIAN_INFO: "politician_profile",
        Intent.POLITICIAN_CONTACT: "politician_profile",
        Intent.POLITICIAN_NEWS: "news_query",

        # Promises
        Intent.PROMISE_LOOKUP: "promise_lookup",
        Intent.PROMISE_STATUS: "promise_lookup",
        Intent.PROMISE_COMPARE: "promise_lookup",

        # Elections
        Intent.CANDIDATE_SEARCH: "election_info",
        Intent.CANDIDATE_FOLLOW: "election_info",
        Intent.CANDIDATE_UNFOLLOW: "election_info",
        Intent.CANDIDATE_COMPARE: "election_info",
        Intent.MY_CANDIDATES: "election_info",
        Intent.ELECTION_INFO: "election_info",
        Intent.VOTER_REGISTRATION: "election_info",
        Intent.POLLING_UNIT: "election_info",

        # News
        Intent.NEWS_QUERY: "news_query",
        Intent.TRENDING: "news_query",

        # Issues
        Intent.REPORT_ISSUE: "issue_intake",
        Intent.TRACK_ISSUE: "issue_tracking",
        Intent.MY_ISSUES: "issue_tracking",

        # Engagement
        Intent.MY_POINTS: "engagement",
        Intent.LEADERBOARD: "engagement",
        Intent.SUBSCRIBE_DIGEST: "engagement",
        Intent.UNSUBSCRIBE_DIGEST: "engagement",

        # Verification
        Intent.FACT_CHECK: "fact_check",

        # Unknown
        Intent.UNKNOWN: "fallback",
    }

    # Intents that can use template responses directly
    TEMPLATE_INTENTS = {
        Intent.GREETING,
        Intent.HELP,
        Intent.THANKS,
        Intent.GOODBYE
    }

    # Template mappings for simple intents
    TEMPLATES = {
        Intent.GREETING: "greeting_response",
        Intent.HELP: "help_menu",
        Intent.THANKS: "thanks_response",
        Intent.GOODBYE: "goodbye_response",
    }

    async def can_handle(self, input: AgentInput) -> bool:
        return True

    async def handle(self, input: AgentInput) -> AgentOutput:
        self._call_count += 1

        intent = input.intent or Intent.UNKNOWN
        confidence = input.confidence

        # Check if this is a template-based response
        if intent in self.TEMPLATE_INTENTS:
            return AgentOutput(
                success=True,
                handoff_to="response_composer",
                handoff_reason="template_response",
                data={
                    "template": self.TEMPLATES.get(intent, "default_response"),
                    "intent": intent,
                    "user": input.user.__dict__ if hasattr(input.user, '__dict__') else input.user
                },
                cost_level=CostLevel.FREE
            )

        # Find the specialist agent
        target_agent = self.ROUTING_TABLE.get(intent, "fallback")

        # Verify agent exists, fallback if not
        agent = registry.get(target_agent)
        if not agent:
            logger.warning(f"Agent '{target_agent}' not found, using fallback")
            target_agent = "fallback"

        return AgentOutput(
            success=True,
            handoff_to=target_agent,
            handoff_reason=f"intent_{intent}",
            data={
                "intent": intent,
                "confidence": confidence,
                "entities": input.entities
            },
            cost_level=CostLevel.FREE,
            analytics_tags={
                "routed_to": target_agent,
                "intent": intent,
                "confidence": confidence
            }
        )
