"""
Multimodal Message Processor for Decide9ja.
Orchestrates voice, image, document, and location handling.
Routes to v5 handler for all processing.

Updated to use message_handler_v5 exclusively.
"""
import logging
from typing import Dict, Optional, Union

from app.services import conversation
from app.services.message_handler_v5 import handle_message

logger = logging.getLogger(__name__)


async def process_multimodal_message(message: dict, user_hash: str) -> str:
    """
    Process any type of message (text, voice, image, document, location).
    
    Args:
        message: Parsed message with type and content
        user_hash: Hashed user identifier
        
    Returns:
        Response text to send back to user
    """
    msg_type = message.get("type", "text")
    
    logger.info(f"Processing {msg_type} message for {user_hash[:8]}...")
    
    try:
        if msg_type == "text":
            return await process_text(message, user_hash)
        
        elif msg_type == "voice":
            return await process_voice(message, user_hash)
        
        elif msg_type == "image":
            return await process_image(message, user_hash)
        
        elif msg_type == "document":
            return await process_document(message, user_hash)
        
        elif msg_type == "location":
            return await process_location(message, user_hash)
        
        else:
            return "I received your message but I'm not sure how to process it. Try sending text, voice, image, or location."
            
    except Exception as e:
        logger.error(f"Multimodal processing error: {e}")
        return "Sorry, I had trouble processing that. Please try again."


async def process_text(message: dict, user_hash: str) -> str:
    """Process text message - delegates to v4 handler."""
    phone = message.get("from_raw", message.get("from", ""))
    text = message.get("text", "")

    return await handle_message(phone, text)


async def process_voice(message: dict, user_hash: str) -> str:
    """Process voice note - transcribe and handle as text."""
    from app.services.voice_handler import transcribe_audio, is_configured
    
    if not is_configured():
        return "Voice notes aren't available yet. Please send your message as text."
    
    audio_url = message.get("audio_url") or message.get("media_url")
    
    if not audio_url:
        return "I couldn't access your voice note. Please try sending it again."
    
    # Transcribe
    result = await transcribe_audio(audio_url)
    
    if result.get("error"):
        logger.error(f"Transcription error: {result['error']}")
        return "I couldn't hear your voice note clearly. Could you try again or type your message?"
    
    transcribed_text = result.get("text", "")
    
    if not transcribed_text:
        return "I couldn't understand that voice note. Try speaking more clearly or send a text message."
    
    # Add transcription to context
    conversation.add_to_context(user_hash, "user", f"[Voice note]: {transcribed_text}")
    
    # Detect language
    if result.get("language") == "pidgin":
        conversation.set_language(user_hash, "pidgin")
    
    # Process as text
    text_message = {"text": transcribed_text, **message}
    response = await process_text(text_message, user_hash)
    
    # Optionally prefix with acknowledgment
    acknowledgment = "🎤 I heard:"
    if len(transcribed_text) > 50:
        acknowledgment += f' "{transcribed_text[:50]}..."'
    else:
        acknowledgment += f' "{transcribed_text}"'
    
    return f"{acknowledgment}\n\n{response}"


async def process_image(message: dict, user_hash: str) -> str:
    """Process image - analyze and take appropriate action."""
    from app.services.image_handler import analyze_image, is_configured
    
    if not is_configured():
        return "Image analysis isn't available yet. Please describe what's in the image."
    
    image_url = message.get("image_url") or message.get("media_url")
    caption = message.get("caption", "")
    
    if not image_url:
        return "I couldn't access your image. Please try sending it again."
    
    # Determine analysis type from context
    conv_state = conversation.get_conversation_state(user_hash)
    active_flow = conv_state.get("active_flow")
    
    if active_flow == "issue_reporting":
        analysis_type = "issue"
    elif any(keyword in caption.lower() for keyword in ["who is", "recognize", "identify"]):
        analysis_type = "politician"
    elif any(keyword in caption.lower() for keyword in ["document", "form", "paper", "read"]):
        analysis_type = "document"
    else:
        analysis_type = "general"
    
    # Analyze image
    result = await analyze_image(image_url, caption, analysis_type)
    
    if result.get("error"):
        logger.error(f"Image analysis error: {result['error']}")
        return "I couldn't analyze that image. Could you describe what you're showing me?"
    
    analysis = result.get("analysis", "")
    detected_type = result.get("detected_type", "general")
    suggested_action = result.get("suggested_action", "respond")
    
    # Add to context
    conversation.add_to_context(user_hash, "user", f"[Image]: {caption or 'No caption'}")
    conversation.add_to_context(user_hash, "assistant", f"[Image analysis]: {analysis[:200]}")
    
    # Take action based on detection
    if detected_type == "issue" and suggested_action == "start_report":
        # Start issue reporting flow
        conversation.start_flow(user_hash, "issue_reporting")
        conversation.update_conversation_state(user_hash, {
            "pending_data": {"image_analysis": analysis}
        })
        return f"📷 I can see an issue in your photo:\n\n{analysis}\n\n📍 To complete the report, please share your location or type the address."
    
    elif detected_type == "politician" and suggested_action == "fetch_profile":
        # Extract politician name and fetch more info via v4 handler
        phone = message.get("from_raw", message.get("from", ""))
        profile_response = await handle_message(phone, f"Who is {analysis[:200]}")
        return f"📷 {analysis}\n\n{profile_response}"
    
    else:
        # General response
        return f"📷 {analysis}"


