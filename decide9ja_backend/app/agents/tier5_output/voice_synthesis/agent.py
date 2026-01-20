"""
VoiceSynthesisAgent
===================
Converts text responses to voice using Eleven Labs.

Cost: MEDIUM (~$0.30/1000 characters)

Features:
- Nigerian-accented English voice
- Automatic text optimization for speech
- Caching of common responses
- Fallback to text on errors

Usage:
    agent = VoiceSynthesisAgent()
    output = await agent.handle(AgentInput(
        raw_text="Hello, how can I help you?"
    ))
    # output.media_url contains the audio URL
"""

import os
import io
import time
import hashlib
import logging
import httpx
from typing import Optional, Dict
from datetime import datetime

from app.agents.base import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentTier,
    CostLevel
)
from app.agents.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class VoiceSynthesisAgent(BaseAgent):
    """Converts text responses to voice using Eleven Labs"""

    name = "voice_synthesis"
    description = "Convert text to speech using Eleven Labs"
    tier = AgentTier.OUTPUT
    cost_level = CostLevel.MEDIUM  # ~$0.30/1000 chars

    # Voice configuration
    # TODO: Replace with actual Nigerian voice IDs after setup
    VOICE_MAP = {
        "en": "pNInz6obpgDQGcFmaJgB",      # Adam - clear English
        "pcm": "pNInz6obpgDQGcFmaJgB",     # Use same for Pidgin (sounds natural)
        "yo": "pNInz6obpgDQGcFmaJgB",      # Yoruba
        "ha": "pNInz6obpgDQGcFmaJgB",      # Hausa
        "ig": "pNInz6obpgDQGcFmaJgB",      # Igbo
        "default": "pNInz6obpgDQGcFmaJgB", # Fallback
    }

    # Model options
    MODELS = {
        "fast": "eleven_turbo_v2_5",       # Fastest, cheapest
        "quality": "eleven_multilingual_v2", # Best quality
    }

    # Configuration
    MAX_CHARS = 500           # Don't synthesize longer than this
    MIN_CHARS = 10            # Skip very short texts
    MODEL = "fast"            # Use turbo for speed
    OUTPUT_FORMAT = "mp3_44100_64"  # WhatsApp compatible
    TIMEOUT_SECONDS = 30

    # Voice settings
    VOICE_SETTINGS = {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True,
    }

    # Audio storage config
    AUDIO_DIR = "/tmp/decide9ja_audio"
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = os.getenv("ELEVEN_LABS_API_KEY")
        self._http_client: Optional[httpx.AsyncClient] = None
        self._audio_cache: Dict[str, str] = {}  # text_hash -> audio_url

        # Ensure audio directory exists
        os.makedirs(self.AUDIO_DIR, exist_ok=True)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS)
        return self._http_client

    async def can_handle(self, input: AgentInput) -> bool:
        """Check if we have text to synthesize"""
        text = input.raw_text or input.entities.get("response_text", "")
        return bool(text) and len(text) >= self.MIN_CHARS

    async def handle(self, input: AgentInput) -> AgentOutput:
        """Convert text to speech and return audio URL"""
        self._call_count += 1
        start_time = time.time()

        # Get text to synthesize
        text = input.raw_text or input.entities.get("response_text", "")
        language = input.entities.get("detected_language", "en")

        if not text:
            return self.fail("No text provided for synthesis")

        if not self.api_key:
            logger.warning("ELEVEN_LABS_API_KEY not configured, returning text only")
            return AgentOutput(
                success=True,
                response_text=text,
                data={"voice_skipped": True, "reason": "not_configured"},
                cost_level=CostLevel.FREE,
            )

        # Check length limit
        if len(text) > self.MAX_CHARS:
            logger.info("Text too long (%d chars), returning text only", len(text))
            return AgentOutput(
                success=True,
                response_text=text,
                data={"voice_skipped": True, "reason": "too_long", "char_count": len(text)},
                cost_level=CostLevel.FREE,
            )

        # Check cache
        text_hash = self._hash_text(text)
        if text_hash in self._audio_cache:
            logger.debug("Voice cache hit for %s", text_hash)
            return AgentOutput(
                success=True,
                response_text=text,
                data={
                    "voice_generated": True,
                    "audio_url": self._audio_cache[text_hash],
                    "cached": True,
                },
                cost_level=CostLevel.FREE,  # Cached = free
            )

        try:
            # Optimize text for speech
            speech_text = self._optimize_for_speech(text)

            # Synthesize audio
            audio_bytes = await self._synthesize(speech_text, language)

            if not audio_bytes:
                return AgentOutput(
                    success=True,
                    response_text=text,
                    data={"voice_skipped": True, "reason": "synthesis_failed"},
                    cost_level=CostLevel.FREE,
                )

            # Save audio file
            audio_url = await self._save_audio(audio_bytes, text_hash)

            # Cache the result
            self._audio_cache[text_hash] = audio_url

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "Synthesized %d chars in %.0fms: %s",
                len(text),
                processing_time,
                audio_url
            )

            return AgentOutput(
                success=True,
                response_text=text,
                data={
                    "voice_generated": True,
                    "audio_url": audio_url,
                    "audio_type": "audio/mpeg",
                    "char_count": len(speech_text),
                    "processing_time_ms": processing_time,
                    "cached": False,
                },
                cost_level=CostLevel.MEDIUM,
                analytics_tags={
                    "modality": "voice_output",
                    "language": language,
                    "char_count": len(speech_text),
                }
            )

        except httpx.TimeoutException:
            logger.error("Voice synthesis timeout")
            return AgentOutput(
                success=True,
                response_text=text,
                data={"voice_skipped": True, "reason": "timeout"},
                cost_level=CostLevel.FREE,
            )

        except Exception as e:
            logger.exception("Voice synthesis failed: %s", e)
            return AgentOutput(
                success=True,
                response_text=text,
                data={"voice_skipped": True, "reason": str(e)},
                cost_level=CostLevel.FREE,
            )

    async def _synthesize(self, text: str, language: str) -> Optional[bytes]:
        """Synthesize speech using Eleven Labs API"""
        client = await self._get_client()

        voice_id = self.VOICE_MAP.get(language, self.VOICE_MAP["default"])
        model_id = self.MODELS[self.MODEL]

        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": model_id,
                "output_format": self.OUTPUT_FORMAT,
                "voice_settings": self.VOICE_SETTINGS,
            },
        )

        if response.status_code != 200:
            logger.error(
                "Eleven Labs API error: %s %s",
                response.status_code,
                response.text[:200]
            )
            return None

        return response.content

    async def _save_audio(self, audio_bytes: bytes, text_hash: str) -> str:
        """Save audio to storage and return URL"""
        filename = f"voice_{text_hash}.mp3"
        filepath = os.path.join(self.AUDIO_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(audio_bytes)

        # Return accessible URL
        # In production, upload to cloud storage (S3, Cloudinary, etc.)
        return f"{self.BASE_URL}/audio/{filename}"

    def _hash_text(self, text: str) -> str:
        """Generate hash for text caching"""
        return hashlib.md5(text.encode()).hexdigest()[:12]

    def _optimize_for_speech(self, text: str) -> str:
        """
        Optimize text for natural speech synthesis.

        - Remove markdown formatting
        - Expand abbreviations
        - Add pauses at appropriate places
        """
        # Remove markdown bold/italic
        text = text.replace("*", "").replace("_", "")

        # Remove emoji (they don't synthesize well)
        import re
        text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', '', text)

        # Expand common abbreviations
        abbreviations = {
            "Gov.": "Governor",
            "Sen.": "Senator",
            "Hon.": "Honorable",
            "Dr.": "Doctor",
            "Prof.": "Professor",
            "Rep.": "Representative",
            "LGA": "Local Government Area",
            "FCT": "Federal Capital Territory",
            "INEC": "I-N-E-C",
            "APC": "A-P-C",
            "PDP": "P-D-P",
            "LP": "Labour Party",
        }

        for abbr, full in abbreviations.items():
            text = text.replace(abbr, full)

        # Clean up extra whitespace
        text = " ".join(text.split())

        return text

    def clear_cache(self):
        """Clear the audio cache"""
        self._audio_cache.clear()

    async def cleanup(self):
        """Cleanup HTTP client"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
