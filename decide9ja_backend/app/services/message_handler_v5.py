"""
Message Handler V5 — Multi-Agent Architecture

This is the thin orchestrator for the new agent-based system.

Key differences from V4:
1. Each agent loads ONLY its own prompt (fixes instruction degradation)
2. RouterAgent classifies intent and dispatches to specialists
3. Agents communicate via typed protocols (AgentMessage, AgentResult)
4. ~60% lower token cost due to focused prompts
5. Higher accuracy due to smaller, focused instructions

Flow:
    User Message
         │
         ▼
    Load State & Memory
         │
         ▼
    Check Escape Commands / Active Flows
         │
         ▼
    RouterAgent (classify intent)
         │
         ├──► ElectionAgent (2027 elections)
         ├──► CommunityAgent (gamification)
         ├──► FactCheckAgent (verification)
         ├──► DigestAgent (subscriptions)
         ├──► FlowAgent (multi-step flows)
         └──► ResponseAgent (complex queries)
         │
         ▼
    Save State & Memory
         │
         ▼
    Return Response
"""
import logging
from typing import Optional

from app.models.state import UserState, ConversationFlow
from app.services.state_manager import _get_state_async, _save_state_async
from app.services.user_memory import user_memory
from app.services.enhanced_memory import enhanced_memory
from app.services.templates import get_template, TEMPLATES

# Agent imports
from app.services.agents import (
    AgentMessage,
    AgentResult,
    UserContext,
    register_agent,
    get_agent,
    dispatch_to_agent
)
from app.services.agents.router_agent import RouterAgent
from app.services.agents.election_agent import ElectionAgent
from app.services.agents.community_agent import CommunityAgent
from app.services.agents.digest_agent import DigestAgent
from app.services.agents.fact_check_agent import FactCheckAgent
from app.services.agents.flow_agent import FlowAgent
from app.services.agents.response_agent import ResponseAgent

logger = logging.getLogger(__name__)

# Escape commands that reset conversation
ESCAPE_COMMANDS = {"reset", "restart", "cancel", "menu", "stop", "start over", "new"}

# Flag to track if agents are registered
_agents_initialized = False


def _initialize_agents():
    """Register all agents. Called once on first message."""
    global _agents_initialized
    if _agents_initialized:
        return

    # Register all agents
    register_agent(RouterAgent())
    register_agent(ElectionAgent())
    register_agent(CommunityAgent())
    register_agent(DigestAgent())
    register_agent(FactCheckAgent())
    register_agent(FlowAgent())
    register_agent(ResponseAgent())

    _agents_initialized = True
    logger.info("All agents initialized")


async def handle_message(phone: str, text: str, media_url: str = None) -> str:
    """
    Main entry point — Multi-Agent Architecture.

    Flow:
    1. Initialize agents (once)
    2. Load state & memory
    3. Save user message to persistent history
    4. Check escape commands
    5. Check for active flows (onboarding, issue, etc.)
    6. If IDLE → dispatch to RouterAgent
    7. Process AgentResult (response, handoffs, flow changes)
    8. Save state & memory
    """
    # Initialize agents on first call
    _initialize_agents()

    text = text.strip() if text else ""
    text_lower = text.lower()

    # ===========================================
    # STEP 1: Load State & Memory
    # ===========================================
    try:
        state = await _get_state_async(phone)
        memory = user_memory.get_user_memory(phone)
        is_returning = memory.is_returning_user if memory else False
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
        state = UserState(
            user_id="temp",
            phone=phone,
            flow=ConversationFlow.IDLE
        )
        memory = None
        is_returning = False

    # ===========================================
    # STEP 2: Save User Message
    # ===========================================
    user_memory.save_message(phone, "user", text)

    # ===========================================
    # STEP 3: Check Escape Commands
    # ===========================================
    if text_lower in ESCAPE_COMMANDS:
        state.clear_flow()
        state.clear_context()
        await _save_state_async(state)
        response = get_template("menu")
        user_memory.save_message(phone, "assistant", response)
        return response

    # ===========================================
    # STEP 4: Add to Session History
    # ===========================================
    state.add_to_history("user", text)

    # ===========================================
    # STEP 5: Handle Active Flows (non-IDLE states)
    # ===========================================
    try:
        if state.flow == ConversationFlow.ONBOARDING:
            # Onboarding is special - still handled by dedicated flow
            from app.services.flows.onboarding import handle_onboarding
            response = await handle_onboarding(state, text)

        elif state.flow in [ConversationFlow.ISSUE_FLOW,
                           ConversationFlow.CONFIRMING,
                           ConversationFlow.AWAITING_CLARIFY]:
            # Route to FlowAgent
            response = await _dispatch_to_flow_agent(state, text, media_url)

        else:
            # IDLE state — use agent dispatch
            response = await _handle_idle_with_agents(state, text, memory)

    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        response = TEMPLATES.get("error_generic", "Something went wrong. Please try again.")

    # ===========================================
    # STEP 6: Update State & Save
    # ===========================================
    state.add_to_history("assistant", response)
    await _save_state_async(state)
    user_memory.save_message(phone, "assistant", response)

    # ===========================================
    # STEP 7: Enhanced Memory (async)
    # ===========================================
    await _process_enhanced_memory(phone, text, state)

    return response


