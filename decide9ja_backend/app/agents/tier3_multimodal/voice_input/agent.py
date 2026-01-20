"""
VoiceTranscriptionAgent
=======================
Transcribes incoming voice notes using OpenAI Whisper.

Cost: CHEAP (~$0.006/minute of audio)

Supports:
- English
- Nigerian Pidgin
- Yoruba, Hausa, Igbo (limited)

Usage:
    agent = VoiceTranscriptionAgent()
    output = await agent.handle(AgentInput(
        raw_text="",
        voice_url="https://..."
    ))
    # output.data["transcribed_text"] contains the text
"""

import os
import io
import time
import logging
import httpx
from typing import Optional, Dict, Tuple
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
class VoiceTranscriptionAgent(BaseAgent):
    """Transcribes incoming voice notes using OpenAI Whisper"""

    name = "voice_transcription"
    description = "Transcribe voice notes to text using Whisper"
    tier = AgentTier.MULTIMODAL
    cost_level = CostLevel.CHEAP  # ~$0.006/minute

    # Supported languages
    SUPPORTED_LANGUAGES = {
        "en": "English",
        "pcm": "Nigerian Pidgin",
        "yo": "Yoruba",
        "ha": "Hausa",
        "ig": "Igbo",
    }

    # Language detection hints for Nigerian context
    NIGERIAN_KEYWORDS = {
        "pcm": ["wetin", "dey", "una", "abi", "wahala", "abeg", "na", "sabi", "oga"],
        "yo": ["se", "omo", "ewo", "bawo", "jare", "sha", "abi"],
        "ha": ["sannu", "yaya", "ina", "kai", "wannan"],
        "ig": ["kedu", "nwanne", "odi", "biko", "chineke"],
    }

    # Configuration
    WHISPER_MODEL = "whisper-1"
    MAX_FILE_SIZE_MB = 25
    TIMEOUT_SECONDS = 60

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = os.getenv("OPENAI_API_KEY")
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS)
        return self._http_client

    async def can_handle(self, input: AgentInput) -> bool:
        """Check if we have voice content to transcribe"""
        return bool(input.voice_url)

    async def handle(self, input: AgentInput) -> AgentOutput:
        """Transcribe voice note and return text"""
        self._call_count += 1
        start_time = time.time()

        if not input.voice_url:
            return self.fail("No voice URL provided")

        if not self.api_key:
            logger.error("OPENAI_API_KEY not configured")
            return self.fail("Voice transcription service not configured")

        try:
            # Download audio
            audio_bytes, content_type = await self._download_audio(input.voice_url)

            if not audio_bytes:
                return self.fail("Failed to download audio file")

            # Check file size
            size_mb = len(audio_bytes) / (1024 * 1024)
            if size_mb > self.MAX_FILE_SIZE_MB:
                return self.fail(f"Audio file too large ({size_mb:.1f}MB > {self.MAX_FILE_SIZE_MB}MB)")

            # Transcribe
            transcript = await self._transcribe(audio_bytes, content_type)

            if not transcript.get("text"):
                return self.fail("Transcription returned empty result")

            # Post-process for Nigerian context
            text = transcript["text"]
            language = transcript.get("language", "en")
            language = self._detect_nigerian_language(text, language)

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "Transcribed %d bytes in %.0fms: %s... (lang=%s)",
                len(audio_bytes),
                processing_time,
                text[:50],
                language
            )

            return AgentOutput(
                success=True,
                response_text=text,
                data={
                    "transcribed_text": text,
                    "detected_language": language,
                    "language_name": self.SUPPORTED_LANGUAGES.get(language, language),
                    "confidence": transcript.get("confidence", 0.9),
                    "duration_seconds": transcript.get("duration"),
                    "original_audio_url": input.voice_url,
                    "processing_time_ms": processing_time,
                },
                cost_level=CostLevel.CHEAP,
                analytics_tags={
                    "modality": "voice_input",
                    "language": language,
                    "audio_size_kb": len(audio_bytes) // 1024,
                }
            )

        except httpx.TimeoutException:
            logger.error("Transcription timeout for %s", input.voice_url)
            return self.fail("Voice transcription timed out. Please try again.")

        except Exception as e:
            logger.exception("Transcription failed: %s", e)
            return self.fail(f"Voice transcription failed: {str(e)}")

    async def _download_audio(self, url: str) -> Tuple[Optional[bytes], str]:
        """Download audio file from URL"""
        client = await self._get_client()

        try:
            # Handle WhatsApp media URLs (need auth)
            headers = {}
            if "graph.facebook.com" in url or "whatsapp" in url.lower():
                whatsapp_token = os.getenv("WHATSAPP_TOKEN")
                if whatsapp_token:
                    headers["Authorization"] = f"Bearer {whatsapp_token}"

            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "audio/ogg")
            return response.content, content_type

        except Exception as e:
            logger.error("Failed to download audio from %s: %s", url, e)
            return None, ""

    async def _transcribe(self, audio_bytes: bytes, content_type: str) -> Dict:
        """Transcribe audio using OpenAI Whisper API"""
        client = await self._get_client()

        # Determine file extension from content type
        extension_map = {
            "audio/ogg": "ogg",
            "audio/mpeg": "mp3",
            "audio/mp4": "m4a",
            "audio/wav": "wav",
            "audio/webm": "webm",
            "audio/x-m4a": "m4a",
        }
        extension = extension_map.get(content_type, "ogg")
        filename = f"audio.{extension}"

        # Prepare multipart form data
        files = {
            "file": (filename, audio_bytes, content_type),
        }
        data = {
            "model": self.WHISPER_MODEL,
            "response_format": "verbose_json",
            "language": "en",  # Hint English, but Whisper auto-detects
        }

        response = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            files=files,
            data=data,
        )

        if response.status_code != 200:
            logger.error("Whisper API error: %s %s", response.status_code, response.text)
            raise Exception(f"Whisper API error: {response.status_code}")

        result = response.json()

        return {
            "text": result.get("text", ""),
            "language": result.get("language", "en"),
            "duration": result.get("duration"),
            "confidence": self._calculate_confidence(result),
        }

    def _calculate_confidence(self, result: Dict) -> float:
        """Calculate confidence score from Whisper result"""
        # Whisper doesn't return confidence directly, but we can estimate
        # from segment-level data if available
        segments = result.get("segments", [])
        if not segments:
            return 0.9  # Default high confidence

        # Average no_speech_prob across segments (lower is better)
        no_speech_probs = [s.get("no_speech_prob", 0) for s in segments]
        avg_no_speech = sum(no_speech_probs) / len(no_speech_probs)

        # Convert to confidence (1 - no_speech_prob)
        return max(0.5, 1.0 - avg_no_speech)

    def _detect_nigerian_language(self, text: str, whisper_lang: str) -> str:
        """
        Detect Nigerian language from text content.

        Whisper often misclassifies Nigerian Pidgin as English.
        This post-processes to detect Pidgin and other Nigerian languages.
        """
        text_lower = text.lower()

        # Count keyword matches for each language
        scores = {}
        for lang, keywords in self.NIGERIAN_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > 0:
                scores[lang] = matches

        # If we have strong Pidgin indicators, override Whisper's detection
        if scores.get("pcm", 0) >= 2:
            return "pcm"

        # Check for other Nigerian languages
        for lang in ["yo", "ha", "ig"]:
            if scores.get(lang, 0) >= 2:
                return lang

        # Otherwise trust Whisper
        return whisper_lang

    async def cleanup(self):
        """Cleanup HTTP client"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
