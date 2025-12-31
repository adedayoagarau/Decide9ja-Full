"""
Decide9ja Message Handler v3
Conversation-design-driven architecture with proper state management.

Key principles:
1. Load state FIRST
2. Check escape commands
3. If in active flow → go to flow handler (SKIP intent classification)
4. If IDLE → classify intent → route to handler
5. Update state LAST
"""
import logging
from datetime import datetime
from typing import Optional, Tuple

from app.models.state import UserState, ConversationFlow
from app.services.state_manager import state_manager
from app.services.router import classify_intent, Intent, is_greeting
from app.services.flows.onboarding import handle_onboarding, extract_nigerian_state, extract_lga
from app.services.templates import get_template, TEMPLATES
from app.services.handlers.followup import handle_followup

logger = logging.getLogger(__name__)


# Escape commands that always reset the flow
ESCAPE_COMMANDS = {"reset", "cancel", "stop", "start over", "restart", "menu"}


async def handle_message(phone: str, text: str, media_url: str = None) -> str:
    """
    Main entry point for processing user messages.
    Returns the response string to send back.
    
    This is the NEW handler that respects conversation state.
    """
    text = text.strip() if text else ""
    text_lower = text.lower()
    
    # =========================================
    # STEP 1: Load State
    # =========================================
    try:
        state = await _get_state_async(phone)
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
        # Fallback: create temporary stateless state
        state = UserState(
            user_id="temp",
            phone=phone,
            flow=ConversationFlow.IDLE
        )
    
    # =========================================
    # STEP 2: Check Escape Commands
    # =========================================
    if text_lower in ESCAPE_COMMANDS:
        state.clear_flow()
        state.clear_context()
        await _save_state_async(state)
        
        if text_lower == "reset":
            return TEMPLATES["reset_confirm"]
        else:
            return TEMPLATES["cancelled"]
    
    # =========================================
    # STEP 3: Add to History
    # =========================================
    state.add_to_history("user", text)
    
    # =========================================
    # STEP 4: Route Based on Flow State
    # =========================================
    try:
        # ACTIVE FLOW: Skip intent classification, go to flow handler
        if state.flow == ConversationFlow.ONBOARDING:
            response = await handle_onboarding(state, text)
        
        elif state.flow == ConversationFlow.ISSUE_FLOW:
            response = await handle_issue_flow(state, text, media_url)
        
        elif state.flow == ConversationFlow.AWAITING_CLARIFY:
            response = await handle_clarification(state, text)
        
        elif state.flow == ConversationFlow.CONFIRMING:
            response = await handle_confirmation(state, text)
        
        # IDLE: Classify intent and route
        else:
            response = await handle_idle_state(state, text)
    
    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        response = TEMPLATES["error_generic"]
    
    # =========================================
    # STEP 5: Update State
    # =========================================
    state.add_to_history("assistant", response)
    await _save_state_async(state)
    
    return response


async def handle_idle_state(state: UserState, text: str) -> str:
    """Handle messages when user is in IDLE state (no active flow)."""
    
    # Check if user needs onboarding
    if not state.is_onboarding_complete():
        # Check if this looks like a greeting or new conversation
        if is_greeting(text):
            state.flow = ConversationFlow.ONBOARDING
            state.flow_step = 0
            return await handle_onboarding(state, text)
        else:
            # User jumped straight to a query without completing onboarding
            return await handle_incomplete_profile(state, text)
    
    # Classify intent
    intent, confidence, entities = classify_intent(text, state)
    
    # Route to appropriate handler
    if intent == Intent.GREETING:
        return await handle_greeting(state, text)
    
    elif intent == Intent.HELP:
        return TEMPLATES["help"]
    
    elif intent == Intent.THANKS:
        return TEMPLATES["thanks_response"]
    
    elif intent == Intent.REP_LOOKUP:
        return await handle_rep_lookup(state, text, entities)
    
    elif intent == Intent.POLITICIAN_INFO:
        return await handle_politician_info(state, text, entities)
    
    elif intent == Intent.POLITICIAN_RECORD:
        return await handle_politician_record(state, text, entities)
    
    elif intent == Intent.NEWS_QUERY:
        return await handle_news_query(state, text, entities)
    
    elif intent == Intent.VOTER_REGISTRATION:
        return TEMPLATES["voter_reg_info"]
    
    elif intent == Intent.ISSUE_REPORT:
        state.flow = ConversationFlow.ISSUE_FLOW
        state.flow_step = 0
        return await handle_issue_flow(state, text, None)
    
    elif intent == Intent.FOLLOWUP:
        return await handle_followup(state, text, entities)
    
    elif intent == Intent.CONFIRMATION:
        # Confirmation outside of flow - treat as greeting or fallback
        return await handle_greeting(state, text)
    
    elif intent == Intent.COMMAND:
        # Already handled above
        return TEMPLATES["cancelled"]
    
    else:  # FALLBACK
        return await handle_fallback(state, text)


