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
from app.services.templates import get_template, TEMPLATES, get_time_aware_greeting
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
    
    # === USE INTELLIGENCE LAYER ===
    # Import retrieval and context assembly
    from app.services.retrieval import retrieve
    from app.services.context_assembler import assemble_context
    
    # Route to appropriate handler
    if intent == Intent.GREETING:
        return await handle_greeting(state, text)
    
    elif intent == Intent.HELP:
        return TEMPLATES["help"]
    
    elif intent == Intent.THANKS:
        return TEMPLATES["thanks_response"]
    
    elif intent == Intent.REP_LOOKUP:
        # Use retrieval orchestrator for representatives
        retrieval = await retrieve(intent, text, state, entities)
        return format_rep_response(retrieval, state)
    
    elif intent == Intent.POLITICIAN_INFO:
        # Use retrieval orchestrator with full intelligence
        retrieval = await retrieve(intent, text, state, entities)
        context = assemble_context(retrieval, state, text)
        return await handle_politician_info_with_context(state, text, retrieval, context)
    
    elif intent == Intent.POLITICIAN_RECORD:
        retrieval = await retrieve(intent, text, state, entities)
        context = assemble_context(retrieval, state, text)
        return await handle_politician_record_with_context(state, text, retrieval, context)
    
    elif intent == Intent.NEWS_QUERY:
        # Use retrieval orchestrator for news (triggers web search)
        retrieval = await retrieve(intent, text, state, entities)
        context = assemble_context(retrieval, state, text)
        return await handle_news_with_context(state, text, retrieval, context)
    
    elif intent == Intent.VOTER_REGISTRATION:
        return TEMPLATES["voter_reg_info"]
    
    elif intent == Intent.ISSUE_REPORT:
        state.flow = ConversationFlow.ISSUE_FLOW
        state.flow_step = 0
        return await handle_issue_flow(state, text, None)
    
    elif intent == Intent.FOLLOWUP:
        retrieval = await retrieve(intent, text, state, entities)
        context = assemble_context(retrieval, state, text)
        return await handle_followup_with_context(state, text, retrieval, context)
    
    elif intent == Intent.CONFIRMATION:
        # Confirmation outside of flow - treat as greeting or fallback
        return await handle_greeting(state, text)
    
    elif intent == Intent.PRIVACY_DELETE:
        # User wants to delete their data - start confirmation flow
        state.flow = ConversationFlow.CONFIRMING
        state.flow_data = {"action": "privacy_delete"}
        return TEMPLATES["privacy_confirm_delete"]
    
    elif intent == Intent.COMMAND:
        # Already handled above
        return TEMPLATES["cancelled"]
    
    else:  # FALLBACK
        retrieval = await retrieve(intent, text, state, entities)
        context = assemble_context(retrieval, state, text)
        return await handle_fallback_with_context(state, text, retrieval, context)


