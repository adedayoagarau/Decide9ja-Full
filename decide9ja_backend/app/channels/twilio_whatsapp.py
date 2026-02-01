"""
Twilio WhatsApp Integration for Tade

Setup:
1. Install: pip install twilio
2. Set environment variables (see above)
3. Configure webhook URL in Twilio console
4. Test with a message!
"""

import os
from typing import Optional
from datetime import datetime
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
import logging

logger = logging.getLogger(__name__)

# Initialize Twilio client
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "+17753632498")

# Validate credentials on import
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN]):
    logger.warning("⚠️  Twilio credentials not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN env vars.")
    twilio_client = None
else:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info(f"✅ Twilio client initialized ({TWILIO_PHONE_NUMBER})")


class TwilioWhatsAppHandler:
    """
    Handles WhatsApp messages via Twilio for Tade.
    
    Usage:
        handler = TwilioWhatsAppHandler()
        
        # In your FastAPI route
        @router.post("/webhook/twilio")
        async def twilio_webhook(request: Request):
            return await handler.handle_incoming(request)
    """
    
    def __init__(self, tade_handler=None):
        self.client = twilio_client
        self.phone_number = TWILIO_PHONE_NUMBER
        self.tade_handler = tade_handler
        
    async def handle_incoming(self, request: Request) -> PlainTextResponse:
        """
        Handle incoming WhatsApp message from Twilio webhook.
        
        Returns TwiML response (XML) that Twilio expects.
        """
        try:
            # Parse form data from Twilio
            form_data = await request.form()
            
            from_number = form_data.get("From", "").replace("whatsapp:", "")
            body = form_data.get("Body", "").strip()
            message_sid = form_data.get("MessageSid", "")
            
            logger.info(f"📩 WhatsApp from {from_number}: {body[:50]}...")
            
            # Get Tade's response
            if self.tade_handler:
                tade_response = await self.tade_handler.handle_message(
                    phone=from_number,
                    message=body
                )
            else:
                # Fallback response if Tade not configured
                tade_response = self._fallback_response(body)
            
            # Create TwiML response
            twiml = MessagingResponse()
            twiml.message(tade_response)
            
            logger.info(f"📤 Replying to {from_number}: {tade_response[:50]}...")
            
            return PlainTextResponse(
                content=str(twiml),
                media_type="application/xml"
            )
            
        except Exception as e:
            logger.error(f"❌ Error handling Twilio webhook: {e}")
            # Return error message to user
            twiml = MessagingResponse()
            twiml.message("Sorry, I encountered an error. Please try again in a moment.")
            return PlainTextResponse(
                content=str(twiml),
                media_type="application/xml"
            )
    
    async def send_message(self, to_number: str, message: str) -> Optional[str]:
        """
        Send proactive WhatsApp message via Twilio.
        
        Args:
            to_number: Phone number (e.g., "+2348160179151")
            message: Message text
            
        Returns:
            Message SID if sent successfully
        """
        if not self.client:
            logger.error("❌ Twilio client not initialized")
            return None
        
        try:
            # Format number for WhatsApp
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"
            
            from_number = f"whatsapp:{self.phone_number}"
            
            msg = self.client.messages.create(
                body=message,
                from_=from_number,
                to=to_number
            )
            
            logger.info(f"✅ Message sent: {msg.sid}")
            return msg.sid
            
        except Exception as e:
            logger.error(f"❌ Failed to send message: {e}")
            return None
    
    def _fallback_response(self, message: str) -> str:
        """Simple fallback if Tade handler not configured"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["hello", "hi", "hey"]):
            return "👋 Hello! I'm Tade, your Nigerian civic engagement assistant. How can I help you today?"
        
        if "help" in message_lower:
            return (
                "🤖 *Tade Commands:*\n\n"
                "• *Location:* Tell me your state/LGA (e.g., 'I dey Lagos')\n"
                "• *Find Rep:* Ask about your representative\n"
                "• *Budget:* Query budget data\n"
                "• *News:* Search historical news archives\n\n"
                "What would you like to know?"
            )
        
        return "I received your message! I'm still learning, but I can help you find information about Nigerian politics, budgets, and representatives. What would you like to explore?"


# FastAPI Router for easy integration
router = APIRouter(prefix="/webhook", tags=["twilio"])

# Global handler instance
_twilio_handler: Optional[TwilioWhatsAppHandler] = None

def get_twilio_handler(tade_handler=None) -> TwilioWhatsAppHandler:
    """Get or create Twilio handler singleton"""
    global _twilio_handler
    if _twilio_handler is None:
        _twilio_handler = TwilioWhatsAppHandler(tade_handler=tade_handler)
    return _twilio_handler


@router.post("/twilio")
async def twilio_webhook(request: Request):
    """
    Main webhook endpoint for Twilio WhatsApp.
    
    Configure this in Twilio Console:
    - URL: https://your-domain.com/api/v1/webhook/twilio
    - Method: POST
    """
    handler = get_twilio_handler()
    return await handler.handle_incoming(request)


@router.get("/twilio/test")
async def test_twilio_config():
    """Test Twilio configuration"""
    return {
        "configured": twilio_client is not None,
        "phone_number": TWILIO_PHONE_NUMBER,
        "account_sid_prefix": TWILIO_ACCOUNT_SID[:10] + "..." if TWILIO_ACCOUNT_SID else None
    }


# Example proactive message sender
async def send_guardian_update(phone: str, progress: dict):
    """Send Guardian crawl progress update"""
    handler = get_twilio_handler()
    
    message = (
        f"📰 *Guardian Crawl Update*\n\n"
        f"Progress: {progress.get('percent', 0)}%\n"
        f"Images: {progress.get('images', 0)}\n"
        f"ETA: {progress.get('eta', 'calculating...')}\n\n"
        f"_Tade Archive System_"
    )
    
    return await handler.send_message(phone, message)


if __name__ == "__main__":
    # Test script
    print("🧪 Twilio Tade Integration Test")
    print("=" * 50)
    
    # Check config
    if twilio_client:
        print("✅ Twilio client initialized")
        print(f"   Phone: {TWILIO_PHONE_NUMBER}")
        
        # Test proactive message (uncomment to send)
        # import asyncio
        # handler = TwilioWhatsAppHandler()
        # asyncio.run(handler.send_message(
        #     "+2348160179151",
        #     "🤖 Tade is now connected via Twilio! Reply to test."
        # ))
    else:
        print("❌ Twilio not configured")
        print("   Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
