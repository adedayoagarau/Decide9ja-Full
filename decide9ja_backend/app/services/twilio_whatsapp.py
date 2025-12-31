"""
Twilio WhatsApp Service for Decide9ja.
Handles WhatsApp messages via Twilio Sandbox for testing.
"""
import os
import hashlib
import logging
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"  # Sandbox number

# Initialize Twilio client
_client = None


def get_client():
    """Get Twilio client (lazy initialization)."""
    global _client
    if _client is None and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            from twilio.rest import Client
            _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            logger.info("Twilio client initialized")
        except ImportError:
            logger.warning("Twilio package not installed. Run: pip install twilio")
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
    return _client


def parse_twilio_message(form_data: dict) -> dict:
    """
    Parse Twilio webhook form data into standard format.
    
    Twilio sends:
    - Body: message text
    - From: whatsapp:+2348160179151
    - To: whatsapp:+14155238886
    - ProfileName: sender's WhatsApp name
    - MessageSid: unique message ID
    """
    from_number = form_data.get("From", "")
    
    return {
        "message_id": form_data.get("MessageSid", ""),
        "from": from_number.replace("whatsapp:", ""),
        "from_raw": from_number,
        "from_hash": hash_phone(from_number),
        "text": form_data.get("Body", ""),
        "type": "text",
        "contact_name": form_data.get("ProfileName", ""),
        "to": form_data.get("To", "").replace("whatsapp:", ""),
        "num_media": int(form_data.get("NumMedia", 0))
    }


def send_message(to: str, text: str) -> dict:
    """
    Send WhatsApp message via Twilio.
    
    Args:
        to: Phone number (with or without whatsapp: prefix)
        text: Message text
        
    Returns:
        Dict with message SID or error
    """
    client = get_client()
    if not client:
        logger.error("Twilio client not configured")
        return {"error": "Twilio not configured"}
    
    # Clean and format phone number
    # Remove any existing prefix and spaces
    to = to.replace("whatsapp:", "").replace(" ", "").strip()
    
    # Ensure + prefix for international format
    if not to.startswith("+"):
        to = f"+{to}"
    
    # Add whatsapp: prefix
    to = f"whatsapp:{to}"
    
    try:
        message = client.messages.create(
            body=text[:1600],  # Twilio limit
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to
        )
        logger.info(f"Twilio message sent: {message.sid}")
        return {"sid": message.sid, "status": message.status}
    except Exception as e:
        logger.error(f"Twilio send error: {e}")
        return {"error": str(e)}


def send_message_with_media(to: str, text: str, media_url: str) -> dict:
    """Send WhatsApp message with media via Twilio."""
    client = get_client()
    if not client:
        return {"error": "Twilio not configured"}
    
    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"
    
    try:
        message = client.messages.create(
            body=text[:1600],
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to,
            media_url=[media_url]
        )
        return {"sid": message.sid}
    except Exception as e:
        logger.error(f"Twilio media send error: {e}")
        return {"error": str(e)}


def hash_phone(phone: str) -> str:
    """Hash phone number for storage. Never store raw phone numbers."""
    return hashlib.sha256(phone.encode()).hexdigest()


def is_configured() -> bool:
    """Check if Twilio is properly configured."""
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)


def format_for_whatsapp(text: str) -> str:
    """
    Format text for WhatsApp (Twilio version).
    Similar to Meta version but simpler.
    """
    import re
    
    if not text:
        return ""
    
    # Convert **bold** to *bold*
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    
    # Convert ## headers to *bold*
    text = re.sub(r'^##+ (.+)$', r'*\1*', text, flags=re.MULTILINE)
    
    # Convert bullet points
    text = re.sub(r'^- ', '• ', text, flags=re.MULTILINE)
    
    # Truncate if too long (Twilio limit is ~1600)
    if len(text) > 1500:
        text = text[:1450] + "\n\n... (message truncated)"
    
    return text.strip()
