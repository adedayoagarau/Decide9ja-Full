"""
Message Handler V4 — Claude-First Architecture

Key changes from V3:
1. Uses Claude for intent classification (not regex)
2. Claude decides retrieval strategy
3. Intelligent retrieval orchestration
4. Still maintains flow-first routing for active flows
"""
import os
import logging
from datetime import datetime
from typing import Optional

from app.models.state import UserState, ConversationFlow
from app.services.state_manager import state_manager, _get_state_async, _save_state_async
from app.services.templates import get_template, TEMPLATES
from app.services.claude_understand import (
    claude_understand, 
    QueryUnderstanding, 
    Intent, 
    RetrievalStrategy
)
from app.services.intelligent_retrieval import (
    intelligent_retrieve, 
    RetrievalResult,
    format_retrieval_for_context
)

logger = logging.getLogger(__name__)

# Escape commands that reset conversation
ESCAPE_COMMANDS = {"reset", "restart", "cancel", "menu", "stop", "start over", "new"}


async def handle_message(phone: str, text: str, media_url: str = None) -> str:
    """
    Main entry point — Claude-First Architecture.
    
    Flow:
    1. Load state
    2. Check escape commands
    3. If in active flow → handle flow (skip Claude understanding)
    4. If IDLE → Claude understands → intelligent retrieval → Claude responds
    5. Save state
    """
    text = text.strip() if text else ""
    text_lower = text.lower()
    
    # ===========================================
    # STEP 1: Load State
    # ===========================================
    try:
        state = await _get_state_async(phone)
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
        state = UserState(
            user_id="temp",
            phone=phone,
            flow=ConversationFlow.IDLE
        )
    
    # ===========================================
    # STEP 2: Check Escape Commands
    # ===========================================
    if text_lower in ESCAPE_COMMANDS:
        state.clear_flow()
        state.clear_context()
        await _save_state_async(state)
        return get_template("menu")
    
    # ===========================================
    # STEP 3: Add to History
    # ===========================================
    state.add_to_history("user", text)
    
    # ===========================================
    # STEP 4: Route Based on Flow State
    # Flow-first: active flows skip Claude understanding
    # ===========================================
    try:
        if state.flow == ConversationFlow.ONBOARDING:
            from app.services.flows.onboarding import handle_onboarding
            response = await handle_onboarding(state, text)
        
        elif state.flow == ConversationFlow.ISSUE_FLOW:
            response = await _handle_issue_flow(state, text, media_url)
        
        elif state.flow == ConversationFlow.CONFIRMING:
            response = await _handle_confirmation(state, text)
        
        elif state.flow == ConversationFlow.AWAITING_CLARIFY:
            response = await _handle_clarification(state, text)
        
        else:
            # IDLE state — use Claude-First architecture
            response = await handle_idle_claude_first(state, text)
    
    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        response = TEMPLATES.get("error_generic", "Something went wrong. Please try again.")
    
    # ===========================================
    # STEP 5: Update State
    # ===========================================
    state.add_to_history("assistant", response)
    await _save_state_async(state)
    
    return response


async def handle_idle_claude_first(state: UserState, text: str) -> str:
    """
    Handle IDLE state using Claude-First architecture.
    
    Flow:
    1. Check if onboarding complete
    2. Claude understands the query
    3. Route to intelligent retrieval
    4. Claude generates response with context
    """
    
    # ===========================================
    # Check Onboarding
    # ===========================================
    if not state.is_onboarding_complete():
        # User hasn't completed onboarding
        from app.services.flows.onboarding import handle_onboarding
        
        # Check if this is a greeting to start onboarding
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "start"}
        if text.lower().strip() in greetings:
            state.flow = ConversationFlow.ONBOARDING
            state.flow_step = 0
            return await handle_onboarding(state, text)
        else:
            # Prompt them to complete onboarding
            return get_template("incomplete_profile")
    
    # ===========================================
    # CLAUDE UNDERSTANDING
    # ===========================================
    understanding = await claude_understand(
        query=text,
        user_state=state.state,
        user_lga=state.lga,
        user_name=state.name,
        active_topic=state.active_politician_name
    )
    
    logger.info(f"Claude understanding: intent={understanding.intent.value}, "
                f"strategy={understanding.retrieval_strategy.value}, "
                f"confidence={understanding.confidence}")
    
    # ===========================================
    # ROUTE BY INTENT
    # ===========================================
    
    # Simple responses (no retrieval needed)
    if understanding.intent == Intent.GREETING:
        return get_template("greeting_returning", name=state.name)
    
    if understanding.intent == Intent.HELP:
        return get_template("menu")
    
    if understanding.intent == Intent.THANKS:
        return get_template("thanks_response")
    
    # Issue report — start flow
    if understanding.intent == Intent.ISSUE_REPORT:
        state.flow = ConversationFlow.ISSUE_FLOW
        state.flow_step = 0
        state.flow_data = {}
        return get_template("issue_start")
    
    # Voter registration
    if understanding.intent == Intent.VOTER_REGISTRATION:
        return get_template("voter_reg_info")
    
    # ===========================================
    # INTELLIGENT RETRIEVAL
    # ===========================================
    retrieval_result = await intelligent_retrieve(
        understanding=understanding,
        user_state=state.state,
        user_lga=state.lga
    )
    
    # ===========================================
    # GENERATE RESPONSE WITH CONTEXT
    # ===========================================
    return await generate_response_with_context(
        query=text,
        understanding=understanding,
        retrieval=retrieval_result,
        state=state
    )


