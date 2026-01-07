import logging
import re
from typing import Optional, Dict, Union
from app.services import whatsapp, conversation
from app.services.location import process_location_for_report, format_location_response
from app.services.intent_classifier import classify_intent, Intent, resolve_followup_intent
from app.services.onboarding import OnboardingManager, OnboardingStep, OnboardingState

logger = logging.getLogger(__name__)


# ===========================================
# CONSTANTS
# ===========================================

NIGERIAN_STATES = [
    "abia", "adamawa", "akwa ibom", "anambra", "bauchi", "bayelsa", "benue",
    "borno", "cross river", "delta", "ebonyi", "edo", "ekiti", "enugu",
    "fct", "gombe", "imo", "jigawa", "kaduna", "kano", "katsina", "kebbi",
    "kogi", "kwara", "lagos", "nasarawa", "niger", "ogun", "ondo", "osun",
    "oyo", "plateau", "rivers", "sokoto", "taraba", "yobe", "zamfara",
    "federal capital territory", "abuja"
]


# ===========================================
# PARSING HELPERS (NEW)
# ===========================================


# ===========================================
# MAIN HANDLER
# ===========================================

async def handle_message(incoming: dict) -> None:
    """Main message handler - orchestrates the full flow."""
    message = whatsapp.parse_incoming_message(incoming)
    if not message:
        logger.debug("Non-message event received, ignoring")
        return
    
    user_hash = message["from_hash"]
    phone = message["from"]
    msg_type = message["type"]
    
    # Mark as read immediately
    whatsapp.mark_as_read(message["message_id"])
    
    # Detect language from text
    if msg_type == "text":
        lang = conversation.detect_language(message.get("text", ""))
        if lang != "en":
            conversation.set_language(user_hash, lang)
    
    # Get conversation state
    conv_state = conversation.get_conversation_state(user_hash)
    
    # Check if conversation is stale (30 min timeout)
    if conversation.is_stale_conversation(user_hash, timeout_minutes=30):
        # Don't fully reset - keep user profile but clear active entities
        conversation.clear_active_entities(user_hash)
    
    # Add to context if text message
    if msg_type == "text":
        conversation.add_to_context(user_hash, "user", message["text"])
    
    try:
        # Route based on message type
        if msg_type == "text":
            response = await process_text_message(message, conv_state, user_hash)
        elif msg_type == "location":
            response = await process_location_message(message, conv_state, user_hash)
        elif msg_type == "image":
            response = await process_image_message(message, conv_state, user_hash)
        elif msg_type == "interactive":
            response = await process_interactive_message(message, conv_state, user_hash)
        else:
            response = "I can only process text, images, and locations right now. Please send a text message."
        
        # Send response
        await send_response(phone, response, user_hash)
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        whatsapp.send_text_message(
            phone,
            "Sorry, something went wrong. Please try again."
        )


async def send_response(phone: str, response: Union[str, dict], user_hash: str):
    """Send response to user, handling different response types."""
    
    if isinstance(response, dict):
        if response.get("buttons"):
            whatsapp.send_message_with_buttons(
                phone,
                response["text"],
                response["buttons"]
            )
        elif response.get("list"):
            whatsapp.send_message_with_list(
                phone,
                response["text"],
                response.get("button_text", "Options"),
                response["list"]
            )
        else:
            whatsapp.send_text_message(phone, response.get("text", str(response)))
    else:
        whatsapp.send_text_message(phone, response)
    
    # Add to context
    response_text = response if isinstance(response, str) else response.get("text", "")
    if response_text:
        conversation.add_to_context(user_hash, "assistant", response_text)


# ===========================================
# MESSAGE TYPE HANDLERS
# ===========================================

async def process_text_message(message: dict, conv_state: dict, user_hash: str) -> Union[str, dict]:
    """Process a text message."""
    text = message.get("text", "").strip()
    text_lower = text.lower()
    
    # Check for special commands
    if text_lower in ["/start", "hi", "hello", "hey", "start", "good morning", "good afternoon"]:
        # Check if we already have user profile
        profile = conversation.get_user_profile(user_hash)
        if profile.get("name"):
            name = profile["name"]
            return f"Welcome back, {name}! 🇳🇬 How can I help you today?"
        return await start_onboarding(user_hash)
    
    if text_lower in ["/help", "help", "menu"]:
        return get_help_message(user_hash)
    
    if text_lower in ["/reset", "reset", "start over"]:
        conversation.clear_conversation_state(user_hash)
        return "Conversation reset! Say 'hi' to start fresh."
    
    # Check if in active flow
    if conversation.is_flow_active(user_hash):
        return await continue_flow(text, conv_state, user_hash)
    
    # Use Intent Classifier
    intent, confidence, entities = classify_intent(text)
    logger.info(f"Classified intent: {intent.name} ({confidence:.2f})")
    
    # Route based on intent
    if intent == Intent.ISSUE_REPORT:
        return await start_issue_flow(user_hash)
        
    elif intent == Intent.GREETING:
         # Check if we already have user profile
        profile = conversation.get_user_profile(user_hash)
        if profile.get("name"):
            name = profile["name"]
            return f"Hello {name}! How can I help you today?"
        return await start_onboarding(user_hash)
        
    elif intent == Intent.NEWS_QUERY:
        return await generate_rag_response(text, user_hash, conv_state)
        
    # Default to RAG for other intents (Politician Info, Policy, etc.)
    return await generate_rag_response(text, user_hash, conv_state)


