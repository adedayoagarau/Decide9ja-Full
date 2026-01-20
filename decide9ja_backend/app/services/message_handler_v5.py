"""
Message Handler V5
==================
Thin orchestrator using the new tiered multi-agent architecture.

Architecture: Database First, LLM Last
Cost Target: 80% of queries at $0 (database + cache + rules)

Flow:
1. Gatekeeper → User recognition (FREE)
2. Classifier → Intent detection (70% FREE, 30% CHEAP)
3. Router → Agent dispatch (FREE)
4. Specialist → Handle query (mostly FREE)
5. DataCollector → Analytics (FREE)

Feature flag: Set USE_V5=true to enable, falls back to v4.
"""

import os
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Optional
import hashlib

from app.agents import (
    AgentInput,
    AgentOutput,
    UserContext,
    registry,
    CostLevel
)

# Import agents to trigger registration
from app.agents.tier1_entry import GatekeeperAgent, ClassifierAgent, RouterAgent
from app.agents.tier2_core.rep_lookup import RepLookupAgent
from app.agents.tier5_output import FallbackAgent
from app.agents.tier6_analytics import DataCollectorAgent

logger = logging.getLogger(__name__)

# Feature flag
USE_V5 = os.getenv("USE_V5", "false").lower() == "true"

# Max handoffs to prevent infinite loops
MAX_HANDOFFS = 10


async def handle_message(
    phone: str,
    text: str,
    voice_url: Optional[str] = None,
    image_urls: Optional[list] = None,
    video_url: Optional[str] = None,
    document_url: Optional[str] = None,
    location: Optional[dict] = None,
) -> str:
    """
    Main entry point for all messages.

    Routes through the tiered agent system:
    Gatekeeper → Classifier → Router → Specialist → Response
    """

    if not USE_V5:
        # Fall back to v4
        from app.services.message_handler_v4 import handle_message as handle_v4
        return await handle_v4(phone, text)

    # Build initial input
    input_data = AgentInput(
        message_id=str(uuid.uuid4()),
        raw_text=text or "",
        timestamp=datetime.utcnow(),
        user=UserContext(phone_hash=_hash_phone(phone)),
        voice_url=voice_url,
        image_urls=image_urls or [],
        video_url=video_url,
        document_url=document_url,
        location=location,
    )

    # Process through agent chain
    output = await _process_agent_chain(input_data)

    # Collect analytics (async, don't block response)
    asyncio.create_task(_collect_analytics(input_data, output))

    # Format and return
    return _format_response(output)


async def _process_agent_chain(input_data: AgentInput) -> AgentOutput:
    """
    Process through agents until we get a final response.

    Chain: gatekeeper → classifier → router → specialist
    """

    current_agent = "gatekeeper"
    handoff_count = 0

    while handoff_count < MAX_HANDOFFS:
        agent = registry.get(current_agent)

        if not agent:
            logger.warning(f"Agent '{current_agent}' not found, using fallback")
            agent = registry.get("fallback")
            if not agent:
                return AgentOutput(
                    success=False,
                    response_text="Sorry, something went wrong. Please try again.",
                    error="no_fallback_agent"
                )

        # Process with agent
        logger.debug(f"Processing with agent: {current_agent}")
        output = await agent.handle(input_data)

        # Check if we need to handoff
        if output.handoff_to:
            # Update input with data from this agent
            _update_input_from_output(input_data, output)

            input_data.source_agent = current_agent
            input_data.handoff_reason = output.handoff_reason

            current_agent = output.handoff_to
            handoff_count += 1

            logger.debug(f"Handoff: {input_data.source_agent} → {current_agent} ({output.handoff_reason})")
            continue

        # No handoff - we have a final response
        return output

    # Too many handoffs - return error
    logger.error(f"Max handoffs ({MAX_HANDOFFS}) exceeded")
    return AgentOutput(
        success=False,
        response_text="Sorry, I'm having trouble processing that. Please try again.",
        error="max_handoffs_exceeded"
    )