async def generate_response_with_context(
    query: str,
    understanding: QueryUnderstanding,
    retrieval: RetrievalResult,
    state: UserState
) -> str:
    """Generate Claude response using retrieved context."""
    
    import anthropic
    
    # Format context from retrieval
    context = format_retrieval_for_context(retrieval)
    
    # Update state with active politician if found
    if retrieval.politician:
        state.active_politician_id = str(retrieval.politician.get("id", ""))
        state.active_politician_name = retrieval.politician.get("name", "")
    
    # Build prompt for response generation
    system_prompt = """You are Tade, the AI assistant for Decide9ja — Nigeria's non-partisan civic engagement platform.

=== YOUR IDENTITY ===
- You help Nigerians understand their government, politicians, policies, and civic duties
- You're knowledgeable, neutral, and trustworthy — like a smart friend who reads the news
- You encourage civic participation without pushing any political agenda
- You speak clearly and warmly, avoiding jargon

=== RESPONSE GUIDELINES ===
1. **Be concise**: 2-5 sentences for most answers. Users are on WhatsApp.
2. **Be factual**: Cite sources for news. Say "I don't have recent information on that" if unsure.
3. **Be neutral**: Present facts without political bias. Don't say who's "good" or "bad".
4. **Be helpful**: End with a follow-up question or next step when appropriate.
5. **Be Nigerian**: Use appropriate local context. Understand naira, states, LGAs, INEC, etc.

=== MULTI-SHOT EXAMPLES ===

USER: Who is the president of Nigeria?
CONTEXT: Bola Ahmed Tinubu, APC, President since 2023
RESPONSE: Nigeria's president is Bola Ahmed Tinubu. He's from the APC party and was sworn in on May 29, 2023. Would you like to know about any of his policies?

USER: What's happening with the tax reform bill?
CONTEXT: [News about tax bill controversy]
RESPONSE: The tax reform bill has been controversial — some states and lawmakers oppose parts of it, citing concerns about revenue allocation. Here's what the debate is about: [brief summary]. Want me to explain a specific aspect?

USER: Who is my senator?
CONTEXT: Senator John Doe (APC), representing Ogun East
RESPONSE: Your senator is John Doe from the APC. He represents Ogun East senatorial district. Want to know about his voting record or any bills he's sponsored?

USER: Compare Tinubu and Obi's economic policies
CONTEXT: [Policy details from web search]
RESPONSE: Both have different approaches: Tinubu has focused on [X], while Obi campaigned on [Y]. Key differences include... Would you like more details on a specific policy area?

USER: Is Wike still fighting with Fubara?
CONTEXT: [Recent news about Rivers State crisis]
RESPONSE: The political tension in Rivers State continues. Recently, [brief update]. This conflict started over [context]. Want to know more about the background?

USER: Why is fuel so expensive?
CONTEXT: [News about fuel subsidy removal]
RESPONSE: Fuel prices rose after the subsidy was removed in May 2023, which was a major policy change. This affected transportation costs and general prices. The government says it will redirect savings to infrastructure. Anything specific about this you'd like to understand?

USER: I want to know about voting in Nigeria
CONTEXT: [INEC registration info]
RESPONSE: To vote in Nigeria, you need a PVC (Permanent Voter's Card) from INEC. Registration is continuous at INEC offices. You can check your registration status on the INEC website. Need help finding your registration center?

=== THINGS TO AVOID ===
- Don't say "Great question!" or "I'd be happy to help!"
- Don't be preachy or lecture users
- Don't express personal political opinions
- Don't use overly formal language
- Don't give very long responses (remember: WhatsApp)"""
    
    user_prompt = f"""Answer this user's question using the context provided.

USER INFO: {state.name or "Friend"} from {state.lga or "Unknown LGA"}, {state.state or "Nigeria"}

QUESTION: {query}

INTENT DETECTED: {understanding.intent.value}

RETRIEVED CONTEXT:
{context}

---

Provide a helpful, concise response (2-5 sentences). If the context doesn't fully answer the question, acknowledge what's missing. End with a relevant follow-up or suggestion."""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        return response.content[0].text.strip()
        
    except Exception as e:
        logger.error(f"Response generation error: {e}")
        
        # Fallback: Format retrieval directly
        if retrieval.politician:
            p = retrieval.politician
            return get_template("politician_info",
                name=p.get("name", "Unknown"),
                party=p.get("party", "Unknown"),
                position=p.get("position", "Politician"),
                bio=p.get("bio", "No biography available.")
            )
        
        if retrieval.representatives:
            reps = retrieval.representatives
            return get_template("rep_all",
                lga=state.lga,
                state=state.state,
                governor=f"{reps[0]['name']} ({reps[0]['party']})" if reps else "Not found",
                senator=f"{reps[1]['name']} ({reps[1]['party']})" if len(reps) > 1 else "Not found",
                house_rep=f"{reps[2]['name']} ({reps[2]['party']})" if len(reps) > 2 else "Not found"
            )
        
        if retrieval.web_results:
            news = retrieval.web_results
            result = "Here's what I found:\n\n"
            for item in news[:3]:
                result += f"• {item.get('title', 'News')}\n"
            return result
        
        return get_template("no_info_found", query=query)


