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

Feature flags: See app/config/feature_flags.py
"""

import uuid
import asyncio
import logging
import time
import hashlib
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from app.agents import (
    AgentInput,
    AgentOutput,
    UserContext,
    registry,
    CostLevel
)

# Import feature flags
from app.config.feature_flags import (
    flags,
    record_v5_error,
    record_v5_success,
)

# Import agents to trigger registration
from app.agents.tier1_entry import GatekeeperAgent, ClassifierAgent, RouterAgent
from app.agents.tier2_core.rep_lookup import RepLookupAgent
from app.agents.tier5_output import FallbackAgent
from app.agents.tier6_analytics import DataCollectorAgent

logger = logging.getLogger(__name__)

# Max handoffs to prevent infinite loops
MAX_HANDOFFS = 10


# =============================================================================
# REQUEST TRACKING
# =============================================================================

@dataclass
class RequestMetrics:
    """Metrics for a single request"""
    request_id: str
    start_time: float
    end_time: float = 0.0
    total_time_ms: float = 0.0
    agents_called: List[str] = field(default_factory=list)
    agent_times_ms: Dict[str, float] = field(default_factory=dict)
    handoffs: List[str] = field(default_factory=list)
    final_agent: str = ""
    intent: str = ""
    cost_level: str = "FREE"
    used_fallback: bool = False
    error: Optional[str] = None

    def finish(self):
        """Mark request as complete and calculate total time"""
        self.end_time = time.time()
        self.total_time_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "total_time_ms": round(self.total_time_ms, 2),
            "agents_called": self.agents_called,
            "agent_times_ms": {k: round(v, 2) for k, v in self.agent_times_ms.items()},
            "handoffs": self.handoffs,
            "final_agent": self.final_agent,
            "intent": self.intent,
            "cost_level": self.cost_level,
            "used_fallback": self.used_fallback,
            "error": self.error,
        }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

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
    user_hash = _hash_phone(phone)

    # Check feature flags for routing decision
    if not flags.should_use_v5(user_hash):
        # Fall back to v4
        if flags.DEBUG_AGENTS:
            logger.debug("Routing to V4 (USE_V5=%s, rollout=%d%%)",
                        flags.USE_V5, flags.V5_ROLLOUT_PERCENTAGE)
        from app.services.message_handler_v4 import handle_message as handle_v4
        return await handle_v4(phone, text)

    # Initialize metrics
    metrics = RequestMetrics(
        request_id=str(uuid.uuid4())[:8],
        start_time=time.time()
    )

    if flags.DEBUG_AGENTS:
        logger.info("[%s] Starting V5 request: %s...",
                   metrics.request_id, text[:50])

    # Build initial input
    input_data = AgentInput(
        message_id=str(uuid.uuid4()),
        raw_text=text or "",
        timestamp=datetime.utcnow(),
        user=UserContext(phone_hash=user_hash),
        voice_url=voice_url,
        image_urls=image_urls or [],
        video_url=video_url,
        document_url=document_url,
        location=location,
    )

    try:
        # Process through agent chain
        output = await _process_agent_chain(input_data, metrics)

        # Record success
        record_v5_success()

        # Collect analytics (async, don't block response)
        if flags.ENABLE_ANALYTICS:
            asyncio.create_task(_collect_analytics(input_data, output, metrics))

        # Log metrics
        metrics.finish()
        _log_metrics(metrics)

        # Format and return
        return _format_response(output)

    except Exception as e:
        # Record error for auto-disable logic
        record_v5_error()
        metrics.error = str(e)
        metrics.finish()

        logger.error("[%s] V5 error after %.0fms: %s",
                    metrics.request_id, metrics.total_time_ms, e)

        # Auto-fallback if enabled
        if flags.AUTO_FALLBACK_ON_ERROR:
            logger.warning("[%s] Falling back to V4", metrics.request_id)
            metrics.used_fallback = True
            from app.services.message_handler_v4 import handle_message as handle_v4
            return await handle_v4(phone, text)

        raise


async def _process_agent_chain(
    input_data: AgentInput,
    metrics: RequestMetrics
) -> AgentOutput:
    """
    Process through agents until we get a final response.

    Chain: gatekeeper → classifier → router → specialist
    """
    current_agent = "gatekeeper"
    handoff_count = 0

    while handoff_count < MAX_HANDOFFS:
        agent = registry.get(current_agent)

        if not agent:
            logger.warning("[%s] Agent '%s' not found, using fallback",
                          metrics.request_id, current_agent)
            agent = registry.get("fallback")
            metrics.used_fallback = True
            if not agent:
                return AgentOutput(
                    success=False,
                    response_text="Sorry, something went wrong. Please try again.",
                    error="no_fallback_agent"
                )

        # Track agent call
        metrics.agents_called.append(current_agent)
        agent_start = time.time()

        # Process with agent
        if flags.DEBUG_AGENTS:
            logger.debug("[%s] → %s", metrics.request_id, current_agent)

        output = await agent.handle(input_data)

        # Track agent time
        agent_time_ms = (time.time() - agent_start) * 1000
        metrics.agent_times_ms[current_agent] = agent_time_ms

        if flags.DEBUG_AGENTS:
            logger.debug("[%s] ← %s (%.0fms)",
                        metrics.request_id, current_agent, agent_time_ms)

        # Check if we need to handoff
        if output.handoff_to:
            # Update input with data from this agent
            _update_input_from_output(input_data, output)

            # Track intent once we have it
            if input_data.intent and not metrics.intent:
                metrics.intent = input_data.intent

            input_data.source_agent = current_agent
            input_data.handoff_reason = output.handoff_reason

            # Log handoff
            handoff_str = f"{current_agent}→{output.handoff_to}"
            metrics.handoffs.append(handoff_str)

            if flags.LOG_HANDOFFS:
                logger.info("[%s] Handoff: %s (%s)",
                           metrics.request_id, handoff_str,
                           output.handoff_reason or "routing")

            current_agent = output.handoff_to
            handoff_count += 1
            continue

        # No handoff - we have a final response
        metrics.final_agent = current_agent
        metrics.cost_level = output.cost_level.name if output.cost_level else "FREE"
        return output

    # Too many handoffs - return error
    logger.error("[%s] Max handoffs (%d) exceeded", metrics.request_id, MAX_HANDOFFS)
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


def _log_metrics(metrics: RequestMetrics):
    """Log request metrics"""
    if not flags.LOG_RESPONSE_TIMES:
        return

    # Summary log
    logger.info(
        "[%s] Completed in %.0fms | agents=%s | intent=%s | cost=%s%s",
        metrics.request_id,
        metrics.total_time_ms,
        "→".join(metrics.agents_called),
        metrics.intent or "unknown",
        metrics.cost_level,
        " [FALLBACK]" if metrics.used_fallback else ""
    )

    # Detailed timing if debug enabled
    if flags.DEBUG_AGENTS and metrics.agent_times_ms:
        timing_parts = [f"{k}={v:.0f}ms" for k, v in metrics.agent_times_ms.items()]
        logger.debug("[%s] Agent times: %s", metrics.request_id, ", ".join(timing_parts))


async def _collect_analytics(
    input_data: AgentInput,
    output: AgentOutput,
    metrics: RequestMetrics
):
    """Collect analytics asynchronously (don't block response)"""
    try:
        collector = registry.get("data_collector")
        if collector:
            # Add metrics to output for analytics
            if not output.analytics_tags:
                output.analytics_tags = {}
            output.analytics_tags["request_id"] = metrics.request_id
            output.analytics_tags["total_time_ms"] = metrics.total_time_ms
            output.analytics_tags["agents_called"] = metrics.agents_called
            output.analytics_tags["used_fallback"] = metrics.used_fallback

            await collector.collect(input_data, output)
    except Exception as e:
        logger.error("[%s] Analytics collection failed: %s", metrics.request_id, e)


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
        logger.error("V5 handler failed, falling back to V4: %s", e)
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


def get_feature_flags() -> dict:
    """Get current feature flag state"""
    return flags.to_dict()


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
    if not flags.ENABLE_FAST_PATH:
        return None

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
        if flags.DEBUG_AGENTS:
            logger.debug("Fast path response for: %s...", text[:30])
        return simple_response

    # Full agent chain for complex queries
    return await handle_message(phone, text, **kwargs)