async def _handle_idle_with_agents(state: UserState, text: str, memory=None) -> str:
    """
    Handle IDLE state using multi-agent dispatch.

    1. Check if onboarding needed
    2. Create AgentMessage
    3. Dispatch to RouterAgent
    4. Process result and any handoffs
    """

    # Check onboarding
    if not state.is_onboarding_complete():
        from app.services.flows.onboarding import handle_onboarding
        was_already_onboarding = state.flow == ConversationFlow.ONBOARDING
        state.flow = ConversationFlow.ONBOARDING
        if not was_already_onboarding:
            state.flow_step = 0
            state.greeted = False
        return await handle_onboarding(state, text)

    # Create AgentMessage from state
    user_context = UserContext.from_user_state(state)

    message = AgentMessage(
        query=text,
        user_context=user_context,
        metadata={
            "is_returning_user": memory.is_returning_user if memory else False,
            "flow_state": state.flow.value if state.flow else "idle"
        }
    )

    # Dispatch to router agent
    result = await dispatch_to_agent("router", message)

    # Process result
    response = _process_agent_result(result, state)

    return response


async def _dispatch_to_flow_agent(state: UserState, text: str, media_url: str = None) -> str:
    """Dispatch to FlowAgent for active flow handling."""
    user_context = UserContext.from_user_state(state)

    # Add flow-specific data
    flow_data = state.flow_data or {}
    flow_data["flow_step"] = state.flow_step
    if media_url:
        flow_data["media_url"] = media_url
    user_context.flow_data = flow_data

    message = AgentMessage(
        query=text,
        user_context=user_context,
        metadata={
            "flow_state": state.flow.value if state.flow else "idle"
        }
    )

    result = await dispatch_to_agent("flow", message)
    return _process_agent_result(result, state)


def _process_agent_result(result: AgentResult, state: UserState) -> str:
    """
    Process AgentResult and update state as needed.

    Handles:
    - Response text
    - Flow state changes
    - Flow data updates
    """
    if not result.success and result.error:
        logger.error(f"Agent error: {result.error}")
        return TEMPLATES.get("error_generic", "Something went wrong. Please try again.")

    # Process data for state changes
    data = result.data or {}

    # Handle flow changes
    if data.get("clear_flow"):
        state.clear_flow()

    if data.get("set_flow"):
        flow_name = data["set_flow"]
        flow_map = {
            "issue_flow": ConversationFlow.ISSUE_FLOW,
            "confirming": ConversationFlow.CONFIRMING,
            "awaiting_clarify": ConversationFlow.AWAITING_CLARIFY,
            "onboarding": ConversationFlow.ONBOARDING,
        }
        state.flow = flow_map.get(flow_name, ConversationFlow.IDLE)

    if "set_flow_step" in data:
        state.flow_step = data["set_flow_step"]

    if data.get("update_flow_data"):
        if state.flow_data is None:
            state.flow_data = {}
        state.flow_data.update(data["update_flow_data"])

    if data.get("flow_data"):
        state.flow_data = data["flow_data"]

    # Handle active politician tracking
    if data.get("active_poll"):
        if state.flow_data is None:
            state.flow_data = {}
        state.flow_data["active_poll"] = data["active_poll"]

    if data.get("clear_active_poll"):
        if state.flow_data:
            state.flow_data.pop("active_poll", None)

    return result.response or TEMPLATES.get("error_generic", "Something went wrong.")


async def _process_enhanced_memory(phone: str, text: str, state: UserState):
    """Process enhanced memory asynchronously."""
    try:
        import asyncio

        # Store embedding for semantic search
        asyncio.create_task(
            enhanced_memory.embed_and_store_message(
                phone, "user", text,
                metadata={"intent": state.flow.value if state.flow else "idle"}
            )
        )

        # Periodic consolidation
        memory_stats = enhanced_memory.get_memory_stats(phone)
        if memory_stats.get("total_messages", 0) % 10 == 0:
            asyncio.create_task(enhanced_memory.consolidate_memory(phone))

    except Exception as e:
        logger.warning(f"Enhanced memory processing error: {e}")


# ===========================================
# Feature flag for switching between v4 and v5
# ===========================================

USE_V5_HANDLER = True  # Set to False to fall back to v4


async def handle_message_with_fallback(phone: str, text: str, media_url: str = None) -> str:
    """
    Entry point with automatic fallback to v4.

    Use this during migration to safely test v5.
    """
    if USE_V5_HANDLER:
        try:
            return await handle_message(phone, text, media_url)
        except Exception as e:
            logger.error(f"V5 handler failed, falling back to V4: {e}")
            from app.services.message_handler_v4 import handle_message as handle_v4
            return await handle_v4(phone, text, media_url)
    else:
        from app.services.message_handler_v4 import handle_message as handle_v4
        return await handle_v4(phone, text, media_url)