async def handle_greeting(state: UserState, text: str) -> str:
    """Handle greeting from existing user."""
    if state.name:
        if not state.greeted:
            state.greeted = True
            return get_template("welcome_back", name=state.name)
        else:
            # Already greeted this session
            return TEMPLATES["help"]
    else:
        return get_template("welcome_back_no_name")


async def handle_incomplete_profile(state: UserState, text: str) -> str:
    """
    User sent a query but hasn't completed onboarding.
    Try to extract info from their message, or ask for what's missing.
    """
    # Try to extract state from message
    if not state.state:
        extracted_state = extract_nigerian_state(text)
        if extracted_state:
            state.state = extracted_state
    
    # Try to extract LGA from message
    if state.state and not state.lga:
        extracted_lga = extract_lga(text, state.state)
        if extracted_lga:
            state.lga = extracted_lga
    
    # If we now have enough info, process the query
    if state.state and state.lga:
        state.flow = ConversationFlow.IDLE
        return await handle_idle_state(state, text)
    
    # Otherwise, ask for missing info
    if not state.name:
        state.flow = ConversationFlow.AWAITING_CLARIFY
        state.flow_data["awaiting"] = "name"
        state.flow_data["original_query"] = text
        return "I can help with that. First, what's your name?"
    
    if not state.state:
        state.flow = ConversationFlow.AWAITING_CLARIFY
        state.flow_data["awaiting"] = "state"
        state.flow_data["original_query"] = text
        return "I can help with that. First, which state are you in?"
    
    if not state.lga:
        state.flow = ConversationFlow.AWAITING_CLARIFY
        state.flow_data["awaiting"] = "lga"
        state.flow_data["original_query"] = text
        return f"Which local government in {state.state}?"
    
    return TEMPLATES["fallback"]


async def handle_clarification(state: UserState, text: str) -> str:
    """Handle response to a clarifying question."""
    awaiting = state.flow_data.get("awaiting")
    original_query = state.flow_data.get("original_query", "")
    
    if awaiting == "name":
        from app.services.flows.onboarding import extract_name
        name = extract_name(text)
        if name:
            state.name = name
            if not state.state:
                state.flow_data["awaiting"] = "state"
                return f"Good to meet you, {name}. Which state are you in?"
            elif not state.lga:
                state.flow_data["awaiting"] = "lga"
                return f"Which local government in {state.state}?"
            else:
                state.clear_flow()
                if original_query:
                    return await handle_idle_state(state, original_query)
                return f"You're set, {name}. What would you like to know?"
        else:
            return "I didn't catch your name. What should I call you?"
    
    elif awaiting == "state":
        extracted = extract_nigerian_state(text)
        if extracted:
            state.state = extracted
            state.flow_data["awaiting"] = "lga"
            return f"Which local government in {state.state}?"
        else:
            return "I didn't recognize that state. Please enter your Nigerian state (e.g., Lagos, Kano, Rivers)."
    
    elif awaiting == "lga":
        extracted = extract_lga(text, state.state)
        if extracted:
            state.lga = extracted
            state.clear_flow()
            # Now process original query
            if original_query:
                return await handle_idle_state(state, original_query)
            else:
                return f"You're set — {state.lga}, {state.state} State. What would you like to know?"
        else:
            return f"I didn't recognize that LGA. Please enter your local government area in {state.state}."
    
    elif awaiting == "politician":
        # User was asked to clarify which politician
        state.clear_flow()
        return await handle_politician_info(state, text, {})
    
    else:
        state.clear_flow()
        return "I'm not sure what happened. What can I help you with?"


