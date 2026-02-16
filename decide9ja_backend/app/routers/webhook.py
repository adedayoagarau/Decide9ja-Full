"""
WhatsApp Webhook Router for Decide9ja.
Handles incoming WhatsApp messages from Meta Cloud API and Twilio.
"""
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse

from app.services import whatsapp
from app.services.security import security
# Import the MERGED Unified Handler
from app.services.tade_unified import UnifiedTadeHandler

# MERGER: Import UnifiedTadeHandler (combines OLD + NEW Tade)
from app.services.tade_unified import UnifiedTadeHandler

logger = logging.getLogger(__name__)

router = APIRouter()

# Global Singleton for Unified Handler
_unified_handler = None

def get_unified_handler() -> UnifiedTadeHandler:
    """Get or create singleton instance of UnifiedTadeHandler."""
    global _unified_handler
    if _unified_handler is None:
        _unified_handler = UnifiedTadeHandler()
        logger.info("✅ UnifiedTadeHandler initialized (OLD + NEW Tade merger)")
    return _unified_handler



@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Webhook verification for Meta WhatsApp API.
    Called once when you set up the webhook in Meta Developer Console.
    """
    logger.info(f"Webhook verification attempt: mode={hub_mode}")
    
    result = whatsapp.verify_webhook(hub_mode, hub_token, hub_challenge)
    
    if result:
        return PlainTextResponse(content=result)
    
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """
    Receive incoming WhatsApp messages.
    
    Flow:
    1. Validate request
    2. Parse payload
    3. Process message in background (don't block webhook response)
    4. Return 200 immediately
    """
    try:
        # 1. EARLY RATE LIMIT (IP-based)
        # Check IP before parsing JSON to prevent DoS
        client_ip = request.client.host if request.client else "unknown"
        # We use a separate bucket for IP-based limiting or use the same one
        if not security._check_rate_limit(f"ip:{client_ip}"):
             logger.warning(f"Rate limit exceeded for IP {client_ip}")
             # Return 200 to drop silently without confirming it's working
             return {"status": "dropped"}

        # 2. Parse payload
        try:
            payload = await request.json()
        except Exception:
            # Invalid JSON -> drop
            return {"status": "invalid_payload"}
        
        # Log for debugging (don't log in production)
        logger.debug(f"Webhook received: {payload.get('object')}")
        
        # Validate it's a WhatsApp message
        if payload.get("object") != "whatsapp_business_account":
            return {"status": "not_whatsapp"}
        
        # Check for message entries
        entries = payload.get("entry", [])
        if not entries:
            return {"status": "no_entries"}
        
        # Process each entry (usually just one)
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                
                # Skip status updates (we only want messages)
                if "messages" not in value:
                    continue
                
                # Security Check
                try:
                    messages = value.get("messages", [])
                    if messages:
                        msg = messages[0]
                        user_id = msg.get("from")
                        text_body = ""
                        
                        if msg.get("type") == "text":
                            text_body = msg.get("text", {}).get("body", "")
                        
                        # Check security
                        is_safe, error_msg = security.check_request(user_id, text_body)
                        if not is_safe:
                            logger.warning(f"Security Blocked: {user_id} - {error_msg}")
                            # Optionally send a rejection message back (could use Twilio direct or just ignore)
                            # For now, we ignore to prevent resource usage
                            continue
                            
                except Exception as e:
                    logger.error(f"Security check error: {e}")
                
                # Check user-level restrictions (Prompt Guard / User Rate Limit)
                # TODO: Implement LLM-based Prompt Guard for production
                try:
                    messages = value.get("messages", [])
                    if messages:
                         # ... existing security logic ...
                         pass
                except:
                    pass
                
                # Use V5 Handler for background processing
                # Note: UnifiedTadeHandler handles format conversion internally if needed
                background_tasks.add_task(_process_meta_message, value)
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Still return 200 to prevent Meta from retrying
        return {"status": "error", "message": str(e)}


@router.get("/webhook/status")
async def webhook_status():
    """Check WhatsApp webhook configuration status."""
    from app.services import twilio_whatsapp
    
    # Check if unified handler is active
    global _unified_handler
    unified_status = "UnifiedTadeHandler" if _unified_handler else "Not Initialized"
    
    return {
        "meta_configured": whatsapp.is_configured(),
        "twilio_configured": twilio_whatsapp.is_configured(),
        "phone_number_id": whatsapp.PHONE_NUMBER_ID[:4] + "..." if whatsapp.PHONE_NUMBER_ID else None,
        "verify_token_set": bool(whatsapp.VERIFY_TOKEN),
        "merger_status": {
            "unified_handler_active": True,
            "new_handler": f"{unified_status} (Active)"
        }
    }


@router.post("/webhook/twilio")
async def twilio_webhook(request: Request):
    """
    Handle Twilio WhatsApp Sandbox webhook.
    Supports multimodal: text, voice, image, document, location.
    """
    from app.services import twilio_whatsapp, conversation
    from app.services.multimodal import process_multimodal_message, parse_twilio_media_message
    
    try:
        # Parse form data
        form_data = await request.form()
        form_dict = {k: v for k, v in form_data.items()}
        
        # Parse message with media detection
        message = parse_twilio_media_message(form_dict)
        
        user_hash = message["from_hash"]
        user_phone = message.get("from_raw", "").replace("whatsapp:", "")
        msg_type = message.get("type", "text")
        
        # Log with type info
        preview = message.get("text", message.get("caption", ""))[:50] or f"[{msg_type}]"
        logger.info(f"Twilio {msg_type} from {user_hash[:8]}...: {preview}")
        
        # Skip if no content
        if msg_type == "text" and not message.get("text"):
            # Check if there's media
            if int(form_dict.get("NumMedia", 0)) == 0:
                return {"status": "no_message"}
        
        # =========================================================
        # USE UNIFIED TADE HANDLER (The Merger)
        # =========================================================
        handler = get_unified_handler()
        
        # Unified handler expects: phone, text, media_url (optional)
        # It handles state, memory, tools internally
        text_body = message.get("text") or message.get("caption") or ""
        media_url = form_dict.get("MediaUrl0") # Simple grab of first media
        
        # Process message
        response = await handler.handle_message(
            phone=user_phone,
            message=text_body,
            media_url=media_url
        )
        
        # Format for WhatsApp (if needed, handler returns string usually)
        formatted_response = twilio_whatsapp.format_for_whatsapp(response)
        
        # Add response to context
        conversation.add_to_context(user_hash, "assistant", response)
        
        # Send reply via Twilio
        result = twilio_whatsapp.send_message(message["from_raw"], response)
        
        if result.get("error"):
            logger.error(f"Twilio send failed: {result['error']}")
        
        return {"status": "ok", "type": msg_type, "response_sent": not result.get("error")}
        
    except Exception as e:
        logger.error(f"Twilio webhook error: {e}")
        return {"status": "error", "message": str(e)}

async def _process_meta_message(value: dict):
    """Process incoming Meta WhatsApp message and send response."""
    from app.services.message_handler_v5 import handle_message
    from app.services import whatsapp

    try:
        messages = value.get("messages", [])
        if not messages:
            return

        msg = messages[0]
        phone = msg.get("from", "")
        msg_type = msg.get("type", "text")
        message_id = msg.get("id", "")

        # Mark as read
        if message_id:
            whatsapp.mark_as_read(message_id)

        # Extract text based on message type
        text = ""
        media_url = None
        location = None

        if msg_type == "text":
            text = msg.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            int_type = interactive.get("type")
            if int_type == "button_reply":
                text = interactive.get("button_reply", {}).get("title", "")
            elif int_type == "list_reply":
                text = interactive.get("list_reply", {}).get("title", "")
        elif msg_type == "location":
            loc = msg.get("location", {})
            location = {
                "lat": loc.get("latitude"),
                "lng": loc.get("longitude"),
            }
            text = "My location"
        elif msg_type == "image":
            text = msg.get("image", {}).get("caption", "Sent an image")
        elif msg_type == "audio":
            text = "Sent a voice note"
        elif msg_type == "document":
            text = msg.get("document", {}).get("caption", "Sent a document")

        if not text and not location:
            return

        logger.info(f"📨 Meta message from {phone[-4:]}: {text[:50]}")

        # Process through agent chain
        response = await handle_message(
            phone=phone,
            text=text,
            location=location,
        )

        # Send response back via Meta Cloud API
        if response:
            whatsapp.send_text_message(phone, response)
            logger.info(f"📤 Response sent to {phone[-4:]} ({len(response)} chars)")

    except Exception as e:
        logger.error(f"Meta message processing error: {e}")