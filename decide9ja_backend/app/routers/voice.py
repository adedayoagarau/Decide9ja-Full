"""
Twilio Voice Router - AI Phone Call Handler
Enables live AI conversations over phone calls.
"""
import os
import logging
from fastapi import APIRouter, Request, Response, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from app.database import get_db
from app.services import voice
from app.services.message_handler_v2 import IntegratedMessageHandler
from app.services import llm
from app.services.rag import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

# Base URL for audio files (will be set dynamically)
BASE_URL = os.getenv("BASE_URL", "")


def twiml_response(content: str) -> Response:
    """Return TwiML XML response."""
    return Response(content=content, media_type="application/xml")


@router.post("/incoming")
async def handle_incoming_call(request: Request, db: Session = Depends(get_db)):
    """
    Handle incoming voice calls.
    Plays welcome message and gathers speech input.
    """
    try:
        form_data = await request.form()
        caller = str(form_data.get("From", "Unknown"))
        
        logger.info(f"Incoming call from: {caller}")
        
        # Get ngrok URL dynamically from request
        host = request.headers.get("host", "localhost:8000")
        scheme = "https" if "ngrok" in host else "http"
        base_url = f"{scheme}://{host}"
        
        # TwiML: Welcome and gather speech
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna" language="en-US">
        Welcome to Decide 9ja. I'm your civic assistant. Ask me anything about Nigerian politics, your representatives, or current issues.
    </Say>
    <Gather input="speech" action="{base_url}/voice/process" method="POST" 
            speechTimeout="auto" timeout="5" language="en-NG">
        <Say voice="Polly.Joanna">Go ahead, I'm listening.</Say>
    </Gather>
    <Say voice="Polly.Joanna">I didn't hear anything. Goodbye.</Say>
</Response>"""
        
        return twiml_response(twiml)
        
    except Exception as e:
        logger.error(f"Incoming call error: {e}")
        return twiml_response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, an error occurred. Please try again later.</Say>
    <Hangup/>
</Response>""")


@router.post("/process")
async def process_speech(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Process speech input and generate AI response.
    """
    try:
        form_data = await request.form()
        
        # Get transcribed speech from Twilio
        speech_result = str(form_data.get("SpeechResult", ""))
        confidence = form_data.get("Confidence", "0")
        caller = str(form_data.get("From", "unknown"))
        
        logger.info(f"Speech received: '{speech_result}' (confidence: {confidence})")
        
        if not speech_result:
            return twiml_response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">I didn't catch that. Please try again.</Say>
    <Redirect>/voice/incoming</Redirect>
</Response>""")
        
        # Get base URL
        host = request.headers.get("host", "localhost:8000")
        scheme = "https" if "ngrok" in host else "http"
        base_url = f"{scheme}://{host}"
        
        # Hash caller for user identification
        from app.services.twilio_whatsapp import hash_phone
        user_hash = hash_phone(caller)
        
        # Initialize handler
        rag = RAGService(db)
        handler = IntegratedMessageHandler(
            db_session=db,
            llm_service=llm,
            rag_service=rag
        )
        
        # Process with AI (shorter response for voice)
        ai_response = await handler.handle(user_hash, speech_result)
        
        # Truncate for voice (max 500 chars for natural speech)
        if len(ai_response) > 500:
            # Find sentence boundary
            truncated = ai_response[:500]
            last_period = truncated.rfind('.')
            if last_period > 200:
                ai_response = truncated[:last_period + 1]
            else:
                ai_response = truncated + "..."
        
        logger.info(f"AI Response: {ai_response[:100]}...")
        
        # Generate audio with ElevenLabs for better voice quality
        audio_path = await voice.text_to_speech(ai_response)
        
        if audio_path:
            # Serve audio file (need to create endpoint for this)
            # For now, use Twilio's built-in <Say>
            pass
        
        # TwiML response with AI answer
        # Using Polly for faster response, ElevenLabs can be added via <Play>
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna" language="en-US">{_escape_xml(ai_response)}</Say>
    <Gather input="speech" action="{base_url}/voice/process" method="POST" 
            speechTimeout="auto" timeout="5" language="en-NG">
        <Say voice="Polly.Joanna">Do you have another question?</Say>
    </Gather>
    <Say voice="Polly.Joanna">Thank you for calling Decide 9ja. Goodbye!</Say>
    <Hangup/>
</Response>"""
        
        return twiml_response(twiml)
        
    except Exception as e:
        logger.error(f"Process speech error: {e}")
        return twiml_response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Sorry, I encountered an error processing your request. Please try again.</Say>
    <Redirect>/voice/incoming</Redirect>
</Response>""")


@router.post("/status")
async def call_status(request: Request):
    """Handle call status callbacks from Twilio."""
    form_data = await request.form()
    call_status = form_data.get("CallStatus", "unknown")
    call_sid = form_data.get("CallSid", "unknown")
    
    logger.info(f"Call {call_sid} status: {call_status}")
    
    return {"status": "ok"}


def _escape_xml(text: str) -> str:
    """Escape special characters for XML/TwiML."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
