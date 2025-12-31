"""
WhatsApp Webhook Router for Decide9ja.
Handles incoming WhatsApp messages from Meta Cloud API.
"""
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse

from app.services import whatsapp
from app.services.message_handler_v2 import handle_whatsapp_message
from app.services.security import security

logger = logging.getLogger(__name__)

router = APIRouter()


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
                
                # Process message in background to not block webhook
                background_tasks.add_task(handle_whatsapp_message, payload)
        
        # Always return 200 quickly to acknowledge receipt
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Still return 200 to prevent Meta from retrying
        return {"status": "error", "message": str(e)}


@router.get("/webhook/status")
async def webhook_status():
    """Check WhatsApp webhook configuration status."""
    from app.services import twilio_whatsapp
    
    return {
        "meta_configured": whatsapp.is_configured(),
        "twilio_configured": twilio_whatsapp.is_configured(),
        "phone_number_id": whatsapp.PHONE_NUMBER_ID[:4] + "..." if whatsapp.PHONE_NUMBER_ID else None,
        "verify_token_set": bool(whatsapp.VERIFY_TOKEN),
        "access_token_set": bool(whatsapp.ACCESS_TOKEN)
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
        msg_type = message.get("type", "text")
        
        # Log with type info
        preview = message.get("text", message.get("caption", ""))[:50] or f"[{msg_type}]"
        logger.info(f"Twilio {msg_type} from {user_hash[:8]}...: {preview}")
        
        # Skip if no content
        if msg_type == "text" and not message.get("text"):
            # Check if there's media
            if int(form_dict.get("NumMedia", 0)) == 0:
                return {"status": "no_message"}
        
        # Process message using multimodal handler
        try:
            response = await process_multimodal_message(message, user_hash)
            
            # Handle dict responses (buttons not supported in Twilio sandbox)
            if isinstance(response, dict):
                response = response.get("text", str(response))
            
            # Format for WhatsApp
            response = twilio_whatsapp.format_for_whatsapp(response)
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            response = "Welcome to Decide9ja! 🇳🇬 Say 'hi' to get started."
        
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