async def process_location_message(message: dict, conv_state: dict, user_hash: str) -> str:
    """Process a location pin."""
    location = message.get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    
    if not lat or not lng:
        return "I couldn't read that location. Please try sharing your location again."
    
    result = await process_location_for_report(lat, lng)
    
    if not result.get("success"):
        return result.get("error", "Could not identify that location.")
    
    # Update user profile with location
    addr = result.get("address", {})
    conversation.update_user_profile(user_hash, {
        "state": addr.get("state"),
        "lga": addr.get("lga")
    })
    
    # Check if in issue reporting flow
    if conv_state.get("active_flow") == "issue_reporting":
        return await continue_issue_flow_with_location(result, user_hash)
    
    # Format response
    name = conversation.get_user_name(user_hash) or ""
    formatted = format_location_response(result)
    
    return f"{formatted}\n\n✅ I've saved this as your location{', ' + name if name else ''}!"


async def process_image_message(message: dict, conv_state: dict, user_hash: str) -> str:
    """Process an image."""
    image_id = message.get("image_id")
    caption = message.get("caption", "")
    
    pending = conv_state.get("pending_data", {})
    pending["images"] = pending.get("images", []) + [{"id": image_id, "caption": caption}]
    conversation.update_conversation_state(user_hash, {"pending_data": pending})
    
    if conv_state.get("active_flow") == "issue_reporting":
        return "📸 Photo received! I've added it to your report. What's the issue you're reporting?"
    
    return "📸 Photo received! Are you reporting an issue? If so, describe what's in the photo."


async def process_interactive_message(message: dict, conv_state: dict, user_hash: str) -> str:
    """Process button/list reply."""
    button_id = message.get("button_id") or message.get("list_id")
    
    if not button_id:
        return "I didn't understand that selection."
    
    if button_id == "save_location":
        return "✅ Location saved!"
    if button_id == "no_thanks":
        return "No problem! What would you like to know?"
    if button_id == "report_issue":
        return await start_issue_flow(user_hash)
    
    return "Got it! How can I help you further?"


# ===========================================
# ONBOARDING FLOW
# ===========================================

async def start_onboarding(user_hash: str) -> str:
    """Start progressive onboarding flow."""
    conversation.start_flow(user_hash, "onboarding")
    manager = OnboardingManager()
    
    # Save initial state
    save_onboarding_state(user_hash, manager)
    
    return manager.get_current_prompt()


def get_onboarding_manager(user_hash: str) -> OnboardingManager:
    """Reconstruct OnboardingManager from storage."""
    conv_state = conversation.get_conversation_state(user_hash)
    data = conv_state.get("onboarding_data", {})
    step_val = conv_state.get("flow_step", 0)  # Changed from step to flow_step
    
    try:
        step = OnboardingStep(step_val)
    except ValueError:
        step = OnboardingStep.NOT_STARTED
        
    state = OnboardingState(
        step=step,
        name=data.get("name"),
        state=data.get("state"),
        lga=data.get("lga"),
        voted_2023=data.get("voted_2023"),
        concerns=data.get("concerns", [])
    )
    return OnboardingManager(state)


def save_onboarding_state(user_hash: str, manager: OnboardingManager):
    """Save OnboardingManager state to storage."""
    profile = manager.get_profile_dict()
    step_val = manager.state.step.value
    
    conversation.update_conversation_state(user_hash, {
        "flow_step": step_val,
        "onboarding_data": profile
    })


async def continue_flow(text: str, conv_state: dict, user_hash: str) -> str:
    """Continue an active flow."""
    active_flow = conv_state.get("active_flow")
    
    if active_flow == "onboarding":
        return await continue_onboarding(text, user_hash)
    elif active_flow == "issue_reporting":
        return await continue_issue_reporting(text, conv_state.get("flow_step", 1), user_hash)
    
    # Fallback
    conversation.end_flow(user_hash)
    return await generate_rag_response(text, user_hash, conv_state)


async def continue_onboarding(text: str, user_hash: str) -> str:
    """Progressive onboarding using OnboardingManager."""
    manager = get_onboarding_manager(user_hash)
    should_continue, response = manager.process_response(text)
    
    save_onboarding_state(user_hash, manager)
    
    if not should_continue and manager.is_complete():
        profile = manager.get_profile_dict()
        conversation.update_user_profile(user_hash, profile)
        conversation.end_flow(user_hash)
        
    return response


# ===========================================
# ISSUE REPORTING FLOW
# ===========================================

async def start_issue_flow(user_hash: str) -> str:
    """Start issue reporting flow."""
    conversation.start_flow(user_hash, "issue_reporting")
    conversation.set_active_topic(user_hash, "issue_reporting")
    
    return """📝 *Issue Report*

I can help you document community issues.

First, please share your location:
1. Tap the 📎 attachment icon
2. Select "Location"
3. Choose "Send your current location"

Or just type the address/area."""


