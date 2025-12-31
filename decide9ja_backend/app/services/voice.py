"""
Voice Service - ElevenLabs TTS + OpenAI Whisper STT
Enables voice interactions for Decide9ja via Twilio Voice.
"""
import os
import httpx
import logging
import tempfile
import hashlib
from pathlib import Path
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ElevenLabs Nigerian Voice Options
VOICE_OPTIONS = {
    # Primary voices
    "1": {"id": "zwbf3iHXH6YGoTCPStfx", "name": "Voice 1"},
    "2": {"id": "9Dbo4hEvXQ5l7MXGZFQA", "name": "Voice 2"},
    "3": {"id": "it5NMxoQQ2INIh4XcO44", "name": "Voice 3"},
    "4": {"id": "JMwQvjJt08OhYlPBWeyc", "name": "Voice 4"},
    "5": {"id": "gM1otA87NrAmOwyCoJE6", "name": "Voice 5"},
    "6": {"id": "NcEGFdSqsghiXx8rytiN", "name": "Voice 6"},
    "7": {"id": "E0K2ijvDA301rITqf72S", "name": "Voice 7"},
    "8": {"id": "YI5bDiiDOYHHb2eLadHv", "name": "Voice 8"},
    
    # Aliases
    "default": {"id": "zwbf3iHXH6YGoTCPStfx", "name": "Default"},
    "male": {"id": "9Dbo4hEvXQ5l7MXGZFQA", "name": "Male"},
    "female": {"id": "it5NMxoQQ2INIh4XcO44", "name": "Female"},
}

# Legacy compatibility
VOICE_IDS = {k: v["id"] for k, v in VOICE_OPTIONS.items()}

# Audio cache directory
AUDIO_CACHE_DIR = Path("/tmp/decide9ja_audio")
AUDIO_CACHE_DIR.mkdir(exist_ok=True)


async def text_to_speech(text: str, voice: str = "default") -> Optional[str]:
    """
    Convert text to speech using ElevenLabs.
    Returns path to audio file.
    """
    if not ELEVENLABS_API_KEY:
        logger.error("ELEVENLABS_API_KEY not configured")
        return None
    
    # Check cache first (hash of text)
    text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    cache_path = AUDIO_CACHE_DIR / f"{text_hash}.mp3"
    
    if cache_path.exists():
        logger.info(f"Using cached audio: {cache_path}")
        return str(cache_path)
    
    voice_id = VOICE_IDS.get(voice, VOICE_IDS["default"])
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    
    # Optimized for speed
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",  # Fastest model
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                # Save to cache
                with open(cache_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"Generated audio: {cache_path}")
                return str(cache_path)
            else:
                logger.error(f"ElevenLabs error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


def text_to_speech_sync(text: str, voice: str = "default") -> Optional[str]:
    """Synchronous version of TTS for simpler use cases."""
    import asyncio
    return asyncio.run(text_to_speech(text, voice))


async def speech_to_text(audio_url: str) -> Optional[str]:
    """
    Transcribe audio using OpenAI Whisper.
    Downloads audio from URL (with Twilio auth) and transcribes.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured")
        return None
    
    # Get Twilio credentials for authenticated media download
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    
    try:
        # Download audio from Twilio with authentication
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Twilio media URLs require basic auth
            if "twilio.com" in audio_url and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
                auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                response = await client.get(audio_url, auth=auth)
            else:
                response = await client.get(audio_url)
            
            if response.status_code != 200:
                logger.error(f"Failed to download audio: {response.status_code}")
                return None
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(response.content)
                temp_path = f.name
        
        # Transcribe with Whisper
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        with open(temp_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"  # Can be auto-detected
            )
        
        # Cleanup
        os.unlink(temp_path)
        
        logger.info(f"Transcribed: {transcript.text[:100]}...")
        return transcript.text
        
    except Exception as e:
        logger.error(f"STT error: {e}")
        return None


def speech_to_text_sync(audio_url: str) -> Optional[str]:
    """Synchronous version of STT."""
    import asyncio
    return asyncio.run(speech_to_text(audio_url))


# Quick response templates for common greetings (pre-generated for speed)
QUICK_RESPONSES = {
    "welcome": "Welcome to Decide9ja. I'm your civic assistant. How can I help you today?",
    "goodbye": "Thank you for calling Decide9ja. Goodbye!",
    "error": "I'm sorry, I didn't catch that. Please try again.",
    "processing": "Let me look that up for you.",
}


async def get_quick_audio(key: str) -> Optional[str]:
    """Get pre-generated audio for common responses."""
    if key in QUICK_RESPONSES:
        return await text_to_speech(QUICK_RESPONSES[key])
    return None