def _update_input_from_output(input_data: AgentInput, output: AgentOutput):
    """Update input with data from agent output for next agent"""
    if not output.data:
        return

    # Update intent and classification
    if "intent" in output.data:
        input_data.intent = output.data["intent"]
    if "confidence" in output.data:
        input_data.confidence = output.data["confidence"]
    if "entities" in output.data:
        input_data.entities = output.data["entities"]

    # Update user context
    if "user" in output.data:
        user_data = output.data["user"]
        if isinstance(user_data, dict):
            input_data.user = UserContext(**user_data)
        elif isinstance(user_data, UserContext):
            input_data.user = user_data


def _format_response(output: AgentOutput) -> str:
    """Format agent output for WhatsApp/user"""

    if not output.success:
        return output.response_text or "Sorry, I couldn't process that. Please try again."

    response = output.response_text or ""

    # Add interactive buttons as numbered options
    if output.buttons:
        response += "\n\n"
        for i, button in enumerate(output.buttons, 1):
            response += f"{i}. {button['text']}\n"

    # Add list items
    if output.list_items:
        response += "\n"
        for item in output.list_items:
            response += f"• {item}\n"

    # Add source citations
    if output.sources:
        response += f"\n\n_Source: {', '.join(output.sources)}_"

    return response.strip()


def _hash_phone(phone: str) -> str:
    """Hash phone number for privacy"""
    return hashlib.sha256(phone.encode()).hexdigest()[:16]


async def _collect_analytics(input_data: AgentInput, output: AgentOutput):
    """Collect analytics asynchronously (don't block response)"""
    try:
        collector = registry.get("data_collector")
        if collector:
            await collector.collect(input_data, output)
    except Exception as e:
        logger.error(f"Analytics collection failed: {e}")


# =============================================================================
# ALTERNATIVE ENTRY POINTS
# =============================================================================

async def handle_message_with_fallback(
    phone: str,
    text: str,
    **kwargs
) -> str:
    """
    Entry point with automatic fallback to v4 on any error.
    Use during migration for safety.
    """
    try:
        return await handle_message(phone, text, **kwargs)
    except Exception as e:
        logger.error(f"V5 handler failed, falling back to V4: {e}")
        from app.services.message_handler_v4 import handle_message as handle_v4
        return await handle_v4(phone, text)


def configure_agents(db_client=None, cache_client=None, llm_client=None):
    """
    Configure shared clients for all agents.
    Call this at application startup.
    """
    registry.configure(
        db_client=db_client,
        cache_client=cache_client,
        llm_client=llm_client
    )
    logger.info("Agent registry configured")


def get_agent_stats() -> dict:
    """Get statistics for all agents"""
    return registry.stats()


# =============================================================================
# SIMPLE QUERIES (bypass full chain for obvious cases)
# =============================================================================

GREETING_WORDS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
HELP_WORDS = {"help", "menu", "options", "commands"}

async def handle_simple_query(phone: str, text: str) -> Optional[str]:
    """
    Fast path for simple queries that don't need full agent chain.
    Returns None if query is not simple.
    """
    text_lower = text.lower().strip()

    # Greetings
    if text_lower in GREETING_WORDS or text_lower.startswith(("hi ", "hello ")):
        return (
            "Hello! I'm Decide9ja, your guide to Nigerian politics.\n\n"
            "I can help you:\n"
            "• Find your representatives\n"
            "• Track 2027 election candidates\n"
            "• Report community issues\n"
            "• Check political promises\n\n"
            "What would you like to know?"
        )

    # Help
    if text_lower in HELP_WORDS:
        return (
            "*Decide9ja Menu*\n\n"
            "Try asking:\n"
            "• \"Who is my senator?\"\n"
            "• \"Who is running for president in 2027?\"\n"
            "• \"What did Tinubu promise?\"\n"
            "• \"Report bad road in my area\"\n"
            "• \"Follow Tinubu\" (get updates)\n\n"
            "Or just ask any question about Nigerian politics!"
        )

    return None


async def handle_message_optimized(
    phone: str,
    text: str,
    **kwargs
) -> str:
    """
    Optimized entry point with simple query fast path.
    Use this for lowest latency.
    """
    # Try simple query first (no agent chain)
    simple_response = await handle_simple_query(phone, text)
    if simple_response:
        return simple_response

    # Full agent chain for complex queries
    return await handle_message(phone, text, **kwargs)