async def handle_greeting(state: UserState, text: str) -> str:
    """Handle greeting from existing user with time-aware response."""
    if state.name:
        if not state.greeted:
            state.greeted = True
            return get_time_aware_greeting(
                name=state.name,
                last_active_at=state.last_active_at,
                message_count=state.message_count
            )
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
    action = state.flow_data.get("action")
    
    # Handle privacy deletion confirmation
    if action == "privacy_delete":
        if text_lower in {"yes delete", "yes, delete", "delete"}:
            # Actually delete user data
            success = state_manager.delete_user_data(state.phone)
            state.clear_flow()
            if success:
                return TEMPLATES["privacy_deleted"]
            else:
                return "There was an issue deleting some data. Please try again later."
        else:
            # Anything else cancels
            state.clear_flow()
            return TEMPLATES["privacy_delete_cancelled"]
    
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
    """Find user's representatives based on their location.

    Uses the lga_representatives table which directly maps each LGA to:
    - Governor (state-wide)
    - Senator (by senatorial district)
    - House Representative (by federal constituency)

    Supports specific lookups: "my senator", "my governor", "my rep"
    """
    try:
        from app.database import get_db
        from sqlalchemy import text as sql_text

        if not state.state or not state.lga:
            return "I need your location to find your representatives. Which state are you in?"

        db = next(get_db())
        text_lower = text.lower()

        # Detect specific rep type requested
        specific_type = None
        if "senator" in text_lower:
            specific_type = "senator"
        elif "governor" in text_lower:
            specific_type = "governor"
        elif "rep" in text_lower or "representative" in text_lower or "house" in text_lower:
            specific_type = "house_rep"

        # Try query with all columns (including optional house_rep columns)
        try:
            result = db.execute(sql_text("""
                SELECT state, lga, senatorial_district, governor_name, governor_party,
                       senator_name, senator_party, house_rep_name, house_rep_party,
                       federal_constituency
                FROM lga_representatives
                WHERE state = :state AND lga = :lga
            """), {"state": state.state, "lga": state.lga})
            row = result.fetchone()
            has_house_rep_cols = True
        except Exception:
            # Fallback: house_rep columns might not exist
            result = db.execute(sql_text("""
                SELECT state, lga, senatorial_district, governor_name, governor_party,
                       senator_name, senator_party
                FROM lga_representatives
                WHERE state = :state AND lga = :lga
            """), {"state": state.state, "lga": state.lga})
            row = result.fetchone()
            has_house_rep_cols = False

        if not row:
            # Fallback: Try fuzzy match on LGA name
            logger.warning(f"No exact match for {state.lga}, {state.state} - trying fuzzy match")
            try:
                result = db.execute(sql_text("""
                    SELECT state, lga, senatorial_district, governor_name, governor_party,
                           senator_name, senator_party, house_rep_name, house_rep_party,
                           federal_constituency
                    FROM lga_representatives
                    WHERE state = :state AND (lga ILIKE :lga_pattern OR :lga ILIKE '%' || lga || '%')
                    LIMIT 1
                """), {"state": state.state, "lga": state.lga, "lga_pattern": f"%{state.lga}%"})
                row = result.fetchone()
                has_house_rep_cols = True
            except Exception:
                result = db.execute(sql_text("""
                    SELECT state, lga, senatorial_district, governor_name, governor_party,
                           senator_name, senator_party
                    FROM lga_representatives
                    WHERE state = :state AND (lga ILIKE :lga_pattern OR :lga ILIKE '%' || lga || '%')
                    LIMIT 1
                """), {"state": state.state, "lga": state.lga, "lga_pattern": f"%{state.lga}%"})
                row = result.fetchone()
                has_house_rep_cols = False

        if not row:
            return get_template("rep_not_found", lga=state.lga, state=state.state)

        # Extract data from row
        senatorial_district = row[2] if len(row) > 2 else None
        governor_name = row[3] if len(row) > 3 else None
        governor_party = row[4] if len(row) > 4 else None
        senator_name = row[5] if len(row) > 5 else None
        senator_party = row[6] if len(row) > 6 else None
        house_rep_name = row[7] if has_house_rep_cols and len(row) > 7 else None
        house_rep_party = row[8] if has_house_rep_cols and len(row) > 8 else None
        federal_constituency = row[9] if has_house_rep_cols and len(row) > 9 else None

        # Format strings
        governor_str = f"{governor_name} ({governor_party})" if governor_name else "Not found"
        senator_str = f"{senator_name} ({senator_party})" if senator_name else "Not found"
        house_rep_str = f"{house_rep_name} ({house_rep_party})" if house_rep_name else None

        # Store politician in context for follow-up
        if specific_type == "senator" and senator_name:
            state.active_politician_name = senator_name
        elif specific_type == "governor" and governor_name:
            state.active_politician_name = governor_name
        elif specific_type == "house_rep" and house_rep_name:
            state.active_politician_name = house_rep_name

        # Return specific type if requested
        if specific_type == "governor":
            return get_template("rep_governor_only",
                state=state.state,
                governor=governor_str
            )

        if specific_type == "senator":
            return get_template("rep_senator_only",
                district=senatorial_district or f"{state.state} Senatorial District",
                senator=senator_str
            )

        if specific_type == "house_rep":
            if house_rep_str:
                return get_template("rep_house_only",
                    constituency=federal_constituency or f"{state.lga} Constituency",
                    house_rep=house_rep_str
                )
            else:
                return get_template("rep_house_not_available",
                    lga=state.lga,
                    governor=governor_str,
                    senator=senator_str
                )

        # Return all representatives
        return get_template("rep_all",
            lga=state.lga,
            state=state.state,
            governor=governor_str,
            senator=senator_str,
            house_rep=house_rep_str or "Data being updated"
        )

    except Exception as e:
        logger.error(f"Error in rep lookup: {e}")
        return get_template("rep_not_found", lga=state.lga, state=state.state)