# ===========================================
# FLOW HANDLERS
# ===========================================

async def _handle_issue_flow(state: UserState, text: str, media_url: str = None) -> str:
    """Handle issue reporting flow."""
    step = state.flow_step
    
    if step == 0:
        # Initial prompt already shown, now waiting for location
        state.flow_step = 1
        return get_template("issue_start")
    
    elif step == 1:
        # Got location
        state.flow_data["location"] = text
        state.flow_step = 2
        return get_template("issue_got_location", location=text)
    
    elif step == 2:
        # Got description
        state.flow_data["description"] = text
        if media_url:
            state.flow_data["media_url"] = media_url
        
        # Move to confirmation
        state.flow = ConversationFlow.CONFIRMING
        state.flow_data["confirm_action"] = "save_issue"
        
        return get_template("issue_confirm",
            issue_type="Community Issue",
            location=state.flow_data.get("location", ""),
            description=text
        )
    
    return get_template("issue_start")


async def _handle_confirmation(state: UserState, text: str) -> str:
    """Handle confirmation responses."""
    text_lower = text.lower().strip()
    
    if text_lower in {"yes", "y", "yeah", "yep", "sure", "ok", "confirm", "correct"}:
        action = state.flow_data.get("confirm_action")
        
        if action == "save_issue":
            # Save the issue
            try:
                from app.database import get_db, UserReport
                db = next(get_db())
                
                report = UserReport(
                    user_hash=state.user_id,
                    location=state.flow_data.get("location", ""),
                    description=state.flow_data.get("description", ""),
                    media_url=state.flow_data.get("media_url"),
                    status="submitted"
                )
                db.add(report)
                db.commit()
                
                state.clear_flow()
                return get_template("issue_saved",
                    issue_type="Community Issue",
                    location=state.flow_data.get("location", "Unknown"),
                    authority="relevant authorities",
                    reference_id=f"ISS-{report.id:05d}"
                )
                
            except Exception as e:
                logger.error(f"Failed to save issue: {e}")
                state.clear_flow()
                return "I had trouble saving your report. Please try again later."
        
        state.clear_flow()
        return "Confirmed. What else can I help with?"
    
    elif text_lower in {"no", "n", "nope", "cancel", "wrong"}:
        state.clear_flow()
        return "No problem. What else can I help with?"
    
    else:
        return "Please respond with 'yes' to confirm or 'no' to cancel."


async def _handle_clarification(state: UserState, text: str) -> str:
    """Handle clarification responses."""
    # Re-process with the clarification as new query
    state.flow = ConversationFlow.IDLE
    return await handle_idle_claude_first(state, text)