async def handle_confirmation(state: UserState, text: str) -> str:
    """Handle yes/no confirmation responses."""
    text_lower = text.lower().strip()
    
    affirmative = text_lower in {"yes", "yeah", "yep", "sure", "ok", "okay", "y", "1", "correct", "confirm"}
    negative = text_lower in {"no", "nope", "nah", "cancel", "n", "2", "wrong"}
    
    confirm_action = state.flow_data.get("confirm_action")
    
    if affirmative:
        if confirm_action == "save_issue":
            # Save the issue
            response = await save_reported_issue(state)
            state.clear_flow()
            return response
        else:
            state.clear_flow()
            return "Done. What else can I help with?"
    
    elif negative:
        state.clear_flow()
        if confirm_action == "save_issue":
            return TEMPLATES["issue_cancelled"]
        return TEMPLATES["cancelled"]
    
    else:
        return "Please respond with 'yes' or 'no'."


# ==========================================
# INTENT HANDLERS
# ==========================================

async def handle_rep_lookup(state: UserState, text: str, entities: dict) -> str:
    """Find user's representatives based on their location."""
    try:
        from app.database import get_db, Politician
        
        if not state.state or not state.lga:
            return "I need your location to find your representatives. Which state are you in?"
        
        db = next(get_db())
        
        # Look up representatives by state/LGA
        reps = db.query(Politician).filter(
            Politician.state == state.state
        ).limit(10).all()
        
        if reps:
            governor = next((r for r in reps if "governor" in (r.position or "").lower()), None)
            senator = next((r for r in reps if "senator" in (r.position or "").lower()), None)
            house_rep = next((r for r in reps if "representative" in (r.position or "").lower()), None)
            
            return get_template("rep_all",
                lga=state.lga,
                state=state.state,
                governor=f"{governor.name} ({governor.party})" if governor else "Not found",
                senator=f"{senator.name} ({senator.party})" if senator else "Not found",
                house_rep=f"{house_rep.name} ({house_rep.party})" if house_rep else "Not found"
            )
        else:
            return get_template("rep_not_found", lga=state.lga, state=state.state)
            
    except Exception as e:
        logger.error(f"Error in rep lookup: {e}")
        return get_template("rep_not_found", lga=state.lga, state=state.state)


async def handle_politician_info(state: UserState, text: str, entities: dict) -> str:
    """Look up information about a specific politician."""
    try:
        from app.database import get_db, Politician
        
        query = entities.get("politician_query", text)
        
        db = next(get_db())
        
        # Search by name
        politician = db.query(Politician).filter(
            Politician.name.ilike(f"%{query}%")
        ).first()
        
        if politician:
            # UPDATE ACTIVE CONTEXT
            state.active_politician_id = str(politician.id)
            state.active_politician_name = politician.name
            
            return get_template("politician_info",
                name=politician.name,
                party=politician.party or "Independent",
                position=politician.position or "Politician",
                bio=(politician.bio or "No biography available.")[:500]
            )
        else:
            return get_template("politician_not_found", query=query)
            
    except Exception as e:
        logger.error(f"Error in politician info: {e}")
        return get_template("politician_not_found", query=text)


