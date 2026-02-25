"""
Router Agent Implementation

The entry point for all user messages in the multi-agent system.
Responsibilities:
1. Classify user intent using claude_understand()
2. Handle simple intents (greeting, help, thanks) directly
3. Dispatch to specialist agents for complex intents
"""
import logging
from typing import Set, Dict

from app.services.agents.base import BaseAgent
from app.services.agents.protocols import (
    AgentMessage,
    AgentResult,
    AgentCapability,
    HandoffReason,
    UserContext
)
from app.services.agents.router_agent.prompt import get_router_prompt
from app.services.templates import get_template

logger = logging.getLogger(__name__)


class RouterAgent(BaseAgent):
    """
    Central router that classifies intent and dispatches to specialists.

    This is the only agent that calls claude_understand().
    Other agents receive pre-classified AgentMessages.
    """

    name = "router"
    capabilities = [AgentCapability.ROUTING]

    # Simple intents handled directly by router
    handled_intents: Set[str] = {
        "greeting",
        "help",
        "thanks",
    }

    # Intent -> Agent mapping for dispatch
    INTENT_TO_AGENT: Dict[str, str] = {
        # Election Agent
        "follow_candidate": "election",
        "unfollow_candidate": "election",
        "my_candidates": "election",
        "compare_candidates": "election",
        "candidate_search": "election",
        "poll_list": "election",
        "poll_vote": "election",
        "poll_results": "election",
        "trending_topics": "election",
        "election_info": "election",

        # Community Agent
        "my_points": "community",
        "leaderboard": "community",
        "my_civic_profile": "community",
        "report_community_issue": "community",

        # Digest Agent
        "subscribe_digest": "digest",
        "unsubscribe_digest": "digest",

        # Fact Check Agent
        "verify_claim": "fact_check",

        # Flow-based intents
        "issue_report": "flow",
        "voter_registration": "flow",

        # Complex queries -> Response Agent (default)
        "politician_info": "response",
        "politician_record": "response",
        "rep_lookup": "response",
        "news_query": "response",
        "clarification": "response",
        "fallback": "response",
    }

    def get_system_prompt(self) -> str:
        """Return the router's simple response prompt."""
        return get_router_prompt()

    async def can_handle(self, message: AgentMessage) -> bool:
        """Router can handle any message (it's the entry point)."""
        return True

    async def handle(self, message: AgentMessage) -> AgentResult:
        """
        Classify intent and route to appropriate agent.

        Flow:
        1. If message already has intent, use it
        2. Otherwise, call claude_understand() to classify
        3. Handle simple intents directly
        4. Dispatch complex intents to specialists
        """
        # If intent is already set (e.g., from v5 handler), use it
        if message.intent:
            return await self._route_by_intent(message)

        # Classify intent using Claude
        try:
            understanding = await self._classify_intent(message)
            message = message.with_intent(
                intent=understanding.intent.value,
                entities=understanding.entities,
                confidence=understanding.confidence
            )
            message.metadata["retrieval_strategy"] = understanding.retrieval_strategy.value

            logger.info(
                f"[RouterAgent] Classified: intent={understanding.intent.value}, "
                f"confidence={understanding.confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"[RouterAgent] Classification failed: {e}")
            # Fallback to response agent on classification failure
            return self.handoff("response", HandoffReason.FALLBACK, {
                "error": str(e),
                "query": message.query
            })

        return await self._route_by_intent(message)

    async def _classify_intent(self, message: AgentMessage):
        """Use claude_understand to classify the message intent."""
        from app.services.claude_understand import claude_understand

        ctx = message.user_context

        return await claude_understand(
            query=message.query,
            user_state=ctx.state,
            user_lga=ctx.lga,
            user_name=ctx.name or ctx.first_name,
            active_topic=ctx.active_politician_name or ctx.active_topic
        )

    async def _route_by_intent(self, message: AgentMessage) -> AgentResult:
        """Route message to appropriate handler based on intent."""
        intent = message.intent.lower() if message.intent else "fallback"

        # Handle simple intents directly
        if intent in self.handled_intents:
            return await self._handle_simple(intent, message)

        # Look up target agent
        target_agent = self.INTENT_TO_AGENT.get(intent, "response")

        logger.info(f"[RouterAgent] Routing '{intent}' to '{target_agent}'")

        return self.handoff(target_agent, HandoffReason.CAPABILITY_REQUIRED, {
            "intent": intent,
            "entities": message.entities,
            "confidence": message.confidence
        })

    async def _handle_simple(self, intent: str, message: AgentMessage) -> AgentResult:
        """Handle simple intents that don't need a specialist."""
        ctx = message.user_context
        name = ctx.first_name or ctx.name

        if intent == "greeting":
            # Check for returning user
            try:
                from app.services.user_memory import user_memory
                memory = user_memory.get_user_memory(ctx.phone)
                if memory and memory.is_returning_user:
                    welcome_back = user_memory.get_returning_user_summary(ctx.phone)
                    if welcome_back:
                        return self.success(
                            f"{welcome_back}\n\nHow can I help you today?"
                        )
            except Exception as e:
                logger.warning(f"Memory lookup failed: {e}")

            response = get_template("greeting_returning", first_name=name)
            return self.success(response)

        elif intent == "help":
            response = get_template("menu")
            return self.success(response)

        elif intent == "thanks":
            response = get_template("thanks_response")
            return self.success(response)

        # Shouldn't reach here, but fallback to response agent
        return self.handoff("response", HandoffReason.FALLBACK)


def create_message_from_text(
    query: str,
    phone: str,
    name: str = None,
    state: str = None,
    lga: str = None,
    **kwargs
) -> AgentMessage:
    """
    Helper to create an AgentMessage from raw text input.

    Use this when integrating with the v5 message handler.
    """
    user_context = UserContext(
        phone=phone,
        name=name,
        first_name=kwargs.get("first_name"),
        state=state,
        lga=lga,
        active_topic=kwargs.get("active_topic"),
        active_politician_id=kwargs.get("active_politician_id"),
        active_politician_name=kwargs.get("active_politician_name"),
        flow_data=kwargs.get("flow_data", {})
    )

    return AgentMessage(
        query=query,
        user_context=user_context,
        metadata=kwargs.get("metadata", {})
    )
