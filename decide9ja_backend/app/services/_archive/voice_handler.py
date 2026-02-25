"""
Voice Handler for Decide9ja.
Transcribes voice notes using OpenAI Whisper API.
Handles Nigerian English, Pidgin, and code-switching.
"""
import os
import logging
import tempfile
import requests
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WHISPER_MODEL = "whisper-1"


def is_configured() -> bool:
    """Check if voice handler is configured."""
    return bool(OPENAI_API_KEY)


async def download_audio(url: str, auth: tuple = None) -> Optional[bytes]:
    """Download audio file from URL."""
    try:
        headers = {}
        if auth:
            import base64
            credentials = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download audio: {e}")
        return None


async def transcribe_audio(audio_url: str) -> Dict:
    """
    Transcribe audio using OpenAI Whisper.
    
    Args:
        audio_url: URL to audio file (from WhatsApp/Twilio)
        
    Returns:
        Dict with transcription, language, and metadata
    """
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key not configured")
        return {"error": "Voice transcription not configured", "text": None}
    
    try:
        # Download audio from Twilio (requires auth)
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        audio_data = await download_audio(audio_url, auth=(twilio_sid, twilio_token))
        
        if not audio_data:
            return {"error": "Failed to download audio", "text": None}
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            # Call Whisper API
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            with open(temp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model=WHISPER_MODEL,
                    file=audio_file,
                    language="en",  # Will detect Nigerian English, Pidgin
                    prompt="Nigerian politics, Tinubu, Obi, Atiku, APC, PDP, INEC, naira, Pidgin English"
                )
            
            text = transcript.text
            
            # Detect if Pidgin
            is_pidgin = detect_pidgin(text)
            
            logger.info(f"Transcribed voice: {text[:50]}... (Pidgin: {is_pidgin})")
            
            return {
                "text": text,
                "language": "pidgin" if is_pidgin else "en",
                "duration_estimate": len(audio_data) / 16000,  # Rough estimate
                "error": None
            }
            
        finally:
            # Clean up temp file
            os.unlink(temp_path)
            
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return {"error": str(e), "text": None}


def detect_pidgin(text: str) -> bool:
    """Detect if text is Nigerian Pidgin."""
    pidgin_markers = [
        "wetin", "dey", "wahala", "oya", "abeg", "shey", "sef",
        "no be", "na so", "e don", "wey", "una", "dem", "sabi"
    ]
    text_lower = text.lower()
    return any(marker in text_lower for marker in pidgin_markers)


def transcribe_sync(audio_url: str) -> Dict:
    """Synchronous version for simpler use cases."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(transcribe_audio(audio_url))
    finally:
        loop.close()