async def handle_politician_record(state: UserState, text: str, entities: dict) -> str:
    """Get a politician's track record."""
    # If we have active context, use it
    if state.active_politician_name:
        from app.services.handlers.followup import get_politician_record
        return await get_politician_record(state.active_politician_id, state.active_politician_name)
    
    # Otherwise, try to extract from the query
    return await handle_politician_info(state, text, entities)


async def handle_news_query(state: UserState, text: str, entities: dict) -> str:
    """Handle news and current events queries."""
    try:
        from app.services.realtime import get_realtime_data
        from app.services.llm import generate_response_sync
        
        news_data = await get_realtime_data(text)
        
        if news_data:
            context = f"Recent news:\n{news_data}"
            response = generate_response_sync(
                user_message=text,
                context=context
            )
            return response
        else:
            return get_template("news_not_found")
            
    except Exception as e:
        logger.error(f"Error in news query: {e}")
        return get_template("news_not_found")


async def handle_issue_flow(state: UserState, text: str, media_url: str = None) -> str:
    """Handle issue reporting flow."""
    step = state.flow_step
    
    if step == 0:
        # Just started - ask for location
        state.flow_step = 1
        return TEMPLATES["issue_start"]
    
    elif step == 1:
        # Waiting for location
        state.flow_data["location"] = text
        state.flow_step = 2
        return get_template("issue_got_location", location=text)
    
    elif step == 2:
        # Waiting for description
        state.flow_data["description"] = text
        state.flow_step = 3
        state.flow = ConversationFlow.CONFIRMING
        state.flow_data["confirm_action"] = "save_issue"
        
        issue_type = state.flow_data.get("issue_type", "General Issue")
        location = state.flow_data.get("location", "Unknown")
        
        return get_template("issue_confirm",
            issue_type=issue_type,
            location=location,
            description=text[:200]
        )
    
    return TEMPLATES["issue_start"]


async def save_reported_issue(state: UserState) -> str:
    """Save a reported issue to the database."""
    try:
        from app.database import get_db, UserReport
        
        db = next(get_db())
        
        report = UserReport(
            phone_hash=state.user_id,
            issue_type=state.flow_data.get("issue_type", "general"),
            location=state.flow_data.get("location", ""),
            description=state.flow_data.get("description", ""),
            state=state.state,
            lga=state.lga,
            status="pending"
        )
        
        db.add(report)
        db.commit()
        
        return get_template("issue_saved",
            issue_type=state.flow_data.get("issue_type", "Issue"),
            location=state.flow_data.get("location", "Unknown"),
            authority=f"{state.lga} Local Government",
            reference_id=f"REF-{report.id}"
        )
        
    except Exception as e:
        logger.error(f"Error saving issue: {e}")
        return "Issue saved. Reference number will be sent shortly.\n\nAnything else?"


async def handle_fallback(state: UserState, text: str) -> str:
    """Handle unrecognized queries using LLM."""
    try:
        from app.services.rag import RAGService
        from app.services.llm import generate_response_sync
        from app.database import get_db
        
        db = next(get_db())
        rag = RAGService(db)
        
        context, sources = rag.retrieve(query=text, top_k=3)
        
        if context:
            response = generate_response_sync(
                user_message=text,
                context=context
            )
            return response
        else:
            return TEMPLATES["fallback_with_context"]
            
    except Exception as e:
        logger.error(f"Error in fallback: {e}")
        return TEMPLATES["fallback"]


# ==========================================
# ASYNC WRAPPERS
# ==========================================

async def _get_state_async(phone: str) -> UserState:
    """Async wrapper for state manager (which is sync)."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, state_manager.get_state, phone)


async def _save_state_async(state: UserState):
    """Async wrapper for state manager save."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, state_manager.save_state, state)


# ==========================================
# LEGACY COMPATIBILITY
# ==========================================

async def handle_whatsapp_message(user_hash: str, text: str, msg_type: str = "text") -> str:
    """Legacy entry point - redirects to new handler."""
    return await handle_message(user_hash, text)