async def handle_politician_info(state: UserState, text: str, entities: dict) -> str:
    """
    Look up information about a specific politician.
    
    Features:
    1. Position-based queries (e.g., "who is the president")
    2. Fuzzy name matching (handles typos like "Dienel" → "Daniel")
    3. Location-aware suggestions (prioritizes user's representatives)
    4. Web search fallback for unknown politicians
    """
    try:
        from app.database import get_db, Politician
        from app.services.fuzzy_match import (
            fuzzy_find_politician, 
            fuzzy_find_among_representatives,
            extract_politician_name_from_text
        )
        
        # Extract clean query
        raw_query = entities.get("politician_query", text)
        text_lower = raw_query.lower()
        
        db = next(get_db())
        
        # =========================================
        # STEP 0: Check for position-based queries
        # E.g., "who is the president", "president of Nigeria"
        # Order matters: more specific patterns first!
        # =========================================
        position_patterns = [
            (r'\b(the\s+)?vice\s*president\b', 'Vice President'),  # Check BEFORE president
            (r'\b(the\s+)?president\b', 'President'),
            (r'\bgovernor\s+of\s+(\w+)', 'Governor'),  # governor of Lagos
            (r'\b(the\s+)?governor\b', 'Governor'),
        ]
        
        import re
        for pattern, position in position_patterns:
            match = re.search(pattern, text_lower)
            if match:
                # Special case: "governor of [state]"
                if 'governor of' in pattern and match.group(1):
                    state_name = match.group(1).title()
                    politician = db.query(Politician).filter(
                        Politician.position == position,
                        Politician.state.ilike(f"%{state_name}%")
                    ).first()
                else:
                    # Generic position lookup (President, VP, or user's state Governor)
                    if position == 'Governor' and state.state:
                        politician = db.query(Politician).filter(
                            Politician.position == position,
                            Politician.state.ilike(f"%{state.state}%")
                        ).first()
                    else:
                        politician = db.query(Politician).filter(
                            Politician.position == position
                        ).first()
                
                if politician:
                    state.active_politician_id = str(politician.id)
                    state.active_politician_name = politician.name
                    
                    return get_template("politician_info",
                        name=politician.name,
                        party=politician.party or "Independent",
                        position=politician.position or "Politician",
                        bio=(politician.bio or "No biography available.")[:500]
                    )
        
        # Extract name for regular name-based lookup
        query = extract_politician_name_from_text(raw_query)
        
        # =========================================
        # STEP 1: Try exact match first
        # =========================================
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
        
        # =========================================
        # STEP 2: Try fuzzy match among user's reps
        # =========================================
        if state.state:
            rep_result = fuzzy_find_among_representatives(
                query=query,
                user_state=state.state,
                user_lga=state.lga,
                db=db
            )
            
            if rep_result:
                politician_dict, context_note = rep_result
                state.active_politician_id = str(politician_dict["id"])
                state.active_politician_name = politician_dict["name"]
                
                # Build response with "Did you mean..." hint if applicable
                response = ""
                if context_note:
                    response = f"Did you mean **{politician_dict['name']}**? {context_note}\n\n"
                
                response += get_template("politician_info",
                    name=politician_dict["name"],
                    party=politician_dict.get("party") or "Independent",
                    position=politician_dict.get("position") or "Politician",
                    bio=(politician_dict.get("bio") or "No biography available.")[:500]
                )
                return response
        
        # =========================================
        # STEP 3: Try fuzzy match against ALL politicians
        # =========================================
        all_politicians = db.query(Politician).limit(500).all()
        
        if all_politicians:
            politician_dicts = [
                {
                    "id": p.id,
                    "name": p.name,
                    "party": p.party,
                    "position": p.position,
                    "state": p.state,
                    "constituency": p.constituency,
                    "bio": p.bio
                }
                for p in all_politicians
            ]
            
            result = fuzzy_find_politician(query, politician_dicts, threshold=75)
            
            if result:
                politician_dict, similarity, suggestion = result
                state.active_politician_id = str(politician_dict["id"])
                state.active_politician_name = politician_dict["name"]
                
                response = ""
                if suggestion:
                    response = f"{suggestion}\n\n"
                
                response += get_template("politician_info",
                    name=politician_dict["name"],
                    party=politician_dict.get("party") or "Independent",
                    position=politician_dict.get("position") or "Politician",
                    bio=(politician_dict.get("bio") or "No biography available.")[:500]
                )
                return response
        
        # =========================================
        # STEP 4: Web search fallback
        # =========================================
        try:
            from app.services.web_search import search_web
            from app.services.llm import generate_response_sync
            
            logger.info(f"Politician not in DB, trying web search: {query}")
            
            search_query = f"{query} Nigeria politician"
            web_context, web_sources = await search_web(search_query)
            
            if web_context:
                response = generate_response_sync(
                    user_message=f"Who is {query}? Provide brief information.",
                    context=f"Web search results:\n{web_context}"
                )
                
                if response and "don't have" not in response.lower():
                    return response
        except Exception as web_error:
            logger.warning(f"Web search fallback failed: {web_error}")
        
        # =========================================
        # STEP 5: Final fallback
        # =========================================
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
# CONTEXT-AWARE HANDLERS (INTELLIGENCE LAYER)
# ==========================================