async def process_document(message: dict, user_hash: str) -> str:
    """Process document/PDF - extract and summarize."""
    from app.services.document_handler import process_document as process_doc, is_configured
    
    if not is_configured():
        return "Document processing isn't available yet. Please try a different format."
    
    doc_url = message.get("document_url") or message.get("media_url")
    
    if not doc_url:
        return "I couldn't access your document. Please try sending it again."
    
    # Process document
    result = await process_doc(doc_url)
    
    if result.get("error"):
        if "pypdf" in result["error"]:
            return "I can't read PDFs yet. Could you copy the important parts as text?"
        logger.error(f"Document processing error: {result['error']}")
        return "I couldn't read that document. Try sending the key parts as text."
    
    summary = result.get("summary", "")
    doc_type = result.get("document_type", "document")
    
    # Add to context
    conversation.add_to_context(user_hash, "user", f"[Document]: {doc_type}")
    conversation.add_to_context(user_hash, "assistant", f"[Document summary]: {summary[:200]}")
    
    return f"📄 *Document Summary*\n\n{summary}\n\nWant me to explain any part in more detail?"


async def process_location(message: dict, user_hash: str) -> str:
    """Process location - find representatives and local info."""
    from app.services.location import process_location_for_report, format_location_response
    
    location = message.get("location", {})
    lat = location.get("lat") or message.get("latitude")
    lng = location.get("lng") or message.get("longitude")
    
    if not lat or not lng:
        return "I couldn't read that location. Please try sharing your location again."
    
    # Process location
    result = await process_location_for_report(lat, lng)
    
    if not result.get("success"):
        return result.get("error", "I couldn't identify that location. Please try again.")
    
    # Update user profile with location
    addr = result.get("address", {})
    conversation.update_user_profile(user_hash, {
        "state": addr.get("state"),
        "lga": addr.get("lga")
    })
    
    # Check if in issue reporting flow
    conv_state = conversation.get_conversation_state(user_hash)
    if conv_state.get("active_flow") == "issue_reporting":
        # v4 handler will detect issue flow and continue it with location data
        phone = message.get("from_raw", message.get("from", ""))
        location_text = f"Location: {addr.get('lga', 'Unknown')}, {addr.get('state', 'Unknown')}"
        return await handle_message(phone, location_text)
    
    # Format response with representative info
    formatted = format_location_response(result)
    
    name = conversation.get_user_name(user_hash)
    greeting = f"Thanks{', ' + name if name else ''}! " if name else ""
    
    return f"📍 {greeting}I've found your location:\n\n{formatted}\n\nAsk me:\n• \"Who is my senator?\"\n• \"I want to report an issue\""


def parse_twilio_media_message(form_data: dict) -> dict:
    """
    Parse Twilio message with media detection.
    Extends basic parsing to detect voice, image, document.
    """
    from app.services.twilio_whatsapp import hash_phone
    
    from_number = form_data.get("From", "")
    body = form_data.get("Body", "").strip()
    
    base = {
        "from": from_number.replace("whatsapp:", ""),
        "from_raw": from_number,
        "from_hash": hash_phone(from_number),
        "message_id": form_data.get("MessageSid", ""),
        "contact_name": form_data.get("ProfileName", ""),
        "caption": body
    }
    
    # Check for media
    num_media = int(form_data.get("NumMedia", 0))
    
    if num_media > 0:
        media_type = form_data.get("MediaContentType0", "")
        media_url = form_data.get("MediaUrl0", "")
        
        if media_type.startswith("audio"):
            return {
                **base,
                "type": "voice",
                "audio_url": media_url,
                "media_type": media_type
            }
        
        elif media_type.startswith("image"):
            return {
                **base,
                "type": "image",
                "image_url": media_url,
                "media_type": media_type
            }
        
        elif media_type == "application/pdf":
            return {
                **base,
                "type": "document",
                "document_url": media_url,
                "media_type": media_type
            }
    
    # Check for location (Twilio provides these fields)
    lat = form_data.get("Latitude")
    lng = form_data.get("Longitude")
    
    if lat and lng:
        return {
            **base,
            "type": "location",
            "location": {
                "lat": float(lat),
                "lng": float(lng)
            }
        }
    
    # Default to text
    return {
        **base,
        "type": "text",
        "text": body
    }