async def continue_issue_flow_with_location(location_data: dict, user_hash: str) -> str:
    """Continue issue flow after receiving location."""
    addr = location_data.get("address", {})
    classification = location_data.get("classification", {})
    
    conversation.advance_flow(user_hash, {"location": location_data})
    
    return f"""📍 Location received: {addr.get('formatted', 'Unknown')}

*LGA:* {addr.get('lga', 'Unknown')}
*Responsible Authority:* {classification.get('authority', 'Unknown')}

Now describe the issue briefly (e.g., "pothole on main road", "no streetlights")."""


async def continue_issue_reporting(text: str, step: int, user_hash: str) -> str:
    """Continue issue reporting flow."""
    
    if step == 1:
        # User typed location instead of sharing
        conversation.advance_flow(user_hash, {"location_text": text})
        return "Got it. Now describe the issue briefly."
    
    if step == 2:
        # Got issue description
        conversation.advance_flow(user_hash, {"description": text})
        data = conversation.get_pending_data(user_hash)
        location = data.get("location", {})
        classification = location.get("classification", {}) if isinstance(location, dict) else {}
        
        name = conversation.get_user_name(user_hash) or "there"
        
        summary = f"""📋 *Issue Summary*

*Location:* {location.get('address', {}).get('formatted', data.get('location_text', 'Unknown'))}
*Issue:* {text}
*Authority:* {classification.get('authority', 'Your Local Government')}

Thanks {name}! I've documented this."""
        
        conversation.end_flow(user_hash)
        
        return summary + "\n\nIs there anything else I can help with?"
    
    return "Please describe the issue you'd like to report."


# ===========================================
# RAG RESPONSE GENERATION
# ===========================================

async def generate_rag_response(text: str, user_hash: str, conv_state: dict) -> str:
    """Generate response using Enhanced RAG + LLM with context awareness."""
    try:
        from app.services.enhanced_rag import EnhancedRAGService
        from app.services.llm import generate_response_sync, extract_politician_name
        from app.services import web_search
        from app.database import SessionLocal
        
        # Get conversation context string
        conv_context = conversation.get_conversation_context_string(user_hash)
        user_context = conversation.get_user_profile_string(user_hash)
        
        # Get user's state for filtering
        user_state = conversation.get_user_state(user_hash)
        
        db = SessionLocal()
        try:
            # Use Enhanced RAG with intent detection and document type boosting
            rag = EnhancedRAGService(db)
            
            # Check if this is a follow-up about active politician
            active_politician = conversation.get_active_politician(user_hash)
            
            # Resolve intent context using new classifier service
            followup_intent, resolved = resolve_followup_intent(text, {"active_politician": active_politician})
            
            if resolved.get("politician_name"):
                # Enhance query with active politician name
                enhanced_query = f"{resolved['politician_name']} {text}"
                logger.info(f"Follow-up detected ({followup_intent.name}), enhanced query: {enhanced_query}")
                context, sources = rag.retrieve(enhanced_query, top_k=5)
            else:
                # Build filters
                filters = {}
                if user_state:
                    filters["state"] = user_state
                
                # Enhanced retrieval with intent detection
                context, sources = rag.retrieve(text, top_k=5, filters=filters if filters else None)
            
            # Log what document types were retrieved
            if sources:
                doc_types = [s.get("doc_type", "unknown") for s in sources]
                logger.info(f"RAG retrieved: {doc_types}")
            
            # Check if web search needed (Serper API)
            web_results = ""
            if web_search.needs_search(text):
                web_results = web_search.search_sync(text) or ""
            
            # Combine context
            full_context = f"{context}\n\n{web_results}" if web_results else context
            
            # Generate response
            response = generate_response_sync(
                user_message=text,
                context=full_context,
                user_context=user_context,
                conversation_context=conv_context
            )
            
            # Track active entities from response
            politician_mentioned = extract_politician_name(response)
            if politician_mentioned:
                conversation.set_active_politician(user_hash, politician_mentioned)
                logger.info(f"Set active politician: {politician_mentioned}")
            
            # Format for WhatsApp
            from app.services.twilio_whatsapp import format_for_whatsapp
            return format_for_whatsapp(response)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"RAG response error: {e}")
        return "I'm having trouble finding that information. Could you rephrase your question?"


# ===========================================
# INTENT DETECTION (FIXED)
# ===========================================





def get_help_message(user_hash: str) -> str:
    """Return personalized help message."""
    name = conversation.get_user_name(user_hash)
    greeting = f"Hi {name}! Here's" if name else "Here's"
    
    return f"""{greeting} what I can do:

📍 *Find Representatives*
"Who is my senator?"
"Who is my governor?"

📝 *Report Issues*
"I want to report an issue"

🔍 *Political Info*
Ask about any politician or policy

💡 *Tips*
• Share your location for local info
• Type "reset" to start over

What would you like to know?"""