def format_rep_response(retrieval, state: UserState) -> str:
    """Format representative lookup response using retrieval results."""
    if not retrieval.representatives:
        return get_template("rep_not_found", lga=state.lga, state=state.state)
    
    reps = retrieval.representatives
    
    # Find specific roles
    governor = next((r for r in reps if "governor" in (r.get("position") or "").lower()), None)
    senator = next((r for r in reps if "senator" in (r.get("position") or "").lower()), None)
    house_rep = next((r for r in reps if "representative" in (r.get("position") or "").lower()), None)
    
    return get_template("rep_all",
        lga=state.lga,
        state=state.state,
        governor=f"{governor['name']} ({governor['party']})" if governor else "Not found",
        senator=f"{senator['name']} ({senator['party']})" if senator else "Not found",
        house_rep=f"{house_rep['name']} ({house_rep['party']})" if house_rep else "Not found"
    )


async def handle_politician_info_with_context(
    state: UserState,
    text: str,
    retrieval,
    context
) -> str:
    """Handle politician info query with full context from intelligence layer."""
    from app.services.llm import generate_response
    
    # Check for suggestions (fuzzy match, multiple candidates)
    if retrieval.suggestions:
        # If we have a politician despite suggestions, show suggestion + info
        if retrieval.politician:
            # Update active context
            state.active_politician_id = str(retrieval.politician.get("id", ""))
            state.active_politician_name = retrieval.politician.get("name")
            
            # Build response with suggestion
            response_parts = []
            if "Did you mean" in (retrieval.suggestions[0] if retrieval.suggestions else ""):
                response_parts.append(retrieval.suggestions[0])
                response_parts.append("")
            
            # Add politician info
            response_parts.append(get_template("politician_info",
                name=retrieval.politician.get("name"),
                party=retrieval.politician.get("party", "Unknown"),
                position=retrieval.politician.get("position", ""),
                bio=(retrieval.politician.get("bio") or "No biography available.")[:500]
            ))
            
            return "\n".join(response_parts)
        else:
            # Multiple candidates or not found - return suggestions
            return "\n".join(retrieval.suggestions)
    
    if retrieval.politician:
        # Update active context
        state.active_politician_id = str(retrieval.politician.get("id", ""))
        state.active_politician_name = retrieval.politician.get("name")
        
        return get_template("politician_info",
            name=retrieval.politician.get("name"),
            party=retrieval.politician.get("party", "Unknown"),
            position=retrieval.politician.get("position", ""),
            bio=(retrieval.politician.get("bio") or "No biography available.")[:500]
        )
    
    # Web search fallback
    if retrieval.web_results:
        try:
            response = await generate_response(
                user_message=text,
                context=context.user_context,
                user_context=f"User: {state.name or 'Unknown'} from {state.state or 'Unknown'}"
            )
            if response:
                return response
        except Exception as e:
            logger.warning(f"LLM generation with web results failed: {e}")
    
    return get_template("politician_not_found", query=text)


async def handle_politician_record_with_context(
    state: UserState,
    text: str,
    retrieval,
    context
) -> str:
    """Handle politician record query with RAG and web search context."""
    from app.services.llm import generate_response
    
    if not state.active_politician_name and not retrieval.politician:
        return "Which politician are you asking about?"
    
    politician_name = state.active_politician_name or (retrieval.politician.get("name") if retrieval.politician else "Unknown")
    
    # Use LLM with the assembled context
    if context.user_context:
        try:
            response = await generate_response(
                user_message=text,
                context=context.user_context,
                user_context=f"Asking about: {politician_name}"
            )
            if response:
                return response
        except Exception as e:
            logger.warning(f"LLM generation for record failed: {e}")
    
    # Fallback
    if retrieval.rag_context:
        return f"Here's what I found about {politician_name}:\n\n{retrieval.rag_context[:1000]}"
    
    if retrieval.news_results:
        news_summary = []
        for n in retrieval.news_results[:3]:
            news_summary.append(f"• {n.get('title', 'News')}")
        return f"Recent news about {politician_name}:\n\n" + "\n".join(news_summary)
    
    return f"I don't have detailed records for {politician_name} yet. Try asking about their basic info instead."


