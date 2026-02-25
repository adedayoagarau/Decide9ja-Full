"""
WhatsApp Webhook Router for Decide9ja.
Handles incoming WhatsApp messages from Meta Cloud API and Twilio.

ALL message paths route through V5 multi-agent handler.
"""
import logging
import hashlib
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse

from app.services import whatsapp
from app.services.security import security

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# META CLOUD API WEBHOOKS
# =============================================================================

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
async def receive_meta_message(request: Request, background_tasks: BackgroundTasks):
    """
    Receive incoming WhatsApp messages from Meta Cloud API.

    Flow:
    1. Validate request
    2. Parse payload
    3. Process message in background via V5 agent chain
    4. Return 200 immediately
    """
    try:
        # Rate limit by IP
        client_ip = request.client.host if request.client else "unknown"
        if not security._check_rate_limit(f"ip:{client_ip}"):
            logger.warning(f"Rate limit exceeded for IP {client_ip}")
            return {"status": "dropped"}

        # Parse payload
        try:
            payload = await request.json()
        except Exception:
            return {"status": "invalid_payload"}

        # Validate it's a WhatsApp message
        if payload.get("object") != "whatsapp_business_account":
            return {"status": "not_whatsapp"}

        entries = payload.get("entry", [])
        if not entries:
            return {"status": "no_entries"}

        # Process each entry
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})

                # Skip status updates (we only want messages)
                if "messages" not in value:
                    continue

                # Security check
                try:
                    messages = value.get("messages", [])
                    if messages:
                        msg = messages[0]
                        user_id = msg.get("from")
                        text_body = ""

                        if msg.get("type") == "text":
                            text_body = msg.get("text", {}).get("body", "")

                        is_safe, error_msg = security.check_request(user_id, text_body)
                        if not is_safe:
                            logger.warning(f"Security Blocked: {user_id} - {error_msg}")
                            continue

                except Exception as e:
                    logger.error(f"Security check error: {e}")

                # Process via V5 agent chain in background
                background_tasks.add_task(_process_meta_message, value)

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}


# =============================================================================
# TWILIO WEBHOOKS
# =============================================================================

@router.post("/webhook/twilio")
async def receive_twilio_message(request: Request, background_tasks: BackgroundTasks):
    """
    Handle incoming Twilio WhatsApp messages.
    Routes through V5 multi-agent handler (same as Meta path).
    """
    from app.services import twilio_whatsapp

    try:
        # Parse Twilio form data
        form_data = await request.form()
        form_dict = {k: v for k, v in form_data.items()}

        phone_from = str(form_dict.get("From", ""))
        message_body = str(form_dict.get("Body", ""))
        profile_name = str(form_dict.get("ProfileName", "User"))
        num_media = int(form_dict.get("NumMedia", 0))
        media_url = str(form_dict.get("MediaUrl0", "")) if num_media > 0 else ""
        media_type = str(form_dict.get("MediaContentType0", ""))

        # Clean phone number
        user_phone = phone_from.replace("whatsapp:", "")
        user_hash = hashlib.sha256(phone_from.encode()).hexdigest()[:16]

        if not message_body and not media_url:
            logger.info(f"Empty message from {user_hash[:8]}")
            return {"status": "no_message"}

        # Log
        logger.info(f"📨 Twilio message from {user_hash[:8]}...: '{message_body[:50]}'")

        # Process in background via V5 agent chain
        background_tasks.add_task(
            _process_twilio_message,
            phone_from,
            user_phone,
            message_body,
            media_url,
            media_type
        )

        # Return 200 immediately
        return {"status": "received"}

    except Exception as e:
        logger.error(f"Twilio webhook error: {e}")
        return {"status": "error", "message": str(e)}


# =============================================================================
# STATUS ENDPOINT
# =============================================================================

@router.get("/webhook/status")
async def webhook_status():
    """Check WhatsApp webhook configuration status."""
    from app.services import twilio_whatsapp

    return {
        "meta_configured": whatsapp.is_configured(),
        "twilio_configured": twilio_whatsapp.is_configured(),
        "phone_number_id": whatsapp.PHONE_NUMBER_ID[:4] + "..." if whatsapp.PHONE_NUMBER_ID else None,
        "verify_token_set": bool(whatsapp.VERIFY_TOKEN),
        "handler": "message_handler_v5 (multi-agent chain)"
    }


# =============================================================================
# BACKGROUND PROCESSORS
# =============================================================================

async def _process_meta_message(value: dict):
    """Process incoming Meta WhatsApp message via V5 and send response."""
    from app.services.message_handler_v5 import handle_message
    from app.services import whatsapp as wa

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
            wa.mark_as_read(message_id)

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

        # Process through V5 agent chain
        response = await handle_message(
            phone=phone,
            text=text,
            location=location,
        )

        # Send response back via Meta Cloud API
        if response:
            wa.send_text_message(phone, response)
            logger.info(f"📤 Response sent to {phone[-4:]} ({len(response)} chars)")

    except Exception as e:
        logger.error(f"Meta message processing error: {e}")


async def _process_twilio_message(
    phone_from: str,
    user_phone: str,
    message_body: str,
    media_url: str,
    media_type: str
):
    """Process incoming Twilio message via V5 and send response."""
    from app.services.message_handler_v5 import handle_message
    from app.services.twilio_whatsapp import send_message
    from app.services import voice

    try:
        # Handle voice notes
        if media_url and "audio" in media_type:
            logger.info("Transcribing voice note...")
            try:
                transcribed = await voice.speech_to_text(media_url)
                if transcribed:
                    message_body = transcribed
            except Exception as e:
                logger.error(f"Voice transcription error: {e}")
                send_message(phone_from, "Sorry, I couldn't understand that voice note. Please try again or type your message.")
                return

        if not message_body:
            return

        # Process through V5 agent chain
        response = await handle_message(
            phone=user_phone,
            text=message_body,
        )

        logger.info(f"📤 Response ready ({len(response)} chars)")

        # Send response via Twilio API
        result = send_message(phone_from, response[:1500])

        if result.get("error"):
            logger.error(f"Twilio send error: {result['error']}")
        else:
            logger.info(f"✅ Response sent via Twilio: {result.get('sid', 'unknown')}")

    except Exception as e:
        logger.error(f"Twilio background processing error: {e}")
        try:
            from app.services.twilio_whatsapp import send_message
            send_message(phone_from, "Sorry, something went wrong. Please try again.")
        except:
            pass
