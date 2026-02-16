"""
WhatsApp Business API Service for Decide9ja.
Handles sending/receiving messages via Meta Cloud API.
"""
import os
import re
import hashlib
import logging
import requests
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# WhatsApp API Configuration
# WhatsApp API Configuration (Hardcoded for Deployment)
WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"
PHONE_NUMBER_ID = "960447083817127"
ACCESS_TOKEN = "EAAYNUf6ZB1yEBQrkeR29X7X0IXeOaX5q600K6uBWQa6PLfhJmJG3jeZCqwfvlphjfRsFuK9tLkY6d61Lv9mT2k1zufLD5Q5eOZBoUYzD0kfk1McXqZCUaZBDevYGlbR30mIrMx5bZAOEss8SFDHzXfvWLqAZAG00W8QVZCwjxHTT4YFd5yPFGNcPjhC1BD2BJQZDZD"
VERIFY_TOKEN = "decide9ja_verify_2024"
BUSINESS_ACCOUNT_ID = "1383059273032709"

# Max message length for WhatsApp
MAX_MESSAGE_LENGTH = 4096


def verify_webhook(mode: str, token: str, challenge: str) -> Optional[str]:
    """
    Verify webhook for Meta WhatsApp API setup.
    Returns challenge if valid, None if invalid.
    """
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified successfully")
        return challenge
    logger.warning(f"Webhook verification failed: mode={mode}")
    return None


def parse_incoming_message(payload: dict) -> Optional[dict]:
    """
    Parse incoming WhatsApp webhook payload.
    
    Returns parsed message dict or None if not a message event.
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        # Check if this is a message event
        messages = value.get("messages", [])
        if not messages:
            return None
        
        message = messages[0]
        msg_type = message.get("type", "text")
        
        # Base message data
        parsed = {
            "message_id": message.get("id", ""),
            "from": message.get("from", ""),
            "from_hash": hash_phone_number(message.get("from", "")),
            "timestamp": message.get("timestamp", ""),
            "type": msg_type,
        }
        
        # Parse based on message type
        if msg_type == "text":
            parsed["text"] = message.get("text", {}).get("body", "")
        
        elif msg_type == "location":
            loc = message.get("location", {})
            parsed["location"] = {
                "lat": loc.get("latitude"),
                "lng": loc.get("longitude"),
                "name": loc.get("name"),
                "address": loc.get("address")
            }
        
        elif msg_type == "image":
            img = message.get("image", {})
            parsed["image_id"] = img.get("id")
            parsed["caption"] = img.get("caption", "")
            parsed["mime_type"] = img.get("mime_type")
        
        elif msg_type == "interactive":
            interactive = message.get("interactive", {})
            int_type = interactive.get("type")
            
            if int_type == "button_reply":
                reply = interactive.get("button_reply", {})
                parsed["button_id"] = reply.get("id")
                parsed["button_text"] = reply.get("title")
            elif int_type == "list_reply":
                reply = interactive.get("list_reply", {})
                parsed["list_id"] = reply.get("id")
                parsed["list_title"] = reply.get("title")
                parsed["list_description"] = reply.get("description")
        
        # Get contact info if available
        contacts = value.get("contacts", [])
        if contacts:
            parsed["contact_name"] = contacts[0].get("profile", {}).get("name")
        
        return parsed
        
    except Exception as e:
        logger.error(f"Error parsing WhatsApp message: {e}")
        return None


def download_media(media_id: str) -> Optional[bytes]:
    """
    Download media (image/audio) from WhatsApp.
    Returns the file bytes or None on error.
    """
    if not ACCESS_TOKEN:
        logger.error("WhatsApp access token not configured")
        return None
    
    try:
        # First, get the media URL
        url = f"{WHATSAPP_API_URL}/{media_id}"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        media_url = response.json().get("url")
        if not media_url:
            return None
        
        # Download the actual file
        file_response = requests.get(media_url, headers=headers)
        file_response.raise_for_status()
        
        return file_response.content
        
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
        return None


def send_text_message(to: str, text: str) -> dict:
    """
    Send a text message to WhatsApp user.
    Handles message length (max 4096 chars).
    """
    if not PHONE_NUMBER_ID or not ACCESS_TOKEN:
        logger.error("WhatsApp credentials not configured")
        return {"error": "WhatsApp not configured"}
    
    # Format and truncate if needed
    text = format_for_whatsapp(text)
    
    # Split if too long
    if len(text) > MAX_MESSAGE_LENGTH:
        messages = split_message(text)
        results = []
        for msg in messages:
            results.append(_send_single_message(to, msg))
        return {"results": results}
    
    return _send_single_message(to, text)


def _send_single_message(to: str, text: str) -> dict:
    """Send a single text message."""
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent to {hash_phone_number(to)[:8]}...")
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return {"error": str(e)}


def send_message_with_buttons(to: str, text: str, buttons: List[dict]) -> dict:
    """
    Send interactive message with buttons.
    
    buttons format:
    [{"id": "option_1", "title": "Option 1"}, ...]
    
    Max 3 buttons, max 20 chars per button title.
    """
    if not PHONE_NUMBER_ID or not ACCESS_TOKEN:
        return {"error": "WhatsApp not configured"}
    
    # Limit to 3 buttons
    buttons = buttons[:3]
    
    # Format button titles (max 20 chars)
    formatted_buttons = []
    for btn in buttons:
        formatted_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn["id"][:256],
                "title": btn["title"][:20]
            }
        })
    
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text[:1024]},
            "action": {"buttons": formatted_buttons}
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error sending button message: {e}")
        return {"error": str(e)}


def send_message_with_list(to: str, text: str, button_text: str, sections: List[dict]) -> dict:
    """
    Send interactive list message.
    
    sections format:
    [{"title": "Section 1", "rows": [{"id": "row_1", "title": "Row 1", "description": "Desc"}]}]
    
    Max 10 rows total.
    """
    if not PHONE_NUMBER_ID or not ACCESS_TOKEN:
        return {"error": "WhatsApp not configured"}
    
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text[:1024]},
            "action": {
                "button": button_text[:20],
                "sections": sections
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error sending list message: {e}")
        return {"error": str(e)}


def send_location_request(to: str, text: str = None) -> dict:
    """
    Send message asking user to share location.
    WhatsApp doesn't have a location request button, so we send text instructions.
    """
    if text is None:
        text = """📍 Please share your location:

1. Tap the 📎 attachment icon
2. Select "Location"
3. Choose "Send your current location"

This helps me identify your state, LGA, and the right representatives for you."""
    
    return send_text_message(to, text)


def mark_as_read(message_id: str) -> dict:
    """Mark message as read (blue ticks)."""
    if not PHONE_NUMBER_ID or not ACCESS_TOKEN:
        return {"error": "WhatsApp not configured"}
    
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Error marking message as read: {e}")
        return {"error": str(e)}


def format_for_whatsapp(text: str) -> str:
    """
    Convert markdown to WhatsApp formatting:
    - **bold** → *bold*
    - _italic_ stays same
    - ## Header → *Header*
    - - bullet → • bullet
    - Truncate to 4096 chars if needed
    """
    if not text:
        return ""
    
    # Convert **bold** to *bold*
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    
    # Convert ## headers to *bold*
    text = re.sub(r'^##+ (.+)$', r'*\1*', text, flags=re.MULTILINE)
    
    # Convert bullet points
    text = re.sub(r'^- ', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'^\* ', '• ', text, flags=re.MULTILINE)
    
    # Remove code blocks (triple backticks)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    
    # Truncate if too long
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH - 50] + "\n\n... (message truncated)"
    
    return text.strip()


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Split a long message into chunks."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current = ""
    
    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_length:
            current += para + "\n\n" if current else para
        else:
            if current:
                chunks.append(current.strip())
            current = para
    
    if current:
        chunks.append(current.strip())
    
    return chunks


def hash_phone_number(phone: str) -> str:
    """
    Hash phone number for storage.
    Never store raw phone numbers.
    """
    return hashlib.sha256(phone.encode()).hexdigest()


def is_configured() -> bool:
    """Check if WhatsApp API is properly configured."""
    return all([PHONE_NUMBER_ID, ACCESS_TOKEN, VERIFY_TOKEN])