async def handle_news_with_context(
    state: UserState,
    text: str,
    retrieval,
    context
) -> str:
    """Handle news query with web search results and political balance."""
    from app.services.llm import generate_response

    if not retrieval.news_results and not retrieval.web_results:
        return get_template("news_not_found")

    # Check if topic is controversial and needs balanced treatment
    is_controversial = _is_controversial_topic(text)

    # Build LLM context with appropriate instructions
    if is_controversial:
        llm_instruction = (
            "This is a politically sensitive topic. Summarize the news FACTUALLY. "
            "Present MULTIPLE perspectives if they exist. Do NOT take sides. "
            "Cite sources. If asked for your opinion, redirect to facts."
        )
    else:
        llm_instruction = "Summarize the news. Be factual and cite sources."

    # Use LLM to synthesize news
    if context.user_context:
        try:
            response = await generate_response(
                user_message=text,
                context=context.user_context,
                user_context=llm_instruction
            )
            if response:
                return response
        except Exception as e:
            logger.warning(f"LLM synthesis for news failed: {e}")

    # Fallback: format news directly
    if retrieval.news_results:
        news_parts = ["Here's what I found:\n"]
        for n in retrieval.news_results[:5]:
            news_parts.append(f"• **{n.get('title', 'News')}**")
            if n.get('summary') or n.get('snippet'):
                news_parts.append(f"  {(n.get('summary') or n.get('snippet', ''))[:150]}")
            source = n.get('source', '')
            if source:
                news_parts.append(f"  _Source: {source}_\n")
        return "\n".join(news_parts)

    return get_template("news_not_found")


# Controversial topics that need balanced treatment
CONTROVERSIAL_TOPICS = [
    "tax reform", "tax bill", "vat", "derivation",
    "pdp crisis", "apc crisis", "party", "defection",
    "north vs south", "northern governors", "southern governors",
    "restructuring", "true federalism", "secession",
    "election", "rigging", "inec", "tribunal",
    "subsidy", "fuel price", "palliative",
    "insecurity", "banditry", "terrorism",
    "muslim-muslim", "christian", "religion",
    "ethnic", "tribe", "marginalization",
    "obi vs tinubu", "atiku vs tinubu", "labour party",
    "wike", "fubara", "rivers crisis",
]


def _is_controversial_topic(query: str) -> bool:
    """Detect if a query touches on politically controversial topics."""
    query_lower = query.lower()
    return any(topic in query_lower for topic in CONTROVERSIAL_TOPICS)


async def handle_followup_with_context(
    state: UserState,
    text: str,
    retrieval,
    context
) -> str:
    """Handle followup questions using active context."""
    from app.services.llm import generate_response
    
    if not state.active_politician_id and not getattr(state, 'active_topic', None):
        return "I'm not sure what you're referring to. Could you be more specific?"
    
    # Use LLM with context
    if context.user_context:
        try:
            response = await generate_response(
                user_message=text,
                context=context.user_context,
                user_context=f"User following up on: {state.active_politician_name or 'previous topic'}"
            )
            if response:
                return response
        except Exception as e:
            logger.warning(f"LLM generation for followup failed: {e}")
    
    # Check what context we have
    if retrieval.rag_context:
        return retrieval.rag_context[:1000]
    
    if retrieval.news_results:
        return await handle_news_with_context(state, text, retrieval, context)
    
    return "I don't have enough context to answer that. Could you rephrase or ask about something specific?"


async def handle_fallback_with_context(
    state: UserState,
    text: str,
    retrieval,
    context
) -> str:
    """Handle unclear queries with hybrid retrieval."""
    from app.services.llm import generate_response
    
    if context.user_context:
        try:
            response = await generate_response(
                user_message=text,
                context=context.user_context,
                user_context=f"User: {state.name or 'Unknown'} from {state.state or 'Unknown'}"
            )
            if response:
                return response
        except Exception as e:
            logger.warning(f"LLM fallback generation failed: {e}")
    
    # Final fallback
    return TEMPLATES.get("fallback", "I'm not sure how to help with that. Try asking about your representatives, a specific politician, or current political news.")


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
